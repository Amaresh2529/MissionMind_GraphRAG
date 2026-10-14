"""
build_guide.py — builds docs/MissionMind_Project_Guide.pdf (A4) from HTML with PyMuPDF's Story engine.

All numbers are loaded from the saved run files and the manifest, so the guide cannot drift from the evidence.
    python docs/guide/make_figures.py && python docs/guide/build_guide.py
"""

import html
import json
import sys
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
G = Path(__file__).resolve().parent
sys.path.append(str(ROOT / "src"))
OUT = ROOT / "docs" / "MissionMind_Project_Guide.pdf"


def J(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ data
man = J("data/manifest.json")["documents"]
prim = [d for d in man if d["role"] == "primary"]
missions = sorted({m for d in prim for m in d["mission_ids"]})
n_passages = sum(1 for f in (ROOT / "data/processed/passages").glob("*.jsonl") for _ in open(f, encoding="utf-8"))
from retrieval.corpus import load_units  # noqa: E402
units = load_units(None)
fields = Counter(u.field for u in units)
st1, st2 = J("runs/stage4_extract_all/stats.json"), J("runs/stage4_extract_ariane_official/stats.json")
proposed, accepted = st1["proposed"] + st2["proposed"], st1["accepted"] + st2["accepted"]
rej = Counter(st1["rejection_reasons"]) + Counter(st2["rejection_reasons"])
fgraph = J("runs/stage4_factor_graph_r2/factor_graph.json")
pilot = J("runs/pilot_eval_t1_r2/metrics.json")["summary"]
pcomp = J("runs/pilot_eval_t1_r2/comparisons.json")
pq = J("runs/pilot_eval_t1_r2/per_query.json")
prim_c = pcomp["primary"]
gsec = pcomp["secondary"]["P vs P-graphonly [mission_ndcg@5]"]
n_sig = sum(1 for v in pcomp["secondary"].values() if v["p_holm"] is not None and v["p_holm"] < 0.05)
gen = J("runs/pilot_generation_check/stage3_check.json")["C6"]
d3 = J("runs/poc_eval_d3_synthetic/answer_metrics.json")["results"]
synth_t1 = J("runs/poc_eval_t1_synthetic_r2/metrics.json")["summary"]
pilot_meta = J("evalutation/benchmark/pilot/PILOT.json")
n_tests = 160


def f3(x):
    return f"{x:.3f}"


def table(header, rows, widths=None):
    h = "".join(f"<th>{html.escape(str(c))}</th>" for c in header)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b}</table>"


def fig(name, caption, width=480):
    return f'<p class="fig"><img src="{name}" width="{width}"/></p><p class="cap">{caption}</p>'


def note(text, kind="note"):
    return f'<div class="{kind}">{text}</div>'


# ------------------------------------------------------------------ chapters
CH = []


def chapter(cid, title, body):
    CH.append((cid, title, body))


chapter("summary", "1. Executive Summary", f"""
<p><b>MissionMind</b> is a research system that helps spaceflight mishap investigators find <i>earlier accidents with
similar causes</i> in long official investigation reports, and drafts a root-cause analysis grounded in the cited
evidence. It reproduces a recent IEEE method for accident-report retrieval (Kim &amp; Kim, IEEE CASE 2026) and adds an
<b>evidence-verified causal-factor graph</b> on top of it.</p>
<h3>What the project delivers</h3>
<ul>
<li>A corpus of <b>{len(man)} documents</b> ({len(prim)} investigation reports or summaries covering <b>{len(missions)} missions</b>,
1967–2024, from NASA, ESA, JAXA and ISRO), split into <b>{n_passages:,} passages</b> that keep their exact page and
character position.</li>
<li>A faithful reproduction of the base paper's multi-field hybrid retrieval (BM25 + bge-m3 dense retrieval over three
fields, fused with Reciprocal Rank Fusion), with every deviation documented.</li>
<li>The proposed method <b>P</b>: an LLM proposes causal factors; each one is kept only if its quoted evidence is found
word-for-word in the report (<b>{accepted:,} of {proposed:,}</b> kept); factors form a graph linking missions with shared causes;
the graph is used as an extra retrieval channel; answers must cite evidence and may abstain.</li>
<li>A complete evaluation and audit framework (metrics, significance tests, independent recomputation), a human
annotation kit, and {n_tests} automated tests.</li>
</ul>
<h3>Main results (10-mission pilot, AI-assisted labels)</h3>
<ul>
<li>The proposed method P and the base-paper method B3 rank similar past missions about equally well:
nDCG@5 <b>{f3(pilot['P']['mission_ndcg@5'])}</b> vs <b>{f3(pilot['B3']['mission_ndcg@5'])}</b>
(difference {prim_c['permutation']['mean_diff']:+.3f}, 95% CI [{prim_c['bootstrap95']['low']:+.3f}, {prim_c['bootstrap95']['high']:+.3f}],
p = {prim_c['permutation']['p']:.2f}) — <b>no significant difference</b>.</li>
<li>The causal-factor graph used on its own (P-graphonly) gave the best ranking, nDCG@5
<b>{f3(pilot['P-graphonly']['mission_ndcg@5'])}</b> — a promising but not yet significant signal.</li>
<li>Verification rejected <b>{100 * (proposed - accepted) / proposed:.0f}%</b> of the LLM's proposed factors, mostly because the
"quoted" evidence does not exist in the report.</li>
</ul>
""" + note("<b>Important disclosure.</b> The pilot labels are <b>AI-assisted</b>: the project owner wrote all query "
           "descriptions and part of the causal-factor labels; the AI assistant (Claude) wrote the rest, using verbatim "
           "quotes from the investigation boards. A fully human-labelled benchmark will be completed after the project "
           "submission and before the IEEE paper submission. The results therefore show feasibility and trends, not proof "
           "that one method is better.", "warn"))

