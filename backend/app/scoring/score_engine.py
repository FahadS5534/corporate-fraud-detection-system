"""
score_engine.py — Cluster-Level Composite Risk Scorer with Explainability
=========================================================================
Implements the 5-factor composite scoring formula from the technical spec:

  Score = (0.25 × norm_director_degree)
        + (0.25 × norm_address_degree)
        + (0.15 × norm_incorporation_burst)
        + (0.15 × shared_lender_density)
        + (0.20 × wilful_defaulter_ratio)

All five component scores are independently normalised to 0–100 before
weighting, so the final composite is also on a 0–100 scale.

Baseline statistics (mean + std for director-degree and address-degree)
are computed ONLY on the ~440 "normal" background CINs read from
data/ground_truth.csv — never on the fraud rings themselves.
"""

import os
import numpy as np
import pandas as pd
import networkx as nx
from datetime import datetime
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------------------------
# Resolve data directory
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Risk level thresholds
RISK_LEVELS = [
    (80, "CRITICAL RISK"),
    (60, "HIGH RISK"),
    (35, "MEDIUM RISK"),
    (0,  "LOW RISK"),
]


def _risk_level(score: float) -> str:
    for threshold, label in RISK_LEVELS:
        if score >= threshold:
            return label
    return "LOW RISK"


# ---------------------------------------------------------------------------
# Baseline statistics calculator
# ---------------------------------------------------------------------------

def calculate_baseline_stats(G: nx.Graph, normal_cins: set) -> Dict[str, float]:
    """
    Compute mean and std of director-degree and address-degree on BACKGROUND nodes only.

    Parameters
    ----------
    G          : The full multi-layer graph (all 4 layers).
    normal_cins: CINs labelled 'normal' in ground_truth.csv.

    Returns
    -------
    dict with keys: dir_mean, dir_std, addr_mean, addr_std
    """
    dir_degrees = []
    addr_degrees = []

    for cin in normal_cins:
        if not G.has_node(cin):
            continue

        # Director-degree of this company = # of director neighbours
        d_deg = sum(
            1 for nb in G.neighbors(cin)
            if G.nodes[nb].get("type") == "director"
        )
        dir_degrees.append(d_deg)

        # Address-degree = degree of the address node connected to this company
        addr_nodes = [
            nb for nb in G.neighbors(cin)
            if G.nodes[nb].get("type") == "address"
        ]
        if addr_nodes:
            a_deg = G.degree(addr_nodes[0])  # # companies at that address
        else:
            a_deg = 1
        addr_degrees.append(a_deg)

    stats = {
        "dir_mean":  float(np.mean(dir_degrees))  if dir_degrees  else 1.0,
        "dir_std":   max(float(np.std(dir_degrees)),  0.1) if dir_degrees  else 0.5,
        "addr_mean": float(np.mean(addr_degrees)) if addr_degrees else 1.0,
        "addr_std":  max(float(np.std(addr_degrees)), 0.1) if addr_degrees else 0.5,
    }

    print("\n--- FROZEN BACKGROUND STATISTICS (normal CINs only) ---")
    print(f"  Director-degree : mean={stats['dir_mean']:.4f},  std={stats['dir_std']:.4f}")
    print(f"  Address-degree  : mean={stats['addr_mean']:.4f}, std={stats['addr_std']:.4f}")
    print(f"  Background CINs used: {len(dir_degrees)}")
    print("-------------------------------------------------------\n")

    return stats


# ---------------------------------------------------------------------------
# Per-cluster helpers
# ---------------------------------------------------------------------------

def _cluster_avg_director_degree(cluster_cins: List[str], G: nx.Graph) -> float:
    """Average number of director neighbours across all company nodes in the cluster."""
    degrees = []
    for cin in cluster_cins:
        if G.has_node(cin):
            d = sum(1 for nb in G.neighbors(cin) if G.nodes[nb].get("type") == "director")
            degrees.append(d)
    return float(np.mean(degrees)) if degrees else 0.0


def _cluster_avg_address_degree(cluster_cins: List[str], G: nx.Graph) -> float:
    """
    Average degree of the address node connected to each company.
    (= how many companies share that address on average.)
    """
    degrees = []
    for cin in cluster_cins:
        if not G.has_node(cin):
            continue
        addr_nodes = [nb for nb in G.neighbors(cin) if G.nodes[nb].get("type") == "address"]
        if addr_nodes:
            degrees.append(G.degree(addr_nodes[0]))
        else:
            degrees.append(1)
    return float(np.mean(degrees)) if degrees else 1.0


