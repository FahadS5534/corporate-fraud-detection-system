import os
import sys
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Dict, Any

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.database import get_db, SessionLocal
from backend.app.models.models import (
    Company,
    DirectorRelationship,
    CersaiSecurityInterest,
    RbiWilfulDefaulter,
    GroundTruth
)
from backend.app.services.graph_service import GraphService
from backend.app.scoring.score_engine import ScoreEngine
from backend.app.services.community_service import CommunityService

# Ensure static folder exists
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

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

# Mount pre-rendered Pyvis graph folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Global in-memory cache
G_SERVICE = None
COMBINED_GRAPH = None
SCORE_ENGINE = None
CLUSTERS = None

def get_background_graph():
    db = SessionLocal()
    try:
        service = GraphService(db)
        # Use only normal background companies for Z-score freezing
        companies = db.query(Company).join(GroundTruth, Company.cin == GroundTruth.cin).filter(GroundTruth.label == "normal").all()
        comp_cins = set(c.cin for c in companies)
        service.build_graph()
        
        nodes_to_remove = []
        for node, data in service.graph.nodes(data=True):
            ntype = data.get("type")
            if ntype == "company" and node not in comp_cins:
                nodes_to_remove.append(node)
            elif ntype == "director":
                neighbors = [nb for nb in service.graph.neighbors(node) if service.graph.nodes[nb].get("type") == "company"]
                if neighbors and all(nb not in comp_cins for nb in neighbors):
                    nodes_to_remove.append(node)
            elif ntype == "address":
                neighbors = [nb for nb in service.graph.neighbors(node) if service.graph.nodes[nb].get("type") == "company"]
                if neighbors and all(nb not in comp_cins for nb in neighbors):
                    nodes_to_remove.append(node)
            elif ntype == "lender":
                neighbors = [nb for nb in service.graph.neighbors(node) if service.graph.nodes[nb].get("type") == "company"]
                if neighbors and all(nb not in comp_cins for nb in neighbors):
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
    
    # 1. Build background graph to freeze baseline parameters
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
    num_lenders = sum(1 for n, d in COMBINED_GRAPH.nodes(data=True) if d.get("type") == "lender")
    
    high_risk_clusters = sum(1 for c in CLUSTERS if c["cluster_risk_score"] >= 75.0)
    
    return {
        "total_companies": num_companies,
        "total_directors": num_directors,
        "total_addresses": num_addresses,
        "total_lenders": num_lenders,
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
            "lenders_count": c.get("lenders_count", 0),
            "defaulters_count": c.get("defaulters_count", 0),
            "average_company_risk": c["average_company_risk"],
            "date_spread_days": c["date_spread_days"],
            "network_density": c["network_density"],
            "cluster_risk_score": c["cluster_risk_score"]
        })
    return summary_clusters

