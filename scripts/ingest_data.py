"""
ingest_data.py — CSV Validation & Graph Build Smoke Test
=========================================================
Validates the 4 source CSV files and runs a smoke test by building the
multi-layer graph to confirm all layers connect correctly.

This script no longer writes to a database.  All downstream processing
(community detection, scoring) reads directly from the CSV files.

Usage
-----
    python scripts/ingest_data.py
    python scripts/ingest_data.py --validate-only
"""

import os
import sys
import io
# Force UTF-8 on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import argparse
import json
import pandas as pd
from datetime import datetime

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")

from backend.app.services.graph_service import MultiSourceGraphBuilder


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_companies(df: pd.DataFrame) -> dict:
    report = {
        "total": len(df),
        "missing_cin": int(df["CIN"].isna().sum()),
        "missing_name": int(df["COMPANY_NAME"].isna().sum()),
        "missing_address": int(df["REGISTERED_OFFICE_ADDRESS"].isna().sum()),
        "duplicate_cins": int(df.duplicated(subset=["CIN"]).sum()),
        "invalid_dates": 0,
        "issues": [],
    }
    today = datetime.today().date()
    for _, row in df.iterrows():
        ds = str(row.get("DATE_OF_REGISTRATION", "")).strip()
        if not ds or ds == "nan":
            report["invalid_dates"] += 1
        else:
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d").date()
                if dt > today:
                    report["invalid_dates"] += 1
                    report["issues"].append(
                        f"CIN {row['CIN']}: future registration date {ds}"
                    )
            except ValueError:
                report["invalid_dates"] += 1
                report["issues"].append(
                    f"CIN {row['CIN']}: bad date format '{ds}'"
                )
    return report


def validate_directors(df: pd.DataFrame, valid_cins: set) -> dict:
    report = {
        "total": len(df),
        "missing_din": int(df["DIN"].isna().sum()),
        "missing_cin": int(df["CIN"].isna().sum()),
        "orphaned_cins": 0,
        "duplicate_links": int(df.duplicated(subset=["DIN", "CIN"]).sum()),
        "issues": [],
    }
    for _, row in df.iterrows():
        cin = str(row.get("CIN", "")).strip()
        if cin not in valid_cins:
            report["orphaned_cins"] += 1
    return report


def validate_cersai(df: pd.DataFrame, valid_cins: set) -> dict:
    report = {
        "total": len(df),
        "missing_cin": int(df["CIN"].isna().sum()),
        "missing_lender": int(df["LENDER_NAME"].isna().sum()),
        "orphaned_cins": sum(
            1 for _, row in df.iterrows()
            if str(row.get("CIN", "")).strip() not in valid_cins
        ),
    }
    return report


