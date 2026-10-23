"""Document Exporter Module for ThaiOCR ONNX System.

Converts OCR Markdown and Source Documents into:
1. Microsoft Word (.docx) with layout reconstruction, tables, fonts, and cropped images.
2. Microsoft Excel (.xlsx) with styled grid tables, formulas, and embedded graphics.
"""

import io
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from server.logger import logger

THAI_FONT_NAME = "TH Sarabun New"


# ---------------------------------------------------------------------------
# 1. Image Extraction & Cropping from Source PDF / Image
# ---------------------------------------------------------------------------

def extract_images_from_source(source_bytes: Optional[bytes], filename: str) -> Dict[int, List[Dict[str, Any]]]:
    """Extract embedded images, logos, stamps, and graphics from source PDF or image.

    Returns a dict mapping: page_number (1-indexed) -> list of image items:
    [{"bytes": bytes, "width": float, "height": float, "is_standalone": bool}]
    """
    if not source_bytes:
        return {}

    lower_name = filename.lower()
    page_images: Dict[int, List[Dict[str, Any]]] = {}

    if lower_name.endswith(".pdf"):
        try:
            import fitz
            doc = fitz.open(stream=source_bytes, filetype="pdf")
            for page_idx in range(len(doc)):
                page_num = page_idx + 1
                page = doc[page_idx]
                page_rect = page.rect
                page_area = max(page_rect.width * page_rect.height, 1.0)
                items = []

                # Find all embedded images on this page
                img_list = page.get_images(full=True)
                seen_xrefs = set()

                for img_info in img_list:
                    xref = img_info[0]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)

                    # Get image position on the page
                    rects = page.get_image_rects(img_info)
                    if not rects:
                        continue

                    for rect in rects:
                        # Exclude full-page background scans (e.g. > 90% page area)
                        area = rect.width * rect.height
                        if area >= 0.88 * page_area:
                            continue

                        # Extract the cropped / embedded image
                        try:
                            # If smaller element (logo, signature, photo), crop precisely via pixmap
                            pix = page.get_pixmap(clip=rect, dpi=200)
                            img_data = pix.tobytes("png")
                            if len(img_data) > 200:  # Valid image
                                items.append({
                                    "bytes": img_data,
                                    "width": rect.width,
                                    "height": rect.height,
                                    "top": rect.y0,
                                    "left": rect.x0
                                })
                        except Exception as ex:
                            logger.debug(f"Failed to extract image xref {xref} on page {page_num}: {ex}")

                # Sort extracted images on page from top to bottom
                items.sort(key=lambda x: x.get("top", 0.0))
                if items:
                    page_images[page_num] = items
            doc.close()
        except Exception as e:
            logger.warning(f"Error extracting images from PDF '{filename}': {e}")
    else:
        # Standalone Image file (e.g. PNG / JPG)
        try:
            pil_img = Image.open(io.BytesIO(source_bytes))
            # Store image preview
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            page_images[1] = [{
                "bytes": buf.getvalue(),
                "width": pil_img.width,
                "height": pil_img.height,
                "top": 0.0,
                "left": 0.0
            }]
        except Exception as e:
            logger.debug(f"Source file is not a readable image: {e}")

    return page_images


# ---------------------------------------------------------------------------
# 2. Markdown Parsing to Structured Elements
# ---------------------------------------------------------------------------