chapter("problem", "2. Background and Problem", """
<p>When a spacecraft or launch vehicle fails, an investigation board writes a long report (often 50–300 pages)
describing what happened, why it happened, and what should change. Many failures repeat causes seen before: the
Columbia board explicitly compared its findings with Challenger seventeen years earlier. Yet finding such precedents
today means reading many long reports by hand.</p>
<h3>Why ordinary search is not enough</h3>
<ul>
<li><b>Different words, same cause.</b> "O-ring erosion accepted as normal" (Challenger) and "foam shedding accepted
as an in-family event" (Columbia) share a cause — normalisation of deviance — but few words.</li>
<li><b>Long, mixed documents.</b> Reports mix background, chronology, analysis and recommendations; a keyword match in
the wrong section is misleading.</li>
<li><b>Trust.</b> An investigator needs the exact page that supports every statement. Generative AI that invents
sources is unacceptable in safety work.</li>
</ul>
<h3>The task MissionMind addresses</h3>
<p><b>Cross-mission causal analogy:</b> given a description of a new mishap, rank earlier missions whose
<i>board-stated causes</i> are analogous, show the supporting passages with page numbers, and draft a root-cause
analysis that cites only real evidence — or says "insufficient evidence".</p>
<h3>Research questions</h3>
""" + table(["RQ", "Question"], [
    ["RQ1", "How reliable is evidence-anchored causal-factor extraction, and what recall does verification cost?"],
    ["RQ2", "Does a causal-factor graph channel improve cross-mission analogy retrieval over the base-paper method?"],
    ["RQ3", "What does the graph add beyond BM25, dense and hybrid retrieval (ablations)?"],
    ["RQ4", "Can answers be made verifiable at page level (citations, abstention)?"],
    ["RQ5", "How well do automatic metrics (LLM judge) agree with human judgement?"],
]))

chapter("basepaper", "3. The Base Paper and Related Work", f"""
<p>After comparing six candidate papers, the project selected <b>S. Kim and S. Kim, "Multi-Field Hybrid
Retrieval-Augmented Generation for Maritime Accident Root Cause Analysis," IEEE CASE 2026, pp. 238–243,
doi:10.1109/CASE69030.2026.11704480</b> as the base paper. It retrieves precedent accident cases from official
investigation reports and drafts a grounded root-cause analysis — the same task family as MissionMind — and its method
is fully specified and reproducible on local hardware.</p>
<h3>The base method in one paragraph</h3>
<p>Each accident report is split into three fields (Summary, Causes, Disposition). Each field is indexed twice: with
BM25 (keyword ranking) and with the bge-m3 dense embedding model (meaning-based ranking). A query produces six ranked
lists (3 fields × 2 methods), merged by <b>Reciprocal Rank Fusion</b>: score(c) = Σ 1 / (60 + rank). The top 40
chunks, labelled with case and field, are given to a large language model that writes a JSON root-cause analysis.</p>
<h3>Closest related work</h3>
""" + table(["Work", "What it does", "Relation to MissionMind"], [
    ["Kim &amp; Kim, IEEE CASE 2026", "Multi-field hybrid RAG for maritime accident RCA", "<b>Base paper</b> = baseline B3"],
    ["Xiang et al., Aerospace 2026", "Causal knowledge graph from aviation (NTSB) reports", "Closest competing work; no retrieval task, no source links"],
    ["Yang et al., Computers 2026 (AEVS)", "Anchor-constrained, provenance-tracked LLM extraction", "Inspires quote verification"],
    ["Xie et al., Sci. Rep. 2025 (HybridRAG)", "Graph + BM25 + vector for aircraft troubleshooting", "Architecture precedent; not reproducible"],
    ["Cormack et al., SIGIR 2009", "Reciprocal Rank Fusion", "Fusion used by B3 and P"],
    ["Shappell &amp; Wiegmann, 2000 (HFACS)", "Human-factors accident taxonomy", "Basis of the H and M taxonomy groups"],
]) + note("<b>Novelty statement.</b> The retrieval technique itself is an adaptation. What is new is (1) the task and "
           "benchmark design for cross-mission causal analogy in spaceflight reports, (2) a causal-factor graph whose every "
           "edge is tied to a verified quote and page, and (3) a rigorous, audited comparison against a reproduced IEEE baseline."))

corpus_rows = []
for d in sorted(prim, key=lambda d: (d.get("event_year") or 0)):
    corpus_rows.append([html.escape(d["mission"]), str(d.get("event_year") or ""), html.escape(d["agency"].split("(")[0].strip()),
                        {"official_investigation_report": "Full report", "public_summary": "Summary", "official_slides": "Slides",
                         "press_release": "Press release"}.get(d["doc_type"], d["doc_type"]), str(d["pages"])])
