# MissionMind — Stage 2: Ingestion and Provenance

Started 2026-10-12 after approval of Stage 1. Branch: `stage1-repair` (continued).

## Objective

Every unit of evidence the system can retrieve or cite must carry its source document, page number and exact character offsets, and the text must be cleaned without destroying information. Stale data must not survive re-ingestion. Corpus expansion is prepared (search + verification of official sources), but files are downloaded only with explicit permission.

The Stage 1 chunk pipeline (250-word windows, baseline B4) is **kept unchanged** so its results stay reproducible. Stage 2 adds a parallel, page-aware passage pipeline.

## Findings that shaped the design (probe of the 7 PDFs on disk)

| Document | Finding | Consequence |
|---|---|---|
| ExoMars (journal article) | 209 `ﬁ` and 16 `ﬂ` ligature characters; the Stage 1 cleaner deletes them ("Pro les", "ew") | NFKC normalisation before any filtering |
| Columbia CAIB Vol. I | 2,397 soft hyphens (words split at line breaks, e.g. "conduct ed") and 1,192 `ʼ` apostrophes (become "Earth s") | Join soft-hyphenated words; map typographic apostrophes/quotes/dashes to ASCII |
| ISRO annual reports | Many `É Ê ú ò ¦` characters — likely Hindi text in a legacy (non-Unicode) font | Not repairable by normalisation; documents are distractors only; recorded |
| Challenger (Rogers Vol. 1) | Scanned; text layer is OCR of unknown quality; 22 near-empty pages | Measure OCR quality; per-page re-OCR comparison |
| All except ExoMars | No usable embedded table of contents | Headings from font size, weight and numbering patterns |

## Acceptance criteria

| ID | Criterion |
|---|---|
| B1 | Every passage has `doc_id`, 1-based `page`, `char_start`, `char_end`, and its text equals the page text slice exactly (100%) |
| B2 | Passages never cross a page or section boundary; passages of a page cover all its non-whitespace text |
| B3 | Normalised text contains no ligature or soft-hyphen characters; apostrophes and words are preserved (unit tests) |
| B4 | Per-page quality metrics for all documents; Challenger text layer compared with fresh Tesseract OCR on ≥ 20 pages; character error rate estimated on ≥ 5 transcribed excerpts; low-quality pages flagged |
| B5 | Pseudo-field assignment accuracy measured on 100 sampled sections (target ≥ 90%) |
| B6 | Re-ingestion updates changed passages, deletes removed ones and skips unchanged ones (integration test); same for the Stage 1 chunk loader |
| B7 | Corpus manifest with SHA-256, page count, size, agency, mission and document role for every PDF; verified by test |
| B8 | Candidate list of public investigation reports with verified official URLs, aiming at ≥ 20 missions, or a documented shortfall; nothing downloaded without permission |
| B9 | Stage 1 chunk files and their outputs unchanged (hash check) |

## Verification report

Run date: 2026-10-12. Branch `stage1-repair`. Every number below comes from a run directory under `runs/` (named in the right-hand column). Gold labels and OCR references were written by the assistant, not by an independent annotator. That is a known limitation (see below).

### Outcome per criterion

| ID | Result | Evidence | Run |
|---|---|---|---|
| B1 | **PASS** | 3,964 passages over 7 documents; 0 slice mismatches, 0 duplicate IDs, 0 invalid pages | `stage2_passage_validation_trial4` |
| B2 | **PASS** | Passages are built per page and per section by construction. The union of passages covers 2,299,198 non-whitespace characters of non-boilerplate text, with 0 uncovered | `stage2_passage_validation_trial4` |
| B3 | **PASS** | 0 ligature, soft-hyphen or modifier-apostrophe characters left in real output; unit tests in `tests/test_normalize.py` and `tests/test_page_parser.py` | same, plus `stage2_verified_tests` |
| B4 | **PASS** (with a deviation) | Per-page metrics for all 7 documents. On 20 Challenger pages, fresh Tesseract output was compared with the text layer. Character error rate on 5 transcribed excerpts: text layer **0.1438**, Tesseract 5.5.3 at 300 dpi **0.0333**. As a result, Challenger is OCR'd on 252 of 261 pages | `stage2_ocr_quality_sample`, `stage2_ocr_quality_cer`, `stage2_parse_trial4` |
| B5 | **FAIL** | Target ≥ 0.90. Measured on 100 sections: rules **0.52** (word-weighted 0.66). See the B5 section below | `stage2_pseudo_field_accuracy_trial4`, `stage2_field_methods_dev`, `stage2_field_4way_dev` |
| B6 | **PASS** | Integration tests for the passage and chunk loaders. Real data: first ingest inserted 3,964 passages (45.9 s); second ingest left 3,964 unchanged with 0 inserts, updates or deletes (6.8 s) | `stage2_passage_ingest_trial4`, `stage2_verified_tests` |
| B7 | **PASS** | `data/manifest.json` records SHA-256, size, pages, role and source check for all 7 PDFs. `tests/test_manifest.py` re-hashes the files | `stage2_verified_tests` |
| B8 | **MET, with caveats** | `data/corpus_candidates.json` lists 20 candidate documents covering 19 new missions (22 with the 4 existing primary missions). All URLs were HEAD-checked; about 135 MB of PDFs plus 4 HTML pages. **Nothing has been downloaded.** Several candidates are summaries or press releases rather than full board reports | — |
| B9 | **PASS** | Stage 1 chunk files and outputs are byte-identical to the pre-Stage-2 hashes | `stage2_baseline/b9_check.json` |

