"""
main.py — FastAPI Application
==============================
Serves the Corporate Fraud Detection API.

On startup, the multi-source graph is built from the 4 CSV files
(no database required), baseline statistics are computed from ground_truth.csv,
Louvain community detection runs, and results are cached in memory.

All responses include the 'explanations' field from the scoring engine.
"""

import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# Add project root to sys.path
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")

import pandas as pd
import networkx as nx
import networkx.algorithms.community as nx_comm

from backend.app.services.graph_service import MultiSourceGraphBuilder
from backend.app.scoring.score_engine import (
    ScoreEngine,
    calculate_baseline_stats,
    compute_cluster_score,
)
from backend.app.services.community_service import CommunityService

app = FastAPI(
    title="MCA21 Corporate Fraud & Shell Company Detection System API",
    description=(
        "Multi-source graph-based corporate network screening API. "
        "Detects fraud rings, shell company clusters, and wilful defaulter networks."
    ),
    version="2.0.0",
)

# Enable CORS for React frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global in-memory cache (populated at startup)
# ---------------------------------------------------------------------------
G_BUILDER: MultiSourceGraphBuilder = None
COMBINED_GRAPH: nx.Graph = None
SCORE_ENGINE: ScoreEngine = None
CLUSTERS: List[Dict[str, Any]] = None
GT_MAP: Dict[str, str] = {}   # {CIN: label}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup_event():
    global G_BUILDER, COMBINED_GRAPH, SCORE_ENGINE, CLUSTERS, GT_MAP

    print("FastAPI startup: Building multi-source graph from CSVs...")

    # 1. Build full graph
    G_BUILDER = MultiSourceGraphBuilder(data_dir=DATA_DIR)
    COMBINED_GRAPH = G_BUILDER.build_graph()

    # 2. Load ground truth → extract normal CINs → compute baseline stats
    gt_path = os.path.join(DATA_DIR, "ground_truth.csv")
    gt_df   = pd.read_csv(gt_path, dtype={"CIN": str})
    GT_MAP  = dict(zip(gt_df["CIN"].str.strip(), gt_df["label"].str.strip()))
    normal_cins = {cin for cin, lbl in GT_MAP.items() if lbl == "normal"}

    baseline_stats = calculate_baseline_stats(COMBINED_GRAPH, normal_cins)
    SCORE_ENGINE = ScoreEngine(background_graph=COMBINED_GRAPH, normal_cins=normal_cins)

    # 3. Community detection + scoring
    comm_service = CommunityService(COMBINED_GRAPH, SCORE_ENGINE)
    CLUSTERS = comm_service.detect_communities()

    print(f"FastAPI startup complete. {len(CLUSTERS)} communities scored and cached.")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "graph_loaded": COMBINED_GRAPH is not None,
        "clusters_ready": CLUSTERS is not None,
    }


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------

@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    if COMBINED_GRAPH is None or CLUSTERS is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")

    num_companies = sum(1 for _, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "company")
    num_directors = sum(1 for _, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "director")
    num_addresses = sum(1 for _, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "address")
    num_lenders   = sum(1 for _, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "lender")
    num_defaulters= sum(
        1 for _, d in COMBINED_GRAPH.nodes(data=True)
        if d.get("type") == "company" and d.get("wilful_defaulter_flag")
    )

    high_risk   = sum(1 for c in CLUSTERS if c["risk_score"] >= 60)
    medium_risk = sum(1 for c in CLUSTERS if 35 <= c["risk_score"] < 60)

    return {
        "total_companies":        num_companies,
        "total_directors":        num_directors,
        "total_addresses":        num_addresses,
        "total_lenders":          num_lenders,
        "total_wilful_defaulters": num_defaulters,
        "total_clusters":         len(CLUSTERS),
        "high_risk_clusters":     high_risk,
        "medium_risk_clusters":   medium_risk,
    }


# ---------------------------------------------------------------------------
# Cluster listing
# ---------------------------------------------------------------------------

@app.get("/api/clusters")
def get_all_clusters():
    if CLUSTERS is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")

    return [
        {
            "rank":             idx + 1,
            "cluster_id":       c["cluster_id"],
            "cluster_name":     c.get("cluster_name", f"Cluster {c['cluster_id']}"),
            "risk_score":       c["risk_score"],
            "risk_level":       c["risk_level"],
            "explanations":     c["explanations"],
            "company_names":    c.get("company_names", []),
            "companies_count":  c["companies_count"],
            "directors_count":  c["directors_count"],
            "addresses_count":  c["addresses_count"],
            "lenders_count":    c.get("lenders_count", 0),
            "date_spread_days": c["date_spread_days"],
            "network_density":  c["network_density"],
            "metrics":          c["metrics"],
        }
        for idx, c in enumerate(CLUSTERS)
    ]


# ---------------------------------------------------------------------------
# Cluster detail
# ---------------------------------------------------------------------------

