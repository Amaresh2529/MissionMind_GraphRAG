"""
page_parser.py

Stage 2 page-aware parsing. For every PDF it produces

  data/processed/pages/<doc_id>.jsonl     one record per page:
      page (1-based), source ("text_layer" | "ocr"), quality scores, the
      normalised page text and its blocks with character offsets and kind
      ("body" | "heading" | "boilerplate")
  data/processed/passages/<doc_id>.jsonl  retrievable passages:
      passage_id, doc_id, page, char_start, char_end, section, chapter,
      pseudo_field, n_words, text
  data/processed/parse_report.json        per-document statistics

Provenance contract (tested): passage["text"] == page_text[char_start:char_end],
a passage never crosses a page or a section boundary, and the passages of a
page together cover every non-boilerplate block of that page.

Section/heading detection is rule-based (font size relative to the document's
body size, bold weight, numbering patterns) because 6 of the 7 PDFs have no
usable embedded table of contents. Its accuracy is measured, not assumed
(docs/research/06_Stage2_Ingestion_Provenance.md).

The Stage 1 word-window pipeline (pdf_loader.py, text_chunker.py) is not
touched; baseline B4 keeps using it.
"""

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from pipeline.normalize import normalize_block
from pipeline.text_cleaner import text_quality_score

OCR_THRESHOLD = 0.6          # same threshold as the Stage 1 loader
PASSAGE_MIN_WORDS = 150
PASSAGE_MAX_WORDS = 300
HEADING_MAX_WORDS = 14

_NUMBERED = re.compile(r"^(?:(?:chapter|section|part)\s+)?(\d{1,2}(?:\.\d{1,2}){0,3}|[IVX]{1,5}|[A-H])[.)]?\s+[A-Z(\"']", re.I)
_CAPTION = re.compile(r"^(f?igure|fig\.?|table|photo|chart|exhibit)\b", re.I)  # "igure": drop-cap F lost
_PAGE_NUMBER = re.compile(r"^\W*(page\s*)?[\dIVXivx]{1,4}\W*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")

# Pseudo-fields (base paper's Summary/Causes/Disposition recovered from headings).
# Checked in this order against the section heading, then the chapter heading.
FIELD_RULES = [
    ("other", ["table of contents", "contents", "foreword", "preface", "acknowledg", "appendix", "acronym",
               "abbreviation", "glossary", "references", "bibliography", "index", "board members",
               "membership", "letter", "signature", "consultants", "in memoriam", "method of investigation",
               "phase ii plan", "investigation board", "inquiry board", "commission on", "report by",
               "endnotes", "notes for chapter", "definitions", "board staff", "key participants"]),
    ("recommendations", ["recommendation", "lessons learned", "corrective action", "lessons"]),
    ("causes", ["root cause", "cause", "causal", "contributing factor", "failure scenario", "why the accident"]),
    ("summary", ["executive summary", "summary", "abstract", "synopsis", "overview of findings"]),
    ("findings", ["finding", "analysis", "investigation", "discussion", "observation", "assessment",
                  "conclusion", "test results", "evaluation"]),
    ("narrative", ["description", "chronology", "sequence of events", "history", "background", "introduction",
                   "overview", "mission", "flight", "events", "the accident", "launch", "program",
                   "mishap", "failure", "anomaly"]),
]


def assign_pseudo_field(section: str | None, chapter: str | None) -> str:
    # Front/back matter is decided at chapter level: numbered items inside an
    # appendix ("1. INTRODUCTION/BACKGROUND" of a charter letter) stay "other".
    if chapter and any(k in chapter.lower() for k in FIELD_RULES[0][1]):
        return "other"
    for heading in (section, chapter):
        if not heading:
            continue
        h = heading.lower()
        for name, keys in FIELD_RULES:
            if any(k in h for k in keys):
                return name
    # Body text under a heading that matches no rule ("Design Questions
    # Resurface", "Decision Making at NASA") is analysis in these reports, so
    # the default is "findings"; "other" is reserved for explicit front/back
    # matter and for text before the first heading. Measured in criterion B5.
    return "findings" if (section or chapter) else "other"