Test suite: **82 passed** (`runs/stage2_verified_tests/pytest_tail.txt`).

### B5: pseudo-field assignment (failed)

The 100-section sample was used to inspect the errors of the rules. It is therefore **DEV data from now on**. Any reportable accuracy must come from a fresh, independently drawn sample.

| Method | 6 labels | 6 labels, word-weighted | 4 labels | 4 labels, word-weighted |
|---|---|---|---|---|
| Heading rules (v4) | 0.52 | 0.66 | 0.59 | **0.77** |
| LLM (llama3, every section) | 0.58 | 0.44 | 0.62 | 0.47 |
| Hybrid (rules for front/back matter, LLM otherwise) | 0.60 | 0.44 | 0.64 | 0.47 |

The 4 labels are description (summary + narrative), analysis (findings + causes), recommendations, and other. They approximate the base paper's Summary / Causes / Disposition fields.

**Causes of the failure:**
1. Findings and narrative are confused in both directions. Investigation boards mix chronology and analysis in the same section, so this confusion is partly inherent.
2. Structural parsing errors:
   - a sidebar heading on a Challenger page ("UMBILICAL CAMERAS…") absorbs about 5,900 words;
   - a section is attributed to the wrong chapter (e.g. "3.1 THE PHYSICAL CAUSE" placed under "ENDNOTES FOR CHAPTER 2").
3. Sampling distinct sections over-weights fragments: 20 of the 100 sections are under 40 words. This is why the section-level and word-weighted figures disagree.
4. The LLM is better on short fragments but worse on long body sections, which dominate by word count.

**Decision needed before Stage 3** (not taken unilaterally):
- (a) accept the rules with the 4-label scheme as a documented limitation;
- (b) curated chapter→field maps for each primary document (human-in-the-loop), verified on a fresh held-out sample. Recommended;
- (c) drop fields, so that B3 becomes a single-field hybrid retriever.

### Deviations from the plan

| Deviation | Reason |
|---|---|
| Scanned documents are OCR'd on every page. Per page, the OCR text is kept if its quality is ≥ the text layer's quality − 0.05 | Challenger's text layer has a 4× higher character error rate than fresh OCR |
| OCR output is cached per page, keyed by PDF hash, dpi and Tesseract version | Full OCR of Challenger takes minutes; the cache keeps reruns identical |
| Line-end hyphens are joined using a word-frequency rule (wordfreq Zipf) | Typeset hyphenation ("includ-ed") was not covered by the soft-hyphen rule |
| Body text under an unmatched heading defaults to "findings" (not "other") | Unmatched headings in board reports are mostly analysis |
| LLM field labels are cached by prompt hash | LLM outputs differed across sessions (Stage 1 finding: 5/96 records) |
| The Stage 1 chunk pipeline is unchanged; passages run as a parallel pipeline | Keeps baseline B4 reproducible (B9) |

### Limitations and lessons

- The gold labels for pseudo-fields and the 5 OCR reference excerpts were written by the assistant. They have not yet been checked by a human annotator.
- The two ISRO reports contain legacy-font Hindi text that normalisation cannot repair. They are used only as distractors.
- CAIB's source URL could not be matched by size (`source_check: unverified`).
- `parse_trial3` was stopped and marked ABORTED. It was rerun as `trial4`; nothing was overwritten.
- Process lesson: in one case a stale `parse_report.json` was read before checking the exit code. The exit code is now always checked first.
