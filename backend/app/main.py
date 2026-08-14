import os
import sys
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Dict, Any

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.database import get_db, SessionLocal
from backend.app.models.models import Company, DirectorRelationship
from backend.app.services.graph_service import GraphService
from backend.app.scoring.score_engine import ScoreEngine
from backend.app.services.community_service import CommunityService

app = FastAPI(
    title="MCA21 Corporate Fraud & Shell Company Detection System API",
    description="Proactive corporate network screening API for smart regulatory analytics.",
    version="1.0.0"
)

# Enable CORS for React frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory cache for graph data and engines to ensure sub-second response times
G_SERVICE = None
COMBINED_GRAPH = None
SCORE_ENGINE = None
CLUSTERS = None

def get_background_graph():
    db = SessionLocal()
    try:
        service = GraphService(db)
        companies = db.query(Company).filter(~Company.cin.like("SYN_C%")).all()
        comp_cins = set(c.cin for c in companies)
        service.build_graph()
        
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
        return service.graph
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    """
    Initialize and cache graph structures and metrics on server boot.
    """
    global G_SERVICE, COMBINED_GRAPH, SCORE_ENGINE, CLUSTERS
    print("FastAPI: Loading data models and initializing relationship graph...")
    
    # 1. Build background graph to calculate/freeze stats
    bg_graph = get_background_graph()
    SCORE_ENGINE = ScoreEngine(background_graph=bg_graph)
    
    # 2. Build full combined graph
    G_SERVICE = GraphService()
    COMBINED_GRAPH = G_SERVICE.build_graph()
    
    # 3. Detect and rank communities
    comm_service = CommunityService(COMBINED_GRAPH, SCORE_ENGINE)
    CLUSTERS = comm_service.detect_communities()
    print("FastAPI: Graph engines successfully initialized.")

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "database": "connected"}

@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    """
    Returns high-level statistics for the dashboard.
    """
    if COMBINED_GRAPH is None or CLUSTERS is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")
        
    num_companies = sum(1 for n, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "company")
    num_directors = sum(1 for n, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "director")
    num_addresses = sum(1 for n, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "address")
    
    high_risk_clusters = sum(1 for c in CLUSTERS if c["cluster_risk_score"] >= 75.0)
    
    return {
        "total_companies": num_companies,
        "total_directors": num_directors,
        "total_addresses": num_addresses,
        "total_clusters": len(CLUSTERS),
        "high_risk_clusters_count": high_risk_clusters
    }

@app.get("/api/clusters")
def get_all_clusters():
    """
    Returns the ranked list of clusters.
    """
    if CLUSTERS is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")
        
    # Return brief info (excluding full list of nodes) for listing
    summary_clusters = []
    for idx, c in enumerate(CLUSTERS):
        summary_clusters.append({
            "rank": idx + 1,
            "cluster_id": c["cluster_id"],
            "cluster_name": c.get("cluster_name", f"Cluster {c['cluster_id']}"),
            "company_names": c.get("company_names", []),
            "companies_count": c["companies_count"],
            "directors_count": c["directors_count"],
            "addresses_count": c["addresses_count"],
            "average_company_risk": c["average_company_risk"],
            "date_spread_days": c["date_spread_days"],
            "network_density": c["network_density"],
            "cluster_risk_score": c["cluster_risk_score"]
        })
    return summary_clusters

