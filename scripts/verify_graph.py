import sys
sys.path.append(r"f:\SIH")

from backend.app.services.graph_service import GraphService

def verify():
    service = GraphService()
    try:
        graph = service.build_graph()
        print("\n--- GRAPH VERIFICATION REPORT ---")
        print(f"Total Nodes: {graph.number_of_nodes()}")
        print(f"Total Edges: {graph.number_of_edges()}")
        
        # Verify node types count
        types = {}
        for node, data in graph.nodes(data=True):
            ntype = data.get("type")
            types[ntype] = types.get(ntype, 0) + 1
            
        print("Nodes by Type:")
        for t, cnt in types.items():
            print(f" - {t}: {cnt}")
            
        # Verify edges count by relationship
        rels = {}
        for u, v, data in graph.edges(data=True):
            rel = data.get("relation")
            rels[rel] = rels.get(rel, 0) + 1
            
        print("Edges by Relation:")
        for r, cnt in rels.items():
            print(f" - {r}: {cnt}")
            
        # Test Cytoscape export
        elements = service.to_cytoscape_json()
        print(f"Cytoscape export has {len(elements)} elements.")
        print("Graph verification successful!")
    except Exception as e:
        print(f"Verification failed: {e}")
    finally:
        service.close()

if __name__ == "__main__":
    verify()
