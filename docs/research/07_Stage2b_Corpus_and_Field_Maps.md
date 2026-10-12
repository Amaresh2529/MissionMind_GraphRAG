# MissionMind — Stage 2b: Corpus Expansion and Curated Field Maps

Date: 2026-10-12. Branch `stage1-repair`. This stage carries out the two decisions taken after the Stage 2 report:

1. **B5 option (b):** assign fields from a curated, human-checked map for each document (page ranges taken from the report's own contents), verified on a fresh held-out sample.
2. **Download the candidate corpus** (`data/corpus_candidates.json`). Approved by the user; X-43A was left out as borderline.

Every number comes from a run directory under `runs/`, named in the tables below.

## 1. Corpus download

| Item | Result | Run |
|---|---|---|
| Documents downloaded | 19 of 19 approved (15 PDFs, 4 HTML press releases); X-43A not fetched | `stage3_fetch_corpus_r2`, `stage3_fetch_corpus_r3_retry` |
| Integrity | Every PDF matched the size recorded when its URL was checked. Manifest SHA-256 = download SHA-256 for 19/19 | same |
| Failures | First attempt crashed on console encoding after saving one file (marked ABORTED). Two DNS failures succeeded on retry | `stage3_fetch_corpus` (ABORTED.txt) |
| Manifest | 26 documents: 23 primary (4 original + 19 new), 2 distractors, 1 excluded (ExoMars journal article, now replaced by the official ESA inquiry report) | `data/manifest.json` |

Downloaded files are git-ignored (`data/raw/`, `data/raw_html/`). Only the manifest (hashes, sizes, URLs) is tracked.

The 23 primary documents cover 22 missions. Two of them (OCO and Glory) both relate to the Taurus XL fairing failures, and the 2019 Taurus summary covers both. By kind:
- full board reports: 12;
- public summaries or executive summaries: 6;
- slide-deck report: 1 (Hitomi);
- press releases: 4.

## 2. Parser changes and full re-parse

| Change | Reason | Evidence |
|---|---|---|
| HTML reader (h1–h4, p and li elements become one "html" page; contact blocks become their own section) | 4 press releases | `src/pipeline/page_parser.py` |
| Boilerplate key strips digits and whitespace; length limit of 160 characters instead of 12 words | CAIB's letter-spaced running header "1 0 R e p o r t V o l u m e I" and ExoMars' 18-word header ended up inside passages | CAIB passages went from 1,181 to 1,123 (457 changed, 58 removed); `tests/test_page_parser.py::test_boiler_key…` |
| Symbol/Wingdings private-use bullets (U+F0B7, F06E, F0A7, F0D8, F0FC, F076, F0A8, F0F9) mapped to "-" | CRS-7, Orb-3, Hitomi and Starliner PDFs | Primary documents: 0 private-use characters left. The 38 left in an ISRO distractor are legacy Hindi-font text |
| Manifest `"ocr_policy": "full"` forces OCR on every page | Glory's text layer clips multi-column pages ("Overvi SUMMA The Glo"), and the quality score misses it | OCR quality on p.1: 0.99 |
| OCR cache writes are atomic; `scripts/ocr_prewarm.py` fills the cache in parallel | About 600 scanned pages (Apollo 13, Apollo 204, Genesis, Starliner/NOAA image pages) | Same per-page function and cache key, so the output is identical |

Re-parse of all 26 documents: `runs/stage3_parse_all` (Starliner again in `stage3_parse_starliner_r2` after the U+F0F9 fix). The interrupted run `stage3_parse_newdocs` is marked ABORTED (superseded).

The Stage 2 outputs of the 7 original documents were snapshotted to `data/processed/_snapshot_stage2_trial4/` before the re-parse. Differences from that snapshot:
- 5 documents are byte-identical;
- CAIB changed through header removal (as intended);
- Challenger: 1 passage removed and 2 changed on p. 241. A 5-digit ZIP code ("35812") is no longer treated as a page number.

**Provenance on all 26 documents: PASS** (`runs/stage3_passage_validation_all`).
- 6,988 passages;
- 0 slice mismatches, 0 uncovered characters, 0 bad characters.

**Stage 1 artefacts unchanged:** 14/14 hashes match.

## 3. Curated field maps (option b)

- **Format.** `data/field_maps/<doc_id>.json` holds ordered page ranges with an optional section-heading regex; the first match wins (`src/pipeline/field_maps.py`).
- **Labels.** Four labels, mirroring the base paper's Summary / Causes / Disposition: description, analysis, recommendations, other.
- **Coverage.** Maps exist for all 23 primary documents.
- **Status.** Every map is a **draft** written by the assistant from each report's contents pages and page outline. 18 ranges are flagged REVIEW.
- **Review sheet.** `data/field_maps/REVIEW.md`.
- **Application.** `scripts/field_map_tool.py apply` writes `data/processed/fields/*.jsonl`.
- **Neo4j.** Passages carry `field` and `field_map_status` (`runs/stage3_passage_ingest_all`):
  - first pass: 3,083 inserted, 3,905 updated, 59 deleted;
  - second pass: 6,988 unchanged.

| Field (primary documents) | Passages |
|---|---|
| analysis | 3,340 |
| description | 926 |
| other | 966 |
| recommendations | 187 |
| *(distractors / excluded document: no field)* | 1,569 |

### Dev check (not reportable)

The maps were checked against the Stage 2 dev sample of 100 sections. That sample had already been inspected, so this result is development evidence, not an accuracy claim (`runs/stage3_field_maps_dev_check`).

| Method (4 labels) | Section accuracy | Word-weighted |
|---|---|---|
| Draft field maps | **0.81** | **0.84** |
| Stage 2 heading rules | 0.59 | 0.77 |

Remaining errors are mostly chronology passages inside analysis chapters (e.g. CAIB ch. 6 imagery-request history). A chapter-level map cannot separate these, so **a ceiling of roughly 0.85 is likely** under content-based labels.

### Held-out test (prepared, not yet run)

| Item | Value |
|---|---|
| Sheet | `evalutation/fixtures/field_test_sheet.csv` (100 passages, empty `label` column) |
| Sampling | Uniform over 5,031 primary passages, seed 20261012. The 388 passages in dev-sample sections were excluded. 14 documents are represented |
| Blank-sheet SHA-256 | `5bdf7a37…bccc71` (`field_test_sheet.meta.json`) |
| Guideline | `evalutation/fixtures/field_labelling_guideline.md` (label by what the passage does) |
| Scoring | `python scripts/field_map_tool.py score --run-id <id>`: maps vs heading rules, section-level and word-weighted, with map hashes recorded |

**Protocol, so the test stays independent:**
1. A human reviews the maps (status → `reviewed`).
2. The maps are committed (frozen).
3. A human labels the sheet. The assistant must not label it, because it drafted the maps.
4. Score once.
5. Do not edit maps after seeing test labels. Any later change needs a new sample.

## 4. Known issues

- Short public summaries (OCO, Glory, DART) have no detected headings and mix causes with recommendations on the same page. Their maps are coarse (REVIEW).
- Press releases (VV17, VV22, GSLV) are single-section pages and are mapped as `analysis` as a whole.
- The 6 public summaries and 4 press releases are much shorter than full board reports. They widen mission coverage but carry little text (143 of 5,419 primary passages, 2.6%).
- Hitomi is a slide deck: one page per slide, many diagram fragments.
- Starliner has 70 image-only pages (OCR'd). Some tables OCR poorly.