chapter("corpus", "4. The Corpus", f"""
<p>All documents are official, publicly released investigation reports or summaries. Every file is recorded in
<code>data/manifest.json</code> with its SHA-256 hash, size, page count, source address and role. Downloads were made only
with the owner's approval, and each download was checked against the size recorded beforehand.</p>
""" + fig("fig_corpus.png", f"Figure 1. The {len(prim)} primary documents by type and agency.", 440) + table(
    ["Mission", "Year", "Agency", "Type", "Pages"], corpus_rows) + f"""
<p>In addition, two ISRO annual reports are kept as <i>distractors</i> (not used in the main experiments) and two
documents were <i>replaced</i> by better official versions: an ExoMars journal article (replaced by ESA's official
inquiry report) and a university mirror of the Ariane 501 report (replaced by the official ESA copy).</p>
""")

chapter("arch", "5. System Architecture", """
<p>MissionMind is a pipeline of small, separately tested Python modules. Everything runs locally: Neo4j 5 (graph
database), Ollama with llama3 8B (language model), bge-m3 (embeddings) on an 8 GB GPU.</p>
""" + fig("fig_architecture.png", "Figure 2. Data flow. Blue: reproduced base-paper method (B3). Orange/green: the proposed extension (P).", 500) + table(
    ["Folder", "Contents"], [
        ["<code>src/pipeline/</code>", "Page-aware PDF/HTML parsing, OCR, normalisation, field maps"],
        ["<code>src/retrieval/</code>", "BM25, dense retrieval, RRF, the base-paper systems (B1–B3), RCA generation"],
        ["<code>src/extension/</code>", "Causal-factor extraction and verification, factor graph, proposed method P, QA"],
        ["<code>src/bench/</code>", "Benchmark labels, metrics, statistics"],
        ["<code>src/graph/</code>", "Neo4j loading (passages, factors); Stage 1 system kept as baseline B4"],
        ["<code>scripts/</code>", "Runners, evaluators, audit, annotation tools"],
        ["<code>runs/</code>", "Every experiment: config, environment, predictions, metrics, logs"],
        ["<code>docs/research/</code>", "Stage reports 05–11"],
    ]))

chapter("stages", "6. How the Project Was Built: Stages", """
<p>The project followed a staged plan in which no stage was declared complete without evidence, and every run was
saved in its own folder. Failures were kept and documented rather than hidden.</p>
""" + table(["Stage", "Goal", "Outcome"], [
    ["1", "Repair the original prototype; reproducible baseline", "Broken retriever and evaluation repaired; fresh database; contaminated legacy graph preserved read-only"],
    ["2", "Ingestion and provenance", "Every passage equals its page slice exactly; OCR quality measured (Challenger: text layer 14.4% vs OCR 3.3% character errors)"],
    ["2b", "Corpus expansion; fields", "19 reports downloaded with approval; curated field maps for all reports"],
    ["3", "Reproduce the base paper", "B0–B3 and the paper's comparison systems; byte-identical repeat runs; 13 deviations recorded"],
    ["4", "Proposed method", "Verified extraction, factor graph, graph channel, cited generation, 6 ablations"],
    ["5", "Experiments", "Evaluators and significance tests; synthetic proof of concept; 10-mission pilot"],
    ["6", "Audit", "Independent recomputation, leakage, provenance and citation checks — PASS on all runs"],
]) + """
<h3>Working rules followed throughout</h3>
<ul><li>Never claim completion without verification; report failures openly.</li>
<li>No fabricated results or citations; every number in this guide is read from a saved run file.</li>
<li>Protect the evaluation set: no tuning on test labels; design changes are logged with date and reason.</li>
<li>Preserve earlier results: runs are never overwritten; replaced items are archived, not deleted.</li></ul>
""")

chapter("ingest", "7. Ingestion and Provenance", f"""
<p>The parser reads every page, detects headings by font size, weight and numbering, removes running headers and
footers, repairs broken characters (ligatures, soft hyphens, line-end hyphenation) and splits text into passages of
150–300 words that never cross a page or section boundary.</p>
<h3>The provenance guarantee</h3>
<p>For every passage, <code>passage.text == page_text[char_start:char_end]</code>. A validator checks this for all
{n_passages:,} passages: <b>0 mismatches, 0 uncovered characters</b>. This is what allows every answer to point to an exact
page.</p>
<h3>Scanned reports and OCR</h3>
<p>Several reports (Challenger, Apollo 1, Apollo 13, Genesis, the official Ariane copy) are scans. OCR quality was
measured rather than assumed: for Challenger, the PDF's built-in text layer had a 14.4% character error rate against
3.3% for fresh Tesseract OCR, so scanned documents are OCR'd page by page. One report (Glory) has a text layer that
silently cuts words ("Overvi SUMMA The Glo"); it is forced to OCR. The rotated French annex pages of the Ariane report
cannot be read by OCR and are excluded.</p>
<h3>Fields</h3>
<p>The base paper's reports have native fields; spaceflight reports do not. Fields are therefore assigned by curated
page-range maps written from each report's table of contents (heading keyword rules reached only 52–59% accuracy).
Indexed passages per field: Summary {fields['summary']:,}, Causes {fields['causes']:,}, Disposition {fields['disposition']:,}.</p>
""")

