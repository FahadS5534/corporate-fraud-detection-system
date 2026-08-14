import os
import sys
import community as community_louvain  # python-louvain
import networkx as nx
import pandas as pd
import numpy as np
from datetime import datetime

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.scoring.score_engine import ScoreEngine

class CommunityService:
    def __init__(self, graph, score_engine: ScoreEngine):
        self.graph = graph
        self.score_engine = score_engine

    def detect_communities(self):
        """
        Runs the Louvain algorithm on the relationship graph,
        filters for clusters containing companies, and calculates metrics for each.
        """
        # Louvain partition (returns dict of {node: community_id})
        partition = community_louvain.best_partition(self.graph)
        
        # Group nodes by community ID
        clusters_raw = {}
        for node, comm_id in partition.items():
            if comm_id not in clusters_raw:
                clusters_raw[comm_id] = []
            clusters_raw[comm_id].append(node)
            
        processed_clusters = []
        
        for comm_id, nodes in clusters_raw.items():
            # Separate companies, directors, and addresses
            companies = []
            directors = []
            addresses = []
            
            for node in nodes:
                ntype = self.graph.nodes[node].get("type")
                if ntype == "company":
                    companies.append(node)
                elif ntype == "director":
                    directors.append(node)
                elif ntype == "address":
                    addresses.append(node)
                    
            # Skip communities that don't contain any companies
            if not companies:
                continue
                
            # Compute company risk scores
            comp_scores = []
            inc_dates = []
            company_names = []
            
            highest_risk_cin = None
            highest_risk_score = -1.0
            
            for cin in companies:
                res = self.score_engine.compute_scores(cin, self.graph)
                score = res["scores"]["composite_score"]
                comp_scores.append(score)
                
                cname = self.graph.nodes[cin].get("name", cin)
                company_names.append(cname)
                
                if score > highest_risk_score:
                    highest_risk_score = score
                    highest_risk_cin = cin
                
                date_str = self.graph.nodes[cin].get("incorporation_date", "")
                if date_str:
                    try:
                        inc_dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
                    except ValueError:
                        pass
                        
            avg_company_risk = float(np.mean(comp_scores)) if comp_scores else 0.0
            
            # Name the cluster based on its highest risk company
            highest_risk_name = self.graph.nodes[highest_risk_cin].get("name", highest_risk_cin) if highest_risk_cin else f"Cluster {comm_id}"
            if highest_risk_score >= 75.0:
                cluster_name = f"{highest_risk_name} Syndicate"
            elif highest_risk_score >= 40.0:
                cluster_name = f"{highest_risk_name} Risk Network"
            else:
                cluster_name = f"{highest_risk_name} Group"
            
            # Date spread calculation
            if len(inc_dates) >= 2:
                min_date = min(inc_dates)
                max_date = max(inc_dates)
                date_spread_days = int((max_date - min_date).days)
            else:
                date_spread_days = 0
                
            # Subgraph density of community nodes
            subg = self.graph.subgraph(nodes)
            density = float(nx.density(subg))
            
            # Compute structural risk (0-100)
            struct_risk = 0.0
            if len(companies) >= 3:
                struct_risk += 30.0 # base structural penalty for size
            if date_spread_days <= 45 and len(companies) >= 2:
                struct_risk += 40.0 # high risk for rapid batch registration
            if density > 0.05:
                struct_risk += 30.0 # density score
                
            # Cluster Risk Score: 60% average member risk + 40% structural risk
            cluster_risk = (0.6 * avg_company_risk) + (0.4 * struct_risk)
            
            processed_clusters.append({
                "cluster_id": comm_id,
                "cluster_name": cluster_name,
                "companies_count": len(companies),
                "directors_count": len(directors),
                "addresses_count": len(addresses),
                "companies": companies,
                "company_names": company_names,
                "directors": directors,
                "addresses": addresses,
                "average_company_risk": avg_company_risk,
                "date_spread_days": date_spread_days,
                "network_density": density,
                "cluster_risk_score": float(cluster_risk)
            })
            
        # Sort clusters by risk score descending
        processed_clusters.sort(key=lambda x: x["cluster_risk_score"], reverse=True)
        
        return processed_clusters
