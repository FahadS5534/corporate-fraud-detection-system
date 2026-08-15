"""
community_service.py — Louvain Community Detection + Cluster Scoring
=====================================================================
Uses networkx.algorithms.community.louvain_communities() (native NetworkX
implementation, seed=42 for reproducibility) to partition the multi-layer
graph into communities, then scores each community using score_engine.py.
"""

import os
import sys
import networkx as nx
import networkx.algorithms.community as nx_comm
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from backend.app.scoring.score_engine import ScoreEngine, compute_cluster_score


class CommunityService:
    """
    Wraps the Louvain community detection step and cluster scoring.

    Parameters
    ----------
    graph        : The full multi-layer NetworkX graph.
    score_engine : A ScoreEngine instance (holds frozen baseline stats).
    """

    def __init__(self, graph: nx.Graph, score_engine: ScoreEngine):
        self.graph = graph
        self.score_engine = score_engine

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def detect_communities(self) -> List[Dict[str, Any]]:
        """
        1. Run Louvain on the full graph (seed=42).
        2. For each community with ≥1 company node, compute a cluster score.
        3. Return clusters sorted by risk_score descending.

        Each returned dict contains:
          cluster_id, cluster_name, risk_score, risk_level, explanations,
          company_cins, companies_count, directors_count, addresses_count,
          lenders_count, metrics, date_spread_days, network_density
        """
        # Louvain returns a list of frozensets (one per community)
        communities = nx_comm.louvain_communities(self.graph, seed=42)

        processed = []

        for idx, community_nodes in enumerate(communities):
            community_nodes = list(community_nodes)

            # Partition nodes by type
            companies  = [n for n in community_nodes if self.graph.nodes[n].get("type") == "company"]
            directors  = [n for n in community_nodes if self.graph.nodes[n].get("type") == "director"]
            addresses  = [n for n in community_nodes if self.graph.nodes[n].get("type") == "address"]
            lenders    = [n for n in community_nodes if self.graph.nodes[n].get("type") == "lender"]

            # Skip communities with no companies
            if not companies:
                continue

            # Score the cluster
            score_result = self.score_engine.score_cluster(
                cluster_id=idx,
                cluster_cins=companies,
                G=self.graph,
            )

            # Incorporation date spread
            dates = []
            for cin in companies:
                ds = self.graph.nodes[cin].get("incorporation_date", "")
                if ds:
                    try:
                        dates.append(datetime.strptime(ds, "%Y-%m-%d"))
                    except ValueError:
                        pass
            date_spread_days = int((max(dates) - min(dates)).days) if len(dates) >= 2 else 0

            # Subgraph density
            subg = self.graph.subgraph(community_nodes)
            density = float(nx.density(subg))

            # Cluster name derived from risk level + top company
            risk_score = score_result["risk_score"]
            risk_level = score_result["risk_level"]
            top_company_name = self.graph.nodes[companies[0]].get("name", companies[0]) if companies else f"Cluster {idx}"
            if risk_score >= 80:
                cluster_name = f"{top_company_name} Syndicate"
            elif risk_score >= 60:
                cluster_name = f"{top_company_name} Risk Network"
            elif risk_score >= 35:
                cluster_name = f"{top_company_name} Watch Group"
            else:
                cluster_name = f"{top_company_name} Group"

            company_names = [self.graph.nodes[c].get("name", c) for c in companies]

            processed.append({
                "cluster_id":       idx,
                "cluster_name":     cluster_name,
                "risk_score":       risk_score,
                "risk_level":       risk_level,
                "explanations":     score_result["explanations"],
                "company_cins":     companies,
                "company_names":    company_names,
                "companies_count":  len(companies),
                "directors_count":  len(directors),
                "addresses_count":  len(addresses),
                "lenders_count":    len(lenders),
                "directors":        directors,
                "addresses":        addresses,
                "lenders":          lenders,
                "date_spread_days": date_spread_days,
                "network_density":  round(density, 6),
                "metrics":          score_result["metrics"],
                # Legacy field aliases (kept for API compatibility)
                "companies":        companies,
                "cluster_risk_score": risk_score,
                "average_company_risk": risk_score,
            })

        # Sort by risk_score descending
        processed.sort(key=lambda x: x["risk_score"], reverse=True)
        return processed
