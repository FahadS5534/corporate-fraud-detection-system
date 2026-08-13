import os
import sys
import argparse
import pandas as pd
import json
from datetime import datetime

# Path setups
RAW_DIR = r"f:\SIH\data\raw"
PROCESSED_DIR = r"f:\SIH\data\processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

COMPANY_RAW = os.path.join(RAW_DIR, "company_master.csv")
DIRECTOR_RAW = os.path.join(RAW_DIR, "director_registry.csv")

def validate_company_data(df):
    report = {
        "total_records": len(df),
        "missing_values": {},
        "duplicate_cins": 0,
        "invalid_dates": 0,
        "invalid_capital": 0,
        "missing_addresses": 0,
        "missing_status_or_filing": 0,
        "errors": []
    }
    
    # 1. Missing Values check per column
    for col in df.columns:
        missing_count = int(df[col].isna().sum())
        if missing_count > 0:
            report["missing_values"][col] = missing_count
            
    valid_mask = pd.Series(True, index=df.index)
    
    # 2. Duplicate CINs
    dup_cins = df[df.duplicated(subset=['cin'], keep=False)]
    report["duplicate_cins"] = int(df.duplicated(subset=['cin']).sum())
    for idx, row in dup_cins.iterrows():
        report["errors"].append({
            "cin": row['cin'],
            "row": idx + 2, # 1-indexed plus header
            "issue": "Duplicate CIN",
            "action": "Flagged/Removed"
        })
    valid_mask &= ~df.duplicated(subset=['cin'], keep='first')
    
    # 3. Invalid dates (incorporation date format YYYY-MM-DD and not in the future)
    today = datetime.today().date()
    for idx, row in df.iterrows():
        date_str = str(row['date_of_incorporation']).strip()
        is_valid = True
        if pd.isna(row['date_of_incorporation']) or date_str == "":
            is_valid = False
            issue = "Missing incorporation date"
        else:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                if dt > today:
                    is_valid = False
                    issue = f"Future incorporation date: {date_str}"
            except ValueError:
                is_valid = False
                issue = f"Invalid date format: {date_str} (expected YYYY-MM-DD)"
                
        if not is_valid:
            report["invalid_dates"] += 1
            valid_mask.loc[idx] = False
            report["errors"].append({
                "cin": row['cin'],
                "row": idx + 2,
                "issue": issue,
                "action": "Flagged/Removed"
            })
            
    # 4. Invalid capital values (authorized < 0, paidup < 0, paidup > authorized)
    for idx, row in df.iterrows():
        try:
            auth = float(row['authorized_capital'])
            paid = float(row['paidup_capital'])
            
            if auth < 0 or paid < 0:
                report["invalid_capital"] += 1
                valid_mask.loc[idx] = False
                report["errors"].append({
                    "cin": row['cin'],
                    "row": idx + 2,
                    "issue": f"Negative capital: auth={auth}, paid={paid}",
                    "action": "Flagged/Removed"
                })
            elif paid > auth:
                report["invalid_capital"] += 1
                valid_mask.loc[idx] = False
                report["errors"].append({
                    "cin": row['cin'],
                    "row": idx + 2,
                    "issue": f"Paid-up capital exceeds authorized: auth={auth}, paid={paid}",
                    "action": "Flagged/Removed"
                })
        except (ValueError, TypeError):
            report["invalid_capital"] += 1
            valid_mask.loc[idx] = False
            report["errors"].append({
                "cin": row['cin'],
                "row": idx + 2,
                "issue": f"Non-numeric capital values: auth={row['authorized_capital']}, paid={row['paidup_capital']}",
                "action": "Flagged/Removed"
            })
            
    # 5. Missing Addresses
    for idx, row in df.iterrows():
        addr = str(row['registered_office_address']).strip()
        if pd.isna(row['registered_office_address']) or addr == "" or len(addr) < 5:
            report["missing_addresses"] += 1
            valid_mask.loc[idx] = False
            report["errors"].append({
                "cin": row['cin'],
                "row": idx + 2,
                "issue": "Missing or too short registered address",
                "action": "Flagged/Removed"
            })
            
    # 6. Missing status/filing fields
    for idx, row in df.iterrows():
        status = str(row['company_status']).strip()
        filing = str(row['filing_status']).strip()
        if pd.isna(row['company_status']) or status == "" or pd.isna(row['filing_status']) or filing == "":
            report["missing_status_or_filing"] += 1
            valid_mask.loc[idx] = False
            report["errors"].append({
                "cin": row['cin'],
                "row": idx + 2,
                "issue": f"Missing company_status ({status}) or filing_status ({filing})",
                "action": "Flagged/Removed"
            })
            
    cleaned_df = df[valid_mask]
    invalid_df = df[~valid_mask]
    
    return cleaned_df, invalid_df, report

