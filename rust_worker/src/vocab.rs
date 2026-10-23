use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

pub struct Vocabulary {
    pub map: HashMap<usize, String>,
    pub blank_id: usize,
}

impl Vocabulary {
    pub fn load_from_file<P: AsRef<Path>>(path: P) -> std::io::Result<Self> {
        let file = File::open(path)?;
        let reader = BufReader::new(file);
        let mut raw_list = Vec::new();

        for line_res in reader.lines() {
            let line = line_res?;
            let trimmed = line.trim();
            if let Some((idx_str, val)) = trimmed.split_once(':') {
                if let Ok(idx) = idx_str.trim().parse::<usize>() {
                    let mut char_val = val.trim_matches(|c| c == '\r' || c == '\n').to_string();
                    if char_val.starts_with(' ') {
                        char_val = char_val[1..].to_string();
                    }
                    raw_list.push((idx, char_val));
                }
            }
        }

        raw_list.sort_by_key(|x| x.0);

        let mut map = HashMap::new();
        if raw_list.len() > 1000 {
            for (idx, ch) in raw_list {
                map.insert(idx, ch);
            }
        } else {
            let mut clean_idx = 1;
            for (idx, ch) in raw_list {
                if idx == 0 || idx == 13 || idx == 16 || idx == 28 || idx == 33 {
                    continue;
                }
                map.insert(clean_idx, ch);
                clean_idx += 1;
            }
        }

        let blank_id = 198; // 199 - 1 for Thai
        Ok(Vocabulary { map, blank_id })
    }
}
