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
    # 1. A shell company
    # 2. A background company
    
    shell_cin = None
    background_cin = None
    
    for node, data in graph.nodes(data=True):
        if data.get("type") == "company":
            gt = data.get("synthetic_shell_ground_truth", "No")
            if gt == "Yes" and shell_cin is None:
                shell_cin = node
            elif gt == "No" and background_cin is None:
                background_cin = node
                    
    print("\n--- COMPOSITE RISK SCORES VERIFICATION ---")
    
    targets = [
        ("Ground-Truth Shell Company", shell_cin),
        ("Background Company", background_cin)
    ]

    for label, cin in targets:
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
            print(f"  - Ground Truth Risk:   {res['scores']['ground_truth_risk']:.2f}")
            print(f" Composite Network Risk Score: {res['scores']['composite_score']:.2f} / 100")
        else:
            print(f"\nEntity: {label} - NOT FOUND")
            
    service.close()

if __name__ == "__main__":
    verify()
