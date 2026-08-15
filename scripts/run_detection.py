"""
run_detection.py — End-to-End Fraud Detection Pipeline
=======================================================
Execution order
---------------
1. Load 4 source CSVs → build MultiSourceGraphBuilder graph (G)
2. Load ground_truth.csv → extract 'normal' CINs → compute baseline stats
3. Run networkx Louvain community detection (seed=42)
4. Score + rank all communities using 5-factor composite formula
5. Cross-reference detected clusters against ground truth labels
6. Print ranked evaluation report for all 4 labelled groups
7. Pre-render interactive PyVis network HTML → outputs/network_graph.html

Usage
-----
    python scripts/run_detection.py
    python scripts/run_detection.py --top-n 10   # show top N clusters
"""

import os
import sys
# Force UTF-8 output on Windows so unicode chars print correctly
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import argparse
import json
from collections import defaultdict, Counter
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import networkx as nx
import networkx.algorithms.community as nx_comm

# ---------------------------------------------------------------------------
# Path setup — make sure project root is importable
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)

DATA_DIR    = os.path.join(PROJECT_ROOT, "data")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

from backend.app.services.graph_service import MultiSourceGraphBuilder
from backend.app.scoring.score_engine import (
    ScoreEngine,
    calculate_baseline_stats,
    compute_cluster_score,
)


# ---------------------------------------------------------------------------
# Ground-truth label sets
# ---------------------------------------------------------------------------

def load_ground_truth(gt_path: str) -> Dict[str, str]:
    """Returns {CIN: label} mapping."""
    df = pd.read_csv(gt_path, dtype={"CIN": str})
    return dict(zip(df["CIN"].str.strip(), df["label"].str.strip()))


def get_cins_by_label(gt_map: Dict[str, str], label: str):
    return {cin for cin, lbl in gt_map.items() if lbl == label}


# ---------------------------------------------------------------------------
# PyVis network HTML renderer
# ---------------------------------------------------------------------------

