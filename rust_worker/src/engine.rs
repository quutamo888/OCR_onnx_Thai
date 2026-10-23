use image::{DynamicImage, GenericImageView};
use ndarray::{Array1, Array2, Array4};
use ort::session::Session;
use ort::value::Tensor;
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use crate::segmenter::segment_lines;
use crate::vocab::Vocabulary;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BoundingRect {
    pub x1: f32, pub y1: f32,
    pub x2: f32, pub y2: f32,
    pub x3: f32, pub y3: f32,
    pub x4: f32, pub y4: f32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OcrLine {
    pub text: String,
    pub bounding_rect: BoundingRect,
    pub confidence: f32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OcrResult {
    pub text: String,
    pub lines: Vec<OcrLine>,
    pub latency_ms: u64,
}

pub struct OcrEngine {
    detector: Mutex<Session>,
    recognizer: Mutex<Session>,
    vocab: Arc<Vocabulary>,
}

impl OcrEngine {
    pub fn new<P: AsRef<Path>>(models_dir: P) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let dir = models_dir.as_ref();
        let detector_path = dir.join("detector").join("text_detector.onnx");
        let recognizer_path = dir.join("recognizers").join("recognizer_thai.onnx");
        let vocab_path = dir.join("vocab").join("vocab_thai.txt");

        let env = Arc::new(ort::init().with_name("thai_ocr").build()?);

        println!("[RUST ENGINE] Loading Detector from {:?}", detector_path);
        let detector = Session::builder(&env)?.commit_from_file(detector_path)?;

        println!("[RUST ENGINE] Loading Recognizer from {:?}", recognizer_path);
        let recognizer = Session::builder(&env)?.commit_from_file(recognizer_path)?;

        println!("[RUST ENGINE] Loading Vocab from {:?}", vocab_path);
        let vocab = Arc::new(Vocabulary::load_from_file(vocab_path)?);

        Ok(Self {
            detector: Mutex::new(detector),
            recognizer: Mutex::new(recognizer),
            vocab,
        })
    }

    pub fn recognize(&self, img: &DynamicImage) -> Result<OcrResult, Box<dyn std::error::Error + Send + Sync>> {
        let t0 = Instant::now();
        let (orig_w, orig_h) = img.dimensions();

        // 1. Calculate Target Dimensions (multiple of 32, max_side 2048)
        let max_side: f32 = 2048.0;
        let scale = (max_side / (orig_w.max(orig_h) as f32)).min(1.0);
        let target_w = ((orig_w as f32 * scale / 32.0).round() * 32.0).max(32.0) as usize;
        let target_h = ((orig_h as f32 * scale / 32.0).round() * 32.0).max(32.0) as usize;

        let sx = target_w as f32 / orig_w as f32;
        let sy = target_h as f32 / orig_h as f32;

        // Resize image for FPN detector
        let resized = img.resize_exact(target_w as u32, target_h as u32, image::imageops::FilterType::CatmullRom);
        let rgb = resized.to_rgb8();

        let mut inp = Array4::<f32>::zeros((1, 3, target_h, target_w));
        for (x, y, pixel) in rgb.enumerate_pixels() {
            // Detector expects raw [0.0, 255.0] RGB range
            inp[[0, 0, y as usize, x as usize]] = pixel[0] as f32;
            inp[[0, 1, y as usize, x as usize]] = pixel[1] as f32;
            inp[[0, 2, y as usize, x as usize]] = pixel[2] as f32;
        }

        let mut im_info = Array2::<f32>::zeros((1, 3));
        im_info[[0, 0]] = target_h as f32;
        im_info[[0, 1]] = target_w as f32;
        im_info[[0, 2]] = 1.0;

        let inp_tensor = Tensor::from_array(inp)?;
        let im_info_tensor = Tensor::from_array(im_info)?;

        // 2. Run Detector Inference
        let (boxes, is_vertical) = {
            let mut det = self.detector.lock().map_err(|e| format!("Detector lock error: {}", e))?;
            let outputs = det.run(ort::inputs![
                "data" => inp_tensor,
                "im_info" => im_info_tensor
            ])?;

            let (sh_shape, sh_slice) = outputs[0].try_extract_tensor::<f32>()?;
            let (_sv_shape, sv_slice) = outputs[2].try_extract_tensor::<f32>()?;
            let (_lh_shape, lh_slice) = outputs[4].try_extract_tensor::<f32>()?;
            let (_lv_shape, lv_slice) = outputs[5].try_extract_tensor::<f32>()?;

            let h_lvl = sh_shape[2] as usize;
            let w_lvl = sh_shape[3] as usize;

            let sh_count: usize = sh_slice.iter().map(|&s| if s > 0.50 { 1 } else { 0 }).sum();
            let sv_count: usize = sv_slice.iter().map(|&s| if s > 0.50 { 1 } else { 0 }).sum();

            let is_vert = sv_count > sh_count;

            let b = if is_vert {
                segment_lines(sv_slice, lv_slice, h_lvl, w_lvl, 0.50, 0.50, true)
            } else {
                segment_lines(sh_slice, lh_slice, h_lvl, w_lvl, 0.50, 0.50, false)
            };
            (b, is_vert)
        };

        let stride = 4.0;

        // 4. Prepare Crops for Recognizer with padding
        struct CropItem {
            crop: DynamicImage,
            bbox: BoundingRect,
        }

        let pad_x = 4u32;
        let pad_y = 6u32;
        let mut crop_items = Vec::new();

        for b in boxes {
            let x1 = ((b.min_c as f32 * stride) / sx).max(0.0);
            let y1 = ((b.min_r as f32 * stride) / sy).max(0.0);
            let x2 = ((b.max_c as f32 * stride) / sx).min(orig_w as f32);
            let y2 = ((b.max_r as f32 * stride) / sy).min(orig_h as f32);

            let w = x2 - x1;
            let h = y2 - y1;

            if w < 5.0 || h < 5.0 {
                continue;
            }

            let crop_x1 = (x1 as u32).saturating_sub(pad_x).min(orig_w - 1);
            let crop_y1 = (y1 as u32).saturating_sub(pad_y).min(orig_h - 1);
            let crop_x2 = (x2 as u32).saturating_add(pad_x).min(orig_w);
            let crop_y2 = (y2 as u32).saturating_add(pad_y).min(orig_h);

            let crop_w = crop_x2.saturating_sub(crop_x1);
            let crop_h = crop_y2.saturating_sub(crop_y1);

            if crop_w < 4 || crop_h < 4 {
                continue;
            }

            let mut cropped = img.crop_imm(crop_x1, crop_y1, crop_w, crop_h);
            if is_vertical {
                cropped = cropped.rotate90();
            }

            crop_items.push(CropItem {
                crop: cropped,
                bbox: BoundingRect {
                    x1, y1,
                    x2, y2: y1,
                    x3: x2, y3: y2,
                    x4: x1, y4: y2,
                },
            });
        }

        // 5. Line Recognition
        let vocab = Arc::clone(&self.vocab);
        let mut results = Vec::new();
        let mut rec = self.recognizer.lock().map_err(|e| format!("Recognizer lock error: {}", e))?;

        for item in crop_items {
            let crop = item.crop;
            let (cw, ch) = crop.dimensions();
            if cw < 4 || ch < 4 {
                continue;
            }
            let aspect = cw as f32 / ch as f32;
            let new_w = ((60.0 * aspect).round() as usize).max(16);
            let resized_crop = crop.resize_exact(new_w as u32, 60, image::imageops::FilterType::CatmullRom);
            let rgb_crop = resized_crop.to_rgb8();

            let mut rec_inp = Array4::<f32>::zeros((1, 3, 60, new_w));
            for (x, y, pixel) in rgb_crop.enumerate_pixels() {
                let b = pixel[2] as f32 / 255.0;
                let g = pixel[1] as f32 / 255.0;
                let r = pixel[0] as f32 / 255.0;
                rec_inp[[0, 0, y as usize, x as usize]] = b;
                rec_inp[[0, 1, y as usize, x as usize]] = g;
                rec_inp[[0, 2, y as usize, x as usize]] = r;
            }

            let seq_len = Array1::from_vec(vec![(new_w / 4) as i32]);
            let Ok(data_tensor) = Tensor::from_array(rec_inp) else { continue };
            let Ok(seq_tensor) = Tensor::from_array(seq_len) else { continue };

            // Forward Recognizer
            let Ok(rec_out) = rec.run(ort::inputs![
                "data" => data_tensor,
                "seq_lengths" => seq_tensor
            ]) else { continue };

            let Ok((logits_shape, logits_data)) = rec_out[0].try_extract_tensor::<f32>() else { continue };
            let t_steps = logits_shape[0] as usize;
            let vocab_dim = logits_shape[2] as usize;

            // CTC Greedy Decode
            let mut decoded = String::new();
            let blank_idx = vocab.blank_id;
            let mut prev = usize::MAX;

            for t in 0..t_steps {
                let offset = t * vocab_dim;
                let slice = &logits_data[offset..offset + vocab_dim];
                let mut max_idx = 0;
                let mut max_val = f32::NEG_INFINITY;
                for (i, &val) in slice.iter().enumerate() {
                    if val > max_val {
                        max_val = val;
                        max_idx = i;
                    }
                }

                if max_idx != prev && max_idx != blank_idx {
                    if max_idx == 0 {
                        decoded.push(' ');
                    } else if let Some(ch) = vocab.map.get(&max_idx) {
                        decoded.push_str(ch);
                    }
                }
                prev = max_idx;
            }

            let text = decoded.trim().to_string();
            if text.is_empty() {
                continue;
            }

            results.push(OcrLine {
                text,
                bounding_rect: item.bbox,
                confidence: 0.95,
            });
        }
        drop(rec); // Release recognizer lock

        // Sort lines top-to-bottom
        let mut sorted_lines = results;
        sorted_lines.sort_by(|a, b| a.bounding_rect.y1.partial_cmp(&b.bounding_rect.y1).unwrap_or(std::cmp::Ordering::Equal));

        let full_text = sorted_lines.iter().map(|l| l.text.as_str()).collect::<Vec<&str>>().join("\n");
        let latency_ms = t0.elapsed().as_millis() as u64;

        Ok(OcrResult {
            text: full_text,
            lines: sorted_lines,
            latency_ms,
        })
    }
}
