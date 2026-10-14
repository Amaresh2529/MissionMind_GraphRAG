"""Figures for the project guide, drawn from the saved run files (no numbers typed by hand)."""
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREEN, GREY = "#2f5d8a", "#d9822b", "#3d8b5a", "#9aa5b1"

# 1. pilot nDCG@5
s = json.loads((ROOT / "runs/pilot_eval_t1_r2/metrics.json").read_text(encoding="utf-8"))["summary"]
names = ["B1", "B2", "H-whole", "B3", "B3-bal", "P", "P-noverif", "P-nofields", "P-noidf", "P-noprf", "P-graphonly"]
vals = [s[n]["mission_ndcg@5"] for n in names]
cols = [GREY if n.startswith(("B1", "B2", "H-")) else BLUE if n.startswith("B3") else ORANGE for n in names]
cols[names.index("P-graphonly")] = GREEN
fig, ax = plt.subplots(figsize=(7.2, 3.2))
ax.bar(names, vals, color=cols)
for i, v in enumerate(vals):
    ax.text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=8)
ax.set_ylim(0.5, 0.75); ax.set_ylabel("nDCG@5 (mission level)")
ax.set_title("10-mission pilot (AI-assisted labels): ranking quality per system", fontsize=10)
plt.xticks(rotation=30, ha="right"); plt.tight_layout(); plt.savefig(OUT / "fig_pilot_ndcg.png", dpi=200); plt.close()

# 2. per-mission
pq = json.loads((ROOT / "runs/pilot_eval_t1_r2/per_query.json").read_text(encoding="utf-8"))
qs = sorted(pq["B3"])
labels = [q[3:].replace("sts-51l-", "").replace("sts-107-", "").replace("mars-climate-orbiter", "MCO").replace("-cft", "").replace("-1998", "").replace("-501", "") for q in qs]
import numpy as np
x = np.arange(len(qs)); w = 0.27
fig, ax = plt.subplots(figsize=(7.2, 3.2))
for k, (sy, c) in enumerate([("B3", BLUE), ("P", ORANGE), ("P-graphonly", GREEN)]):
    ax.bar(x + (k - 1) * w, [pq[sy][q]["mission_ndcg@5"] for q in qs], w, label=sy, color=c)
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha="right"); ax.set_ylabel("nDCG@5"); ax.set_ylim(0, 1)
ax.legend(ncol=3, fontsize=8, frameon=False); ax.set_title("Per-mission ranking quality (pilot)", fontsize=10)
plt.tight_layout(); plt.savefig(OUT / "fig_pilot_missions.png", dpi=200); plt.close()

# 3. extraction funnel
st = json.loads((ROOT / "runs/stage4_extract_all/stats.json").read_text(encoding="utf-8"))
st2 = json.loads((ROOT / "runs/stage4_extract_ariane_official/stats.json").read_text(encoding="utf-8"))
prop, acc = st["proposed"] + st2["proposed"], st["accepted"] + st2["accepted"]
rej = Counter(st["rejection_reasons"]) + Counter(st2["rejection_reasons"])
fig, ax = plt.subplots(figsize=(7.2, 2.6))
bars = [("Proposed by LLM", prop, GREY), ("Accepted (verified)", acc, GREEN), ("Quote not in passage", rej["quote_not_in_passage"], ORANGE),
        ("Quote too short", rej["quote_too_short"], ORANGE), ("Invalid code", rej["bad_code"], ORANGE)]
ax.barh([b[0] for b in bars][::-1], [b[1] for b in bars][::-1], color=[b[2] for b in bars][::-1])
for i, b in enumerate(bars[::-1]):
    ax.text(b[1] + 20, i, str(b[1]), va="center", fontsize=8)
ax.set_title("Evidence verification of LLM-proposed causal factors", fontsize=10); ax.set_xlim(0, prop * 1.12)
plt.tight_layout(); plt.savefig(OUT / "fig_extraction.png", dpi=200); plt.close()

# 4. corpus
man = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))["documents"]
prim = [d for d in man if d["role"] == "primary"]
kinds = Counter({"official_investigation_report": "Full board report", "public_summary": "Public summary",
                 "official_slides": "Slide report", "press_release": "Press release"}.get(d["doc_type"], d["doc_type"]) for d in prim)
ag = Counter(d["agency"].split()[0].split("/")[0] for d in prim)
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.6))
axs[0].bar(list(kinds), list(kinds.values()), color=BLUE); axs[0].set_title("Primary documents by type", fontsize=10)
axs[0].tick_params(axis="x", rotation=20)
axs[1].bar(list(ag), list(ag.values()), color=ORANGE); axs[1].set_title("Primary documents by agency", fontsize=10)
plt.tight_layout(); plt.savefig(OUT / "fig_corpus.png", dpi=200); plt.close()

# 5. architecture
fig, ax = plt.subplots(figsize=(7.2, 4.0)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 6)
def box(x, y, w, h, t, c):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", fc=c, ec="#333", lw=0.8))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=8, wrap=True)
def arrow(x1, y1, x2, y2):
    ax.annotate("", (x2, y2), (x1, y1), arrowprops=dict(arrowstyle="->", lw=1))
box(0.1, 4.7, 2.0, 0.9, "27 PDF / HTML\nreports", "#e8eef5")
box(2.7, 4.7, 2.2, 0.9, "Parsing + OCR\npage-aware passages", "#e8eef5")
box(5.5, 4.7, 2.0, 0.9, "Field maps\nSummary/Causes/Disp.", "#e8eef5")
box(8.0, 4.7, 1.9, 0.9, "Neo4j\n7,117 passages", "#e8eef5")
box(0.6, 2.7, 2.6, 1.1, "B3 (base paper)\nBM25 + bge-m3 x 3 fields\nRRF k=60 (6 lists)", "#dbe7f3")
box(3.7, 2.7, 2.7, 1.1, "Causal-factor extraction\nLLM + quote verification\n22-code taxonomy", "#fbe7d3")
box(6.9, 2.7, 2.6, 1.1, "Factor graph\nmission analogy\n(idf-weighted Jaccard)", "#fbe7d3")
box(2.3, 0.7, 3.0, 1.1, "P = B3 lists + graph list\nRRF fusion\n(leave-one-mission-out)", "#dff0e4")
box(6.0, 0.7, 3.4, 1.1, "Grounded RCA / QA (llama3)\ncitation enforcement\n+ abstention", "#dff0e4")
arrow(2.1, 5.15, 2.7, 5.15); arrow(4.9, 5.15, 5.5, 5.15); arrow(7.5, 5.15, 8.0, 5.15)
arrow(6.5, 4.7, 1.9, 3.8); arrow(6.5, 4.7, 5.0, 3.8); arrow(6.4, 3.25, 6.9, 3.25)
arrow(1.9, 2.7, 3.3, 1.8); arrow(8.2, 2.7, 4.6, 1.8); arrow(5.3, 1.25, 6.0, 1.25)
ax.set_title("MissionMind architecture (blue: base paper B3; orange/green: proposed extension P)", fontsize=9)
plt.tight_layout(); plt.savefig(OUT / "fig_architecture.png", dpi=200); plt.close()
print("figures written")
