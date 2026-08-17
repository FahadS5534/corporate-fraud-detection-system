import os
import sys
import numpy as np
from backend.app.services.signals import SignalsEngine

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

class ScoreEngine:
    def __init__(self, background_graph=None):
        self.bg_stats = {
            "addr_mean": 1.0, "addr_std": 0.5,
            "dir_mean": 1.0, "dir_std": 0.5,
            "burst_mean": 1.0, "burst_std": 0.5
        }
        
        if background_graph is not None:
            self.calculate_baseline_statistics(background_graph)

    def calculate_baseline_statistics(self, graph):
        """
        Calculates and freezes mean and standard deviation of graph metrics
        using the REAL background (normal) graph only.
        """
        engine = SignalsEngine(graph)
        
        addr_degrees = []
        dir_degrees = []
        burst_counts = []
        
        for node, data in graph.nodes(data=True):
            if data.get("type") == "company":
                # 1. Address degrees
                addr_sig = engine.get_address_signal(node)
                addr_degrees.append(addr_sig["address_degree"])
                
                # 2. Director degrees
                dir_sig = engine.get_director_signal(node)
                dir_degrees.append(dir_sig["max_director_degree"])
                
                # 3. Burst counts (30 days)
                burst_sig = engine.get_incorporation_burst_signal(node, window_days=30)
                burst_counts.append(burst_sig["burst_company_count"])
                
        # Calculate stats, avoiding 0 division by using max std epsilon
        self.bg_stats["addr_mean"] = float(np.mean(addr_degrees)) if addr_degrees else 1.0
        self.bg_stats["addr_std"] = max(float(np.std(addr_degrees)), 0.1) if addr_degrees else 0.5
        
        self.bg_stats["dir_mean"] = float(np.mean(dir_degrees)) if dir_degrees else 1.0
        self.bg_stats["dir_std"] = max(float(np.std(dir_degrees)), 0.1) if dir_degrees else 0.5
        
        self.bg_stats["burst_mean"] = float(np.mean(burst_counts)) if burst_counts else 1.0
        self.bg_stats["burst_std"] = max(float(np.std(burst_counts)), 0.1) if burst_counts else 0.5
        
        print("\n--- FROZEN BACKGROUND STATISTICS ---")
        print(f"Address Degree:  mean={self.bg_stats['addr_mean']:.4f}, std={self.bg_stats['addr_std']:.4f}")
        print(f"Director Degree: mean={self.bg_stats['dir_mean']:.4f}, std={self.bg_stats['dir_std']:.4f}")
        print(f"Burst Count:     mean={self.bg_stats['burst_mean']:.4f}, std={self.bg_stats['burst_std']:.4f}")
        print("------------------------------------\n")

    def normalize_value(self, val, mean, std, z_threshold=2.0, max_val_cap=8.0):
        z = (val - mean) / std
        if z <= z_threshold:
            return 0.0
            
        # Scale linearly between z_threshold and max_val_cap
        ratio = (val - (mean + z_threshold * std)) / max_val_cap
        score = min(ratio * 100.0, 100.0)
        return float(max(score, 0.0))

    def compute_scores(self, company_cin, graph, window_days=30):
        """
        Computes individual risk signals and the weighted 5-factor composite score.
        """
        from backend.app.database import SessionLocal
        from backend.app.models.models import CersaiSecurityInterest, RbiWilfulDefaulter

        engine = SignalsEngine(graph)
        raw = engine.compute_all_raw_signals(company_cin, window_days)
        
        # 1. Address Risk (0.20 weight)
        z_addr = (raw["address_degree"] - self.bg_stats["addr_mean"]) / self.bg_stats["addr_std"]
        s_addr = min((z_addr / 3.0) * 100.0, 100.0) if z_addr > 0.0 else 0.0
        
        # 2. Director Risk (0.20 weight)
        # Calculate the average director boarding rate instead of the max
        directors = [n for n in graph.neighbors(company_cin) if graph.nodes[n].get("type") == "director"]
        dir_degrees = [graph.degree(d) for d in directors]
        avg_dir_degree = float(np.mean(dir_degrees)) if dir_degrees else self.bg_stats["dir_mean"]
        z_dir = (avg_dir_degree - self.bg_stats["dir_mean"]) / self.bg_stats["dir_std"]
        s_dir = min((z_dir / 3.0) * 100.0, 100.0) if z_dir > 0.0 else 0.0
        
        # 3. Temporal Burst Risk (0.15 weight)
        burst_val = raw["burst_company_count"]
        s_temp = min((max(0, burst_val - 1) / 4.0) * 100.0, 100.0)
            
        # 4. Lender Density & Leverage Risk (0.20 weight)
        # Find how many unique lenders are connected to this company
        lenders = [n for n in graph.neighbors(company_cin) if graph.nodes[n].get("type") == "lender"]
        num_lenders = len(lenders)
        s_lender_count = min((num_lenders / 3.0) * 100.0, 100.0)
        
        # Fetch actual loans from DB to compute debt-to-paidup-capital leverage
        db = SessionLocal()
        try:
            loans_db = db.query(CersaiSecurityInterest).filter(CersaiSecurityInterest.cin == company_cin).all()
            total_loans = float(sum(l.charge_amount for l in loans_db))
            
            defaults_db = db.query(RbiWilfulDefaulter).filter(RbiWilfulDefaulter.cin == company_cin).all()
            total_defaults = float(sum(d.default_amount for d in defaults_db))
        finally:
            db.close()
            
        paid_cap = max(1000.0, raw["paidup_capital"])
        leverage_ratio = total_loans / paid_cap
        s_leverage = min((leverage_ratio / 20.0) * 100.0, 100.0)
        
        s_lender = 0.5 * s_lender_count + 0.5 * s_leverage
            
        # 5. Defaulter & Capital Risk (0.25 weight)
        s_def_base = min((total_defaults / 10000000.0) * 100.0, 100.0) if raw["wilful_defaulter_flag"] else 0.0
        s_ratio = min((max(0.0, 1.0 - raw["paidup_ratio"]) / 0.99) * 100.0, 100.0)
        s_cap_size = max(0.0, 100.0 - (raw["paidup_capital"] / 5000.0))
        
        s_def = 0.5 * s_def_base + 0.25 * s_ratio + 0.25 * s_cap_size
            
        # Weighted composite score (0-100)
        composite_score = (0.20 * s_addr) + (0.20 * s_dir) + (0.15 * s_temp) + (0.20 * s_lender) + (0.25 * s_def)
        
        # Capital/Filing Mismatch Risk (optional descriptive display metric)
        s_file = 0.0
        if raw["is_zero_paidup"]:
            s_file += 50.0
        if raw["is_defaulter"]:
            s_file += 50.0

        return {
            "cin": company_cin,
            "name": raw["name"],
            "raw_signals": raw,
            "scores": {
                "address_risk": float(s_addr),
                "director_risk": float(s_dir),
                "temporal_risk": float(s_temp),
                "lender_risk": float(s_lender),
                "defaulter_risk": float(s_def),
                "capital_filing_risk": float(s_file),
                "composite_score": float(composite_score)
            }
        }
