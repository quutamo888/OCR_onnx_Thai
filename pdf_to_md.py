"""Convert PDF to structured Markdown with auto-orientation and table detection using Windows OneOCR.

Pipeline:
1. Render PDF page to PIL Image in memory (PyMuPDF / pypdfium2)
2. Check page orientation & text angle via OneOCR:
   - If rotated/skewed (e.g. landscape scanned in portrait PDF, angle ~90/180/270), auto-rotate to upright
3. Spatial Layout Analysis:
   - Detect visual rows and column alignments
   - Detect and format table blocks (| col 1 | col 2 | ...)
   - Preserve headers, numbered sections, and paragraph flow
4. Generate clean Markdown with page orientation metadata
"""

import argparse
import io
import os
import re
import sys
import time
from pathlib import Path
from PIL import Image

# Ensure local oneocr wrapper is loaded
REPO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_DIR / "oneocr"))
import oneocr


def render_pdf_pages(pdf_path: str, dpi: int = 150, pages=None):
    """Render PDF pages to PIL Images using fitz or pypdfium2."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        total = len(doc)
        page_indices = range(total) if pages is None else [p for p in pages if 0 <= p < total]
        for idx in page_indices:
            page = doc[idx]
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            yield idx + 1, total, img
        doc.close()
        return
    except ImportError:
        pass

    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        total = len(pdf)
        page_indices = range(total) if pages is None else [p for p in pages if 0 <= p < total]
        scale = dpi / 72.0
        for idx in page_indices:
            page = pdf[idx]
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            yield idx + 1, total, img
        pdf.close()
        return
    except ImportError:
        raise RuntimeError("Missing PDF renderer. Install PyMuPDF (`pip install pymupdf`) or pypdfium2.")


def parse_page_range(range_str: str):
    """Parse '1-3,5' into 0-based page index list."""
    if not range_str:
        return None
    indices = set()
    for part in range_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            for p in range(int(start), int(end) + 1):
                indices.add(p - 1)
        else:
            indices.add(int(part) - 1)
    return sorted(indices)


def recognize_with_orientation_check(engine: oneocr.OcrEngine, img: Image.Image):
    """Perform OCR with auto-rotation check (handles 90/180/270 deg and skew)."""
    res = engine.recognize_pil(img)
    angle = res.get("text_angle", 0.0) or 0.0

    # Normalize angle to range [-180, 180]
    norm_angle = (angle + 180.0) % 360.0 - 180.0

    rotated = False
    # If angle is significant (more than 1.5 deg off upright), rotate and re-run OCR
    if abs(norm_angle) > 1.5:
        img = img.rotate(angle, expand=True, resample=Image.BICUBIC)
        res = engine.recognize_pil(img)
        rotated = True

    is_landscape = img.width > img.height
    orient_label = "แนวนอน (Landscape)" if is_landscape else "แนวตั้ง (Portrait)"
    return res, orient_label, angle, rotated


def cluster_into_rows(ocr_lines: list) -> list:
    """Group OCR bounding boxes on the same horizontal band into visual rows."""
    rows = []
    for l in ocr_lines:
        b = l.get("bounding_rect")
        if not b:
            continue
        y_mid = (b["y1"] + b["y3"]) / 2
        h = max(1.0, abs(b["y3"] - b["y1"]))

        placed = False
        for r in rows:
            # Match lines within 55% of line height
            if abs(r["y_mid"] - y_mid) < (max(r["h"], h) * 0.55):
                r["items"].append(l)
                # Recalculate average y_mid
                r["y_mid"] = sum((it["bounding_rect"]["y1"] + it["bounding_rect"]["y3"]) / 2 for it in r["items"]) / len(r["items"])
                placed = True
                break
        if not placed:
            rows.append({"y_mid": y_mid, "h": h, "items": [l]})

    # Sort rows vertically
    rows.sort(key=lambda r: r["y_mid"])
    for r in rows:
        # Sort items inside each row horizontally by x1
        r["items"].sort(key=lambda it: it["bounding_rect"]["x1"])
    return rows


def sanitize_cell(text: str) -> str:
    """Escape pipe characters and normalize whitespace for Markdown table cells."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_table_block(table_rows: list) -> str:
    """Render consecutive multi-column rows into a valid Markdown table."""
    if not table_rows:
        return ""

    # Clean cell text
    grid = []
    for r in table_rows:
        row_cells = [sanitize_cell(it["text"]) for it in r["items"] if it["text"].strip()]
        if row_cells:
            grid.append(row_cells)

    if not grid:
        return ""

    max_cols = max(len(row) for row in grid)
    if max_cols <= 1:
        # Not a real table
        return "\n".join(" ".join(row) for row in grid)

    # Pad all rows to max_cols
    lines = []
    header = grid[0] + [""] * (max_cols - len(grid[0]))
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    for row in grid[1:]:
        padded = row + [""] * (max_cols - len(row))
        lines.append("| " + " | ".join(padded) + " |")

    return "\n" + "\n".join(lines) + "\n"


