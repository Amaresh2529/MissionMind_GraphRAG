"""
ocr_quality_study.py — Stage 2 criterion B4.

1. Summarises the per-page quality scores the parser stored for every document.
2. For Challenger (a scanned report whose text layer is an OCR of unknown
   origin), draws 20 pages at random (seed 42) from pages kept on the text
   layer, re-OCRs them with Tesseract at 300 dpi, and compares
   - dictionary-based quality score (text_cleaner.text_quality_score),
   - share of tokens that are real English words (wordfreq),
   - character-level agreement between the two transcriptions (difflib ratio).
3. Character error rate (CER) against reference transcriptions of short
   excerpts, if `--references <json>` is given ({"page": int, "text": str} list).
   CER = Levenshtein(hyp, ref) / len(ref) after the same normalisation.

Outputs runs/<run_id>/ocr_quality.json and page images for transcription
(images are written outside the repository by default: --image-dir).
"""

import argparse
import difflib
import json
import random
import re
import statistics
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from config import get_settings  # noqa: E402
from runlog import new_run_dir, write_json  # noqa: E402
from pipeline.text_cleaner import text_quality_score  # noqa: E402
from pipeline.normalize import normalize_block  # noqa: E402

DOC = "Challenger"


def english_word_share(text: str) -> float:
    from wordfreq import zipf_frequency
    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", text)]
    if not words:
        return 0.0
    return sum(zipf_frequency(w, "en") > 1.5 for w in words) / len(words)


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(hyp: str, ref: str) -> float:
    return levenshtein(hyp, ref) / max(1, len(ref))


def best_window(page_text: str, ref: str) -> str:
    """The substring of page_text that best aligns with a reference excerpt."""
    sm = difflib.SequenceMatcher(None, page_text, ref, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= 4]
    if not blocks:
        return ""
    start = max(0, blocks[0].a - blocks[0].b)
    return page_text[start:start + len(ref) + 20].strip()[:len(ref) + 5]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--image-dir", default=None, help="where to save page PNGs for transcription")
    ap.add_argument("--references", default=None, help="JSON list of {page, text} reference excerpts")
    args = ap.parse_args(argv)
    s = get_settings()
    run_dir = new_run_dir(args.run_id, prefix="ocr_quality")
    result = {"per_document": {}}

    for f in sorted((s.processed_dir / "pages").glob("*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        q = [max(r["quality_text_layer"], r["quality_ocr"] or 0) for r in rows]
        result["per_document"][f.stem] = {
            "pages": len(rows), "ocr_pages": sum(r["source"] == "ocr" for r in rows),
            "quality_mean": round(statistics.mean(q), 4), "quality_min": round(min(q), 4),
            "pages_below_0.6": sum(x < 0.6 for x in q), "pages_below_0.8": sum(x < 0.8 for x in q),
            "english_word_share": round(english_word_share(" ".join(r["text"] for r in rows)), 4),
        }

    pages = {r["page"]: r for r in map(json.loads, open(s.processed_dir / "pages" / f"{DOC}.jsonl", encoding="utf-8"))}
    candidates = sorted(p for p, r in pages.items() if r["source"] == "text_layer" and len(r["text"].split()) > 150)
    sample = sorted(random.Random(42).sample(candidates, min(args.sample, len(candidates))))
    from pipeline.pdf_loader import ocr_page
    from pipeline.page_parser import _text_layer_blocks
    import pymupdf
    pdf = s.raw_dir / f"{DOC}.pdf"
    pdf_doc = pymupdf.open(pdf)

    def layer_text(p: int) -> str:  # recomputed with the CURRENT normaliser
        return "\n\n".join(b.text for b in _text_layer_blocks(pdf_doc[p - 1]))

    comparison = []
    for p in sample:
        layer = layer_text(p)
        ocr = normalize_block(ocr_page(pdf, p - 1))
        comparison.append({
            "page": p,
            "quality_text_layer": round(text_quality_score(layer), 4), "quality_tesseract": round(text_quality_score(ocr), 4),
            "english_share_text_layer": round(english_word_share(layer), 4),
            "english_share_tesseract": round(english_word_share(ocr), 4),
            "agreement_ratio": round(difflib.SequenceMatcher(None, layer, ocr, autojunk=False).ratio(), 4),
            "words_text_layer": len(layer.split()), "words_tesseract": len(ocr.split()),
        })
        print(comparison[-1])
        if args.image_dir:
            import pymupdf
            out = Path(args.image_dir)
            out.mkdir(parents=True, exist_ok=True)
            pymupdf.open(pdf)[p - 1].get_pixmap(dpi=150).save(out / f"{DOC}_p{p:04d}.png")
            (out / f"{DOC}_p{p:04d}_tesseract.txt").write_text(ocr, encoding="utf-8")
    result["challenger_sample"] = {"seed": 42, "pages": sample, "comparison": comparison,
                                   "mean": {k: round(statistics.mean(c[k] for c in comparison), 4)
                                            for k in comparison[0] if k != "page"}}

    if args.references:
        refs = json.load(open(args.references, encoding="utf-8"))
        cer_rows = []
        for ref in refs:
            ref_text = normalize_block(ref["text"])
            layer_hyp = best_window(layer_text(ref["page"]), ref_text)
            tess_text = normalize_block(ocr_page(pdf, ref["page"] - 1))
            tess_hyp = best_window(tess_text, ref_text)
            cer_rows.append({"page": ref["page"], "ref_chars": len(ref_text),
                             "cer_text_layer": round(cer(layer_hyp, ref_text), 4),
                             "cer_tesseract": round(cer(tess_hyp, ref_text), 4)})
            print(cer_rows[-1])
        result["cer"] = {"rows": cer_rows, "transcriber": refs[0].get("transcriber") if refs else None,
                         "mean_cer_text_layer": round(statistics.mean(r["cer_text_layer"] for r in cer_rows), 4),
                         "mean_cer_tesseract": round(statistics.mean(r["cer_tesseract"] for r in cer_rows), 4)}
    write_json(run_dir / "ocr_quality.json", result)
    print(json.dumps(result["per_document"], indent=1))
    print("sample means:", result["challenger_sample"]["mean"])
    return result


if __name__ == "__main__":
    main()
