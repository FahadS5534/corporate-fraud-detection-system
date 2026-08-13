import sys
sys.path.append(r"f:\SIH")

from backend.app.services.graph_service import GraphService
from backend.app.scoring.score_engine import ScoreEngine
from backend.app.services.community_service import CommunityService

def verify():
    # Build graph
    service = GraphService()
    graph = service.build_graph()
    
    # Initialize engines
    se = ScoreEngine(graph)
    cs = CommunityService(graph, se)
    
    # Detect clusters
    clusters = cs.detect_communities()
    
    print("\n--- LOUVAIN CLUSTER DETECTION VERIFICATION ---")
    print(f"Total Clusters Detected: {len(clusters)}")
    
    print("\nTop 5 Risk Clusters:")
    for idx, c in enumerate(clusters[:5]):
        print(f"\nCluster Rank #{idx+1} (ID: {c['cluster_id']})")
        print(f" Risk Score: {c['cluster_risk_score']:.2f}")
        print(f" Companies:  {c['companies_count']}")
        print(f" Directors:  {c['directors_count']}")
        print(f" Addresses:  {c['addresses_count']}")
        print(f" Avg Company Risk: {c['average_company_risk']:.2f}")
        print(f" Date Spread: {c['date_spread_days']} days")
        print(f" Density:     {c['network_density']:.4f}")
        # Print first 3 company names
        sample_names = [graph.nodes[cin].get("name", "") for cin in c['companies'][:3]]
        print(f" Sample Companies: {', '.join(sample_names)}")
        
    service.close()

if __name__ == "__main__":
    verify()
