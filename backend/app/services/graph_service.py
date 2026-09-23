import os
import sys
import re
import math
import networkx as nx
from datetime import date
from sqlalchemy.orm import Session

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.database import SessionLocal
from backend.app.models.models import (
    Company,
    DirectorRelationship,
    CersaiSecurityInterest,
    RbiWilfulDefaulter,
    GroundTruth
)

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

def geocode_address_offline(address_str):
    if not address_str:
        return 28.6139, 77.2090
    address_upper = str(address_str).upper()
    
    # Major corporate hubs in India
    cities = {
        "MUMBAI": (19.0760, 72.8777),
        "BOMBAY": (19.0760, 72.8777),
        "DELHI": (28.6139, 77.2090),
        "NEW DELHI": (28.6139, 77.2090),
        "NOIDA": (28.5355, 77.3910),
        "GURGAON": (28.4595, 77.0266),
        "GURUGRAM": (28.4595, 77.0266),
        "BANGALORE": (12.9716, 77.5946),
        "BENGALURU": (12.9716, 77.5946),
        "CHENNAI": (13.0827, 80.2707),
        "MADRAS": (13.0827, 80.2707),
        "KOLKATA": (22.5726, 88.3639),
        "CALCUTTA": (22.5726, 88.3639),
        "HYDERABAD": (17.3850, 78.4867),
        "PUNE": (18.5204, 73.8567),
        "AHMEDABAD": (23.0225, 72.5714),
        "JAIPUR": (26.9124, 75.7873),
        "LUCKNOW": (26.8467, 80.9462),
    }
    
    base_lat, base_lng = 28.6139, 77.2090
    for city, coords in cities.items():
        if city in address_upper:
            base_lat, base_lng = coords
            break
            
    import hashlib
    addr_hash = int(hashlib.md5(address_str.encode('utf-8')).hexdigest(), 16)
    
    # Deterministic scatter (jitter) within ~3km so they scatter nicely around the city hub
    jitter_lat = ((addr_hash % 1000) / 1000.0 - 0.5) * 0.03
    jitter_lng = (((addr_hash // 1000) % 1000) / 1000.0 - 0.5) * 0.03
    
    return base_lat + jitter_lat, base_lng + jitter_lng

class GraphService:
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.graph = nx.Graph()

    def build_graph(self):
        """
        Loads companies, director relationships, CERSAI loans, and RBI defaulters from database
        and constructs the in-memory NetworkX relationship graph.
        """
        self.graph.clear()
        
        # 1. Fetch all companies from DB
        companies = self.db.query(Company).all()
        print(f"GraphService: Loading {len(companies)} companies into graph...")
        
        for comp in companies:
            norm_addr = normalize_address(comp.registered_office_address)
            
            # Add Company Node
            self.graph.add_node(
                comp.cin,
                type="company",
                name=comp.company_name,
                status=comp.company_status,
                incorporation_date=comp.date_of_registration.isoformat() if comp.date_of_registration else "",
                authorized_capital=float(comp.authorized_capital),
                paidup_capital=float(comp.paidup_capital),
                filing_status=comp.filing_status,
                wilful_defaulter_flag=False,
                ground_truth_label="normal"
            )
            
            # Add Address Node if valid
            if norm_addr:
                if not self.graph.has_node(norm_addr):
                    lat, lng = geocode_address_offline(norm_addr)
                    self.graph.add_node(
                        norm_addr,
                        type="address",
                        raw_address=comp.registered_office_address,
                        latitude=lat,
                        longitude=lng
                    )
                # Add edge: Company is REGISTERED_AT Address
                self.graph.add_edge(comp.cin, norm_addr, relation="REGISTERED_AT", weight=1.0)

        # 2. Fetch all director relationships
        relations = self.db.query(DirectorRelationship).all()
        print(f"GraphService: Loading {len(relations)} director relationships into graph...")
        
        for rel in relations:
            din = str(rel.din)
            if not self.graph.has_node(din):
                self.graph.add_node(
                    din,
                    type="director",
                    name=rel.director_name
                )
            if self.graph.has_node(rel.cin):
                # Calculate edge weight based on active status and resignation date
                if not bool(rel.is_active) and rel.resignation_date:
                    years_since = (date.today() - rel.resignation_date).days / 365.25
                    weight = math.exp(-0.5 * max(0.0, years_since))
                else:
                    weight = 1.0
                self.graph.add_edge(
                    din,
                    rel.cin,
                    relation="DIRECTOR_OF",
                    weight=weight,
                    is_active=bool(rel.is_active),
                    appointment_date=rel.appointment_date.isoformat() if rel.appointment_date else None,
                    resignation_date=rel.resignation_date.isoformat() if rel.resignation_date else None,
                )

        # 3. Fetch all CERSAI Loans (Lenders)
        loans = self.db.query(CersaiSecurityInterest).all()
        print(f"GraphService: Loading {len(loans)} CERSAI loans into graph...")
        
        for loan in loans:
            lender = loan.lender_name
            if not self.graph.has_node(lender):
                self.graph.add_node(
                    lender,
                    type="lender",
                    name=lender
                )
            if self.graph.has_node(loan.cin):
                self.graph.add_edge(loan.cin, lender, relation="LENDER_OF", weight=1.0)

        # 4. Fetch all RBI Defaulters
        defaulters = self.db.query(RbiWilfulDefaulter).all()
        print(f"GraphService: Loading {len(defaulters)} RBI defaulters...")
        for d in defaulters:
            if self.graph.has_node(d.cin):
                self.graph.nodes[d.cin]["wilful_defaulter_flag"] = True

        # 5. Fetch Ground Truth Labels
        gt_labels = self.db.query(GroundTruth).all()
        print(f"GraphService: Loading {len(gt_labels)} Ground Truth labels into graph...")
        for gt in gt_labels:
            if self.graph.has_node(gt.cin):
                self.graph.nodes[gt.cin]["ground_truth_label"] = gt.label

        print(f"GraphService: Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
        return self.graph

    def get_neighbors(self, node_id):
        if not self.graph.has_node(node_id):
            return []
        return list(self.graph.neighbors(node_id))

    def get_subgraph_for_nodes(self, node_list):
        sub_nodes = set(node_list)
        for node in node_list:
            if self.graph.has_node(node):
                sub_nodes.update(self.graph.neighbors(node))
        return self.graph.subgraph(sub_nodes)

    def to_cytoscape_json(self, custom_graph=None):
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

    def add_director_relationship_incrementally(self, cin, din, director_name, is_active=True, resignation_date=None):
        """
        Dynamically adds/updates a director relationship in the NetworkX graph in-memory.
        """
        # 1. Add/Update Director node
        if not self.graph.has_node(din):
            self.graph.add_node(din, type="director", name=director_name)
        else:
            self.graph.nodes[din]["name"] = director_name
        
        # 2. Add/Update edge
        if not self.graph.has_node(cin):
            company = self.db.query(Company).filter(Company.cin == cin).one_or_none()
            if company is None:
                raise ValueError(f"Company {cin} does not exist")
            norm_addr = normalize_address(company.registered_office_address)
            self.graph.add_node(
                cin,
                type="company",
                name=company.company_name,
                status=company.company_status,
                incorporation_date=company.date_of_registration.isoformat() if company.date_of_registration else "",
                authorized_capital=float(company.authorized_capital),
                paidup_capital=float(company.paidup_capital),
                filing_status=company.filing_status,
                wilful_defaulter_flag=False,
                ground_truth_label="normal",
            )
            if norm_addr:
                if not self.graph.has_node(norm_addr):
                    lat, lng = geocode_address_offline(norm_addr)
                    self.graph.add_node(
                        norm_addr,
                        type="address",
                        raw_address=company.registered_office_address,
                        latitude=lat,
                        longitude=lng,
                    )
                self.graph.add_edge(cin, norm_addr, relation="REGISTERED_AT", weight=1.0)

        if not self.graph.has_node(cin):
            raise ValueError(f"Company {cin} does not exist")

        if not is_active and resignation_date:
            years_since = (date.today() - resignation_date).days / 365.25
            weight = math.exp(-0.5 * max(0.0, years_since))
        else:
            weight = 1.0

        self.graph.add_edge(
            din,
            cin,
            relation="DIRECTOR_OF",
            weight=weight,
            is_active=bool(is_active),
            resignation_date=resignation_date.isoformat() if resignation_date else None,
        )
        print(f"GraphService: Incrementally updated relationship {din} -> {cin} with weight={weight}")

    def close(self):
        self.db.close()