def parse_markdown_pages(md_text: str) -> List[Dict[str, Any]]:
    """Parse Markdown into structured pages with headings, paragraphs, and tables."""
    pages = []
    lines = md_text.splitlines()

    current_page_num = 1
    current_elements = []
    table_buffer = []

    def flush_table():
        if not table_buffer:
            return
        parsed_rows = []
        for raw_line in table_buffer:
            stripped = raw_line.strip()
            # Skip Markdown table separator rows like |---|---|
            if re.match(r"^\|?[\s\-:|]+\|?$", stripped):
                continue
            cells = [c.strip().replace(r"\|", "|") for c in stripped.strip("|").split("|")]
            if any(cells):
                parsed_rows.append(cells)
        if parsed_rows:
            current_elements.append({
                "type": "table",
                "rows": parsed_rows
            })
        table_buffer.clear()

    for line in lines:
        trimmed = line.strip()

        # Page Divider Detection: e.g. "## หน้า 2 (แนวตั้ง) ..." or "--- หน้า 2 ---"
        page_match = re.match(r"^(?:##|---)\s*หน้า\s*([0-9๑-๙]+)", trimmed)
        if page_match and current_elements:
            flush_table()
            pages.append({
                "page_num": current_page_num,
                "elements": current_elements
            })
            # Convert Thai numerals if present
            raw_pnum = page_match.group(1)
            thai_digits = "๑๒๓๔๕๖๗๘๙"
            for d_idx, d_char in enumerate(thai_digits, 1):
                raw_pnum = raw_pnum.replace(d_char, str(d_idx))
            raw_pnum = raw_pnum.replace("๐", "0")
            try:
                current_page_num = int(raw_pnum)
            except ValueError:
                current_page_num += 1
            current_elements = []
            continue

        # Table row
        if trimmed.startswith("|") and trimmed.endswith("|"):
            table_buffer.append(trimmed)
            continue

        flush_table()

        if not trimmed or trimmed == "---":
            continue

        # Headings
        if trimmed.startswith("# "):
            current_elements.append({"type": "title", "text": trimmed[2:].strip()})
        elif trimmed.startswith("## "):
            current_elements.append({"type": "heading1", "text": trimmed[3:].strip()})
        elif trimmed.startswith("### "):
            current_elements.append({"type": "heading2", "text": trimmed[4:].strip()})
        elif trimmed.startswith("#### "):
            current_elements.append({"type": "heading3", "text": trimmed[5:].strip()})
        elif re.match(r"^[0-9๑-๙]+\.\s+", trimmed):
            current_elements.append({"type": "list_item", "text": trimmed})
        else:
            current_elements.append({"type": "paragraph", "text": trimmed})

    flush_table()
    if current_elements:
        pages.append({
            "page_num": current_page_num,
            "elements": current_elements
        })

    return pages if pages else [{"page_num": 1, "elements": [{"type": "paragraph", "text": md_text}]}]


# ---------------------------------------------------------------------------
# 3. Export to Microsoft Word (.docx)
# ---------------------------------------------------------------------------

def export_to_docx(source_bytes: Optional[bytes], filename: str, md_text: str) -> bytes:
    """Generate high-fidelity DOCX document from OCR markdown and extracted source images."""
    doc = docx.Document()

    # Configure normal margins (0.8 inch)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Set normal style font to Thai Sarabun New
    style_normal = doc.styles["Normal"]
    style_normal.font.name = THAI_FONT_NAME
    style_normal.font.size = Pt(14)
    style_normal.font.color.rgb = RGBColor(30, 41, 59)  # Slate-800

    extracted_images = extract_images_from_source(source_bytes, filename)
    parsed_pages = parse_markdown_pages(md_text)

    for p_idx, page in enumerate(parsed_pages):
        page_num = page["page_num"]

        # Insert page break between pages
        if p_idx > 0:
            doc.add_page_break()

        # Insert any cropped images for this page (e.g. emblems, logos, photos)
        if page_num in extracted_images:
            for img_item in extracted_images[page_num]:
                try:
                    img_stream = io.BytesIO(img_item["bytes"])
                    # Scale image nicely up to 4.5 inches max width
                    orig_w = img_item.get("width", 200)
                    orig_h = img_item.get("height", 100)
                    aspect = orig_h / max(orig_w, 1.0)

                    target_w = min(orig_w / 72.0, 4.5) if orig_w > 0 else 3.0
                    target_w = max(target_w, 1.2)

                    p_img = doc.add_paragraph()
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p_img.paragraph_format.space_after = Pt(8)
                    run = p_img.add_run()
                    run.add_picture(img_stream, width=Inches(target_w))
                except Exception as ex:
                    logger.debug(f"Failed to add picture in DOCX: {ex}")

        # Render Page Elements
        for elem in page["elements"]:
            etype = elem["type"]

            if etype == "title":
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(10)
                p.paragraph_format.space_after = Pt(8)
                run = p.add_run(elem["text"])
                run.font.name = THAI_FONT_NAME
                run.font.size = Pt(18)
                run.bold = True
                run.font.color.rgb = RGBColor(15, 23, 42)

            elif etype == "heading1":
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run(elem["text"])
                run.font.name = THAI_FONT_NAME
                run.font.size = Pt(16)
                run.bold = True
                run.font.color.rgb = RGBColor(30, 41, 59)

            elif etype == "heading2":
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(3)
                run = p.add_run(elem["text"])
                run.font.name = THAI_FONT_NAME
                run.font.size = Pt(15)
                run.bold = True

            elif etype == "heading3":
                p = doc.add_paragraph()
                run = p.add_run(elem["text"])
                run.font.name = THAI_FONT_NAME
                run.font.size = Pt(14)
                run.bold = True

            elif etype == "table":
                rows_data = elem["rows"]
                if not rows_data:
                    continue
                num_rows = len(rows_data)
                num_cols = max(len(r) for r in rows_data)

                table = doc.add_table(rows=num_rows, cols=num_cols)
                table.style = "Table Grid"
                table.alignment = WD_TABLE_ALIGNMENT.CENTER

                for r_idx, row in enumerate(rows_data):
                    # Check if header row
                    is_header = (r_idx == 0)
                    for c_idx in range(num_cols):
                        cell = table.cell(r_idx, c_idx)
                        val = row[c_idx] if c_idx < len(row) else ""
                        cell.text = val

                        # Format cell text
                        for cp in cell.paragraphs:
                            cp.paragraph_format.space_before = Pt(2)
                            cp.paragraph_format.space_after = Pt(2)
                            for crun in cp.runs:
                                crun.font.name = THAI_FONT_NAME
                                crun.font.size = Pt(13 if is_header else 12)
                                if is_header:
                                    crun.bold = True

                        # Shading header row
                        if is_header:
                            shading_xml = parse_xml(r'<w:shd {} w:fill="F1F5F9"/>'.format(nsdecls('w')))
                            cell._tc.get_or_add_tcPr().append(shading_xml)

                # Add space after table
                p_spacer = doc.add_paragraph()
                p_spacer.paragraph_format.space_before = Pt(0)
                p_spacer.paragraph_format.space_after = Pt(6)

            else:
                # Normal paragraph / list item
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.line_spacing = 1.15
                run = p.add_run(elem.get("text", ""))
                run.font.name = THAI_FONT_NAME
                run.font.size = Pt(14)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 4. Export to Microsoft Excel (.xlsx)
