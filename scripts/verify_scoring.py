import sys
sys.path.append(r"f:\SIH")

from backend.app.services.graph_service import GraphService
from backend.app.scoring.score_engine import ScoreEngine

def verify():
    # Build graph
    service = GraphService()
    graph = service.build_graph()
    
    # Initialize Score Engine (calculates and freezes stats)
    engine = ScoreEngine(graph)
    
    # Find:
    # 1. A TATA Steel Subsidiary
    # 2. A company at the CA Address
    # 3. A general background company
    
    tata_cin = None
    ca_cin = None
    general_cin = None
    
    for node, data in graph.nodes(data=True):
        if data.get("type") == "company":
            name = data.get("name", "")
            if "TATA STEEL SUBSIDIARY" in name:
                tata_cin = node
            elif "MERLIN CHAMBERS" in graph.nodes[list(graph.neighbors(node))[0]].get("raw_address", ""):
                ca_cin = node
            elif tata_cin and ca_cin and not general_cin:
                if "TATA" not in name and "MERLIN" not in name:
                    general_cin = node
                    
    print("\n--- COMPOSITE RISK SCORES VERIFICATION ---")
    
    for label, cin in [("TATA Subsidiary", tata_cin), ("CA Address Co", ca_cin), ("General Co", general_cin)]:
        if cin:
            res = engine.compute_scores(cin, graph)
            print(f"\nEntity: {label} (CIN: {cin})")
            print(f" Name: {res['name']}")
            print(f" Raw Address Degree: {res['raw_signals']['address_degree']}")
            print(f" Raw Max Director Degree: {res['raw_signals']['max_director_degree']}")
            print(f" Raw Burst size: {res['raw_signals']['burst_company_count']}")
            print(f" Risk Signals Breakdown:")
            print(f"  - Address Risk:       {res['scores']['address_risk']:.2f}")
            print(f"  - Director Risk:      {res['scores']['director_risk']:.2f}")
            print(f"  - Temporal Risk:      {res['scores']['temporal_risk']:.2f}")
            print(f"  - Capital/Filing Risk: {res['scores']['capital_filing_risk']:.2f}")
            print(f" Composite Network Risk Score: {res['scores']['composite_score']:.2f} / 100")
        else:
            print(f"\nEntity: {label} - NOT FOUND")
            
    service.close()

if __name__ == "__main__":
    verify()
