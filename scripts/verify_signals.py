import sys
sys.path.append(r"f:\SIH")

from backend.app.services.graph_service import GraphService
from backend.app.services.signals import SignalsEngine

def verify():
    # Build graph
    service = GraphService()
    graph = service.build_graph()
    
    # Initialize Signals Engine
    engine = SignalsEngine(graph)
    
    # Let's find:
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
                # Connected to CA address
                ca_cin = node
            elif tata_cin and ca_cin and not general_cin:
                # A general company
                if "TATA" not in name and "MERLIN" not in name:
                    general_cin = node
                    
    print("\n--- RAW SIGNALS VERIFICATION ---")
    
    for label, cin in [("TATA Subsidiary", tata_cin), ("CA Address Co", ca_cin), ("General Co", general_cin)]:
        if cin:
            signals = engine.compute_all_raw_signals(cin)
            print(f"\nEntity: {label} (CIN: {cin})")
            print(f" Name: {signals['name']}")
            print(f" Address Degree: {signals['address_degree']}")
            print(f" Max Director Degree: {signals['max_director_degree']}")
            print(f" Burst Company Count (30d): {signals['burst_company_count']}")
            print(f" Capital: Auth={signals['authorized_capital']}, Paid={signals['paidup_capital']}")
            print(f" Filing Status: {signals['filing_status']} (Defaulter={signals['is_defaulter']}, Zero Paid-up={signals['is_zero_paidup']})")
        else:
            print(f"\nEntity: {label} - NOT FOUND")
            
    service.close()

if __name__ == "__main__":
    verify()