# ---------------------------------------------------------------------------

def export_to_xlsx(source_bytes: Optional[bytes], filename: str, md_text: str) -> bytes:
    """Generate structured XLSX workbook from OCR markdown and extracted tables."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active

    extracted_images = extract_images_from_source(source_bytes, filename)
    parsed_pages = parse_markdown_pages(md_text)

    # Styles
    font_title = Font(name=THAI_FONT_NAME, size=14, bold=True, color="0F172A")
    font_section = Font(name=THAI_FONT_NAME, size=12, bold=True, color="1E293B")
    font_header = Font(name=THAI_FONT_NAME, size=11, bold=True, color="FFFFFF")
    font_cell = Font(name=THAI_FONT_NAME, size=11, color="1E293B")

    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Dark blue
    fill_alt = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color="CBD5E1"),
        right=Side(style='thin', color="CBD5E1"),
        top=Side(style='thin', color="CBD5E1"),
        bottom=Side(style='thin', color="CBD5E1")
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    for p_idx, page in enumerate(parsed_pages):
        page_num = page["page_num"]
        sheet_title = f"หน้า {page_num}"
        ws = wb.create_sheet(title=sheet_title)

        current_row = 1

        # Check if page has cropped images
        if page_num in extracted_images:
            for img_item in extracted_images[page_num]:
                try:
                    img_stream = io.BytesIO(img_item["bytes"])
                    xl_img = openpyxl.drawing.image.Image(img_stream)
                    # Resize to fit nicely
                    if xl_img.width > 300:
                        ratio = 300 / xl_img.width
                        xl_img.width = 300
                        xl_img.height = int(xl_img.height * ratio)
                    ws.add_image(xl_img, f"A{current_row}")
                    # Leave rows for image height
                    current_row += max(int(xl_img.height / 20) + 1, 3)
                except Exception as ex:
                    logger.debug(f"Failed to add image in XLSX: {ex}")

        # Render elements
        for elem in page["elements"]:
            etype = elem["type"]

            if etype in ("title", "heading1"):
                cell = ws.cell(row=current_row, column=1, value=elem["text"])
                cell.font = font_title if etype == "title" else font_section
                current_row += 2

            elif etype in ("heading2", "heading3"):
                cell = ws.cell(row=current_row, column=1, value=elem["text"])
                cell.font = font_section
                current_row += 1

            elif etype == "table":
                rows_data = elem["rows"]
                if not rows_data:
                    continue

                for r_idx, row in enumerate(rows_data):
                    is_header = (r_idx == 0)
                    for c_idx, val in enumerate(row, start=1):
                        cell = ws.cell(row=current_row, column=c_idx, value=val)
                        cell.border = thin_border

                        if is_header:
                            cell.font = font_header
                            cell.fill = fill_header
                            cell.alignment = align_center
                        else:
                            cell.font = font_cell
                            cell.alignment = align_left
                            if r_idx % 2 == 0:
                                cell.fill = fill_alt
                    current_row += 1
                current_row += 1  # Blank row after table

            else:
                # Text paragraph
                text_val = elem.get("text", "")
                cell = ws.cell(row=current_row, column=1, value=text_val)
                cell.font = font_cell
                cell.alignment = align_left
                current_row += 1

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if val_str:
                    max_len = max(max_len, len(val_str))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    # Remove the initial blank sheet
    if default_sheet in wb.worksheets and len(wb.worksheets) > 1:
        wb.remove(default_sheet)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
