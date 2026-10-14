# Commit ID map (2026-10-14)

Before the first push to GitHub, `data/raw.zip` (287 MB, a local archive of the downloaded reports) was found in the
history: it had been staged by mistake with the pilot labels (old commit `3a9de92`). GitHub rejects files over 100 MB,
and the downloaded reports are intentionally not redistributed. So the file was removed from the 36 unpushed commits with
`git filter-branch --index-filter 'git rm --cached data/raw.zip'`. Nothing else changed: the rewritten history's final tree
is identical to the old one except for that file (`git diff backup-before-rawzip-removal HEAD`).

The rewrite changed every commit ID. Reports and run folders (`runs/*/env.json`, field `git_commit`) cite the **old**
IDs. Use this table to find the corresponding commit on GitHub. The file itself was kept on disk and is now ignored
(`data/*.zip` in `.gitignore`).

| Old ID (cited in docs and runs) | New ID (on GitHub) | Commit |
|---|---|---|
| `91e3ca4` | `91e3ca4` | Stage 1: repair query/eval entry points, add config, tests and run logging |
| `40cf711` | `40cf711` | Add Stage 1 query-path check script (CLI + HTTP API) |
| `cb1ed32` | `cb1ed32` | Stage 1 verification: verified runs, test log and report |
| `15f6d92` | `15f6d92` | Stage 2: page-aware ingestion with provenance, OCR policy, manifest, verification |
| `123b614` | `123b614` | Stage 2b: corpus expansion (19 reports) and curated field maps (B5 option b) |
| `0fb4833` | `0fb4833` | Stage 3: base-paper retrieval (BM25, bge-m3, RRF, multi-field B3), RCA generation, runner, |
| `dbcff59` | `dbcff59` | Stage 3: generation no-cache determinism probe; C5 compares generation content apart from  |
| `6063507` | `6063507` | Stage 3: verified runs, determinism probe, artefact check and verification report |
| `429f43e` | `429f43e` | Benchmark annotation kit: draft causal taxonomy, D1/D2a/D2b/D3 blank sheets (seeded), guid |
| `dcfb18f` | `dcfb18f` | Stage 4: evidence-anchored causal-factor extractor and batch runner |
| `906f080` | `906f080` | Stage 4: factor graph, proposed retriever P + ablations, citation-constrained generation,  |
| `9c60a3b` | `9c60a3b` | Stage 5: label loader, metrics, paired permutation/bootstrap/Holm, guarded evaluator, test |
| `650b84f` | `650b84f` | Stage 5: D3 QA mode (B0/B3/P), answer and extraction evaluators with human-rating export |
| `3d7e7ee` | `3d7e7ee` | Stage 6 audit script; uniform citation-id normalisation across systems and checkers |
| `6b4847b` | `6b4847b` | Stage 4-6 protocol (pre-registration) and IEEE paper skeleton with PENDING placeholders |
| `e127605` | `e127605` | README status and stage commands; manifest: official ESA Ariane 501 copy found (not downlo |
| `570d716` | `570d716` | Stage 4: factor graph build script |
| `fe54a5c` | `fe54a5c` | Stage 4: corpus-wide factor extraction run and factor graph build |
| `a12d9e6` | `a12d9e6` | Official ESA Ariane 501 report replaces MIT mirror (user-approved); P query-code expansion |
| `3de259e` | `3de259e` | Synthetic pseudo-labels (keyword rules + templates, no LLM) for end-to-end proof of concep |
| `e8f6897` | `e8f6897` | End-to-end proof of concept on synthetic pseudo-labels: T1 (17 systems), extraction, D3 QA |
| `a86723a` | `a86723a` | B3-bal: sqrt(field size) weights (owner decision, before human labels) |
| `f7ed804` | `f7ed804` | B3-bal sqrt weighting: PoC re-run r2, audit PASS; reports 09/10 updated |
| `5ff3dd6` | `5ff3dd6` | 10-mission human pilot: blank D2a/D2q sheets + guide, derive script (D2b by guide rule), e |
| `3a9de92` | `6497733` | Pilot labels: owner D2q (10) + owner D2a (5 missions) + assistant D2a (5 missions) with pe |
| `d3d856f` | `963b9b4` | evaluate.py: record pilot label provenance (mixed owner/assistant) instead of a 'human lab |
| `3a57c85` | `90edf27` | 10-mission pilot: runs, evaluation, audits, generation; pilot report 11 and project submis |
| `45ce49a` | `92f3ddc` | Project guide (25-page PDF) with build scripts; all numbers read from run files |
| `e999e42` | `1c713ba` | Second-generation design frozen before running: P2 weighted graph + generic filter, specif |
| `127f720` | `6316717` | Review-driven improvements run: P2 pilot results, bias diagnostic, P2 generation, support  |
| `71487da` | `2debe1e` | Protocol section 10 frozen before running: two-step generation, P2 in QA, retention metric |
| `e5378b3` | `f14f106` | Two-step generation (P2-2step), P2/P2-2step in QA, retention metric, D4 scoring script, te |
| `d01cc9e` | `6e5451f` | Round 3: two-step generation results (retention 56% vs 29%), precedent-transfer caveat, gu |
| `f4d8e3a` | `92d265a` | Protocol section 11 frozen before running: precedent-attributed hypotheses (P2-2step-hyp) |
| `dfd1657` | `ed32693` | P2-2step-hyp: precedent-attributed hypotheses with deterministic relabelling, attribution  |
| `e359d92` | `92c2e7e` | Round 4: precedent-attributed hypotheses run (0 false attributions; model ignored schema,  |