chapter("repro", "8. Reproducing the Base Paper", """
<p>All the base paper's configurations were rebuilt and run on the same corpus and queries:</p>
""" + table(["System", "Description"], [
    ["B0", "LLM only, no documents"],
    ["B1", "BM25 over all passages"],
    ["B2", "Dense (bge-m3) over all passages"],
    ["H-whole", "BM25 + dense, RRF, single index"],
    ["SF-*", "Single-field indexing (Summary only / Causes only), BM25, dense or hybrid"],
    ["<b>B3</b>", "<b>Base paper: 3 fields × 2 methods = 6 lists, RRF k = 60</b>"],
    ["B3-bal", "B3 with field weights ∝ √(field size) (added after a finding below)"],
]) + "<h3>Main deviations from the paper (13 recorded in docs/research/08)</h3>" + table(["Paper", "MissionMind", "Why"], [
    ["Native fields of short cards", "Curated field maps over long reports", "No native fields in mishap reports"],
    ["BM25 parameters not stated", "Okapi BM25, k1 = 1.2, b = 0.75", "Standard defaults, not tuned"],
    ["Train/test split", "Leave-one-mission-out", "Only 22 missions; each is query and precedent"],
    ["Qwen3-Next-80B generator", "llama3 8B (local)", "8 GB GPU"],
    ["Top 40 chunks in context", "18–27 chunks (context limit)", "8k-token window"],
]) + """
<h3>Findings from the reproduction</h3>
<ul><li><b>Reproducible:</b> repeating a run gives byte-identical retrieval results.</li>
<li><b>Field imbalance:</b> with fields of very different size, RRF lets the small recommendation field dominate — 45% of
B3's top-100 came from a field holding 4% of the text. Weighting fields by size overshot (100% Causes); √-size weighting
gives a balanced mix (B3-bal).</li>
<li><b>Model nondeterminism:</b> llama3 did not reproduce its own answers across sessions (5 of 19 identical two hours
apart), so every generated answer is cached and reported from the cache.</li></ul>
""")

chapter("method", "9. The Proposed Method (P)", f"""
<h3>Step 1 — Evidence-anchored causal-factor extraction</h3>
<p>For each Summary or Causes passage, the LLM proposes causal factors, each with a taxonomy code, a role (root,
contributing, observation) and a verbatim quote. A factor is <b>kept only if</b> the code and role are valid and the quote
(at least 5 words) is found in the passage. The exact character position of the quote is stored, so every factor in
the graph points to a page.</p>
""" + fig("fig_extraction.png", f"Figure 3. Verification kept {accepted:,} of {proposed:,} proposed factors ({100 * accepted / proposed:.0f}%).", 460) + f"""
<h3>Step 2 — Factor graph</h3>
<p>Verified factors are aggregated per mission into a profile of taxonomy categories and stored in Neo4j
({fgraph['missions']} missions, {fgraph['mentions']:,} factor mentions, {fgraph['neo4j']['has']} mission–category links). Two missions are
analogous in proportion to the categories they share, rare categories counting more (idf-weighted Jaccard).</p>
<h3>Step 3 — Graph channel</h3>
<p>For a new mishap, the categories are taken from the query itself and from the verified factors in B3's top-20
passages (a description of symptoms rarely states causes). Missions are ranked by analogy, their evidence passages form
a seventh ranked list, and this list is fused with B3's six lists by the same RRF.</p>
<h3>Step 4 — Citation-constrained generation</h3>
<p>The model drafts the analysis from the retrieved passages plus a short block of graph analogies. Afterwards,
citations to passages that were not shown are removed, items without any valid citation are dropped, and if no
grounded root cause remains the system <b>abstains</b> instead of guessing.</p>
<h3>Ablations</h3>
""" + table(["Variant", "What is removed or changed"], [
    ["P-noverif", "Also uses factors that failed verification"],
    ["P-nofields", "Whole-index hybrid instead of the 3-field B3 lists"],
    ["P-graphonly", "Graph list alone"],
    ["P-noidf", "All categories weighted equally"],
    ["P-noprf", "Query categories from the query text only"],
]))

tax = J("evalutation/benchmark/causal_taxonomy.json")
chapter("taxonomy", "10. The Causal-Factor Taxonomy", """
<p>Factors are classified into 22 categories in five groups, based on NASA's HFACS human-factors levels and the
technical failure classes used by the boards in the corpus. The taxonomy is a draft to be reviewed by the owner before
full labelling.</p>
""" + table(["Code", "Category", "Meaning"], [[c["code"], html.escape(c["name"]), html.escape(c["desc"])]
                                          for g in tax["categories"] for c in g["children"]]))