@app.get("/api/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: int):
    """
    Returns full detail of a specific cluster.
    """
    if CLUSTERS is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")
        
    for c in CLUSTERS:
        if c["cluster_id"] == cluster_id:
            # We enrich companies details
            company_details = []
            for cin in c["companies"]:
                res = SCORE_ENGINE.compute_scores(cin, COMBINED_GRAPH)
                company_details.append({
                    "cin": cin,
                    "name": res["name"],
                    "scores": res["scores"],
                    "incorporation_date": COMBINED_GRAPH.nodes[cin].get("incorporation_date"),
                    "filing_status": res["raw_signals"]["filing_status"],
                    "paidup_capital": res["raw_signals"]["paidup_capital"]
                })
            
            return {
                **c,
                "companies_detailed": company_details
            }
            
    raise HTTPException(status_code=404, detail="Cluster not found")

@app.get("/api/clusters/{cluster_id}/graph")
def get_cluster_graph(cluster_id: int):
    """
    Returns Cytoscape JSON for rendering a specific cluster's network.
    """
    if CLUSTERS is None or G_SERVICE is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")
        
    for c in CLUSTERS:
        if c["cluster_id"] == cluster_id:
            # Collect all nodes in this cluster
            all_nodes = c["companies"] + c["directors"] + c["addresses"]
            
            # Extract subgraph from combined graph
            subg = G_SERVICE.get_subgraph_for_nodes(all_nodes)
            
            # Convert to Cytoscape JSON
            return G_SERVICE.to_cytoscape_json(subg)
            
    raise HTTPException(status_code=404, detail="Cluster not found")

@app.get("/api/companies/{cin}/evidence")
def get_company_evidence(cin: str):
    """
    Returns evidence logs for an anomalous company.
    """
    if COMBINED_GRAPH is None or SCORE_ENGINE is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")
        
    if not COMBINED_GRAPH.has_node(cin):
        raise HTTPException(status_code=404, detail="Company not found")
        
    res = SCORE_ENGINE.compute_scores(cin, COMBINED_GRAPH)
    
    # Generate structured human-readable logs
    logs = []
    
    # 1. Address
    deg_addr = res["raw_signals"]["address_degree"]
    if res["scores"]["address_risk"] > 0:
        logs.append(f"High-density address sharing detected: {deg_addr} companies share this registered office (Risk Score: {res['scores']['address_risk']:.1f}/100).")
    else:
        logs.append(f"Normal address distribution: {deg_addr} company registered at this location.")
        
    # 2. Directors
    deg_dir = res["raw_signals"]["max_director_degree"]
    if res["scores"]["director_risk"] > 0:
        logs.append(f"Unusual director centralisation: One or more directors hold boards across {deg_dir} companies, exceeding background parameters (Risk Score: {res['scores']['director_risk']:.1f}/100).")
    else:
        logs.append(f"Normal director affiliations: Directors hold boards across {deg_dir} active company/companies.")
        
    # 3. Burst
    burst = res["raw_signals"]["burst_company_count"]
    if res["scores"]["temporal_risk"] > 0:
        logs.append(f"Temporal anomaly: Coordinated incorporation burst of {burst} related companies registered within a 30-day window (Risk Score: {res['scores']['temporal_risk']:.1f}/100).")
    else:
        logs.append("Normal incorporation schedule: No burst/batch registrations detected within date windows.")
        
    # 4. Capital/Filing
    if res["scores"]["capital_filing_risk"] > 0:
        log_cf = "Compliance mismatches: "
        sub_flags = []
        if res["raw_signals"]["is_zero_paidup"]:
            sub_flags.append("declared paid-up capital is zero")
        if res["raw_signals"]["is_defaulter"]:
            sub_flags.append("company is in active filing default / nil return status")
        log_cf += " and ".join(sub_flags) + f" (Risk Score: {res['scores']['capital_filing_risk']:.1f}/100)."
        logs.append(log_cf)
    else:
        logs.append("Good compliance profile: Paid-up capital is active and filings are up-to-date.")
        
    return {
        "cin": cin,
        "name": res["name"],
        "composite_score": res["scores"]["composite_score"],
        "individual_scores": res["scores"],
        "raw_signals": res["raw_signals"],
        "evidence_trail": logs
    }

@app.get("/api/evaluation")
def get_evaluation_metrics():
    """
    Computes and returns pipeline evaluation metrics.
    """
    if CLUSTERS is None or COMBINED_GRAPH is None or SCORE_ENGINE is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")
        
    # Find the cluster containing the synthetic companies
    planted_cluster = None
    planted_rank = -1
    for idx, c in enumerate(CLUSTERS):
        syn_members = [cin for cin in c["companies"] if cin.startswith("SYN_C")]
        if len(syn_members) > 0:
            planted_cluster = c
            planted_rank = idx + 1
            break
            
    detected_planted = 0
    if planted_cluster:
        detected_planted = len([cin for cin in planted_cluster["companies"] if cin.startswith("SYN_C")])
        
    # False positives on background (score >= 75)
    false_positives = 0
    for node, data in COMBINED_GRAPH.nodes(data=True):
        if data.get("type") == "company" and not node.startswith("SYN_C"):
            res = SCORE_ENGINE.compute_scores(node, COMBINED_GRAPH)
            if res["scores"]["composite_score"] >= 75.0:
                false_positives += 1
                
    detection_rate = (detected_planted / 10) * 100.0
    false_positive_rate = (false_positives / 1000) * 100.0
    
    # Legitimate Edge Case results
    ca_office_cluster_rank = -1
    tata_holding_cluster_rank = -1
    
    for idx, c in enumerate(CLUSTERS):
        is_ca = any("MERLIN CHAMBERS" in COMBINED_GRAPH.nodes[list(COMBINED_GRAPH.neighbors(cin))[0]].get("raw_address", "") 
                    for cin in c["companies"] if not cin.startswith("SYN_C"))
        if is_ca and ca_office_cluster_rank == -1:
            ca_office_cluster_rank = idx + 1
            
        is_tata = any("TATA STEEL" in COMBINED_GRAPH.nodes[cin].get("name", "") for cin in c["companies"])
        if is_tata and tata_holding_cluster_rank == -1:
            tata_holding_cluster_rank = idx + 1
            
    status = "PASS" if (detection_rate == 100.0 and planted_rank == 1 and false_positive_rate < 2.0) else "FAIL"
    
    return {
        "real_companies": 1000,
        "synthetic_fraud_companies": 10,
        "total_clusters": len(CLUSTERS),
        "planted_cluster_rank": planted_rank,
        "detected_planted_entities": detected_planted,
        "total_planted_entities": 10,
        "detection_rate_pct": detection_rate,
        "false_positive_count": false_positives,
        "false_positive_rate_pct": false_positive_rate,
        "ca_office_cluster_rank": ca_office_cluster_rank,
        "tata_holding_cluster_rank": tata_holding_cluster_rank,
        "status": status
    }
