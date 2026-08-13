import os
import sys
import pandas as pd
from datetime import datetime

# Add root folder to sys.path for importing app modules
sys.path.append(r"f:\SIH")

from backend.app.database import engine, Base, SessionLocal
from backend.app.models.models import Company, DirectorRelationship

PROCESSED_DIR = r"f:\SIH\data\processed"
CLEANED_COMPANY_FILE = os.path.join(PROCESSED_DIR, "cleaned_companies.csv")
CLEANED_DIRECTOR_FILE = os.path.join(PROCESSED_DIR, "cleaned_directors.csv")

def parse_date(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "":
        return None
    try:
        return datetime.strptime(str(date_val).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

def load_data():
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    
    if not os.path.exists(CLEANED_COMPANY_FILE) or not os.path.exists(CLEANED_DIRECTOR_FILE):
        print("Error: Cleaned data files not found. Please run scripts/ingest_data.py first.")
        sys.exit(1)
        
    db = SessionLocal()
    try:
        # Clear existing data to support clean reruns
        print("Clearing existing data...")
        db.query(DirectorRelationship).delete()
        db.query(Company).delete()
        db.commit()
        
        print("Loading cleaned companies...")
        comp_df = pd.read_csv(CLEANED_COMPANY_FILE, dtype={"cin": str})
        companies_to_insert = []
        for _, row in comp_df.iterrows():
            company = Company(
                cin=row["cin"],
                company_name=row["company_name"],
                roc_code=row["roc_code"],
                company_status=row["company_status"],
                date_of_incorporation=parse_date(row["date_of_incorporation"]),
                company_class=row["company_class"],
                company_category=row["company_category"],
                authorized_capital=float(row["authorized_capital"]),
                paidup_capital=float(row["paidup_capital"]),
                registered_office_address=row["registered_office_address"],
                filing_status=row["filing_status"]
            )
            companies_to_insert.append(company)
            
        db.bulk_save_objects(companies_to_insert)
        db.commit()
        print(f"Successfully loaded {len(companies_to_insert)} companies.")
        
        print("Loading cleaned director relationships...")
        dir_df = pd.read_csv(CLEANED_DIRECTOR_FILE, dtype={"din": str, "cin": str})
        directors_to_insert = []
        for _, row in dir_df.iterrows():
            rel = DirectorRelationship(
                din=row["din"],
                director_name=row["director_name"],
                cin=row["cin"],
                designation=row.get("designation", "Director"),
                appointment_date=parse_date(row.get("appointment_date"))
            )
            directors_to_insert.append(rel)
            
        db.bulk_save_objects(directors_to_insert)
        db.commit()
        print(f"Successfully loaded {len(directors_to_insert)} director relationships.")
        
    except Exception as e:
        db.rollback()
        print(f"Error occurred during DB load: {e}")
        sys.exit(1)
    finally:
        db.close()
        
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    load_data()