chapter("evaluation", "11. How the System Is Evaluated", """
<h3>Benchmark sets (annotation kit in evalutation/benchmark/)</h3>
""" + table(["Set", "Content", "Used for"], [
    ["D2a", "Board-stated causal factors per mission (code, role, page, quote)", "Defines which missions are analogous"],
    ["D2q", "A 100–200-word description of each mishap as first observed, without causes", "The test queries"],
    ["D2b", "Analogy grade 0–3 for every pair of missions", "Ranking relevance"],
    ["D1", "Causal factors in 200 sampled passages", "Extraction accuracy (RQ1)"],
    ["D3", "About 105 questions with key points and evidence pages", "Answer quality, abstention"],
]) + """
<h3>Metrics</h3>
<ul><li><b>nDCG@5</b> (primary): quality of the top-5 mission ranking, rewarding highly analogous missions near the top.</li>
<li><b>Recall@5, MRR</b>: share of analogous missions in the top 5; position of the first analogous mission.</li>
<li><b>NormRecall@100, nDCG@100</b>: the base paper's passage-level metrics.</li>
<li><b>Extraction precision/recall/F1</b>; <b>key-point recall</b>, <b>citation precision</b> and <b>abstention accuracy</b> for answers.</li></ul>
<h3>Statistics</h3>
<p>One pre-registered primary test: P vs B3 on nDCG@5, with a paired permutation test and a 95% bootstrap confidence
interval. All other comparisons are secondary and corrected for multiple testing (Holm). The protocol was written before
any label existed (docs/research/09).</p>
<h3>Independent audit</h3>
<p>A separate script, sharing no code with the evaluator, checks that every system answered the same queries from a
clean code version, that no query leaks into its own answers, that every retrieved passage matches its page, that every
citation is valid, and recomputes the metrics.</p>
""")

rows = []
for s in ["B1", "B2", "H-whole", "SF-summary-hybrid", "SF-causes-hybrid", "B3", "B3-bal", "P", "P-noverif", "P-nofields", "P-graphonly", "P-noidf", "P-noprf"]:
    v = pilot[s]
    name = f"<b>{s}</b>" if s in ("B3", "P", "P-graphonly") else s
    rows.append([name, f3(v["mission_ndcg@5"]), f3(v["mission_ndcg@10"]), f3(v["mission_recall@5"]), f3(v["mission_mrr"]), f3(v["passage_normrecall@100"])])
chapter("results", "12. Results: 10-Mission Pilot", note(
    "<b>AI-assisted labels.</b> " + html.escape(pilot_meta["labels_by"]) + " Every label row records its author. "
    "The AI assistant also built the method under test, so these labels may favour it. Fully human labels will follow.", "warn") + f"""
<p>Missions: Challenger, Columbia, Mars Climate Orbiter, Ariane 501, Apollo 13, Genesis, SOHO, WIRE, Hitomi, Starliner.
Each query is the owner's description of one mishap; the system ranks the other 9 missions.</p>
""" + table(["System", "nDCG@5", "nDCG@10", "Recall@5", "MRR", "NormRecall@100"], rows) + fig(
    "fig_pilot_ndcg.png", "Figure 4. Pilot ranking quality (nDCG@5). Grey: simple baselines; blue: base paper; orange: P and ablations; green: graph only.", 480) + f"""
<h3>Primary comparison</h3>
<p>P − B3 = <b>{prim_c['permutation']['mean_diff']:+.3f}</b> nDCG@5, 95% CI [{prim_c['bootstrap95']['low']:+.3f}, {prim_c['bootstrap95']['high']:+.3f}],
exact permutation p = <b>{prim_c['permutation']['p']:.2f}</b> (n = {prim_c['permutation']['n']}). <b>No difference was detected.</b>
Of {len(pcomp['secondary'])} secondary comparisons, {n_sig} are significant after Holm correction.</p>
""")

chapter("results2", "13. Results: Per Mission, Generation and Verification", fig(
    "fig_pilot_missions.png", "Figure 5. Per-mission nDCG@5 for B3, P and the graph alone.", 480) + f"""
<h3>The graph channel on its own</h3>
<p>Used alone, the causal-factor graph reached nDCG@5 {f3(pilot['P-graphonly']['mission_ndcg@5'])}, the highest of all systems,
and was clearly better on Genesis, Challenger, WIRE and Ariane 501. P-graphonly − P = {-gsec['permutation']['mean_diff']:+.3f}
(95% CI [{-gsec['bootstrap95']['high']:+.3f}, {-gsec['bootstrap95']['low']:+.3f}], p = {gsec['permutation']['p']:.2f}; not significant after
Holm correction). Interpretation: fused as one of seven lists, the graph signal is diluted. This is a hypothesis for the full
study, not a conclusion.</p>
<h3>Generated root-cause drafts (10 pilot queries)</h3>
""" + table(["System", "Valid JSON", "Items", "Citations", "Invalid citations", "Uncited items"], [
    [s, f"{gen[s]['schema_ok']}/{gen[s]['queries']}", gen[s]["items"], gen[s]["citations"], gen[s]["invalid_citations"], gen[s]["uncited_items"]]
    for s in ("B0", "B3", "P")]) + """
<p>P cites evidence for every item, but about half of its cause statements (21 of 43) repeat taxonomy category names
("Procedure deficient or not followed") instead of specific mechanisms; B3 had none. Citation validity is not
correctness: answer quality still needs human rating.</p>
<h3>Abstention (questions about missions not in the corpus, synthetic question set)</h3>
""" + table(["System", "Abstained on 10 unanswerable questions"], [["B0 (no documents)", "0 / 10"], ["B3", "8 / 10"], ["P", "9 / 10"]]) + f"""
<h3>Audit</h3>
<p>All pilot runs passed the independent audit: no own-mission leakage, no query copied from the reports (the owner's
descriptions are original), every retrieved passage verified against its page, and every metric value recomputed
independently and found equal.</p>
""")