def render_pyvis_html(
    G: nx.Graph,
    clusters: List[Dict[str, Any]],
    output_path: str,
    top_n: int = 10,
):
    """
    Renders an interactive PyVis HTML file.

    Node colours
    ------------
    company  (normal)   → #4A90D9  (steel blue)
    company  (high risk)→ #E74C3C  (red)
    company  (medium)   → #F39C12  (amber)
    director            → #27AE60  (green)
    address             → #8E44AD  (purple)
    lender              → #E67E22  (orange)

    Edges are coloured by relation type.
    """
    try:
        from pyvis.network import Network
    except ImportError:
        print("[WARNING] pyvis not installed. Skipping HTML visualisation.")
        print("          Run: pip install pyvis")
        return

    net = Network(
        height="900px", width="100%",
        bgcolor="#1a1a2e", font_color="#ffffff",
        directed=False,
        notebook=False,
    )
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=120)

    # Map each company to its cluster's risk score for colour coding
    cin_to_score: Dict[str, float] = {}
    cin_to_cluster: Dict[str, int] = {}
    cin_to_explanation: Dict[str, List[str]] = {}

    for c in clusters:
        for cin in c["company_cins"]:
            cin_to_score[cin] = c["risk_score"]
            cin_to_cluster[cin] = c["cluster_id"]
            cin_to_explanation[cin] = c["explanations"]

    NODE_COLORS = {
        "director": "#27AE60",
        "address":  "#8E44AD",
        "lender":   "#E67E22",
    }

    def company_color(score: float) -> str:
        if score >= 80:
            return "#E74C3C"
        elif score >= 60:
            return "#E74C3C"
        elif score >= 35:
            return "#F39C12"
        else:
            return "#4A90D9"

    def company_size(score: float) -> int:
        if score >= 80: return 30
        elif score >= 60: return 24
        elif score >= 35: return 18
        else: return 12

    # Build set of nodes that belong to top-N clusters
    top_cluster_ids = {c["cluster_id"] for c in clusters[:top_n]}
    highlight_cins   = {
        cin for c in clusters[:top_n] for cin in c["company_cins"]
    }

    added_nodes = set()

    for node_id, data in G.nodes(data=True):
        ntype = data.get("type", "")
        label = data.get("name", str(node_id))
        node_str = str(node_id)

        if ntype == "company":
            score = cin_to_score.get(node_str, 0.0)
            color = company_color(score)
            size  = company_size(score)
            cluster_id = cin_to_cluster.get(node_str, -1)
            explanations = cin_to_explanation.get(node_str, [])
            tooltip = (
                f"<b>{label}</b><br>"
                f"CIN: {node_str}<br>"
                f"Risk Score: {score:.1f}<br>"
                f"Cluster: #{cluster_id}<br>"
                + ("<br>".join(explanations) if explanations else "No signals detected")
            )
            shape = "dot"
        elif ntype == "director":
            color = NODE_COLORS["director"]
            size  = 10
            tooltip = f"<b>Director</b>: {label}"
            shape = "triangle"
        elif ntype == "address":
            color = NODE_COLORS["address"]
            size  = 10
            tooltip = f"<b>Address</b>: {data.get('raw_address', node_str)}"
            shape = "square"
        elif ntype == "lender":
            color = NODE_COLORS["lender"]
            size  = 12
            tooltip = f"<b>Lender</b>: {label}"
            shape = "diamond"
        else:
            color = "#95a5a6"
            size  = 8
            tooltip = str(node_id)
            shape = "dot"

        # Only render nodes in top-N clusters + their neighbours, to keep the
        # HTML manageable. Full graph can have 1000+ nodes.
        in_top = (ntype == "company" and node_str in highlight_cins)
        neighbor_of_top = any(
            (G.nodes[nb].get("type") == "company" and str(nb) in highlight_cins)
            for nb in G.neighbors(node_id)
        )
        if not (in_top or neighbor_of_top):
            continue

        net.add_node(
            node_str,
            label=label[:28] + "…" if len(label) > 30 else label,
            color=color,
            size=size,
            title=tooltip,
            shape=shape,
        )
        added_nodes.add(node_str)

    EDGE_COLORS = {
        "REGISTERED_AT": "#8E44AD",
        "DIRECTOR_OF":   "#27AE60",
        "BORROWED_FROM": "#E67E22",
    }
    for src, tgt, edata in G.edges(data=True):
        if str(src) in added_nodes and str(tgt) in added_nodes:
            rel = edata.get("relation", "")
            net.add_edge(
                str(src), str(tgt),
                color=EDGE_COLORS.get(rel, "#555555"),
                title=rel,
                width=1.5,
            )

    # Legend HTML injected into the page
    legend_html = """
    <div style="position:fixed;top:15px;right:15px;background:#16213e;padding:14px 18px;
                border-radius:10px;border:1px solid #0f3460;font-family:sans-serif;
                font-size:13px;color:#fff;z-index:9999;min-width:220px;">
      <b style="font-size:15px;">🔍 Risk Legend</b><br><br>
      <span style="color:#E74C3C;">●</span> CRITICAL / HIGH RISK company<br>
      <span style="color:#F39C12;">●</span> MEDIUM RISK company<br>
      <span style="color:#4A90D9;">●</span> LOW RISK company<br>
      <span style="color:#27AE60;">▲</span> Director node<br>
      <span style="color:#8E44AD;">■</span> Address node<br>
      <span style="color:#E67E22;">◆</span> Lender node<br><br>
      <i style="color:#aaa;">Click any node for details</i>
    </div>
    """

    net.set_options("""
    var options = {
      "nodes": { "borderWidth": 2, "shadow": true },
      "edges": { "smooth": { "type": "dynamic" }, "shadow": false },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "hideEdgesOnDrag": true
      },
      "physics": {
        "enabled": true,
        "stabilization": { "iterations": 200 }
      }
    }
    """)

    html_path = output_path
    net.save_graph(html_path)

    # Inject legend into saved HTML
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    html_content = html_content.replace("</body>", legend_html + "\n</body>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n[PyVis] Network graph saved → {html_path}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(top_n: int = 10):
    print("=" * 62)
    print("   MULTI-SOURCE GRAPH FRAUD DETECTION PIPELINE")
    print("=" * 62)

    # ------------------------------------------------------------------
    # Step 1: Build multi-layer graph from 4 CSV sources
    # ------------------------------------------------------------------
    print("\n[Step 1] Building multi-source 4-layer graph from CSVs...")
    builder = MultiSourceGraphBuilder(data_dir=DATA_DIR)
    G = builder.build_graph()

    # ------------------------------------------------------------------
    # Step 2: Load ground truth → compute background baseline stats
    # ------------------------------------------------------------------
    print("\n[Step 2] Loading ground truth & computing background baselines...")
    gt_path = os.path.join(DATA_DIR, "ground_truth.csv")
    gt_map  = load_ground_truth(gt_path)

    normal_cins = get_cins_by_label(gt_map, "normal")
    print(f"  Normal background CINs:   {len(normal_cins)}")
    print(f"  Fraud Ring A CINs:        {len(get_cins_by_label(gt_map, 'fraud_ring_A'))}")
    print(f"  Fraud Ring B CINs:        {len(get_cins_by_label(gt_map, 'fraud_ring_B'))}")
    print(f"  Fraud Ring C CINs:        {len(get_cins_by_label(gt_map, 'fraud_ring_C'))}")
    print(f"  Legit Edge Case CINs:     {len(get_cins_by_label(gt_map, 'legit_edge_case'))}")

    baseline_stats = calculate_baseline_stats(G, normal_cins)

    # ------------------------------------------------------------------
    # Step 3: Louvain community detection
    # ------------------------------------------------------------------
    print("\n[Step 3] Running Louvain community detection (seed=42)...")
    communities = nx_comm.louvain_communities(G, seed=42)
    print(f"  Total raw communities found: {len(communities)}")

    # ------------------------------------------------------------------
    # Step 4: Score & rank all communities
    # ------------------------------------------------------------------
    print("\n[Step 4] Scoring all communities with 5-factor composite formula...")
    scored_clusters = []
    for idx, community_nodes in enumerate(communities):
        community_nodes = list(community_nodes)
        companies = [
            n for n in community_nodes
            if G.nodes[n].get("type") == "company"
        ]
        if not companies:
            continue
        result = compute_cluster_score(idx, companies, G, baseline_stats)
        scored_clusters.append(result)

    scored_clusters.sort(key=lambda x: x["risk_score"], reverse=True)
    print(f"  Communities with companies: {len(scored_clusters)}")

    # ------------------------------------------------------------------
    # Step 5: Cross-reference with ground truth labels
    # ------------------------------------------------------------------
    print("\n[Step 5] Cross-referencing clusters with ground truth labels...")

    ring_a_cins    = get_cins_by_label(gt_map, "fraud_ring_A")
    ring_b_cins    = get_cins_by_label(gt_map, "fraud_ring_B")
    ring_c_cins    = get_cins_by_label(gt_map, "fraud_ring_C")
    legit_cins     = get_cins_by_label(gt_map, "legit_edge_case")

    def find_cluster_for_cins(target_cins, clusters):
        """Find rank (1-indexed) and cluster dict for the cluster with most overlap."""
        best_rank, best_cluster, best_overlap = -1, None, 0
        for rank, c in enumerate(clusters, start=1):
            overlap = len(set(c["company_cins"]) & target_cins)
            if overlap > best_overlap:
                best_overlap = overlap
                best_rank = rank
                best_cluster = c
        return best_rank, best_cluster, best_overlap

    ring_a_rank, ring_a_cluster, ring_a_overlap = find_cluster_for_cins(ring_a_cins, scored_clusters)
    ring_b_rank, ring_b_cluster, ring_b_overlap = find_cluster_for_cins(ring_b_cins, scored_clusters)
    ring_c_rank, ring_c_cluster, ring_c_overlap = find_cluster_for_cins(ring_c_cins, scored_clusters)
    legit_rank,  legit_cluster,  legit_overlap  = find_cluster_for_cins(legit_cins,  scored_clusters)

    # ------------------------------------------------------------------
    # Step 6: Print evaluation report
    # ------------------------------------------------------------------
    print("\n" + "=" * 62)
    print("   FRAUD DETECTION EVALUATION REPORT")
    print("=" * 62)
    print(f"  Total companies in graph    : {sum(1 for _,d in G.nodes(data=True) if d.get('type')=='company')}")
    print(f"  Total directors in graph    : {sum(1 for _,d in G.nodes(data=True) if d.get('type')=='director')}")
    print(f"  Total addresses in graph    : {sum(1 for _,d in G.nodes(data=True) if d.get('type')=='address')}")
    print(f"  Total lenders in graph      : {sum(1 for _,d in G.nodes(data=True) if d.get('type')=='lender')}")
    print(f"  Scored communities          : {len(scored_clusters)}")
    print()

    def print_cluster_block(label: str, rank: int, cluster, overlap: int, expected_size: int):
        if cluster is None:
            print(f"  [!] {label}: NOT DETECTED")
            return
        score      = cluster["risk_score"]
        risk_level = cluster["risk_level"]
        metrics    = cluster["metrics"]
        expls      = cluster["explanations"]

        print(f"  {'='*56}")
        print(f"  >> {label}")
        print(f"     Rank          : #{rank}")
        print(f"     Risk Score    : {score:.1f}/100  [{risk_level}]")
        print(f"     CINs detected : {overlap}/{expected_size} ground-truth members in cluster")
        print(f"     Cluster size  : {metrics['cluster_size']} companies")
        print(f"     Spread (days) : {metrics['incorporation_spread_days']}")
        print(f"     Shared dirs   : {metrics['shared_director_count']}")
        print(f"     Defaulters    : {metrics['wilful_defaulter_count']}/{metrics['cluster_size']}")
        if metrics["top_lender"]:
            print(f"     Top lender    : {metrics['top_lender']}")
        print(f"     Explanations  :")
        for e in expls:
            print(f"       {e}")
        if not expls:
            print("       (no signals above threshold)")

    print_cluster_block("Fraud Ring A (Kolkata - Dense Ring)",  ring_a_rank, ring_a_cluster, ring_a_overlap, len(ring_a_cins))
    print_cluster_block("Fraud Ring B (Pune - Subtler Ring)",   ring_b_rank, ring_b_cluster, ring_b_overlap, len(ring_b_cins))
    print_cluster_block("Fraud Ring C (Ahmedabad - Defaulter)", ring_c_rank, ring_c_cluster, ring_c_overlap, len(ring_c_cins))
    print_cluster_block("Legit Edge Case (Mumbai - CA Office)", legit_rank,  legit_cluster,  legit_overlap,  len(legit_cins))

    print(f"\n  {'='*56}")
    print(f"  TOP {top_n} CLUSTERS BY RISK SCORE:")
    for i, c in enumerate(scored_clusters[:top_n], start=1):
        print(f"    #{i:2d}  Score={c['risk_score']:5.1f}  [{c['risk_level']:<14s}]  "
              f"n={c['metrics']['cluster_size']:3d}  "
              f"explanations={len(c['explanations'])}")

    # Sanity check: legit edge case should be scored LOWER than all 3 rings
    ring_scores  = [
        ring_a_cluster["risk_score"] if ring_a_cluster else 0,
        ring_b_cluster["risk_score"] if ring_b_cluster else 0,
        ring_c_cluster["risk_score"] if ring_c_cluster else 0,
    ]
    legit_score  = legit_cluster["risk_score"] if legit_cluster else 0
    legit_lower  = all(legit_score < rs for rs in ring_scores if rs > 0)

    print(f"\n  {'='*56}")
    print(f"  LEGIT EDGE CASE CHECK:")
    print(f"     Ring A score = {ring_a_cluster['risk_score']:.1f}" if ring_a_cluster else "     Ring A = N/A")
    print(f"     Ring B score = {ring_b_cluster['risk_score']:.1f}" if ring_b_cluster else "     Ring B = N/A")
    print(f"     Ring C score = {ring_c_cluster['risk_score']:.1f}" if ring_c_cluster else "     Ring C = N/A")
    print(f"     Legit  score = {legit_score:.1f}")
    if legit_lower:
        print("     [PASS] Legit edge case scores LOWER than all 3 fraud rings")
    else:
        print("     [WARNING] Legit edge case scored higher than one or more rings")

    print("=" * 62)

    # ------------------------------------------------------------------
    # Step 7: PyVis HTML visualisation
    # ------------------------------------------------------------------
    print(f"\n[Step 7] Rendering interactive network visualisation...")

    # Build full cluster dicts for renderer (it needs company_cins + explanations)
    viz_clusters = [
        {
            "cluster_id":    c["cluster_id"],
            "risk_score":    c["risk_score"],
            "risk_level":    c["risk_level"],
            "explanations":  c["explanations"],
            "company_cins":  c["company_cins"],
        }
        for c in scored_clusters
    ]

    html_output = os.path.join(OUTPUTS_DIR, "network_graph.html")
    render_pyvis_html(G, viz_clusters, html_output, top_n=top_n)

    print("\n[Pipeline complete]")
    return scored_clusters


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the multi-source graph fraud detection pipeline."
    )
    parser.add_argument(
        "--top-n", type=int, default=10,
        help="Number of top clusters to display and include in visualisation (default: 10)."
    )
    args = parser.parse_args()
    run_pipeline(top_n=args.top_n)
