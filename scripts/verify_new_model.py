import urllib.request
import json
import sys

def verify_pipeline():
    url = "http://127.0.0.1:8000/api/evaluation"
    print(f"Requesting pipeline evaluation from {url}...")
    try:
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode('utf-8'))
        print(json.dumps(data, indent=2))
        
        status = data.get("status")
        detection_rate = data.get("detection_rate_pct")
        false_positive_rate = data.get("false_positive_rate_pct")
        ring_a = data.get("ring_a_rank")
        ring_b = data.get("ring_b_rank")
        ring_c = data.get("ring_c_rank")
        legit = data.get("legit_edge_case_rank")
        
        print("\n=== Validation Results ===")
        print(f"Status: {status}")
        print(f"Detection Rate: {detection_rate}%")
        print(f"False Positive Rate: {false_positive_rate}%")
        print(f"Ring A Rank: #{ring_a}")
        print(f"Ring B Rank: #{ring_b}")
        print(f"Ring C Rank: #{ring_c}")
        print(f"Legitimate CA Hub Rank: #{legit}")
        
        assert status == "PASS", "Error: Pipeline status is NOT PASS!"
        assert detection_rate == 100.0, "Error: Shell detection rate is not 100%!"
        assert false_positive_rate < 5.0, f"Error: False positive rate too high ({false_positive_rate}%)!"
        assert ring_a in [1, 2, 3], f"Error: Ring A rank is #{ring_a}, expected top 3!"
        assert ring_b in [1, 2, 3], f"Error: Ring B rank is #{ring_b}, expected top 3!"
        assert ring_c in [1, 2, 3], f"Error: Ring C rank is #{ring_c}, expected top 3!"
        
        print("\nALL BENCHMARKS PASSED SUCCESSFULLY! The 5-factor scoring model has achieved 100% detection rate and clear segregation.")
        sys.exit(0)
    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_pipeline()
