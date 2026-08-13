import os
import sys
import re
import networkx as nx
from sqlalchemy.orm import Session

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.database import SessionLocal
from backend.app.models.models import Company, DirectorRelationship

def normalize_address(address_str):
    if not address_str:
        return ""
    # Convert to uppercase
    clean = str(address_str).upper()
    # Replace common punctuation with spaces
    clean = re.sub(r'[,.\-;:/\\]', ' ', clean)
    # Collapse multiple whitespaces into a single space
    clean = " ".join(clean.split())
    return clean

class GraphService:
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.graph = nx.Graph()

    def build_graph(self):
        """
        Loads companies and director relationships from database
        and constructs the in-memory NetworkX relationship graph.
        """
        self.graph.clear()
        
        # 1. Fetch all companies from DB
        companies = self.db.query(Company).all()
        print(f"GraphService: Loading {len(companies)} companies into graph...")
        
        for comp in companies:
            # Normalize registered address
            norm_addr = normalize_address(comp.registered_office_address)
            
            # Add Company Node
            self.graph.add_node(
                comp.cin,
                type="company",
                name=comp.company_name,
                status=comp.company_status,
                incorporation_date=comp.date_of_incorporation.isoformat() if comp.date_of_incorporation else "",
                authorized_capital=float(comp.authorized_capital),
                paidup_capital=float(comp.paidup_capital),
                filing_status=comp.filing_status,
                roc_code=comp.roc_code
            )
            
            # Add Address Node if valid
            if norm_addr:
                if not self.graph.has_node(norm_addr):
                    self.graph.add_node(
                        norm_addr,
                        type="address",
                        raw_address=comp.registered_office_address
                    )
                # Add edge: Company is REGISTERED_AT Address
                self.graph.add_edge(comp.cin, norm_addr, relation="REGISTERED_AT")

        # 2. Fetch all director relationships
        relations = self.db.query(DirectorRelationship).all()
        print(f"GraphService: Loading {len(relations)} relationships into graph...")
        
        for rel in relations:
            din = rel.din
            # Add Director Node if not exists
            if not self.graph.has_node(din):
                self.graph.add_node(
                    din,
                    type="director",
                    name=rel.director_name
                )
                
            # Add edge: Director is a DIRECTOR_OF Company (if company node exists)
            if self.graph.has_node(rel.cin):
                self.graph.add_edge(din, rel.cin, relation="DIRECTOR_OF", designation=rel.designation)

        print(f"GraphService: Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
        return self.graph

    def get_neighbors(self, node_id):
        if not self.graph.has_node(node_id):
            return []
        return list(self.graph.neighbors(node_id))

    def get_subgraph_for_nodes(self, node_list):
        """
        Extracts a subgraph containing the specified nodes and their direct connections.
        """
        # Collect nodes and their immediate neighbors
        sub_nodes = set(node_list)
        for node in node_list:
            if self.graph.has_node(node):
                sub_nodes.update(self.graph.neighbors(node))
        return self.graph.subgraph(sub_nodes)

    def to_cytoscape_json(self, custom_graph=None):
        """
        Converts the NetworkX graph to Cytoscape.js compatible JSON format.
        """
        g = custom_graph if custom_graph is not None else self.graph
        elements = []
        
        # Add Nodes
        for node_id, data in g.nodes(data=True):
            elements.append({
                "data": {
                    "id": node_id,
                    "label": data.get("name", node_id),
                    **data
                }
            })
            
        # Add Edges
        for source, target, data in g.edges(data=True):
            elements.append({
                "data": {
                    "id": f"{source}_{target}",
                    "source": source,
                    "target": target,
                    **data
                }
            })
            
        return elements

    def close(self):
        self.db.close()