def validate_rbi(df: pd.DataFrame, valid_cins: set) -> dict:
    report = {
        "total": len(df),
        "missing_cin": int(df["CIN"].isna().sum()),
        "orphaned_cins": sum(
            1 for _, row in df.iterrows()
            if str(row.get("CIN", "")).strip() not in valid_cins
        ),
    }
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate 4 source CSVs and run graph build smoke test."
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Only run validation; skip graph build."
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  MULTI-SOURCE CSV VALIDATION")
    print("=" * 60)

    # ---- Load files -------------------------------------------------------
    companies_path  = os.path.join(DATA_DIR, "mca_companies.csv")
    directors_path  = os.path.join(DATA_DIR, "mca_directors.csv")
    cersai_path     = os.path.join(DATA_DIR, "cersai_security_interests.csv")
    rbi_path        = os.path.join(DATA_DIR, "rbi_wilful_defaulters.csv")
    gt_path         = os.path.join(DATA_DIR, "ground_truth.csv")

    for path in [companies_path, directors_path, cersai_path, rbi_path, gt_path]:
        if not os.path.exists(path):
            print(f"[ERROR] Missing file: {path}")
            sys.exit(1)

    companies_df = pd.read_csv(companies_path, dtype={"CIN": str})
    directors_df = pd.read_csv(directors_path, dtype={"CIN": str, "DIN": str})
    cersai_df    = pd.read_csv(cersai_path,    dtype={"CIN": str})
    rbi_df       = pd.read_csv(rbi_path,       dtype={"CIN": str})
    gt_df        = pd.read_csv(gt_path,        dtype={"CIN": str})

    valid_cins = set(companies_df["CIN"].dropna().str.strip())

    # ---- Run validators ---------------------------------------------------
    comp_report  = validate_companies(companies_df)
    dir_report   = validate_directors(directors_df, valid_cins)
    cer_report   = validate_cersai(cersai_df, valid_cins)
    rbi_report   = validate_rbi(rbi_df, valid_cins)

    all_reports = {
        "mca_companies":            comp_report,
        "mca_directors":            dir_report,
        "cersai_security_interests": cer_report,
        "rbi_wilful_defaulters":    rbi_report,
    }

    print(f"\n{'-'*60}")
    print(f"  mca_companies.csv")
    print(f"    Rows            : {comp_report['total']}")
    print(f"    Duplicate CINs  : {comp_report['duplicate_cins']}")
    print(f"    Missing names   : {comp_report['missing_name']}")
    print(f"    Missing address : {comp_report['missing_address']}")
    print(f"    Invalid dates   : {comp_report['invalid_dates']}")

    print(f"\n  mca_directors.csv")
    print(f"    Rows            : {dir_report['total']}")
    print(f"    Missing DINs    : {dir_report['missing_din']}")
    print(f"    Orphaned CINs   : {dir_report['orphaned_cins']}")
    print(f"    Duplicate links : {dir_report['duplicate_links']}")

    print(f"\n  cersai_security_interests.csv")
    print(f"    Rows            : {cer_report['total']}")
    print(f"    Missing lender  : {cer_report['missing_lender']}")
    print(f"    Orphaned CINs   : {cer_report['orphaned_cins']}")

    print(f"\n  rbi_wilful_defaulters.csv")
    print(f"    Rows            : {rbi_report['total']}")
    print(f"    Orphaned CINs   : {rbi_report['orphaned_cins']}")

    print(f"\n  ground_truth.csv")
    label_counts = gt_df["label"].value_counts().to_dict()
    for lbl, cnt in sorted(label_counts.items()):
        print(f"    {lbl:<20s} : {cnt}")

    # Save validation JSON report
    report_path = os.path.join(DATA_DIR, "validation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_reports, f, indent=2)
    print(f"\n  Validation report saved → {report_path}")

    if args.validate_only:
        print("\n[--validate-only] Graph build skipped.")
        return

    # ---- Graph build smoke test ------------------------------------------
    print(f"\n{'-'*60}")
    print("  GRAPH BUILD SMOKE TEST")
    print(f"{'-'*60}")

    builder = MultiSourceGraphBuilder(data_dir=DATA_DIR)
    G = builder.build_graph()

    n_company  = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "company")
    n_director = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "director")
    n_address  = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "address")
    n_lender   = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "lender")
    n_defaulter= sum(
        1 for _, d in G.nodes(data=True)
        if d.get("type") == "company" and d.get("wilful_defaulter_flag")
    )

    print(f"\n  Graph node counts:")
    print(f"    Companies  : {n_company}")
    print(f"    Directors  : {n_director}")
    print(f"    Addresses  : {n_address}")
    print(f"    Lenders    : {n_lender}")
    print(f"    Total nodes: {G.number_of_nodes()}")
    print(f"    Total edges: {G.number_of_edges()}")
    print(f"    Defaulter flags: {n_defaulter} company nodes")

    # Quick sanity checks
    assert n_company > 0,  "No company nodes!"
    assert n_director > 0, "No director nodes!"
    assert n_address > 0,  "No address nodes!"
    assert n_lender > 0,   "No lender nodes!"
    print("\n  ✅ All smoke-test assertions PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