def format_page_markdown(ocr_lines: list, page_num: int, orient_label: str) -> tuple[str, bool, int]:
    """Format OCR lines into structured Markdown with auto-detected tables and headings."""
    if not ocr_lines:
        return f"## หน้า {page_num} ({orient_label})\n\n*(ไม่พบข้อความ)*\n", False, 0

    rows = cluster_into_rows(ocr_lines)
    if not rows:
        return f"## หน้า {page_num} ({orient_label})\n\n*(ไม่พบข้อความ)*\n", False, 0

    # Calculate median line height using only single-item body rows to prevent dense table rows from skewing median
    body_heights = [r["h"] for r in rows if len(r["items"]) == 1 and r["h"] > 20]
    all_heights = [r["h"] for r in rows if r["h"] > 0]
    median_body_h = sorted(body_heights)[len(body_heights) // 2] if body_heights else (
        sorted(all_heights)[len(all_heights) // 2] if all_heights else 30.0
    )

    # Count how many rows are multi-column
    multi_col_rows = sum(1 for r in rows if len(r["items"]) >= 2)
    has_table = multi_col_rows >= 2
    max_table_cols = max((len(r["items"]) for r in rows), default=1)

    table_note = f" | ตาราง {max_table_cols} คอลัมน์" if has_table else ""
    md_lines = [f"## หน้า {page_num} ({orient_label}{table_note})\n"]

    current_table = []
    prev_y = None

    for r in rows:
        items = r["items"]
        row_h = r["h"]
        y_mid = r["y_mid"]
        gap = (y_mid - prev_y) if prev_y is not None else 0

        # Check if row is part of a table (2 or more items across x)
        if len(items) >= 2:
            current_table.append(r)
            prev_y = y_mid
            continue

        # Single item row: flush any pending table block
        if current_table:
            md_lines.append(render_table_block(current_table))
            current_table = []

        text = items[0]["text"].strip()
        if not text:
            continue

        # Header and field detection based on Thai official document hierarchy
        is_known_doc_title = text in ("บันทึกข้อความ", "คำสั่ง", "ประกาศ", "รายงานการประชุม", "พระราชบัญญัติ")
        is_large_title = is_known_doc_title or (
            row_h >= (median_body_h * 1.45)
            and len(text) <= 50
            and not bool(re.search(r"(บาท|ดังนี้|ต่อไปนี้|จำนวน|ได้แก่|ว่า|และ|ฯลฯ)$", text))
        )
        is_section_header = bool(re.match(r"^([๑-๙0-9]+)\.\s+[^\d]", text)) and len(text) <= 80
        is_subsection = bool(re.match(r"^([๑-๙0-9]+\.[๑-๙0-9]+)\s+", text)) and len(text) <= 100
        field_match = re.match(r"^(ส่วนราชการ|ที่|วันที่|เรื่อง|เรียน)\s+(.*)$", text)

        if is_large_title:
            md_lines.append(f"\n# {text}\n")
        elif is_section_header:
            md_lines.append(f"\n### {text}\n")
        elif is_subsection:
            md_lines.append(f"\n#### {text}\n")
        else:
            line_text = f"**{field_match.group(1)}** {field_match.group(2)}" if field_match else text
            # Paragraph text: check line spacing
            if gap > (median_body_h * 1.6) or field_match:
                md_lines.append(f"\n{line_text}")
            else:
                # Continuation line
                if md_lines and md_lines[-1] and not md_lines[-1].startswith("#") and not md_lines[-1].startswith("|"):
                    md_lines[-1] += f" {line_text}"
                else:
                    md_lines.append(line_text)

        prev_y = y_mid

    # Flush any remaining table at end of page
    if current_table:
        md_lines.append(render_table_block(current_table))

    return "\n".join(md_lines).strip() + "\n", has_table, max_table_cols


def ocr_pdf_to_markdown(pdf_path: str, output_path: str = None, dpi: int = 150, pages_arg: str = None):
    """Run full PDF to Markdown OCR pipeline with auto-orientation and table detection."""
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    if output_path is None:
        output_path = pdf_file.with_suffix(".md")
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Loading OneOCR engine...")
    engine = oneocr.OcrEngine()
    print("OneOCR engine ready.")

    page_filter = parse_page_range(pages_arg)

    start_time = time.time()
    md_pages = []
    page_summary = []

    processed = 0
    for page_num, total_pages, img in render_pdf_pages(str(pdf_file), dpi=dpi, pages=page_filter):
        t0 = time.time()
        # Step 1 & 2: Check orientation, rotate if needed, run OCR
        res, orient_label, angle, rotated = recognize_with_orientation_check(engine, img)
        dt = time.time() - t0

        # Step 3: Layout analysis & table formatting
        page_md, has_table, cols = format_page_markdown(res.get("lines", []), page_num, orient_label)
        md_pages.append(page_md)
        md_pages.append("\n---\n")

        processed += 1
        rot_msg = f", หมุน {angle:.1f}°" if rotated else ""
        table_msg = f", ตาราง {cols} cols" if has_table else ""
        print(f"[{processed}/{total_pages if page_filter is None else len(page_filter)}] หน้า {page_num}: {orient_label}{rot_msg}{table_msg} ({len(res.get('lines', []))} บรรทัด) - {dt:.2f} วิ")
        page_summary.append((page_num, orient_label, has_table, cols))

    # Header with overall document metadata
    portrait_count = sum(1 for _, o, _, _ in page_summary if "Portrait" in o)
    landscape_count = sum(1 for _, o, _, _ in page_summary if "Landscape" in o)
    table_page_count = sum(1 for _, _, t, _ in page_summary if t)

    doc_header = [
        f"# {pdf_file.name}\n",
        f"*แปลงด้วย Windows OneOCR Engine*",
        f"- **จำนวนหน้าทั้งหมด:** {processed} หน้า",
        f"- **ทิศทางหน้า:** แนวตั้ง {portrait_count} หน้า | แนวนอน {landscape_count} หน้า",
        f"- **พบหน้าที่มีตาราง:** {table_page_count} หน้า\n",
        "---\n"
    ]

    full_md = "\n".join(doc_header) + "\n".join(md_pages).strip() + "\n"
    output_file.write_text(full_md, encoding="utf-8")

    total_time = time.time() - start_time
    print(f"\nเสร็จสิ้น: {processed} หน้า ใช้เวลา {total_time:.2f} วิ ({total_time/max(1, processed):.2f} วิ/หน้า)")
    print(f"สรุป: แนวตั้ง {portrait_count} หน้า | แนวนอน {landscape_count} หน้า | มีตาราง {table_page_count} หน้า")
    print(f"บันทึกไฟล์ Markdown ที่: {output_file.resolve()}")
    return str(output_file)


def main():
    parser = argparse.ArgumentParser(description="OCR PDF to Markdown with OneOCR (Auto-orientation + Table detection)")
    parser.add_argument("pdf", help="Path to input PDF file")
    parser.add_argument("-o", "--output", help="Output .md file path (default: <pdf_name>.md)")
    parser.add_argument("--dpi", type=int, default=150, help="Render DPI (default: 150)")
    parser.add_argument("--pages", help="Pages to process, e.g. 1-3,5 (default: all)")
    args = parser.parse_args()

    ocr_pdf_to_markdown(args.pdf, args.output, dpi=args.dpi, pages_arg=args.pages)


if __name__ == "__main__":
    main()