def _incorporation_burst_score(cluster_cins: List[str], G: nx.Graph) -> float:
    """
    Returns a 0–100 score based on how tightly clustered incorporation dates are.
    Spread ≤ 30 days → 100, ≤ 90 days → 60, ≤ 180 days → 30, > 180 days → 0.
    """
    dates = []
    for cin in cluster_cins:
        if not G.has_node(cin):
            continue
        ds = G.nodes[cin].get("incorporation_date", "")
        if ds:
            try:
                dates.append(datetime.strptime(ds, "%Y-%m-%d"))
            except ValueError:
                pass

    if len(dates) < 2:
        return 0.0

    spread_days = (max(dates) - min(dates)).days

    if spread_days <= 30:
        return 100.0
    elif spread_days <= 90:
        return 60.0
    elif spread_days <= 180:
        return 30.0
    else:
        return 0.0


def _shared_lender_density(cluster_cins: List[str], G: nx.Graph) -> float:
    """
    Ratio of companies in the cluster that share at least one common lender.
    Returns a 0–100 score.
    Also returns the name of the most common shared lender (or empty string).
    """
    from collections import Counter

    lender_counts: Counter = Counter()
    for cin in cluster_cins:
        if not G.has_node(cin):
            continue
        for nb in G.neighbors(cin):
            if G.nodes[nb].get("type") == "lender":
                lender_counts[nb] += 1

    if not lender_counts:
        return 0.0

    # Most common lender
    top_lender, top_count = lender_counts.most_common(1)[0]
    ratio = top_count / max(len(cluster_cins), 1)
    return min(ratio * 100.0, 100.0)


def _get_top_lender(cluster_cins: List[str], G: nx.Graph) -> str:
    """Returns the name of the lender shared by the most companies in the cluster."""
    from collections import Counter
    lender_counts: Counter = Counter()
    for cin in cluster_cins:
        if not G.has_node(cin):
            continue
        for nb in G.neighbors(cin):
            if G.nodes[nb].get("type") == "lender":
                lender_counts[nb] += 1
    if not lender_counts:
        return ""
    return lender_counts.most_common(1)[0][0]


def _wilful_defaulter_ratio(cluster_cins: List[str], G: nx.Graph):
    """
    Returns (score_0_to_100, defaulter_count, total_count).
    """
    total = len(cluster_cins)
    count = sum(
        1 for cin in cluster_cins
        if G.has_node(cin) and G.nodes[cin].get("wilful_defaulter_flag", False)
    )
    score = (count / max(total, 1)) * 100.0
    return score, count, total


def _shared_director_count(cluster_cins: List[str], G: nx.Graph) -> int:
    """
    Count of DINs that appear as director-neighbours of MORE THAN ONE company in the cluster.
    """
    from collections import Counter
    din_hits: Counter = Counter()
    for cin in cluster_cins:
        if not G.has_node(cin):
            continue
        for nb in G.neighbors(cin):
            if G.nodes[nb].get("type") == "director":
                din_hits[nb] += 1
    return sum(1 for v in din_hits.values() if v > 1)