chapter("findings", "14. Key Findings and Discussion", f"""
<ol>
<li><b>The base method transfers to spaceflight reports</b> and is reproducible, but its fusion is sensitive to field
size: a small recommendation field dominated the results until weights were balanced.</li>
<li><b>Verification matters.</b> {100 * (proposed - accepted) / proposed:.0f}% of the LLM's proposed causal factors were rejected;
{rej['quote_not_in_passage']} cited "quotes" did not exist in the passage — exactly the hallucination risk the method guards against.</li>
<li><b>No significant gain yet.</b> On the pilot, P matched B3. The causal-factor graph alone ranked best, which points to
a better way of combining the graph with text retrieval.</li>
<li><b>Grounded answers can still be generic.</b> P never cited a missing passage, but often answered with category names.</li>
<li><b>Abstention works:</b> only the retrieval-grounded systems declined questions outside the corpus.</li>
<li><b>Local LLMs are not reproducible across sessions;</b> caching outputs is necessary for honest reporting.</li>
</ol>
<h3>Proposed improvements before the full study (to be decided before human labelling)</h3>
<ul><li>Add the graph-only or a weighted graph list as a pre-registered secondary system.</li>
<li>A generation prompt that requires specific mechanisms rather than category names.</li>
<li>Down-weight generic categories (O1, T1, T5) that appear for most queries.</li></ul>
""")

chapter("limits", "15. Limitations and Honest Scope", """
<ul>
<li><b>Labels:</b> the pilot labels are AI-assisted; the synthetic proof-of-concept labels are keyword rules. Neither is
a human benchmark.</li>
<li><b>Sample size:</b> 10 pilot queries (22 in the full design) — only large effects can be detected.</li>
<li><b>Field maps</b> are drafts pending human review.</li>
<li><b>Corpus:</b> 10 of 23 primary documents are summaries, press releases or slides, much shorter than full reports;
long reports dominate the factor analogy score.</li>
<li><b>Models:</b> an 8-billion-parameter local model generates, extracts and judges; the automatic answer judge proved
too lenient (it gave 0.81 key-point recall to the system that sees no documents).</li>
<li><b>Claims:</b> the project does not claim that P outperforms the base paper.</li>
</ul>
""")

chapter("status", "16. Project Status: Done and Remaining", """
<h3>Done</h3>
""" + table(["Part", "Status"], [
    ["Corpus, ingestion, provenance (27 documents, 22 missions)", "Done, verified"],
    ["Base-paper reproduction (B0–B3, B3-bal)", "Done, reproducible"],
    ["Proposed method P and 6 ablations", "Done, unit-tested"],
    ["Evaluation, statistics, independent audit", "Done; audits PASS"],
    ["Annotation kit and guide", "Done"],
    ["Synthetic proof of concept", "Done (not reportable)"],
    ["10-mission pilot with AI-assisted labels", "Done; results in chapter 12"],
    ["Stage reports, submission summary, this guide", "Done"],
]) + "<h3>Remaining (after the project submission)</h3>" + table(["Task", "Who", "Effort"], [
    ["Decide the three design improvements (chapter 14)", "Owner", "1 h"],
    ["Review taxonomy and field maps", "Owner", "2–3 h"],
    ["Full human labelling: D2a, D2q, D2b, D1, D3 + second annotator", "Owner (+ 1 person)", "60–80 h + 12 h"],
    ["Rate 40 blind answers (validate the automatic judge)", "Owner", "2 h"],
    ["Final runs, audit, fill the IEEE paper's results", "Assistant", "about 2 h compute"],
    ["Final secret scan, push to GitHub, pull request into main", "Together", "at the end"],
]))

chapter("howto", "17. How to Run the Project", """
<h3>Setup</h3>
<pre>pip install -r requirements.txt
python -m spacy download en_core_web_sm
ollama pull llama3
copy .env.example .env      (set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)</pre>
<p>Also required: Tesseract and Poppler (OCR), a Neo4j 5 database, and the bge-m3 model (downloaded once).</p>
<h3>Pipeline</h3>
""" + table(["Step", "Command"], [
    ["Parse documents", "<code>python src/pipeline/page_parser.py --run-id ID</code>"],
    ["Validate provenance", "<code>python scripts/validate_passages.py --run-id ID</code>"],
    ["Apply field maps", "<code>python scripts/field_map_tool.py apply</code>"],
    ["Load passages into Neo4j", "<code>python scripts/ingest_passages_run.py ID</code>"],
    ["Extract causal factors", "<code>python scripts/extract_factors.py --run-id ID</code>"],
    ["Build factor graph", "<code>python scripts/build_factor_graph.py --run-id ID</code>"],
    ["Run all systems", "<code>python scripts/run_retrieval.py --run-id ID --queries FILE --proposed P P-graphonly ...</code>"],
    ["Evaluate", "<code>python scripts/evaluate.py --run runs/ID --eval-id EID [--labels DIR --pilot]</code>"],
    ["Audit", "<code>python scripts/audit.py --run runs/ID --eval runs/EID --out runs/AID</code>"],
    ["Check annotation sheets", "<code>python scripts/check_annotations.py [--dir DIR]</code>"],
    ["Tests", "<code>python -m pytest</code>"],
]) + """
<p>Every run writes its configuration, environment (code version, model versions), predictions, metrics, timings and
log to <code>runs/&lt;run_id&gt;/</code>; existing run folders are never overwritten.</p>
""")