def _plausible_heading(text: str) -> bool:
    """Rejects OCR noise from photos/figures that is printed large ("lll",
    "eeoooce", "a > wOORR"): most tokens must be dictionary words and at least
    one real word of 4+ letters must be present."""
    try:
        from wordfreq import zipf_frequency
    except ImportError:
        return True
    words = re.findall(r"[A-Za-z]{2,}", text)
    if not words:
        return False
    known = [w for w in words if zipf_frequency(w.lower(), "en") >= 2.5 or w.isupper() and len(w) <= 5]
    return len(known) / len(words) >= 0.6 and any(len(w) >= 4 and zipf_frequency(w.lower(), "en") >= 2.5 for w in words)


@dataclass
class Block:
    text: str
    max_size: float = 0.0
    bold_frac: float = 0.0
    n_lines: int = 1
    kind: str = "body"
    level: int = 0
    start: int = 0
    end: int = 0


@dataclass
class Page:
    number: int
    blocks: list = field(default_factory=list)
    source: str = "text_layer"
    q_text_layer: float = 1.0
    q_ocr: float | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)


def _text_layer_blocks(page) -> list[Block]:
    blocks = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        lines, sizes, bold_chars, chars = [], [], 0, 0
        for line in b["lines"]:
            line_text = "".join(s["text"] for s in line["spans"])
            if line_text.strip():
                lines.append(line_text)
            for s in line["spans"]:
                n = len(s["text"].strip())
                if n:
                    sizes.append(s["size"])
                    chars += n
                    bold_chars += n if s["flags"] & 16 else 0
        text = normalize_block("\n".join(lines))
        if text:
            blocks.append(Block(text, max(sizes) if sizes else 0.0,
                                bold_chars / chars if chars else 0.0, len(lines)))
    return blocks


OCR_DPI = 300
SCANNED_MARGIN = 0.05   # scanned docs: keep OCR unless its quality is this much LOWER than the text layer


_SHA_CACHE: dict[Path, str] = {}


def _ocr_cache_path(pdf_path: Path, page_index: int) -> Path | None:
    """Cache key = PDF SHA-256 + page + DPI + Tesseract version, so a cached
    OCR result is reused only for byte-identical input and the same engine.
    Raw Tesseract output is cached (before normalisation), so normaliser
    changes still take effect on re-parse."""
    try:
        import hashlib
        import pytesseract
        if pdf_path not in _SHA_CACHE:
            version = re.sub(r"[^0-9.]", "", str(pytesseract.get_tesseract_version()))
            digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            _SHA_CACHE[pdf_path] = f"{digest[:16]}_dpi{OCR_DPI}_tess{version}"
    except Exception:
        return None
    key = _SHA_CACHE[pdf_path]
    return get_settings().processed_dir / "ocr_cache" / pdf_path.stem / key / f"p{page_index + 1:04d}.json"


def _ocr_raw_paragraphs(pdf_path: Path, page_index: int) -> list[dict] | None:
    """[{"raw": text with line breaks, "heights": [...], "n_lines": int}] per Tesseract paragraph."""
    cache = _ocr_cache_path(pdf_path, page_index)
    if cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return None
    try:
        images = convert_from_path(str(pdf_path), first_page=page_index + 1, last_page=page_index + 1, dpi=OCR_DPI)
        data = pytesseract.image_to_data(images[0], output_type=pytesseract.Output.DICT)
    except Exception as err:
        print(f"   ⚠️  OCR failed on page {page_index + 1}: {err}")
        return None
    paras: dict[tuple, dict] = {}
    for i, word in enumerate(data["text"]):
        if not word.strip() or float(data["conf"][i]) < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i])
        para = paras.setdefault(key, {"lines": {}, "heights": []})
        para["lines"].setdefault(data["line_num"][i], []).append(word)
        para["heights"].append(data["height"][i])
    raw_paras = [{"raw": "\n".join(" ".join(ws) for _, ws in sorted(p["lines"].items())),
                  "heights": p["heights"], "n_lines": len(p["lines"])}
                 for p in paras.values()]  # dict keeps Tesseract's reading order
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(raw_paras), encoding="utf-8")
    return raw_paras