def _norm(val: float, mean: float, std: float, cap: float = 5.0) -> float:
    """
    Z-score normalisation capped at `cap` sigmas, mapped to 0–100.
    Values at or below mean return 0. Values at mean + cap*std return 100.
    """
    z = (val - mean) / max(std, 0.01)
    if z <= 0:
        return 0.0
    return min((z / cap) * 100.0, 100.0)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def compute_cluster_score(
    cluster_id: Any,
    cluster_cins: List[str],
    G: nx.Graph,
    baseline_stats: Dict[str, float],
) -> Dict[str, Any]:
    """
    Compute the 5-factor composite risk score for a community/cluster.

    Parameters
    ----------
    cluster_id    : Any hashable identifier for the cluster.
    cluster_cins  : List of CIN strings belonging to this cluster.
    G             : The full multi-layer NetworkX graph.
    baseline_stats: Output of calculate_baseline_stats() — background mean/std.

    Returns
    -------
    {
        "cluster_id"  : ...,
        "risk_score"  : float  (0–100),
        "risk_level"  : str,
        "explanations": [str, ...],
        "company_cins": [...],
        "metrics"     : { raw metric values },
    }
    """
    n = len(cluster_cins)
    if n == 0:
        return {
            "cluster_id": cluster_id, "risk_score": 0.0,
            "risk_level": "LOW RISK", "explanations": [],
            "company_cins": [], "metrics": {},
        }

    # ---- Raw metric values -----------------------------------------------
    avg_dir_deg   = _cluster_avg_director_degree(cluster_cins, G)
    avg_addr_deg  = _cluster_avg_address_degree(cluster_cins, G)
    burst_score   = _incorporation_burst_score(cluster_cins, G)
    lender_score  = _shared_lender_density(cluster_cins, G)
    deflt_score, deflt_count, deflt_total = _wilful_defaulter_ratio(cluster_cins, G)
    shared_dirs   = _shared_director_count(cluster_cins, G)
    top_lender    = _get_top_lender(cluster_cins, G)

    # Spread in days (for explanation text)
    dates = []
    for cin in cluster_cins:
        ds = G.nodes[cin].get("incorporation_date", "") if G.has_node(cin) else ""
        if ds:
            try:
                dates.append(datetime.strptime(ds, "%Y-%m-%d"))
            except ValueError:
                pass
    spread_days = int((max(dates) - min(dates)).days) if len(dates) >= 2 else 0

    # ---- Normalised component scores (0–100) -----------------------------
    s_director = _norm(avg_dir_deg,  baseline_stats["dir_mean"],  baseline_stats["dir_std"],  cap=4.0)
    s_address  = _norm(avg_addr_deg, baseline_stats["addr_mean"], baseline_stats["addr_std"], cap=4.0)
    s_burst    = burst_score   # already 0–100
    s_lender   = lender_score  # already 0–100
    s_defaulter= deflt_score   # already 0–100

    # ---- Weighted composite (spec formula) --------------------------------
    composite = (
        0.25 * s_director
      + 0.25 * s_address
      + 0.15 * s_burst
      + 0.15 * s_lender
      + 0.20 * s_defaulter
    )
    composite = round(min(max(composite, 0.0), 100.0), 2)

    # ---- Explanation generation -------------------------------------------
    explanations: List[str] = []

    # Director signal
    if shared_dirs > 1:
        explanations.append(f"✓ {shared_dirs} shared directors across companies")
    elif shared_dirs == 1:
        explanations.append("✓ 1 shared director across companies")

    # Address signal
    addr_threshold = baseline_stats["addr_mean"] + baseline_stats["addr_std"]
    if avg_addr_deg > addr_threshold:
        explanations.append(
            f"✓ Common registered address detected "
            f"(avg {avg_addr_deg:.1f} companies/address vs baseline {addr_threshold:.1f})"
        )

    # Lender signal
    if top_lender:
        companies_with_lender = sum(
            1 for cin in cluster_cins
            if G.has_node(cin) and any(
                nb == top_lender for nb in G.neighbors(cin)
            )
        )
        explanations.append(
            f"✓ Common lender shared: {top_lender} "
            f"({companies_with_lender}/{n} companies)"
        )

    # Wilful defaulter signal
    if deflt_count > 0:
        explanations.append(
            f"✓ {deflt_count}/{deflt_total} companies are flagged wilful defaulters"
        )

    # Temporal burst signal
    if burst_score > 0:
        if spread_days <= 30:
            explanations.append(
                f"✓ Companies incorporated within a tight time window ({spread_days} days)"
            )
        else:
            explanations.append(
                f"✓ Companies incorporated within a short period ({spread_days} days)"
            )

    # ---- Final result object ----------------------------------------------
    score_breakdown = [
        {
            "label": "Director concentration",
            "weight": 25,
            "signal_score": round(s_director, 2),
            "contribution": round(0.25 * s_director, 2),
            "reason": f"Average of {avg_dir_deg:.1f} director links per company, normalised against the normal-company baseline.",
        },
        {
            "label": "Registered-address concentration",
            "weight": 25,
            "signal_score": round(s_address, 2),
            "contribution": round(0.25 * s_address, 2),
            "reason": f"{avg_addr_deg:.1f} companies share the registered address; the alert threshold is {addr_threshold:.1f}.",
        },
        {
            "label": "Incorporation timing",
            "weight": 15,
            "signal_score": round(s_burst, 2),
            "contribution": round(0.15 * s_burst, 2),
            "reason": f"Incorporation-window signal is {s_burst:.0f}/100 over a {spread_days}-day span.",
        },
        {
            "label": "Shared lender",
            "weight": 15,
            "signal_score": round(s_lender, 2),
            "contribution": round(0.15 * s_lender, 2),
            "reason": f"{s_lender:.0f}% of companies share the same lender" + (f" ({top_lender})." if top_lender else "."),
        },
        {
            "label": "Wilful-defaulter status",
            "weight": 20,
            "signal_score": round(s_defaulter, 2),
            "contribution": round(0.20 * s_defaulter, 2),
            "reason": f"{deflt_count} of {deflt_total} companies are marked as wilful defaulters.",
        },
    ]

    return {
        "cluster_id":   cluster_id,
        "risk_score":   composite,
        "risk_level":   _risk_level(composite),
        "explanations": explanations,
        "score_breakdown": score_breakdown,
        "company_cins": cluster_cins,
        "metrics": {
            "avg_director_degree":     round(avg_dir_deg, 3),
            "avg_address_degree":      round(avg_addr_deg, 3),
            "incorporation_burst_score": round(burst_score, 2),
            "shared_lender_density":   round(lender_score, 2),
            "wilful_defaulter_ratio":  round(deflt_score, 2),
            "shared_director_count":   shared_dirs,
            "wilful_defaulter_count":  deflt_count,
            "cluster_size":            n,
            "incorporation_spread_days": spread_days,
            "top_lender":              top_lender,
            "component_scores": {
                "director":   round(s_director, 2),
                "address":    round(s_address, 2),
                "burst":      round(s_burst, 2),
                "lender":     round(s_lender, 2),
                "defaulter":  round(s_defaulter, 2),
            },
        },
    }


