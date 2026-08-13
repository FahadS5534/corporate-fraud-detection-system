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
        
        # Load weights from env or use default 25% each
        self.w_addr = float(os.getenv("WEIGHT_ADDRESS_SIGNAL", 0.25))
        self.w_dir = float(os.getenv("WEIGHT_DIRECTOR_SIGNAL", 0.25))
        self.w_temp = float(os.getenv("WEIGHT_TEMPORAL_SIGNAL", 0.25))
        self.w_file = float(os.getenv("WEIGHT_FILING_SIGNAL", 0.25))
        
        # Normalize weights to sum to 1.0 just in case
        total_w = self.w_addr + self.w_dir + self.w_temp + self.w_file
        if total_w > 0:
            self.w_addr /= total_w
            self.w_dir /= total_w
            self.w_temp /= total_w
            self.w_file /= total_w

        if background_graph is not None:
            self.calculate_baseline_statistics(background_graph)

    def calculate_baseline_statistics(self, graph):
        """
        Calculates and freezes mean and standard deviation of graph metrics
        using the REAL background graph only.
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
                
                # 3. Burst counts (30 days default)
                burst_sig = engine.get_incorporation_burst_signal(node, window_days=30)
                burst_counts.append(burst_sig["burst_company_count"])
                
        # Calculate stats, avoiding 0 division by adding small epsilon
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
        """
        Calculates the z-score. If it exceeds z_threshold, maps it to a 0-100 score.
        """
        z = (val - mean) / std
        if z <= z_threshold:
            return 0.0
            
        # Scale linearly between z_threshold and max_val_cap
        ratio = (val - (mean + z_threshold * std)) / max_val_cap
        score = min(ratio * 100.0, 100.0)
        return float(max(score, 0.0))

    def compute_scores(self, company_cin, graph, window_days=30):
        """
        Computes individual risk signals and the weighted composite score for a company.
        """
        engine = SignalsEngine(graph)
        raw = engine.compute_all_raw_signals(company_cin, window_days)
        
        # 1. Address Risk (Normalizes based on background stats)
        # We cap maximum scale at 15 companies sharing
        s_addr = self.normalize_value(
            raw["address_degree"], 
            self.bg_stats["addr_mean"], 
            self.bg_stats["addr_std"], 
            z_threshold=2.0, 
            max_val_cap=12.0
        )
        
        # 2. Director Risk
        # We cap maximum scale at 8 companies sharing (common legal/practical limit)
        s_dir = self.normalize_value(
            raw["max_director_degree"], 
            self.bg_stats["dir_mean"], 
            self.bg_stats["dir_std"], 
            z_threshold=2.0, 
            max_val_cap=6.0
        )
        
        # 3. Temporal Burst Risk
        # 1 company = 0 risk, 2 companies = 20, 3 = 50, >=5 = 100
        burst_val = raw["burst_company_count"]
        if burst_val <= 1:
            s_temp = 0.0
        elif burst_val == 2:
            s_temp = 20.0
        elif burst_val == 3:
            s_temp = 50.0
        elif burst_val == 4:
            s_temp = 80.0
        else:
            s_temp = 100.0
            
        # 4. Capital/Filing Mismatch Risk
        s_file = 0.0
        if raw["is_zero_paidup"]:
            s_file += 50.0
        if raw["is_defaulter"]:
            s_file += 50.0
            
        # Weighted composite score (0-100)
        composite_score = (self.w_addr * s_addr) + (self.w_dir * s_dir) + (self.w_temp * s_temp) + (self.w_file * s_file)
        
        return {
            "cin": company_cin,
            "name": raw["name"],
            "raw_signals": raw,
            "scores": {
                "address_risk": float(s_addr),
                "director_risk": float(s_dir),
                "temporal_risk": float(s_temp),
                "capital_filing_risk": float(s_file),
                "composite_score": float(composite_score)
            }
        }
