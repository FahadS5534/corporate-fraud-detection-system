import sys
import os
import argparse
import pandas as pd
import numpy as np

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.database import SessionLocal
from backend.app.models.models import Company, DirectorRelationship
from backend.app.services.graph_service import GraphService
from backend.app.scoring.score_engine import ScoreEngine
from backend.app.services.community_service import CommunityService

def build_background_graph():
    """
    Builds the graph containing only REAL background companies (no SYN_ prefix).
    """
    db = SessionLocal()
    service = GraphService(db)
    
    # 1. Fetch only background companies
    companies = db.query(Company).filter(~Company.cin.like("SYN_C%")).all()
    comp_cins = set(c.cin for c in companies)
    
    # 2. Build graph using GraphService
    service.build_graph()
    
    # 3. Filter out synthetic nodes
    nodes_to_remove = []
    for node, data in service.graph.nodes(data=True):
        ntype = data.get("type")
        if ntype == "company" and node not in comp_cins:
            nodes_to_remove.append(node)
        elif ntype == "director" and str(node).startswith("SYN_D"):
            nodes_to_remove.append(node)
        elif ntype == "address" and str(node).startswith("SYN_ADDR"):
            nodes_to_remove.append(node)
            
    service.graph.remove_nodes_from(nodes_to_remove)
    db.close()
    return service.graph

def run_evaluation():
    print("==================================================")
    print("      RUNNING NETWORK FRAUD SCREENING PIPELINE     ")
    print("==================================================")
    
    # Step 1: Build real background graph
    print("\n[Step 1] Building background graph for statistical baselines...")
    bg_graph = build_background_graph()
    
    # Step 2: Initialize score engine and freeze thresholds on background only
    print("\n[Step 2] Calculating & freezing background thresholds...")
    score_engine = ScoreEngine(background_graph=bg_graph)
    
    # Step 3: Build combined graph (real + synthetic ring)
    print("\n[Step 3] Building full combined relationship graph...")
    service = GraphService()
    combined_graph = service.build_graph()
    
    # Step 4: Run Louvain community detection
    print("\n[Step 4] Running Louvain community detection on combined graph...")
    community_service = CommunityService(combined_graph, score_engine)
    clusters = community_service.detect_communities()
    
    # Step 5: Evaluate results
    print("\n[Step 5] Analyzing evaluation metrics...")
    
    # Find the cluster containing the synthetic companies (starting with SYN_C)
    planted_cluster = None
    planted_rank = -1
    
    for idx, c in enumerate(clusters):
        syn_members = [cin for cin in c["companies"] if cin.startswith("SYN_C")]
        if len(syn_members) > 0:
            planted_cluster = c
            planted_rank = idx + 1
            break
            
    # Calculate detection metrics
    total_real = 1000
    total_planted = 10
    detected_planted = 0
    false_positives = 0
    
    if planted_cluster:
        detected_planted = len([cin for cin in planted_cluster["companies"] if cin.startswith("SYN_C")])
        
    # Count false positives (background companies flagged with high composite score >= 75)
    high_risk_background_companies = []
    for node, data in combined_graph.nodes(data=True):
        if data.get("type") == "company" and not node.startswith("SYN_C"):
            res = score_engine.compute_scores(node, combined_graph)
            if res["scores"]["composite_score"] >= 75.0:
                false_positives += 1
                high_risk_background_companies.append({
                    "cin": node,
                    "name": data.get("name"),
                    "score": res["scores"]["composite_score"]
                })
                
    detection_rate = (detected_planted / total_planted) * 100.0
    false_positive_rate = (false_positives / total_real) * 100.0
    
    # Find Legitimate Edge Case results
    ca_office_cluster_rank = -1
    tata_holding_cluster_rank = -1
    
    for idx, c in enumerate(clusters):
        # Identify CA office cluster: contains companies registered at Merlin Chambers
        is_ca = any("MERLIN CHAMBERS" in combined_graph.nodes[list(combined_graph.neighbors(cin))[0]].get("raw_address", "") 
                    for cin in c["companies"] if not cin.startswith("SYN_C"))
        if is_ca and ca_office_cluster_rank == -1:
            ca_office_cluster_rank = idx + 1
            
        # Identify Tata cluster: contains TATA sons/subsidiary names
        is_tata = any("TATA STEEL" in combined_graph.nodes[cin].get("name", "") for cin in c["companies"])
        if is_tata and tata_holding_cluster_rank == -1:
            tata_holding_cluster_rank = idx + 1
            
    # Output the final SIH evaluation report
    print("\n==================================================")
    print("     NETWORK FRAUD SCREENING EVALUATION REPORT    ")
    print("==================================================")
    print(f"Real Background Companies:       {total_real}")
    print(f"Synthetic Fraud-Ring Companies:  {total_planted}")
    print(f"Total Clusters Detected:         {len(clusters)}")
    print("--------------------------------------------------")
    print(f"Planted Fraud-Ring Cluster Rank: #{planted_rank}")
    print(f"Planted Entities in Database:    {total_planted}")
    print(f"Detected Planted Entities:       {detected_planted}")
    print(f"Detection Rate:                  {detection_rate:.1f}%")
    print("--------------------------------------------------")
    print(f"False-Positive Count (Score>=75): {false_positives}")
    print(f"False-Positive Rate:             {false_positive_rate:.2f}%")
    print("--------------------------------------------------")
    print("LEGITIMATE EDGE CASES CHECKS:")
    print(f" - CA Office Address Cluster Rank: #{ca_office_cluster_rank} (Pass if > 5 or low risk)")
    print(f" - Tata Holding Structure Rank:    #{tata_holding_cluster_rank} (Pass if > 5 or low risk)")
    
    # Overall check status
    status = "PASS" if (detection_rate == 100.0 and planted_rank == 1 and false_positive_rate < 2.0) else "FAIL"
    print("--------------------------------------------------")
    print(f"EVALUATION STATUS:               {status}")
    print("==================================================\n")
    
    service.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run fraud network detection pipeline and evaluation.")
    parser.add_argument("--evaluation", action="store_true", default=True, help="Run evaluation metrics.")
    args = parser.parse_args()
    
    run_evaluation()