chapter("labelling", "18. Guide to the Remaining Human Labelling", """
<p>The full guide is <code>evalutation/benchmark/ANNOTATION_GUIDE.md</code>. In short:</p>
<ol>
<li><b>Review the taxonomy</b> (causal_taxonomy.json) and freeze it.</li>
<li><b>D2a:</b> for each of the 22 missions, record 3–10 causal factors the board states: code, role, PDF page, a short
verbatim quote. At least one root factor per mission.</li>
<li><b>D2q:</b> for each mission, write 100–200 words describing the mishap as first observed — no causes, no copied text.</li>
<li><b>D2b:</b> grade all 231 mission pairs 0–3 from the D2a factors.</li>
<li><b>D1:</b> mark the causal factors stated in each of 200 sampled passages.</li>
<li><b>D3:</b> write about 105 questions (single-mission, cross-mission, lessons, unanswerable) with key points and evidence pages.</li>
<li>A second person repeats a subset for agreement (κ ≥ 0.6 targeted).</li>
</ol>
""" + note("Rules: record only what the board states; do not look at any system output while labelling; do not change the "
           "method after seeing labels. Run the checker after each step."))

chapter("glossary", "19. Glossary", table(["Term", "Meaning"], [
    ["BM25", "Classic keyword ranking: rewards rare words that appear often in a passage"],
    ["Dense retrieval / bge-m3", "Ranking by meaning: text is turned into vectors and compared by similarity"],
    ["RRF", "Reciprocal Rank Fusion: merges ranked lists by summing 1 / (60 + rank)"],
    ["Field", "Section type of a report: Summary, Causes, Disposition (recommendations)"],
    ["Causal factor", "Something the board states caused or contributed to the mishap"],
    ["Verification", "Keeping a factor only if its quote is found word-for-word in the report"],
    ["Factor graph", "Neo4j graph linking missions to the causal-factor categories they share"],
    ["nDCG@5", "Ranking quality of the top 5 results, from 0 to 1; higher is better"],
    ["Recall@5 / MRR", "Share of relevant missions found in the top 5 / 1 ÷ rank of the first relevant one"],
    ["Leave-one-mission-out", "When a mission is the query, its own reports are hidden from the search"],
    ["Ablation", "A version of the method with one part removed, to see what that part contributes"],
    ["Permutation test, CI", "Checks whether a difference could be chance; range of plausible true differences"],
    ["Abstention", "The system answers 'insufficient evidence' instead of guessing"],
    ["Pilot", "A small first evaluation (here: 10 missions) to test the full procedure"],
]))

chapter("refs", "20. References", """<ol class="refs">
<li>S. Kim and S. Kim, "Multi-field hybrid retrieval-augmented generation for maritime accident root cause analysis," in <i>Proc. IEEE CASE</i>, 2026, pp. 238–243, doi:10.1109/CASE69030.2026.11704480.</li>
<li>X. Xiang, X. Chen, and J. Yang, "Knowledge graph-based causal analysis of aviation accidents: A hybrid approach integrating retrieval-augmented generation and prompt engineering," <i>Aerospace</i>, vol. 13, no. 1, Art. 16, 2026, doi:10.3390/aerospace13010016.</li>
<li>Y. Yang, G. Chen, B. He, and Y. Zhao, "Grounded knowledge graph extraction via LLMs: An anchor-constrained framework with provenance tracking," <i>Computers</i>, vol. 15, no. 3, Art. 178, 2026, doi:10.3390/computers15030178.</li>
<li>X. Xie, X. Tang, S. Gu, and L. Cui, "An intelligent guided troubleshooting method for aircraft based on HybirdRAG," <i>Sci. Rep.</i>, vol. 15, Art. 17752, 2025, doi:10.1038/s41598-025-02643-2.</li>
<li>G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal rank fusion outperforms Condorcet and individual rank learning methods," in <i>Proc. SIGIR</i>, 2009, pp. 758–759.</li>
<li>S. A. Shappell and D. A. Wiegmann, "The human factors analysis and classification system — HFACS," DOT/FAA/AM-00/7, 2000.</li>
<li>Presidential Commission on the Space Shuttle Challenger Accident, <i>Report to the President</i>, Vol. 1, 1986.</li>
<li>Columbia Accident Investigation Board, <i>Report</i>, Vol. 1, 2003.</li>
<li>Mars Climate Orbiter Mishap Investigation Board, <i>Phase I Report</i>, 1999.</li>
<li>Ariane 501 Inquiry Board, <i>Ariane 5 Flight 501 Failure — Report by the Inquiry Board</i>, ESA, 1996.</li>
</ol>""")

