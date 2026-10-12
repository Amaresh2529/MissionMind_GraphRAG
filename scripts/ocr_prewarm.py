"""
ocr_prewarm.py — fills the per-page OCR cache of scanned PDFs in parallel.

Produces exactly what page_parser would compute page by page (same function,
same cache key); it only saves wall-clock time. Pages are processed from the
last page backwards so a sequential parse running at the same time meets the
pre-warmed pages instead of duplicating them.

    python scripts/ocr_prewarm.py --docs NASA_Apollo204_Review_Board NASA_Genesis_MIB_Report --workers 10
"""

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))


def _one(args):
    from pipeline.page_parser import _ocr_raw_paragraphs
    pdf, i = args
    return i, _ocr_raw_paragraphs(Path(pdf), i) is not None


def main(argv=None):
    import pymupdf
    from config import get_settings
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only-image-pages", action="store_true",
                    help="only pages without a text layer but with images (OCR'd even in non-scanned PDFs)")
    args = ap.parse_args(argv)
    jobs = []
    for doc in args.docs:
        pdf = get_settings().raw_dir / f"{doc}.pdf"
        doc_pages = pymupdf.open(pdf)
        idx = [i for i, pg in enumerate(doc_pages)
               if not args.only_image_pages or (not pg.get_text().strip() and pg.get_images())]
        jobs += [(str(pdf), i) for i in reversed(idx)]
    t0, failed = time.time(), 0
    with ProcessPoolExecutor(args.workers) as ex:
        for n, (i, ok) in enumerate(ex.map(_one, jobs), 1):
            failed += not ok
            if n % 25 == 0:
                print(f"{n}/{len(jobs)} pages, {time.time() - t0:.0f} s", flush=True)
    print(f"done: {len(jobs)} pages, {failed} failed, {time.time() - t0:.0f} s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
