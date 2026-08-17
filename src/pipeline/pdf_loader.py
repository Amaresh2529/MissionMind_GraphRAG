"""
pdf_loader.py

Extracts text from PDFs in data/raw, with automatic OCR fallback for pages
that score poorly on extraction quality (scanned/corrupted pages).

Text cleaning and quality scoring now live in text_cleaner.py — this file
only handles PDF-specific work (page iteration, OCR).
"""

import sys
from pathlib import Path

import fitz  # PyMuPDF

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from pipeline.text_cleaner import sanitize_text, text_quality_score, WORDFREQ_AVAILABLE

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def ocr_page(pdf_path: Path, page_num: int) -> str:
    """Falls back to OCR for a single page when direct text extraction is unreliable."""
    if not OCR_AVAILABLE:
        print(f"   ⚠️  Page {page_num + 1} needs OCR fallback but pytesseract/pdf2image "
              f"aren't installed. Run: pip install pytesseract pdf2image "
              f"(and install the Tesseract OCR + Poppler binaries separately).")
        return ""
    try:
        images = convert_from_path(str(pdf_path), first_page=page_num + 1,
                                    last_page=page_num + 1, dpi=300)
        if not images:
            return ""
        return pytesseract.image_to_string(images[0])
    except Exception as ocr_err:
        print(f"   ⚠️  OCR failed on page {page_num + 1}: {ocr_err}")
        return ""


def process_all_pdfs(quality_threshold: float = 0.6):
    """
    Reads every PDF in data/raw, extracts text via PyMuPDF, and automatically
    falls back to OCR for any page whose extracted text scores below
    `quality_threshold`. Writes clean text to data/processed.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"

    processed_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(raw_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in: {raw_dir}")
        return

    if not WORDFREQ_AVAILABLE:
        print("ℹ️  'wordfreq' not installed — dictionary check disabled, relying only "
              "on embedded-digit detection. Run: pip install wordfreq for a more "
              "thorough scan.\n")

    print(f"Found {len(pdf_files)} PDFs in data/raw/. Starting extraction...\n")

    for pdf_path in pdf_files:
        output_txt_path = processed_dir / f"{pdf_path.stem}.txt"

        if output_txt_path.exists():
            print(f"Skipping {pdf_path.name} (already processed at {output_txt_path.name})")
            continue

        print(f"Processing: {pdf_path.name}...")
        try:
            doc = fitz.open(pdf_path)
            extracted_pages = []
            ocr_page_count = 0
            flagged_page_count = 0

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                raw_page_text = page.get_text("text")
                clean_page_text = sanitize_text(raw_page_text)

                score = text_quality_score(clean_page_text)
                if score < quality_threshold:
                    flagged_page_count += 1
                    ocr_text = ocr_page(pdf_path, page_num)
                    if ocr_text:
                        ocr_clean = sanitize_text(ocr_text)
                        if text_quality_score(ocr_clean) > score:
                            clean_page_text = ocr_clean
                            ocr_page_count += 1

                if clean_page_text:
                    extracted_pages.append(clean_page_text)

            full_document_text = "\n\n".join(extracted_pages)

            with open(output_txt_path, "w", encoding="utf-8") as f:
                f.write(full_document_text)

            notes = []
            if flagged_page_count:
                notes.append(f"{flagged_page_count} page(s) flagged as low quality")
            if ocr_page_count:
                notes.append(f"{ocr_page_count} recovered via OCR")
            note_str = f" ({', '.join(notes)})" if notes else ""
            print(f"Completed: Saved {output_txt_path.name}{note_str}")

        except Exception as err:
            print(f"Error processing {pdf_path.name}: {err}")


if __name__ == "__main__":
    process_all_pdfs()