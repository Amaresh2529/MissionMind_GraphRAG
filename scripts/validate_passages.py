"""
validate_passages.py — Stage 2 criteria B1/B2/B3 on the REAL parser output.

For every document in data/processed/pages|passages:
  B1  passage text == page text[char_start:char_end]; ids unique; page >= 1
  B2  passages never span two pages (by construction) and their union covers
      every non-whitespace character of every non-boilerplate block
  B3  no ligature / soft-hyphen / modifier-apostrophe characters remain
Exit code 1 if any check fails. Writes runs/<run_id>/passage_validation.json.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from config import get_settings  # noqa: E402
from runlog import new_run_dir, write_json  # noqa: E402

BAD_CHARS = re.compile("[ﬀ-ﬆ­ʼ]")


def validate() -> dict:
    base = get_settings().processed_dir
    report, ids = {}, set()
    for pf in sorted((base / "pages").glob("*.jsonl")):
        doc = pf.stem
        pages = {r["page"]: r for r in map(json.loads, open(pf, encoding="utf-8"))}
        passages = [json.loads(l) for l in open(base / "passages" / f"{doc}.jsonl", encoding="utf-8")]
        r = {"pages": len(pages), "passages": len(passages), "slice_mismatch": 0, "duplicate_ids": 0,
             "bad_page": 0, "uncovered_chars": 0, "covered_chars": 0, "bad_chars": 0}
        by_page = {}
        for p in passages:
            r["duplicate_ids"] += p["passage_id"] in ids
            ids.add(p["passage_id"])
            if p["page"] not in pages:
                r["bad_page"] += 1
                continue
            if pages[p["page"]]["text"][p["char_start"]:p["char_end"]] != p["text"]:
                r["slice_mismatch"] += 1
            r["bad_chars"] += len(BAD_CHARS.findall(p["text"]))
            by_page.setdefault(p["page"], []).append((p["char_start"], p["char_end"]))
        for num, page in pages.items():
            covered = set()
            for a, z in by_page.get(num, []):
                covered.update(range(a, z))
            for b in page["blocks"]:
                if b["kind"] == "boilerplate":
                    continue
                for i in range(b["start"], b["end"]):
                    if not page["text"][i].isspace():
                        if i in covered:
                            r["covered_chars"] += 1
                        else:
                            r["uncovered_chars"] += 1
        report[doc] = r
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)
    report = validate()
    failures = {d: {k: v for k, v in r.items() if k in ("slice_mismatch", "duplicate_ids", "bad_page",
                                                         "uncovered_chars", "bad_chars") and v}
                for d, r in report.items()}
    failures = {d: f for d, f in failures.items() if f}
    run_dir = new_run_dir(args.run_id, prefix="passage_validation")
    write_json(run_dir / "passage_validation.json", {"documents": report, "failures": failures})
    for d, r in report.items():
        print(f"{d[:40]:40s} pages={r['pages']:4d} passages={r['passages']:5d} covered={r['covered_chars']:8d} "
              f"uncovered={r['uncovered_chars']} slice_mismatch={r['slice_mismatch']} bad_chars={r['bad_chars']}")
    print("PASS" if not failures else f"FAIL: {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