@app.get("/api/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: int):
    if CLUSTERS is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")

    for c in CLUSTERS:
        if c["cluster_id"] == cluster_id:
            company_details = []
            for cin in c["company_cins"]:
                node_data = COMBINED_GRAPH.nodes.get(cin, {})
                gt_label  = GT_MAP.get(cin, "unknown")
                company_details.append({
                    "cin":                  cin,
                    "name":                 node_data.get("name", ""),
                    "city":                 node_data.get("city", ""),
                    "state":                node_data.get("state", ""),
                    "incorporation_date":   node_data.get("incorporation_date", ""),
                    "company_status":       node_data.get("company_status", ""),
                    "authorized_capital":   node_data.get("authorized_capital", 0.0),
                    "paidup_capital":       node_data.get("paidup_capital", 0.0),
                    "wilful_defaulter":     node_data.get("wilful_defaulter_flag", False),
                    "ground_truth_label":   gt_label,
                })

            return {
                **{k: v for k, v in c.items() if k not in ("companies", "directors", "addresses")},
                "companies_detailed": company_details,
            }

    raise HTTPException(status_code=404, detail="Cluster not found")


# ---------------------------------------------------------------------------
# Cluster subgraph (Cytoscape JSON)
# ---------------------------------------------------------------------------

@app.get("/api/clusters/{cluster_id}/graph")
def get_cluster_graph(cluster_id: int):
    if CLUSTERS is None or G_BUILDER is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")

    for c in CLUSTERS:
        if c["cluster_id"] == cluster_id:
            all_nodes = (
                c.get("company_cins", [])
                + c.get("directors", [])
                + c.get("addresses", [])
                + c.get("lenders", [])
            )
            subg = G_BUILDER.get_subgraph_for_nodes(all_nodes)
            return G_BUILDER.to_cytoscape_json(subg)

    raise HTTPException(status_code=404, detail="Cluster not found")


# ---------------------------------------------------------------------------
# Company evidence trail
# ---------------------------------------------------------------------------

@app.get("/api/companies/{cin}/evidence")
def get_company_evidence(cin: str):
    if COMBINED_GRAPH is None or SCORE_ENGINE is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")

    if not COMBINED_GRAPH.has_node(cin):
        raise HTTPException(status_code=404, detail="Company not found in graph")

    res = SCORE_ENGINE.compute_scores(cin, COMBINED_GRAPH)
    gt_label = GT_MAP.get(cin, "unknown")

    return {
        "cin":              cin,
        "name":             res["name"],
        "ground_truth":     gt_label,
        "composite_score":  res["scores"]["composite_score"],
        "individual_scores": res["scores"],
        "raw_signals":      res["raw_signals"],
        "explanations":     res["explanations"],
    }


# ---------------------------------------------------------------------------
# Evaluation metrics (cross-referenced against ground_truth.csv labels)
# ---------------------------------------------------------------------------

@app.get("/api/evaluation")
def get_evaluation_metrics():
    if CLUSTERS is None or COMBINED_GRAPH is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")

    def find_cluster_for_label(label: str):
        target_cins = {cin for cin, lbl in GT_MAP.items() if lbl == label}
        best_rank, best_cluster, best_overlap = -1, None, 0
        for rank, c in enumerate(CLUSTERS, start=1):
            overlap = len(set(c["company_cins"]) & target_cins)
            if overlap > best_overlap:
                best_overlap = overlap
                best_rank = rank
                best_cluster = c
        return best_rank, best_cluster, best_overlap

    ra_rank, ra_cluster, ra_overlap = find_cluster_for_label("fraud_ring_A")
    rb_rank, rb_cluster, rb_overlap = find_cluster_for_label("fraud_ring_B")
    rc_rank, rc_cluster, rc_overlap = find_cluster_for_label("fraud_ring_C")
    le_rank, le_cluster, le_overlap = find_cluster_for_label("legit_edge_case")

    ring_scores = [
        ra_cluster["risk_score"] if ra_cluster else 0,
        rb_cluster["risk_score"] if rb_cluster else 0,
        rc_cluster["risk_score"] if rc_cluster else 0,
    ]
    legit_score = le_cluster["risk_score"] if le_cluster else 0
    legit_lower = all(legit_score < rs for rs in ring_scores if rs > 0)

    return {
        "total_clusters":       len(CLUSTERS),
        "fraud_ring_A": {
            "rank":         ra_rank,
            "risk_score":   ra_cluster["risk_score"] if ra_cluster else None,
            "risk_level":   ra_cluster["risk_level"] if ra_cluster else None,
            "overlap":      ra_overlap,
            "explanations": ra_cluster["explanations"] if ra_cluster else [],
        },
        "fraud_ring_B": {
            "rank":         rb_rank,
            "risk_score":   rb_cluster["risk_score"] if rb_cluster else None,
            "risk_level":   rb_cluster["risk_level"] if rb_cluster else None,
            "overlap":      rb_overlap,
            "explanations": rb_cluster["explanations"] if rb_cluster else [],
        },
        "fraud_ring_C": {
            "rank":         rc_rank,
            "risk_score":   rc_cluster["risk_score"] if rc_cluster else None,
            "risk_level":   rc_cluster["risk_level"] if rc_cluster else None,
            "overlap":      rc_overlap,
            "explanations": rc_cluster["explanations"] if rc_cluster else [],
        },
        "legit_edge_case": {
            "rank":         le_rank,
            "risk_score":   legit_score,
            "risk_level":   le_cluster["risk_level"] if le_cluster else None,
            "overlap":      le_overlap,
            "lower_than_rings": legit_lower,
        },
    }