# ---------------------------------------------------------------------------
# Backward-compat shim — old code imported ScoreEngine
# ---------------------------------------------------------------------------

class ScoreEngine:
    """
    Thin wrapper kept for API/startup backward compatibility.
    New code should call compute_cluster_score() directly.
    """

    def __init__(self, background_graph=None, normal_cins: Optional[set] = None):
        self.baseline_stats = {
            "dir_mean": 1.0, "dir_std": 0.5,
            "addr_mean": 1.0, "addr_std": 0.5,
        }
        if background_graph is not None and normal_cins is not None:
            self.baseline_stats = calculate_baseline_stats(background_graph, normal_cins)
        elif background_graph is not None:
            # Fallback: treat all company nodes as background
            all_cins = {
                n for n, d in background_graph.nodes(data=True)
                if d.get("type") == "company"
            }
            self.baseline_stats = calculate_baseline_stats(background_graph, all_cins)

    def score_cluster(
        self,
        cluster_id: Any,
        cluster_cins: List[str],
        G: nx.Graph,
    ) -> Dict[str, Any]:
        return compute_cluster_score(cluster_id, cluster_cins, G, self.baseline_stats)

    # Legacy per-company API kept so old evidence trail endpoints keep working
    def compute_scores(self, company_cin: str, G: nx.Graph) -> Dict[str, Any]:
        result = compute_cluster_score(
            cluster_id=company_cin,
            cluster_cins=[company_cin],
            G=G,
            baseline_stats=self.baseline_stats,
        )
        return {
            "cin": company_cin,
            "name": G.nodes[company_cin].get("name", "") if G.has_node(company_cin) else "",
            "scores": {
                "composite_score": result["risk_score"],
                "director_risk":   result["metrics"]["component_scores"]["director"],
                "address_risk":    result["metrics"]["component_scores"]["address"],
                "temporal_risk":   result["metrics"]["component_scores"]["burst"],
                "lender_risk":     result["metrics"]["component_scores"]["lender"],
                "defaulter_risk":  result["metrics"]["component_scores"]["defaulter"],
            },
            "raw_signals": {
                "address_degree":       result["metrics"]["avg_address_degree"],
                "max_director_degree":  result["metrics"]["avg_director_degree"],
                "burst_company_count":  result["metrics"]["incorporation_burst_score"],
                "wilful_defaulter_flag": G.nodes[company_cin].get("wilful_defaulter_flag", False)
                    if G.has_node(company_cin) else False,
                "is_zero_paidup": (G.nodes[company_cin].get("paidup_capital", 1.0) <= 0.0)
                    if G.has_node(company_cin) else False,
                "is_defaulter": G.nodes[company_cin].get("wilful_defaulter_flag", False)
                    if G.has_node(company_cin) else False,
                "filing_status": "Defaulter" if G.has_node(company_cin)
                    and G.nodes[company_cin].get("wilful_defaulter_flag", False) else "Filed",
                "paidup_capital": G.nodes[company_cin].get("paidup_capital", 0.0)
                    if G.has_node(company_cin) else 0.0,
                "name": G.nodes[company_cin].get("name", "") if G.has_node(company_cin) else "",
            },
            "explanations": result["explanations"],
            "score_breakdown": result["score_breakdown"],
        }
