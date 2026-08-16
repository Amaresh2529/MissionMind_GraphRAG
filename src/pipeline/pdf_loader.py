import fitz  # PyMuPDF
import re
from pathlib import Path

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from wordfreq import zipf_frequency
    WORDFREQ_AVAILABLE = True
except ImportError:
    WORDFREQ_AVAILABLE = False

# Signal 1: a digit fused directly between letters is close to unambiguous
# evidence of extraction corruption (e.g. "faci8ities" from "facilities").
# Legitimate technical tokens like "STS-51-L" or "24/7" don't match this —
# the digit has to sit *inside* an unbroken run of letters on both sides.
_EMBEDDED_DIGIT_RE = re.compile(r'[A-Za-z]\d[A-Za-z]')

_STRIP_CHARS = '.,;:()[]{}"\'`'

# Known, fixed font-mapping artifact in older scanned reports: the glyph for
# capital "O" gets extracted as digit "0" specifically in "O-ring"/"O-rings"
# (e.g. Challenger's report). This is a deterministic substitution — "0-ring"
# never legitimately means a numeric zero — so it's safe to correct globally
# rather than relying on OCR to catch it.
_ORING_RE = re.compile(r'\b0-ring', re.IGNORECASE)


def _fix_oring(match: re.Match) -> str:
    return 'O' + match.group(0)[1:]


def sanitize_text(text: str) -> str:
    """Removes excessive newlines, unprintable characters, and fixes broken formatting."""
    cleaned = re.sub(r'\s+', ' ', text)
    cleaned = re.sub(r'[^\x00-\x7F]+', ' ', cleaned)
    cleaned = _ORING_RE.sub(_fix_oring, cleaned)
    return cleaned.strip()


def text_quality_score(text: str) -> float:
    """
    Estimates extraction quality for a page, returning a score in [0, 1]
    where higher is cleaner. Two signals are combined, and both are
    designed to leave normal technical-document text (citations, page
    numbers, hyphenated part names, ALL-CAPS acronyms, proper nouns)
    completely untouched:

    1. Embedded-digit corruption — a digit fused directly between letters
       is a strong, low-noise signature of broken font/encoding
       extraction. Any meaningful presence of it fails the page outright.

    2. Dictionary coverage — for ordinary *lowercase* words only (numbers,
       proper nouns, and ALL-CAPS acronyms are excluded so we never punish
       "Marshall", "Thiokol", or "NASA"), the fraction that are
       recognizable English words. Requires the `wordfreq` package; if
       it isn't installed, this signal is skipped and only signal 1 runs.
    """
    tokens = text.split()
    if not tokens:
        return 1.0  # nothing to judge; don't force OCR on a blank page

    embedded_digit_hits = sum(1 for t in tokens if _EMBEDDED_DIGIT_RE.search(t))
    if embedded_digit_hits / len(tokens) > 0.01:
        return 0.0

    if not WORDFREQ_AVAILABLE:
        return 1.0

    checkable = []
    for t in tokens:
        core = t.strip(_STRIP_CHARS)
        if len(core) < 3 or not core.isalpha():
            continue
        if core[0].isupper() or core.isupper():
            continue  # assume proper noun / acronym — don't penalize
        checkable.append(core.lower())

    if len(checkable) < 8:
        return 1.0  # too little evidence either way; don't force OCR

    known = sum(1 for w in checkable if zipf_frequency(w, 'en') > 0)
    return known / len(checkable)


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