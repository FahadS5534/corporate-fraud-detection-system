"""
graph_service.py — Multi-Source 4-Layer Graph Builder
======================================================
Builds a single connected networkx.Graph() from 4 CSV source tables:

  Layer 1 — Companies & Addresses : mca_companies.csv
  Layer 2 — Directors             : mca_directors.csv
  Layer 3 — Lenders               : cersai_security_interests.csv
  Layer 4 — Wilful Defaulters     : rbi_wilful_defaulters.csv (flags on company nodes)

No database / SQLAlchemy dependency. All data is read directly via pandas.
"""

import os
import re
import hashlib
import networkx as nx
import pandas as pd

# ---------------------------------------------------------------------------
# Resolve the project root regardless of where this file is imported from
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


# ---------------------------------------------------------------------------
# Address helpers
# ---------------------------------------------------------------------------

def normalize_address(address_str: str) -> str:
    """Uppercase + collapse whitespace + strip common punctuation."""
    if not address_str or pd.isna(address_str):
        return ""
    clean = str(address_str).upper()
    clean = re.sub(r"[,.\-;:/\\]", " ", clean)
    clean = " ".join(clean.split())
    return clean


def geocode_address_offline(address_str: str):
    """
    Deterministic offline geo-lookup: city keyword → base coords + small hash jitter.
    Returns (latitude, longitude).
    """
    if not address_str:
        return 28.6139, 77.2090

    address_upper = str(address_str).upper()

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

    addr_hash = int(hashlib.md5(address_str.encode("utf-8")).hexdigest(), 16)
    jitter_lat = ((addr_hash % 1000) / 1000.0 - 0.5) * 0.03
    jitter_lng = (((addr_hash // 1000) % 1000) / 1000.0 - 0.5) * 0.03

    return base_lat + jitter_lat, base_lng + jitter_lng


# ---------------------------------------------------------------------------
# Main Graph Builder
# ---------------------------------------------------------------------------

class MultiSourceGraphBuilder:
    """
    Builds and owns a single networkx.Graph() containing all 4 node layers.

    Node types
    ----------
    company  — keyed by CIN
    address  — keyed by normalized address string
    director — keyed by DIN
    lender   — keyed by LENDER_NAME
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or DATA_DIR
        self.graph = nx.Graph()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build_graph(self) -> nx.Graph:
        """
        Load all 4 CSVs and build the multi-layer graph.
        Returns the populated nx.Graph.
        """
        self.graph.clear()

        companies_df = pd.read_csv(
            os.path.join(self.data_dir, "mca_companies.csv"),
            dtype={"CIN": str},
        )
        directors_df = pd.read_csv(
            os.path.join(self.data_dir, "mca_directors.csv"),
            dtype={"CIN": str, "DIN": str},
        )
        cersai_df = pd.read_csv(
            os.path.join(self.data_dir, "cersai_security_interests.csv"),
            dtype={"CIN": str},
        )
        rbi_df = pd.read_csv(
            os.path.join(self.data_dir, "rbi_wilful_defaulters.csv"),
            dtype={"CIN": str},
        )

        wilful_defaulter_cins = set(rbi_df["CIN"].dropna().str.strip())

        self._add_layer1_companies_and_addresses(companies_df, wilful_defaulter_cins)
        self._add_layer2_directors(directors_df)
        self._add_layer3_lenders(cersai_df)

        n_nodes = self.graph.number_of_nodes()
        n_edges = self.graph.number_of_edges()
        n_companies = sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "company")
        n_directors = sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "director")
        n_addresses = sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "address")
        n_lenders = sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "lender")
        n_defaulters = sum(
            1 for _, d in self.graph.nodes(data=True)
            if d.get("type") == "company" and d.get("wilful_defaulter_flag")
        )

        print(f"MultiSourceGraphBuilder: Graph built successfully.")
        print(f"  Nodes : {n_nodes}  (companies={n_companies}, directors={n_directors}, "
              f"addresses={n_addresses}, lenders={n_lenders})")
        print(f"  Edges : {n_edges}")
        print(f"  Wilful defaulter flags set on {n_defaulters} company nodes.")

        return self.graph

    # ------------------------------------------------------------------
    # Layer 1 — Companies & Addresses
    # ------------------------------------------------------------------

    def _add_layer1_companies_and_addresses(
        self, df: pd.DataFrame, wilful_defaulter_cins: set
    ):
        """
        For each row in mca_companies:
          - Add company node (type='company')
          - Add address node (type='address') if address non-empty
          - Add CIN–address edge (relation='REGISTERED_AT')
          - Set wilful_defaulter_flag=True on matching companies
        """
        for _, row in df.iterrows():
            cin = str(row["CIN"]).strip()
            name = str(row.get("COMPANY_NAME", "")).strip()
            raw_addr = str(row.get("REGISTERED_OFFICE_ADDRESS", "")).strip()
            city = str(row.get("CITY", "")).strip()
            state = str(row.get("STATE", "")).strip()
            date_reg = str(row.get("DATE_OF_REGISTRATION", "")).strip()
            auth_cap = float(row["AUTHORIZED_CAPITAL"]) if pd.notna(row.get("AUTHORIZED_CAPITAL")) else 0.0
            paid_cap = float(row["PAIDUP_CAPITAL"]) if pd.notna(row.get("PAIDUP_CAPITAL")) else 0.0
            status = str(row.get("COMPANY_STATUS", "")).strip()

            is_defaulter = cin in wilful_defaulter_cins

            self.graph.add_node(
                cin,
                type="company",
                name=name,
                city=city,
                state=state,
                incorporation_date=date_reg,
                authorized_capital=auth_cap,
                paidup_capital=paid_cap,
                company_status=status,
                wilful_defaulter_flag=is_defaulter,
            )

            # Address node
            norm_addr = normalize_address(raw_addr)
            if norm_addr:
                if not self.graph.has_node(norm_addr):
                    lat, lng = geocode_address_offline(raw_addr)
                    self.graph.add_node(
                        norm_addr,
                        type="address",
                        raw_address=raw_addr,
                        latitude=lat,
                        longitude=lng,
                    )
                self.graph.add_edge(cin, norm_addr, relation="REGISTERED_AT")

    # ------------------------------------------------------------------
    # Layer 2 — Directors
    # ------------------------------------------------------------------

    def _add_layer2_directors(self, df: pd.DataFrame):
        """
        For each row in mca_directors:
          - Add director node (type='director') keyed by DIN
          - Add DIN–CIN edge (relation='DIRECTOR_OF')
        """
        for _, row in df.iterrows():
            din = str(row["DIN"]).strip()
            cin = str(row["CIN"]).strip()
            name = str(row.get("DIRECTOR_NAME", "")).strip()

            if not din or not cin:
                continue

            if not self.graph.has_node(din):
                self.graph.add_node(din, type="director", name=name)

            if self.graph.has_node(cin):
                self.graph.add_edge(din, cin, relation="DIRECTOR_OF")

    # ------------------------------------------------------------------
    # Layer 3 — Lenders
    # ------------------------------------------------------------------

    def _add_layer3_lenders(self, df: pd.DataFrame):
        """
        For each row in cersai_security_interests:
          - Add lender node (type='lender') keyed by LENDER_NAME
          - Add CIN–lender edge (relation='BORROWED_FROM')
        """
        for _, row in df.iterrows():
            cin = str(row["CIN"]).strip()
            lender = str(row.get("LENDER_NAME", "")).strip()

            if not lender or not cin:
                continue

            if not self.graph.has_node(lender):
                self.graph.add_node(lender, type="lender", name=lender)

            if self.graph.has_node(cin):
                self.graph.add_edge(cin, lender, relation="BORROWED_FROM")

    # ------------------------------------------------------------------
    # Utility helpers (used by API)
    # ------------------------------------------------------------------

    def get_neighbors(self, node_id: str):
        if not self.graph.has_node(node_id):
            return []
        return list(self.graph.neighbors(node_id))

    def get_subgraph_for_nodes(self, node_list):
        """Subgraph containing specified nodes plus all their direct neighbours."""
        sub_nodes = set(node_list)
        for node in node_list:
            if self.graph.has_node(node):
                sub_nodes.update(self.graph.neighbors(node))
        return self.graph.subgraph(sub_nodes)

    def to_cytoscape_json(self, custom_graph=None):
        """Returns Cytoscape.js-compatible element list for the graph (or a subgraph)."""
        g = custom_graph if custom_graph is not None else self.graph
        elements = []

        for node_id, data in g.nodes(data=True):
            elements.append({
                "data": {
                    "id": str(node_id),
                    "label": data.get("name", str(node_id)),
                    **{k: v for k, v in data.items()},
                }
            })

        for source, target, data in g.edges(data=True):
            elements.append({
                "data": {
                    "id": f"{source}__{target}",
                    "source": str(source),
                    "target": str(target),
                    **data,
                }
            })

        return elements

    def close(self):
        """No-op — kept for API compatibility with old GraphService."""
        pass


# ---------------------------------------------------------------------------
# Backward-compat alias so old imports don't break immediately
# ---------------------------------------------------------------------------
GraphService = MultiSourceGraphBuilder