def _ocr_blocks(pdf_path: Path, page_index: int) -> list[Block] | None:
    """Tesseract OCR at 300 dpi with layout: one Block per Tesseract paragraph,
    font size estimated from median word height (px -> pt at 300 dpi), so
    heading detection also works on OCR pages. Bold is unknown (0)."""
    raw_paras = _ocr_raw_paragraphs(pdf_path, page_index)
    if raw_paras is None:
        return None
    blocks = []
    for para in raw_paras:
        text = normalize_block(para["raw"])
        if text and para["heights"]:
            heights = sorted(para["heights"])
            size_pt = heights[len(heights) // 2] * 72.0 / OCR_DPI
            blocks.append(Block(text, max_size=round(size_pt, 1), n_lines=para["n_lines"]))
    return blocks or None


def is_scanned(doc) -> bool:
    """A document is a scan when most pages are covered by one large image."""
    covered = 0
    for p in doc:
        area = p.rect.width * p.rect.height
        if any(r.width * r.height >= 0.8 * area for img in p.get_images() for r in p.get_image_rects(img[0])):
            covered += 1
    return len(doc) > 0 and covered / len(doc) >= 0.8


def _read_pages(pdf_path: Path, use_ocr: bool) -> tuple[list[Page], bool]:
    doc = pymupdf.open(pdf_path)
    scanned = use_ocr and is_scanned(doc)
    pages = []
    for i, p in enumerate(doc):
        page = Page(number=i + 1, blocks=_text_layer_blocks(p))
        page.q_text_layer = text_quality_score(page.text)
        empty_scan = not page.text.strip() and bool(p.get_images())
        if use_ocr and (scanned or page.q_text_layer < OCR_THRESHOLD or empty_scan):
            ocr = _ocr_blocks(pdf_path, i)
            if ocr:
                page.q_ocr = text_quality_score("\n\n".join(b.text for b in ocr))
                better = page.q_ocr >= page.q_text_layer - SCANNED_MARGIN if scanned else page.q_ocr > page.q_text_layer
                if better or empty_scan:
                    page.blocks, page.source = ocr, "ocr"
        pages.append(page)
    return pages, scanned


def _boilerplate_keys(pages: list[Page]) -> set[str]:
    """Short block texts repeated on many pages (running headers/footers)."""
    seen = collections.Counter()
    for page in pages:
        keys = {re.sub(r"\d+", "#", b.text.lower()) for b in page.blocks if len(b.text.split()) <= 12}
        seen.update(keys)
    threshold = max(3, int(0.25 * len(pages)))
    return {k for k, n in seen.items() if n >= threshold}


def _body_size(pages: list[Page]) -> float:
    weights = collections.Counter()
    for page in pages:
        for b in page.blocks:
            if b.max_size:
                weights[round(b.max_size)] += len(b.text)
    return float(weights.most_common(1)[0][0]) if weights else 0.0


def _classify_blocks(pages: list[Page]) -> None:
    boiler = _boilerplate_keys(pages)
    body = _body_size(pages)
    for page in pages:
        for b in page.blocks:
            words = b.text.split()
            if _PAGE_NUMBER.match(b.text) or re.sub(r"\d+", "#", b.text.lower()) in boiler:
                b.kind = "boilerplate"
                continue
            half = len(words) // 2
            duplicated = len(words) >= 2 and len(words) % 2 == 0 and words[:half] == words[half:]
            if (len(words) > HEADING_MAX_WORDS or len(re.findall(r"[A-Za-z]", b.text)) < 3
                    or _CAPTION.match(b.text) or b.text.endswith((",", ";")) or duplicated
                    or not _plausible_heading(b.text)):
                continue  # duplicated = diagram text drawn twice (shadow/outline), not a heading
            numbered = _NUMBERED.match(b.text)
            bigger = body and b.max_size >= body + 1.0
            # bold text SMALLER than body text is a figure/diagram label, not a heading
            not_small = not body or b.max_size == 0.0 or b.max_size >= body - 0.5
            bold = b.bold_frac >= 0.9 and b.n_lines <= 2 and not_small
            small_numbered = numbered and b.bold_frac >= 0.9 and not not_small
            caps = sum(c.isupper() for c in b.text) >= 0.8 * sum(c.isalpha() for c in b.text)
            if numbered and (bigger or bold or b.max_size == 0.0 or (caps and not_small)):
                b.kind = "heading"
                b.level = numbered.group(1).count(".") + 1 if numbered.group(1)[0].isdigit() else 1
            elif small_numbered:
                b.kind, b.level = "heading", 3   # numbered items inside small-print appendices
            elif bigger or (bold and not b.text.endswith(".")):
                b.kind = "heading"
                b.level = 1 if body and b.max_size >= body + 4.0 else 2


def _assign_offsets(page: Page) -> None:
    pos = 0
    for b in page.blocks:
        b.start, b.end = pos, pos + len(b.text)
        pos = b.end + 2  # "\n\n" separator, as in Page.text


def _split_long(text: str, base: int) -> list[tuple[int, int]]:
    """Splits a long block at sentence boundaries into <= PASSAGE_MAX_WORDS pieces (offsets)."""
    pieces, start, words = [], 0, 0
    cuts = [m.start() for m in _SENTENCE_END.finditer(text)] + [len(text)]
    prev = 0
    for cut in cuts:
        seg_words = len(text[prev:cut].split())
        if words and words + seg_words > PASSAGE_MAX_WORDS:
            pieces.append((start, prev))
            start, words = prev, 0
            while start < len(text) and text[start] == " ":
                start += 1
        words += seg_words
        prev = cut
    pieces.append((start, len(text)))
    return [(base + a, base + b) for a, b in pieces if text[a:b].strip()]


def build_passages(doc_id: str, pages: list[Page]) -> list[dict]:
    passages = []
    chapter = section = None
    for page in pages:
        page_text = page.text
        groups, current = [], []
        for b in page.blocks:
            if b.kind == "boilerplate":
                if current:
                    groups.append(current)
                current = []
                continue
            if b.kind == "heading":
                # a heading directly after a heading of the same level continues it
                # (titles wrapped into two blocks, e.g. "Letter Establishing the ..." /
                # "Mishap Investigation Board"); otherwise it starts a new section
                continues = bool(current) and all(x[0].kind == "heading" for x in current) \
                    and current[-1][0].level == b.level
                if continues:
                    section = f"{section} {b.text}"
                    if b.level <= 1:
                        chapter = f"{chapter} {b.text}"
                    current = [(x[0], section, chapter) for x in current]
                else:
                    if current:
                        groups.append(current)
                    current = []
                    section = b.text
                    if b.level <= 1:
                        chapter = b.text
            if not current:
                current = [(b, section, chapter)]
            else:
                current.append((b, section, chapter))
            words = sum(len(x[0].text.split()) for x in current)
            if words >= PASSAGE_MIN_WORDS:
                groups.append(current)
                current = []
        if current:
            groups.append(current)

        n = 0
        for group in groups:
            first, sec, chap = group[0]
            start, end = first.start, group[-1][0].end
            spans = [(start, end)]
            if len(page_text[start:end].split()) > PASSAGE_MAX_WORDS:
                spans = _split_long(page_text[start:end], start)
            for a, z in spans:
                text = page_text[a:z]
                passages.append({
                    "passage_id": f"{doc_id}::p{page.number:04d}::{n:02d}",
                    "doc_id": doc_id, "page": page.number, "char_start": a, "char_end": z,
                    "section": sec, "chapter": chap, "pseudo_field": assign_pseudo_field(sec, chap),
                    "n_words": len(text.split()), "source": page.source,
                    "low_quality": max(page.q_text_layer, page.q_ocr or 0.0) < OCR_THRESHOLD,
                    "text": text,
                })
                n += 1
    return passages


def parse_document(pdf_path: Path, use_ocr: bool = True) -> tuple[list[Page], list[dict], dict]:
    doc_id = pdf_path.stem
    pages, scanned = _read_pages(pdf_path, use_ocr)
    _classify_blocks(pages)
    for page in pages:
        _assign_offsets(page)
    passages = build_passages(doc_id, pages)
    kinds = collections.Counter(b.kind for p in pages for b in p.blocks)
    stats = {
        "doc_id": doc_id, "pages": len(pages), "scanned": scanned,
        "pages_ocr": sum(p.source == "ocr" for p in pages),
        "pages_low_quality": sum(max(p.q_text_layer, p.q_ocr or 0.0) < OCR_THRESHOLD for p in pages),
        "pages_empty": sum(not p.text.strip() for p in pages),
        "blocks": dict(kinds), "headings": kinds.get("heading", 0),
        "passages": len(passages),
        "words_in_passages": sum(p["n_words"] for p in passages),
        "pseudo_fields": dict(collections.Counter(p["pseudo_field"] for p in passages)),
        "body_font_size": _body_size(pages),
    }
    return pages, passages, stats


def page_record(doc_id: str, page: Page) -> dict:
    return {"doc_id": doc_id, "page": page.number, "source": page.source,
            "quality_text_layer": round(page.q_text_layer, 4),
            "quality_ocr": None if page.q_ocr is None else round(page.q_ocr, 4),
            "text": page.text,
            "blocks": [{"start": b.start, "end": b.end, "kind": b.kind, "level": b.level,
                        "size": round(b.max_size, 1), "bold": round(b.bold_frac, 2)} for b in page.blocks]}


def write_outputs(doc_id: str, pages: list[Page], passages: list[dict]) -> None:
    base = get_settings().processed_dir
    for sub, rows in (("pages", [page_record(doc_id, p) for p in pages]), ("passages", passages)):
        out = base / sub / f"{doc_id}.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv=None):
    from runlog import new_run_dir, write_json, environment_info, tee_output, Timer
    parser = argparse.ArgumentParser(description="Stage 2 page-aware parsing")
    parser.add_argument("--docs", nargs="*", default=None, help="PDF stems; default: all in data/raw")
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    pdfs = sorted(get_settings().raw_dir.glob("*.pdf"))
    if args.docs:
        pdfs = [p for p in pdfs if p.stem in set(args.docs)]
    run_dir = new_run_dir(args.run_id, prefix="parse")
    timer, report = Timer(), {}
    with tee_output(run_dir / "log.txt"):
        write_json(run_dir / "config.json", {"args": vars(args), "ocr_threshold": OCR_THRESHOLD,
                                             "passage_words": [PASSAGE_MIN_WORDS, PASSAGE_MAX_WORDS]})
        write_json(run_dir / "env.json", environment_info(include_services=False))
        for pdf in pdfs:
            print(f"Parsing {pdf.name} ...")
            try:
                with timer.step(pdf.stem):
                    pages, passages, stats = parse_document(pdf, use_ocr=not args.no_ocr)
                    write_outputs(pdf.stem, pages, passages)
                report[pdf.stem] = stats
                print(f"   {stats['pages']} pages ({stats['pages_ocr']} OCR, {stats['pages_low_quality']} low quality), "
                      f"{stats['headings']} headings, {stats['passages']} passages")
            except Exception as err:  # recorded, not hidden
                report[pdf.stem] = {"error": f"{type(err).__name__}: {err}"}
                print(f"   ❌ {pdf.name}: {err}")
        write_json(get_settings().processed_dir / "parse_report.json", report)
        write_json(run_dir / "parse_report.json", report)
        write_json(run_dir / "timings.json", timer.timings)
    return report


if __name__ == "__main__":
    main()
