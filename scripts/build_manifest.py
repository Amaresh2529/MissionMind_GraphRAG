"""
build_manifest.py — fills the computed fields (sha256, bytes, pages) of
data/manifest.json from the files on disk, and reports PDFs in data/raw that
the manifest does not describe.

    python scripts/build_manifest.py           # update computed fields
    python scripts/build_manifest.py --check   # exit 1 if anything differs
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"


def file_facts(path: Path) -> dict:
    data = path.read_bytes()
    if path.suffix.lower() == ".html":      # web pages (press releases) count as one page
        pages = 1
    else:
        import pymupdf
        pages = len(pymupdf.open(path))
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "pages": pages}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = []
    described = set()
    for doc in manifest["documents"]:
        path = ROOT / doc["file"]
        described.add(path.resolve())
        if not path.exists():
            problems.append(f"missing file: {doc['file']}")
            continue
        facts = file_facts(path)
        for k, v in facts.items():
            if doc.get(k) != v:
                problems.append(f"{doc['doc_id']}: {k} {doc.get(k)!r} -> {v!r}")
                doc[k] = v
    for pdf in sorted((ROOT / "data" / "raw").glob("*.pdf")):
        if pdf.resolve() not in described:
            problems.append(f"not in manifest: {pdf.name}")
    if args.check:
        print("\n".join(problems) or "manifest matches files")
        return 1 if problems else 0
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(problems) or "no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