def validate_director_data(dir_df, clean_comp_df, report):
    # Checking director registry relationships
    # We check if directors link to valid companies (present in the cleaned company dataset)
    total_dirs = len(dir_df)
    report["director_relationship"] = {
        "total_relationships": total_dirs,
        "valid_cin_references": 0,
        "invalid_cin_references": 0,
        "missing_dins": 0,
        "duplicate_links": 0
    }
    
    valid_mask = pd.Series(True, index=dir_df.index)
    valid_cins = set(clean_comp_df['cin'])
    
    # Check duplicate links (same DIN and CIN combo)
    dup_links = dir_df.duplicated(subset=['din', 'cin'], keep=False)
    report["director_relationship"]["duplicate_links"] = int(dir_df.duplicated(subset=['din', 'cin']).sum())
    valid_mask &= ~dir_df.duplicated(subset=['din', 'cin'], keep='first')
    
    for idx, row in dir_df.iterrows():
        # Missing DIN
        din = str(row['din']).strip()
        if pd.isna(row['din']) or din == "" or len(din) != 8 or not din.isdigit():
            report["director_relationship"]["missing_dins"] += 1
            valid_mask.loc[idx] = False
            report["errors"].append({
                "din": row['din'],
                "cin": row['cin'],
                "row": idx + 2,
                "issue": f"Invalid or missing DIN: {row['din']}",
                "action": "Flagged/Removed"
            })
            continue
            
        # Valid CIN reference check
        cin = str(row['cin']).strip()
        if cin in valid_cins:
            report["director_relationship"]["valid_cin_references"] += 1
        else:
            report["director_relationship"]["invalid_cin_references"] += 1
            valid_mask.loc[idx] = False
            report["errors"].append({
                "din": row['din'],
                "cin": row['cin'],
                "row": idx + 2,
                "issue": f"CIN {cin} not found in cleaned companies",
                "action": "Flagged/Removed"
            })
            
    cleaned_dir_df = dir_df[valid_mask]
    invalid_dir_df = dir_df[~valid_mask]
    
    return cleaned_dir_df, invalid_dir_df

def main():
    parser = argparse.ArgumentParser(description="Ingest and validate company master and director records.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate files and output reports, don't write to DB.")
    args = parser.parse_args()
    
    if not os.path.exists(COMPANY_RAW) or not os.path.exists(DIRECTOR_RAW):
        print(f"Error: Raw data files not found in {RAW_DIR}")
        print("Please run scripts/generate_baseline_data.py first.")
        sys.exit(1)
        
    print("Reading raw CSV files...")
    comp_df = pd.read_csv(COMPANY_RAW, dtype={"cin": str})
    dir_df = pd.read_csv(DIRECTOR_RAW, dtype={"din": str, "cin": str})
    
    print("Validating company master data...")
    clean_comp, invalid_comp, report = validate_company_data(comp_df)
    
    print("Validating director registry relationships...")
    clean_dir, invalid_dir = validate_director_data(dir_df, clean_comp, report)
    
    # Save cleaned and invalid files
    clean_comp.to_csv(os.path.join(PROCESSED_DIR, "cleaned_companies.csv"), index=False)
    invalid_comp.to_csv(os.path.join(PROCESSED_DIR, "invalid_companies.csv"), index=False)
    clean_dir.to_csv(os.path.join(PROCESSED_DIR, "cleaned_directors.csv"), index=False)
    invalid_dir.to_csv(os.path.join(PROCESSED_DIR, "invalid_directors.csv"), index=False)
    
    # Calculate final status
    report["summary"] = {
        "raw_companies_count": len(comp_df),
        "cleaned_companies_count": len(clean_comp),
        "invalid_companies_count": len(invalid_comp),
        "raw_directors_count": len(dir_df),
        "cleaned_directors_count": len(clean_dir),
        "invalid_directors_count": len(invalid_dir)
    }
    
    report_file = os.path.join(PROCESSED_DIR, "validation_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
        
    print("\n--- VALIDATION REPORT SUMMARY ---")
    print(f"Raw Companies:      {report['summary']['raw_companies_count']}")
    print(f"Cleaned Companies:  {report['summary']['cleaned_companies_count']}")
    print(f"Invalid Companies:  {report['summary']['invalid_companies_count']}")
    print(f"Duplicate CINs:     {report['duplicate_cins']}")
    print(f"Invalid Date Recs:  {report['invalid_dates']}")
    print(f"Invalid Cap Recs:   {report['invalid_capital']}")
    print(f"Missing Address:    {report['missing_addresses']}")
    print(f"Missing Status/Fil: {report['missing_status_or_filer'] if 'missing_status_or_filer' in report else report['missing_status_or_filing']}")
    print(f"Cleaned Directors:  {report['summary']['cleaned_directors_count']}")
    print(f"Invalid Directors:  {report['summary']['invalid_directors_count']}")
    print(f"Validation report saved to {report_file}")
    
    if args.validate_only:
        print("Validation complete. Skipping database load (--validate-only).")
        return
        
    # Database load will happen here in later steps
    # We will build the DB load service in the next step.

if __name__ == "__main__":
    main()