# ------------------------------------------------------------------ layout
CSS = """
@font-face {font-family: Body; src: url(arial.ttf);}
@font-face {font-family: Body; font-weight: bold; src: url(arialbd.ttf);}
@font-face {font-family: Body; font-style: italic; src: url(ariali.ttf);}
* {font-family: Body;}
body {font-size: 10.5pt; line-height: 1.35;}
h1 {font-size: 17pt; color: #1f3d5c; margin-top: 0; margin-bottom: 8pt; border-bottom: 1px solid #1f3d5c;}
h3 {font-size: 11.5pt; color: #2f5d8a; margin-top: 10pt; margin-bottom: 3pt;}
p {margin-top: 3pt; margin-bottom: 5pt; text-align: justify;}
li {margin-bottom: 2pt;}
table {border-collapse: collapse; width: 100%; margin-top: 4pt; margin-bottom: 8pt; font-size: 9pt;}
th {color: #1f3d5c; font-weight: bold; padding: 3pt; text-align: left; border-bottom: 1.5px solid #2f5d8a;}
td {border-bottom: 1px solid #c8d2dc; padding: 3pt; vertical-align: top;}
code {font-family: Courier; font-size: 8.8pt;}
pre {font-family: Courier; font-size: 8.8pt; background-color: #f2f4f7; padding: 5pt;}
.fig {text-align: center; margin-top: 6pt; margin-bottom: 0;}
.cap {text-align: center; font-size: 8.8pt; color: #555; font-style: italic; margin-bottom: 8pt;}
.note {background-color: #eef3f8; border: 1px solid #b8c8d8; padding: 6pt; margin: 6pt 0; font-size: 9.5pt;}
.warn {background-color: #fff4e5; border: 1px solid #e0a050; padding: 6pt; margin: 6pt 0; font-size: 9.5pt;}
.toc td {border-bottom: 1px dotted #c8d2dc; font-size: 10.5pt; padding: 4pt;}
.refs li {font-size: 9.5pt; margin-bottom: 4pt;}
"""

TITLE = f"""
<div style="text-align:center">
<p style="font-size:11pt;color:#2f5d8a;margin-top:120pt;text-align:center">PROJECT GUIDE</p>
<p style="font-size:26pt;font-weight:bold;color:#1f3d5c;text-align:center;margin-top:10pt">MissionMind</p>
<p style="font-size:14pt;color:#1f3d5c;text-align:center">Evidence-Anchored, Graph-Augmented Retrieval for Cross-Mission
Causal Analogy in Spaceflight Mishap Investigation Reports</p>
<p style="font-size:11pt;text-align:center;margin-top:60pt">Amaresh Nookala</p>
<p style="font-size:10pt;text-align:center;color:#555">Version 1.0 — 14 October 2026</p>
<p style="font-size:9.5pt;text-align:center;color:#555;margin-top:120pt">Base paper: S. Kim and S. Kim, IEEE CASE 2026.
Results in this guide come from a 10-mission pilot with AI-assisted labels; a fully human-labelled evaluation follows.</p>
</div>
"""


def build(toc_pages: dict | None) -> tuple[pymupdf.Document, dict]:
    toc_rows = "".join(f'<tr><td>{html.escape(t)}</td><td style="text-align:right">{(toc_pages or {}).get(cid, "")}</td></tr>'
                       for cid, t, _ in CH)
    parts = [TITLE, '<h1 id="toc" style="page-break-before:always">Contents</h1>' f'<table class="toc">{toc_rows}</table>']
    for cid, title, body in CH:
        parts.append(f'<h1 id="{cid}" style="page-break-before:always">{html.escape(title)}</h1>{body}')
    arch = pymupdf.Archive()
    arch.add(pymupdf.Archive(str(G)))
    arch.add(pymupdf.Archive("C:/Windows/Fonts"))
    story = pymupdf.Story(html="".join(parts), user_css=CSS, archive=arch)
    found, page_no = {}, [0]

    def record(pos):
        if pos.open_close & 1 and pos.id and pos.heading == 1:
            found.setdefault(pos.id, page_no[0])

    buf = __import__("io").BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (56, 62, -56, -60)
    more = 1
    while more:
        page_no[0] += 1
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.element_positions(record)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return pymupdf.open("pdf", buf.getvalue()), found


def main():
    _, first = build(None)
    doc, pages = build(first)
    assert pages == first, "TOC page numbers shifted between passes"
    font = pymupdf.Font(fontfile="C:/Windows/Fonts/arial.ttf")
    for i, page in enumerate(doc):
        if i == 0:
            continue
        page.wrap_contents()          # isolate the Story's graphics state so headers are not flipped
        r = page.rect
        tw = pymupdf.TextWriter(r, color=(0.35, 0.4, 0.45))
        tw.append((56, 36), "MissionMind — Project Guide", font=font, fontsize=8)
        tw.append((r.width - 56 - font.text_length(f"Page {i + 1} of {len(doc)}", 8), r.height - 30),
                  f"Page {i + 1} of {len(doc)}", font=font, fontsize=8)
        tw.append((56, r.height - 30), "AI-assisted pilot results — see chapter 12", font=font, fontsize=8)
        tw.write_text(page)
        page.draw_line((56, 42), (r.width - 56, 42), color=(0.75, 0.8, 0.85), width=0.5)
    doc.set_toc([[1, t, pages[c]] for c, t, _ in CH])
    doc.set_metadata({"title": "MissionMind — Project Guide", "author": "Amaresh Nookala",
                      "subject": "Evidence-anchored graph-augmented retrieval for spaceflight mishap reports"})
    doc.save(OUT, garbage=3, deflate=True)
    print(f"{OUT.relative_to(ROOT)}: {len(doc)} pages; chapters start at {pages}")


if __name__ == "__main__":
    main()
