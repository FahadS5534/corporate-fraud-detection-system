import os
import sys
import pandas as pd
from datetime import datetime

# Add root folder to sys.path for importing app modules
sys.path.append(r"f:\SIH")

from backend.app.database import engine, Base, SessionLocal
from backend.app.models.models import (
    Company,
    DirectorRelationship,
    CersaiSecurityInterest,
    RbiWilfulDefaulter,
    GroundTruth
)

PROCESSED_DIR = r"f:\SIH\data\processed"
CLEANED_COMPANY_FILE = os.path.join(PROCESSED_DIR, "cleaned_companies.csv")
CLEANED_DIRECTOR_FILE = os.path.join(PROCESSED_DIR, "cleaned_directors.csv")
CLEANED_CERSAI_FILE = os.path.join(PROCESSED_DIR, "cleaned_cersai_security_interests.csv")
CLEANED_RBI_FILE = os.path.join(PROCESSED_DIR, "cleaned_rbi_wilful_defaulters.csv")
CLEANED_GT_FILE = os.path.join(PROCESSED_DIR, "cleaned_ground_truth.csv")

def parse_date(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "":
        return None
    try:
        return datetime.strptime(str(date_val).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

def load_data():
    print("Dropping and recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    files = [CLEANED_COMPANY_FILE, CLEANED_DIRECTOR_FILE, CLEANED_CERSAI_FILE, CLEANED_RBI_FILE, CLEANED_GT_FILE]
    if not all(os.path.exists(f) for f in files):
        print("Error: Cleaned data files not found. Please run scripts/ingest_data.py first.")
        sys.exit(1)
        
    db = SessionLocal()
    try:
        # 1. Load Companies
        print("Seeding companies...")
        comp_df = pd.read_csv(CLEANED_COMPANY_FILE, dtype={"cin": str})
        companies_to_insert = []
        for _, row in comp_df.iterrows():
            company = Company(
                cin=row["cin"],
                company_name=row["company_name"],
                registered_office_address=row["registered_office_address"],
                city=row.get("city") if pd.notna(row.get("city")) else None,
                state=row.get("state") if pd.notna(row.get("state")) else None,
                date_of_registration=parse_date(row["date_of_registration"]),
                authorized_capital=float(row["authorized_capital"]),
                paidup_capital=float(row["paidup_capital"]),
                company_status=row["company_status"],
                filing_status=row["filing_status"]
            )
            companies_to_insert.append(company)
        db.bulk_save_objects(companies_to_insert)
        db.commit()
        print(f"Successfully loaded {len(companies_to_insert)} companies.")

        # 2. Load Directors
        print("Seeding director relationships...")
        dir_df = pd.read_csv(CLEANED_DIRECTOR_FILE, dtype={"din": str, "cin": str})
        directors_to_insert = []
        for _, row in dir_df.iterrows():
            rel = DirectorRelationship(
                din=str(row["din"]),
                director_name=row["director_name"],
                cin=row["cin"]
            )
            directors_to_insert.append(rel)
        db.bulk_save_objects(directors_to_insert)
        db.commit()
        print(f"Successfully loaded {len(directors_to_insert)} director relationships.")

        # 3. Load CERSAI Loans
        print("Seeding CERSAI security interests...")
        cersai_df = pd.read_csv(CLEANED_CERSAI_FILE, dtype={"cin": str})
        loans_to_insert = []
        for _, row in cersai_df.iterrows():
            loan = CersaiSecurityInterest(
                cin=row["cin"],
                borrower_name=row.get("borrower_name") if pd.notna(row.get("borrower_name")) else None,
                lender_name=row["lender_name"],
                security_type=row.get("security_type") if pd.notna(row.get("security_type")) else None,
                asset_description=row.get("asset_description") if pd.notna(row.get("asset_description")) else None,
                charge_amount=float(row["charge_amount"]),
                charge_registration_date=parse_date(row["charge_registration_date"])
            )
            loans_to_insert.append(loan)
        db.bulk_save_objects(loans_to_insert)
        db.commit()
        print(f"Successfully loaded {len(loans_to_insert)} CERSAI loan records.")

        # 4. Load RBI Defaulters
        print("Seeding RBI wilful defaulters...")
        rbi_df = pd.read_csv(CLEANED_RBI_FILE, dtype={"cin": str})
        defaulters_to_insert = []
        for _, row in rbi_df.iterrows():
            defaulter = RbiWilfulDefaulter(
                cin=row["cin"],
                company_name=row.get("company_name") if pd.notna(row.get("company_name")) else None,
                lender_name=row["lender_name"],
                default_amount=float(row["default_amount"]),
                classification_date=parse_date(row["classification_date"]),
                wilful_default_reason=row.get("wilful_default_reason") if pd.notna(row.get("wilful_default_reason")) else None
            )
            defaulters_to_insert.append(defaulter)
        db.bulk_save_objects(defaulters_to_insert)
        db.commit()
        print(f"Successfully loaded {len(defaulters_to_insert)} RBI defaulter records.")

        # 5. Load Ground Truth
        print("Seeding Ground Truth labels...")
        gt_df = pd.read_csv(CLEANED_GT_FILE, dtype={"cin": str})
        gt_to_insert = []
        for _, row in gt_df.iterrows():
            gt = GroundTruth(
                cin=row["cin"],
                label=row["label"]
            )
            gt_to_insert.append(gt)
        db.bulk_save_objects(gt_to_insert)
        db.commit()
        print(f"Successfully loaded {len(gt_to_insert)} Ground Truth labels.")

    except Exception as e:
        db.rollback()
        print(f"Error occurred during DB seed: {e}")
        sys.exit(1)
    finally:
        db.close()
        
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    load_data()
