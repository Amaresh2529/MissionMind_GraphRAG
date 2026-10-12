"""
fetch_corpus.py — downloads approved candidates from data/corpus_candidates.json.

Run ONLY after the download list has been approved. For each candidate:
  - PDF: downloaded to data/raw/<doc_id>.pdf; content type must be PDF and the
    size must equal the size recorded at verification time (else rejected).
  - HTML (press releases): saved to data/raw_html/<doc_id>.html unchanged;
    converted to text in a later step (not part of this script).
Every download is logged to runs/<run_id>/fetch_log.json with SHA-256; the
manifest is then updated with scripts/build_manifest.py after curation.

    python scripts/fetch_corpus.py --doc-ids NASA_WIRE_MIB_Vol1 ...   # subset
    python scripts/fetch_corpus.py --all
"""

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from runlog import new_run_dir, write_json  # noqa: E402

CANDIDATES = ROOT / "data" / "corpus_candidates.json"


def fetch(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MissionMind research corpus)"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read(), r.headers.get("Content-Type", "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)
    if not args.all and not args.doc_ids:
        ap.error("choose --all or --doc-ids")
    cands = json.loads(CANDIDATES.read_text(encoding="utf-8"))["candidates"]
    if args.doc_ids:
        cands = [c for c in cands if c["doc_id"] in set(args.doc_ids)]
    run_dir = new_run_dir(args.run_id, prefix="fetch")
    log = []
    for c in cands:
        entry = {"doc_id": c["doc_id"], "url": c["url"]}
        try:
            data, ctype = fetch(c["url"])
            entry.update(content_type=ctype, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            if c["format"] == "pdf":
                if "pdf" not in ctype.lower() or not data.startswith(b"%PDF"):
                    raise ValueError(f"not a PDF ({ctype})")
                if c.get("bytes") and len(data) != c["bytes"]:
                    raise ValueError(f"size {len(data)} != verified {c['bytes']}")
                out = ROOT / "data" / "raw" / f"{c['doc_id']}.pdf"
            else:
                out = ROOT / "data" / "raw_html" / f"{c['doc_id']}.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                raise FileExistsError(f"{out.name} already exists; not overwritten")
            out.write_bytes(data)
            entry["saved"] = str(out.relative_to(ROOT))
            print(f"✅ {c['doc_id']}: {len(data):,} bytes")
        except Exception as err:
            entry["error"] = f"{type(err).__name__}: {err}"
            print(f"❌ {c['doc_id']}: {err}")
        log.append(entry)
    write_json(run_dir / "fetch_log.json", log)
    return 0 if all("error" not in e for e in log) else 1


if __name__ == "__main__":
    sys.exit(main())