@app.get("/api/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: int):
    """
    Returns full detail of a specific cluster, enriched with database loan/default data.
    """
    if CLUSTERS is None:
        raise HTTPException(status_code=503, detail="Graph service is warming up.")
        
    db = SessionLocal()
    try:
        for c in CLUSTERS:
            if c["cluster_id"] == cluster_id:
                company_details = []
                for cin in c["companies"]:
                    res = SCORE_ENGINE.compute_scores(cin, COMBINED_GRAPH)
                    
                    # Fetch loans from database
                    loans_db = db.query(CersaiSecurityInterest).filter(CersaiSecurityInterest.cin == cin).all()
                    loans_list = [{
                        "lender_name": l.lender_name,
                        "security_type": l.security_type,
                        "asset_description": l.asset_description,
                        "charge_amount": float(l.charge_amount),
                        "charge_registration_date": l.charge_registration_date.isoformat() if l.charge_registration_date else None
                    } for l in loans_db]
                    
                    # Fetch defaults from database
                    defaults_db = db.query(RbiWilfulDefaulter).filter(RbiWilfulDefaulter.cin == cin).all()
                    defaults_list = [{
                        "lender_name": d.lender_name,
                        "default_amount": float(d.default_amount),
                        "classification_date": d.classification_date.isoformat() if d.classification_date else None,
                        "wilful_default_reason": d.wilful_default_reason
                    } for d in defaults_db]
                    
                    company_details.append({
                        "cin": cin,
                        "name": res["name"],
                        "scores": res["scores"],
                        "incorporation_date": COMBINED_GRAPH.nodes[cin].get("incorporation_date"),
                        "filing_status": res["raw_signals"]["filing_status"],
                        "paidup_capital": res["raw_signals"]["paidup_capital"],
                        "loans": loans_list,
                        "defaults": defaults_list
                    })
                
                return {
                    **c,
                    "companies_detailed": company_details
                }
    finally:
        db.close()
            
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
            # Collect all nodes in this cluster (companies, directors, addresses, lenders)
            all_nodes = c["companies"] + c["directors"] + c["addresses"] + c.get("lenders", [])
            subg = G_SERVICE.get_subgraph_for_nodes(all_nodes)
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
        
    # 4. Lenders (CERSAI)
    lenders = [n for n in COMBINED_GRAPH.neighbors(cin) if COMBINED_GRAPH.nodes[n].get("type") == "lender"]
    if lenders:
        logs.append(f"Active loan registration detected: Linked to lenders: {', '.join(lenders)} (Risk Score: {res['scores']['lender_risk']:.1f}/100).")
    else:
        logs.append("No active loan registration detected.")
        
    # 5. Defaulter (RBI)
    if res["raw_signals"]["wilful_defaulter_flag"]:
        logs.append(f"RBI Defaulter Alert: Classified as a Wilful Defaulter by RBI registry (Risk Score: 100.0/100).")
    else:
        logs.append("RBI clean profile: Not listed in RBI defaulter index.")
        
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
        
    # Find rank of clusters containing Ring A, Ring B, Ring C members
    ring_a_rank = -1
    ring_b_rank = -1
    ring_c_rank = -1
    legit_edge_rank = -1
    
    for idx, c in enumerate(CLUSTERS):
        c_labels = [COMBINED_GRAPH.nodes[cin].get("ground_truth_label") for cin in c["companies"]]
        if ring_a_rank == -1 and "fraud_ring_A" in c_labels:
            ring_a_rank = idx + 1
        if ring_b_rank == -1 and "fraud_ring_B" in c_labels:
            ring_b_rank = idx + 1
        if ring_c_rank == -1 and "fraud_ring_C" in c_labels:
            ring_c_rank = idx + 1
        if legit_edge_rank == -1 and "legit_edge_case" in c_labels:
            legit_edge_rank = idx + 1
            
    # Count total ground truth shell companies and false positives
    total_shells = 0
    detected_shells = 0
    false_positives = 0
    total_bg = 0
    
    for node, data in COMBINED_GRAPH.nodes(data=True):
        if data.get("type") == "company":
            label = data.get("ground_truth_label", "normal")
            res = SCORE_ENGINE.compute_scores(node, COMBINED_GRAPH)
            score = res["scores"]["composite_score"]
            
            if "fraud_ring" in label:
                total_shells += 1
                if score >= 50.0:
                    detected_shells += 1
            elif label == "normal":
                total_bg += 1
                if score >= 75.0:
                    false_positives += 1
                    
    detection_rate = (detected_shells / total_shells) * 100.0 if total_shells > 0 else 0.0
    false_positive_rate = (false_positives / total_bg) * 100.0 if total_bg > 0 else 0.0
    
    status = "PASS" if (ring_a_rank <= 2 and ring_b_rank <= 5 and ring_c_rank <= 5 and false_positive_rate < 5.0) else "FAIL"
    
    return {
        "real_companies": total_bg,
        "synthetic_fraud_companies": total_shells,
        "total_clusters": len(CLUSTERS),
        "ring_a_rank": ring_a_rank,
        "ring_b_rank": ring_b_rank,
        "ring_c_rank": ring_c_rank,
        "legit_edge_case_rank": legit_edge_rank,
        "detection_rate_pct": detection_rate,
        "false_positive_count": false_positives,
        "false_positive_rate_pct": false_positive_rate,
        "status": status
    }
