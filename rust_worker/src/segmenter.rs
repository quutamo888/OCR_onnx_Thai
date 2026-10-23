// 8-neighbor directions: (dy, dx)
const DY: [i32; 8] = [-1, -1, -1,  0,  1,  1,  1,  0];
const DX: [i32; 8] = [-1,  0,  1,  1,  1,  0, -1, -1];

#[derive(Debug, Clone)]
pub struct BBox {
    pub min_r: usize,
    pub max_r: usize,
    pub min_c: usize,
    pub max_c: usize,
}

fn find(parent: &mut [usize], mut p: usize) -> usize {
    let mut root = p;
    while root != parent[root] {
        root = parent[root];
    }
    while p != root {
        let nxt = parent[p];
        parent[p] = root;
        p = nxt;
    }
    root
}

fn union(parent: &mut [usize], p1: usize, p2: usize) {
    let r1 = find(parent, p1);
    let r2 = find(parent, p2);
    if r1 != r2 {
        parent[r1] = r2;
    }
}

pub fn segment_lines(
    scores: &[f32],
    links: &[f32],
    h: usize,
    w: usize,
    score_threshold: f32,
    link_threshold: f32,
    is_vertical_text: bool,
) -> Vec<BBox> {
    let total = h * w;
    let mut parent: Vec<usize> = (0..total).collect();
    let mut active = vec![false; total];

    for idx in 0..total {
        if scores[idx] > score_threshold {
            active[idx] = true;
        }
    }

    // Directional thresholds: cross-line connections require higher confidence
    // to prevent adjacent text lines (such as Thai vowels/descenders) from merging.
    let cross_line_threshold = (link_threshold * 1.3).min(0.80);

    for r in 0..h {
        let r_offset = r * w;
        for c in 0..w {
            let p1 = r_offset + c;
            if !active[p1] {
                continue;
            }

            for (n_idx, (&dy, &dx)) in DY.iter().zip(DX.iter()).enumerate() {
                let nr = r as i32 + dy;
                let nc = c as i32 + dx;
                if nr >= 0 && nr < h as i32 && nc >= 0 && nc < w as i32 {
                    let p2 = (nr as usize) * w + (nc as usize);
                    if active[p2] {
                        let link_val = links[n_idx * total + p1];
                        let effective_th = if !is_vertical_text && dy != 0 {
                            cross_line_threshold
                        } else if is_vertical_text && dx != 0 {
                            cross_line_threshold
                        } else {
                            link_threshold
                        };

                        if link_val > effective_th {
                            union(&mut parent, p1, p2);
                        }
                    }
                }
            }
        }
    }

    #[derive(Clone)]
    struct RootInfo {
        min_r: usize,
        max_r: usize,
        min_c: usize,
        max_c: usize,
        count: usize,
    }

    let mut roots = vec![
        RootInfo {
            min_r: usize::MAX,
            max_r: 0,
            min_c: usize::MAX,
            max_c: 0,
            count: 0,
        };
        total
    ];

    for r in 0..h {
        let r_offset = r * w;
        for c in 0..w {
            let p = r_offset + c;
            if !active[p] {
                continue;
            }
            let r_id = find(&mut parent, p);
            let info = &mut roots[r_id];
            info.count += 1;
            if r < info.min_r { info.min_r = r; }
            if r > info.max_r { info.max_r = r; }
            if c < info.min_c { info.min_c = c; }
            if c > info.max_c { info.max_c = c; }
        }
    }

    let mut boxes = Vec::new();
    for info in roots {
        if info.count >= 5 {
            boxes.push(BBox {
                min_r: info.min_r,
                max_r: info.max_r,
                min_c: info.min_c,
                max_c: info.max_c,
            });
        }
    }

    boxes
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_does_not_merge_adjacent_horizontal_lines() {
        // 2 lines: line 0 at r=0..2, line 1 at r=4..6
        let h = 8;
        let w = 10;
        let total = h * w;
        let mut scores = vec![0.0f32; total];
        let mut links = vec![0.0f32; 8 * total];

        // Activate line 0 (r=1) and line 1 (r=5)
        for c in 2..8 {
            scores[1 * w + c] = 0.9;
            scores[5 * w + c] = 0.9;
            // High horizontal links (dx=1, ch=3; dx=-1, ch=7)
            links[3 * total + (1 * w + c)] = 0.9;
            links[7 * total + (1 * w + c)] = 0.9;
            links[3 * total + (5 * w + c)] = 0.9;
            links[7 * total + (5 * w + c)] = 0.9;
        }

        // Add a vertical link between r=1 and r=2 with 0.55 (should be blocked by cross_line_threshold)
        scores[2 * w + 5] = 0.8;
        scores[4 * w + 5] = 0.8;
        links[4 * total + (1 * w + 5)] = 0.55; // vertical link down

        let boxes = segment_lines(&scores, &links, h, w, 0.50, 0.50, false);
        assert_eq!(boxes.len(), 2, "Adjacent lines should remain separate boxes");
    }
}
