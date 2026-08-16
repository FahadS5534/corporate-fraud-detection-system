import os
import sys
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

class SignalsEngine:
    def __init__(self, graph):
        self.graph = graph

    def get_address_signal(self, company_cin):
        """
        Returns the number of companies registered at the same address.
        """
        if not self.graph.has_node(company_cin):
            return {"address_degree": 0, "address": None}
            
        # Find the address node connected to the company
        address_nodes = [n for n in self.graph.neighbors(company_cin) 
                         if self.graph.nodes[n].get("type") == "address"]
        
        if not address_nodes:
            return {"address_degree": 0, "address": None}
            
        addr_node = address_nodes[0]
        # Degree of address node represents number of companies connected to it
        company_count = self.graph.degree(addr_node)
        
        return {
            "address_degree": company_count,
            "address": addr_node
        }

    def get_director_signal(self, company_cin):
        """
        Returns the maximum company count for any director of this company,
        and details of all directors and their company counts.
        """
        if not self.graph.has_node(company_cin):
            return {"max_director_degree": 0, "directors": []}
            
        # Find all director nodes connected to the company
        director_nodes = [n for n in self.graph.neighbors(company_cin) 
                          if self.graph.nodes[n].get("type") == "director"]
        
        directors_details = []
        max_degree = 0
        
        for d_node in director_nodes:
            # Degree of director node represents number of companies they are registered with
            deg = self.graph.degree(d_node)
            max_degree = max(max_degree, deg)
            directors_details.append({
                "din": d_node,
                "name": self.graph.nodes[d_node].get("name", ""),
                "degree": deg
            })
            
        return {
            "max_director_degree": max_degree,
            "directors": directors_details
        }

    def get_incorporation_burst_signal(self, company_cin, window_days=30):
        """
        Calculates if there is a burst of registrations within window_days
        among companies sharing directors or addresses with this company.
        """
        if not self.graph.has_node(company_cin):
            return {"burst_company_count": 0, "related_companies": []}
            
        comp_data = self.graph.nodes[company_cin]
        comp_date_str = comp_data.get("incorporation_date", "")
        if not comp_date_str:
            return {"burst_company_count": 0, "related_companies": []}
            
        comp_date = datetime.strptime(comp_date_str, "%Y-%m-%d").date()
        
        # Collect all related companies (sharing address or directors)
        related_companies = set()
        
        # 1. Address sharing companies
        addr_info = self.get_address_signal(company_cin)
        addr = addr_info["address"]
        if addr:
            for neighbor in self.graph.neighbors(addr):
                if neighbor != company_cin and self.graph.nodes[neighbor].get("type") == "company":
                    related_companies.add(neighbor)
                    
        # 2. Director sharing companies
        dir_info = self.get_director_signal(company_cin)
        for d in dir_info["directors"]:
            for neighbor in self.graph.neighbors(d["din"]):
                if neighbor != company_cin and self.graph.nodes[neighbor].get("type") == "company":
                    related_companies.add(neighbor)
                    
        # Filter related companies registered within the window of target company's date
        burst_companies = []
        for rc in related_companies:
            rc_date_str = self.graph.nodes[rc].get("incorporation_date", "")
            if rc_date_str:
                rc_date = datetime.strptime(rc_date_str, "%Y-%m-%d").date()
                diff_days = abs((rc_date - comp_date).days)
                if diff_days <= window_days:
                    burst_companies.append({
                        "cin": rc,
                        "name": self.graph.nodes[rc].get("name", ""),
                        "incorporation_date": rc_date_str,
                        "difference_days": diff_days
                    })
                    
        return {
            "burst_company_count": len(burst_companies) + 1, # Including self
            "related_companies": burst_companies
        }

    def get_capital_filing_signal(self, company_cin):
        """
        Exposes capital structure and filing status risks.
        """
        if not self.graph.has_node(company_cin):
            return {
                "auth_capital": 0.0,
                "paidup_capital": 0.0,
                "paidup_ratio": 1.0,
                "filing_status": "Unknown",
                "is_zero_paidup": False,
                "is_defaulter": False
            }
            
        comp_data = self.graph.nodes[company_cin]
        auth = float(comp_data.get("authorized_capital", 0.0))
        paid = float(comp_data.get("paidup_capital", 0.0))
        filing = comp_data.get("filing_status", "Filed")
        
        ratio = (paid / auth) if auth > 0 else 1.0
        
        is_zero_paidup = (paid <= 0.0)
        is_defaulter = (filing in ["Defaulter", "Nil Filed"])
        
        return {
            "auth_capital": auth,
            "paidup_capital": paid,
            "paidup_ratio": ratio,
            "filing_status": filing,
            "is_zero_paidup": is_zero_paidup,
            "is_defaulter": is_defaulter
        }

    def get_ground_truth_signal(self, company_cin):
        if not self.graph.has_node(company_cin):
            return {
                "synthetic_shell_ground_truth": "No",
                "synthetic_ring_id": None
            }
        comp_data = self.graph.nodes[company_cin]
        label = comp_data.get("ground_truth_label", "normal")
        is_shell = "Yes" if "fraud_ring" in label else "No"
        ring_id = label if "fraud_ring" in label or label == "legit_edge_case" else None
        return {
            "synthetic_shell_ground_truth": is_shell,
            "synthetic_ring_id": ring_id
        }

    def get_rbi_defaulter_signal(self, company_cin):
        if not self.graph.has_node(company_cin):
            return {"wilful_defaulter": False}
        comp_data = self.graph.nodes[company_cin]
        return {
            "wilful_defaulter": comp_data.get("wilful_defaulter_flag", False)
        }

    def compute_all_raw_signals(self, company_cin, window_days=30):
        """
        Returns a combined dictionary of all raw features.
        """
        addr = self.get_address_signal(company_cin)
        dirs = self.get_director_signal(company_cin)
        burst = self.get_incorporation_burst_signal(company_cin, window_days)
        cap = self.get_capital_filing_signal(company_cin)
        gt = self.get_ground_truth_signal(company_cin)
        rbi = self.get_rbi_defaulter_signal(company_cin)
        
        return {
            "cin": company_cin,
            "name": self.graph.nodes[company_cin].get("name", ""),
            "address_degree": addr["address_degree"],
            "max_director_degree": dirs["max_director_degree"],
            "burst_company_count": burst["burst_company_count"],
            "authorized_capital": cap["auth_capital"],
            "paidup_capital": cap["paidup_capital"],
            "paidup_ratio": cap["paidup_ratio"],
            "filing_status": cap["filing_status"],
            "is_zero_paidup": cap["is_zero_paidup"],
            "is_defaulter": cap["is_defaulter"],
            "synthetic_shell_ground_truth": gt["synthetic_shell_ground_truth"],
            "synthetic_ring_id": gt["synthetic_ring_id"],
            "wilful_defaulter_flag": rbi["wilful_defaulter"]
        }
