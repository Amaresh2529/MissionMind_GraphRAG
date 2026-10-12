"""B7: every corpus PDF is described in data/manifest.json and matches its checksum."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
REQUIRED = {"doc_id", "file", "title", "agency", "mission", "doc_type", "role", "source_check", "sha256", "bytes", "pages"}


@pytest.mark.parametrize("doc", MANIFEST["documents"], ids=lambda d: d["doc_id"][:30])
def test_entry_complete_and_checksum_matches(doc):
    assert REQUIRED <= doc.keys()
    assert doc["role"] in {"primary", "distractor", "exclude_replace"}
    path = ROOT / doc["file"]
    if not path.exists():
        pytest.skip("corpus PDFs are not in git; checksum verified only where the file is present")
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_manifest import file_facts
    assert file_facts(path) == {k: doc[k] for k in ("sha256", "bytes", "pages")}


def test_every_raw_pdf_is_in_manifest():
    files = {d["file"] for d in MANIFEST["documents"]}
    for pdf in (ROOT / "data" / "raw").glob("*.pdf"):
        assert pdf.relative_to(ROOT).as_posix() in files


def test_primary_documents_have_mission_ids():
    for d in MANIFEST["documents"]:
        assert isinstance(d["mission_ids"], list)
        if d["role"] == "primary":
            assert d["mission_ids"], d["doc_id"]
