import os
import sys
import pandas as pd
import json
import random
from datetime import datetime, timedelta

# Set seed for reproducibility
random.seed(42)

# Path setups
RAW_DIR = r"f:\SIH\data\raw"
PROCESSED_DIR = r"f:\SIH\data\processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

# File paths
COMPANIES_RAW = os.path.join(RAW_DIR, "companies.csv")
DIRECTORS_RAW = os.path.join(RAW_DIR, "directors.csv")

def parse_raw_date(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "":
        return None
    date_str = str(date_val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    if " " in date_str:
        try:
            return datetime.strptime(date_str.split()[0], "%Y-%m-%d").date()
        except ValueError:
            pass
    raise ValueError(f"Date '{date_str}' doesn't match known formats")

def extract_city(address, state):
    address_upper = str(address).upper()
    for c in ["MUMBAI", "DELHI", "BENGALURU", "BANGALORE", "CHENNAI", "KOLKATA", "PUNE", "AHMEDABAD", "JAIPUR", "LUCKNOW", "HYDERABAD"]:
        if c in address_upper:
            return c.title()
    return str(state).strip()

def validate_companies(df):
    report = {
        "total_records": len(df),
        "missing_values": {},
        "duplicate_cins": 0,
        "invalid_dates": 0,
        "invalid_capital": 0,
        "missing_addresses": 0,
        "errors": []
    }
    
    for col in df.columns:
        missing_count = int(df[col].isna().sum())
        if missing_count > 0:
            report["missing_values"][col] = missing_count
            
    valid_mask = pd.Series(True, index=df.index)
    
    # Duplicate CIN check
    report["duplicate_cins"] = int(df.duplicated(subset=['cin']).sum())
    valid_mask &= ~df.duplicated(subset=['cin'], keep='first')
    
    today = datetime.today().date()
    for idx, row in df.iterrows():
        # Date validation
        date_str = str(row['date_of_registration']).strip()
        is_valid = True
        if pd.isna(row['date_of_registration']) or date_str == "":
            is_valid = False
            issue = "Missing date of registration"
        else:
            try:
                dt = parse_raw_date(date_str)
                if dt is None:
                    is_valid = False
                    issue = "Missing date of registration"
                elif dt > today:
                    is_valid = False
                    issue = f"Future date of registration: {date_str}"
                else:
                    df.at[idx, 'date_of_registration'] = dt.strftime("%Y-%m-%d")
            except ValueError:
                is_valid = False
                issue = f"Invalid date format: {date_str}"
                
        # Capital validation
        try:
            auth = float(row['authorized_capital'])
            paid = float(row['paidup_capital'])
            if auth < 0 or paid < 0:
                is_valid = False
                issue = f"Negative capital: auth={auth}, paid={paid}"
            elif paid > auth:
                is_valid = False
                issue = f"Paid-up exceeds authorized: auth={auth}, paid={paid}"
        except (ValueError, TypeError):
            is_valid = False
            issue = f"Non-numeric capital values: auth={row['authorized_capital']}, paid={row['paidup_capital']}"
            
        # Address validation
        addr = str(row['registered_office_address']).strip()
        if pd.isna(row['registered_office_address']) or addr == "" or len(addr) < 5:
            is_valid = False
            issue = "Missing or invalid registered address"
            
        if not is_valid:
            valid_mask.loc[idx] = False
            report["errors"].append({
                "cin": row['cin'],
                "issue": issue,
                "action": "Removed"
            })
            
    cleaned_df = df[valid_mask].copy()
    
    # Derive filing status based on company status
    def derive_filing(status):
        st = str(status).strip()
        if st in ("Dormant", "Strike Off"):
            return "Defaulter"
        return "Filed"
    cleaned_df["filing_status"] = cleaned_df["company_status"].apply(derive_filing)
    
    return cleaned_df, report

def validate_directors(df, valid_cins, report):
    valid_mask = pd.Series(True, index=df.index)
    for idx, row in df.iterrows():
        cin = str(row['cin']).strip()
        din = str(row['din']).strip()
        
        # Validate CIN reference
        if cin not in valid_cins:
            valid_mask.loc[idx] = False
            report["errors"].append({"cin": cin, "issue": "Director linked to non-existent CIN", "action": "Removed"})
            continue
            
        # Validate DIN format
        if pd.isna(row['din']) or din == "" or len(din) < 5 or len(din) > 10 or not din.isdigit():
            valid_mask.loc[idx] = False
            report["errors"].append({"cin": cin, "issue": f"Invalid DIN format: {din}", "action": "Removed"})
            
    return df[valid_mask].copy()

def main():
    print("Reading new raw CSV files...")
    if not all(os.path.exists(p) for p in [COMPANIES_RAW, DIRECTORS_RAW]):
        print("Error: Missing companies.csv or directors.csv in data/raw.")
        sys.exit(1)
        
    companies_df = pd.read_csv(COMPANIES_RAW, dtype={"CIN": str})
    directors_df = pd.read_csv(DIRECTORS_RAW, dtype={"DIN": str, "CIN": str})
    
    # Map and rename companies_df
    companies_df = companies_df.rename(columns={
        "CIN": "cin",
        "Company_Name": "company_name",
        "Registered_Address": "registered_office_address",
        "Registered_State": "state",
        "Date_of_Incorporation": "date_of_registration",
        "Authorized_Capital_Rs": "authorized_capital",
        "Paid_up_Capital_Rs": "paidup_capital",
        "Company_Status": "company_status"
    })
    
    # Add default city extraction
    companies_df["city"] = companies_df.apply(lambda r: extract_city(r["registered_office_address"], r["state"]), axis=1)
    
    # Map and rename directors_df
    directors_df = directors_df.rename(columns={
        "CIN": "cin",
        "DIN": "din",
        "Director_Name": "director_name"
    })
    
    print("Validating companies...")
    clean_companies, report = validate_companies(companies_df)
    valid_cins = set(clean_companies["cin"])
    
    # Inject legitimate edge case: 7 companies sharing 1 address with different directors
    print("Injecting 7 legitimate office case companies...")
    shared_address = "Plot 88, Nariman Point Business Centre, Mumbai, MH"
    first_names = ["Arvind", "Pradeep", "Harish", "Karthik", "Sridhar", "Raman", "Madhav"]
    last_names = ["Nair", "Pillai", "Subramanian", "Kulkarni", "Deshmukh", "Gokhale", "Joshi"]
    
    legit_cos = []
    legit_dirs = []
    for i in range(7):
        while True:
            seq = f"{900000 + i:06d}"
            cin = f"U74999MH2015PTC{seq}"
            if cin not in valid_cins:
                break
        
        comp_name = f"Vanguard Consultants Group {i+1} Pvt Ltd"
        incorp_date = f"2015-04-{10+i:02d}"
        
        # Add to companies DataFrame
        new_row = {
            "cin": cin,
            "company_name": comp_name,
            "registered_office_address": shared_address,
            "city": "Mumbai",
            "state": "MH",
            "date_of_registration": incorp_date,
            "authorized_capital": 1000000.0,
            "paidup_capital": 500000.0,
            "company_status": "Active",
            "filing_status": "Filed",
            "Synthetic_Ring_ID": None,
            "Synthetic_Shell_Ground_Truth": "No",
            "label": "legit_edge_case"
        }
        legit_cos.append(new_row)
        valid_cins.add(cin)
        
        # Add to directors
        legit_dirs.append({
            "cin": cin,
            "din": f"8000000{i}",
            "director_name": f"{first_names[i]} {last_names[i]}"
        })
        
    legit_cos_df = pd.DataFrame(legit_cos)
    clean_companies = pd.concat([clean_companies, legit_cos_df], ignore_index=True)
    
    # Process directors
    print("Validating directors...")
    clean_directors = validate_directors(directors_df, valid_cins, report)
    legit_dirs_df = pd.DataFrame(legit_dirs)
    clean_directors = pd.concat([clean_directors, legit_dirs_df], ignore_index=True)
    
    # Generate CERSAI and RBI records dynamically based on shell companies
    print("Generating CERSAI, RBI, and Ground Truth datasets...")
    cersai_records = []
    rbi_records = []
    gt_records = []
    
    banks = [
        "State Bank of India", "Punjab National Bank", "Bank of Baroda",
        "Canara Bank", "Union Bank of India", "HDFC Bank", "ICICI Bank"
    ]
    
    coop_banks = [
        "Vardhman Cooperative Bank Ltd", "Continental Urban Cooperative Bank",
        "Orion Multistate Cooperative Bank", "Apex Cooperative Bank Ltd",
        "Janata Sahakari Bank Ltd", "Saraswat Cooperative Bank Ltd"
    ]
    
    for _, row in clean_companies.iterrows():
        cin = row["cin"]
        name = row["company_name"]
        is_shell = row.get("Synthetic_Shell_Ground_Truth") == "Yes"
        ring_id = row.get("Synthetic_Ring_ID")
        
        # Label mapping for ground truth
        if is_shell:
            if ring_id == "RING-01":
                label = "fraud_ring_A"
            elif ring_id == "RING-02":
                label = "fraud_ring_B"
            elif ring_id == "RING-03":
                label = "fraud_ring_C"
            else:
                label = f"fraud_ring_{ring_id}"
        else:
            label = row.get("label")
            if pd.isna(label) or not label or str(label).strip() == "" or str(label) == "nan":
                label = "normal"
            
        gt_records.append({
            "cin": cin,
            "label": label
        })
        
        reg_date = datetime.strptime(row["date_of_registration"], "%Y-%m-%d")
        
        if is_shell:
            # All shell companies get a loan and default to ensure high score
            if ring_id == "RING-01":
                lender = coop_banks[0]
            elif ring_id == "RING-02":
                lender = coop_banks[1]
            elif ring_id == "RING-03":
                lender = coop_banks[2]
            else:
                lender_idx = hash(str(ring_id)) % len(coop_banks)
                lender = coop_banks[lender_idx]
                
            # Create loan
            cersai_records.append({
                "cin": cin,
                "borrower_name": name,
                "lender_name": lender,
                "security_type": "hypothecation",
                "asset_description": f"Plant & Machinery - {name}",
                "charge_amount": float(random.choice([2500000, 3500000, 5000000])),
                "charge_registration_date": (reg_date + timedelta(days=random.randint(15, 45))).strftime("%Y-%m-%d")
            })
            
            # Create default
            rbi_records.append({
                "cin": cin,
                "company_name": name,
                "lender_name": lender,
                "default_amount": float(random.choice([3000000, 4500000, 6000000])),
                "classification_date": (reg_date + timedelta(days=random.randint(300, 600))).strftime("%Y-%m-%d"),
                "wilful_default_reason": "Diversion of funds"
            })
        else:
            # Normal background: ~18% loans, ~1% default
            if random.random() < 0.18:
                lender = random.choice(banks)
                loan_date = reg_date + timedelta(days=random.randint(90, 1500))
                cersai_records.append({
                    "cin": cin,
                    "borrower_name": name,
                    "lender_name": lender,
                    "security_type": random.choice(["hypothecation", "mortgage", "pledge"]),
                    "asset_description": f"Inventory - {name}",
                    "charge_amount": float(random.choice([500000, 1200000, 2000000, 3000000])),
                    "charge_registration_date": loan_date.strftime("%Y-%m-%d")
                })
                
                if random.random() < 0.05:
                    rbi_records.append({
                        "cin": cin,
                        "company_name": name,
                        "lender_name": lender,
                        "default_amount": float(random.choice([1500000, 2800000])),
                        "classification_date": (loan_date + timedelta(days=random.randint(300, 1000))).strftime("%Y-%m-%d"),
                        "wilful_default_reason": random.choice(["Diversion of funds", "Siphoning of funds"])
                    })
                    
    clean_cersai = pd.DataFrame(cersai_records)
    clean_rbi = pd.DataFrame(rbi_records)
    clean_gt = pd.DataFrame(gt_records)
    
    # Save cleaned files to processed directory
    clean_companies.to_csv(os.path.join(PROCESSED_DIR, "cleaned_companies.csv"), index=False)
    clean_directors.to_csv(os.path.join(PROCESSED_DIR, "cleaned_directors.csv"), index=False)
    clean_cersai.to_csv(os.path.join(PROCESSED_DIR, "cleaned_cersai_security_interests.csv"), index=False)
    clean_rbi.to_csv(os.path.join(PROCESSED_DIR, "cleaned_rbi_wilful_defaulters.csv"), index=False)
    clean_gt.to_csv(os.path.join(PROCESSED_DIR, "cleaned_ground_truth.csv"), index=False)
    
    report["summary"] = {
        "companies_count": len(clean_companies),
        "directors_count": len(clean_directors),
        "cersai_count": len(clean_cersai),
        "rbi_count": len(clean_rbi),
        "gt_count": len(clean_gt),
    }
    
    report_file = os.path.join(PROCESSED_DIR, "validation_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
        
    print("\n--- INGESTION VALIDATION SUMMARY ---")
    print(f"Cleaned Companies: {len(clean_companies)}")
    print(f"Cleaned Directors: {len(clean_directors)}")
    print(f"Cleaned Loans:     {len(clean_cersai)}")
    print(f"Cleaned Defaulters:{len(clean_rbi)}")
    print(f"Cleaned GT Labels: {len(clean_gt)}")
    print(f"Validation report saved to {report_file}")

if __name__ == "__main__":
    main()

