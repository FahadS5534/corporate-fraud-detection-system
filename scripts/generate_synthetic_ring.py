import sys
import os
from datetime import datetime, timedelta

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.database import SessionLocal, engine
from backend.app.models.models import Company, DirectorRelationship

def plant_fraud_ring():
    print("Planting synthetic coordinated fraud ring into database...")
    db = SessionLocal()
    try:
        # Check if already planted to avoid double inserts
        existing = db.query(Company).filter(Company.cin.like("SYN_C%")).first()
        if existing:
            print("Synthetic fraud ring already exists in database. Skipping insertion.")
            return

        # 1. Define common address
        syn_address = "SYN_ADDR_001, Building 4B, Kistopur Road, Salt Lake, Kolkata, West Bengal - 700102"
        
        # 2. Define directors
        syn_directors = [
            {"din": "SYN_D001", "name": "SYN_DIR Mohit Deora"},
            {"din": "SYN_D002", "name": "SYN_DIR Shiva Kumar"},
            {"din": "SYN_D003", "name": "SYN_DIR Amit Gupta"}
        ]
        
        # 3. Create 10 synthetic companies with tight dates
        # Incorporation dates from 2024-05-01 to 2024-05-14 (14 days window)
        start_date = datetime.strptime("2024-05-01", "%Y-%m-%d").date()
        
        companies_to_insert = []
        for i in range(1, 11):
            cin = f"SYN_C{i:03d}"
            inc_date = start_date + timedelta(days=(i % 14))
            
            comp = Company(
                cin=cin,
                company_name=f"SYN_COMP Apex Trade & Invoice Line {i} Private Limited",
                roc_code="ROC-KOLKATA",
                company_status="Active",
                date_of_incorporation=inc_date,
                company_class="PTC",
                company_category="Company limited by Shares",
                authorized_capital=1000000.0,
                paidup_capital=0.0, # Zero paid-up capital
                registered_office_address=syn_address,
                filing_status="Defaulter" # Compliancy default
            )
            companies_to_insert.append(comp)
            
        db.bulk_save_objects(companies_to_insert)
        db.commit()
        print(f"Successfully planted {len(companies_to_insert)} synthetic companies.")
        
        # 4. Link directors to companies (creating overlapping network)
        # Director 1 -> Comp 1-6
        # Director 2 -> Comp 3-8
        # Director 3 -> Comp 5-10
        links_to_insert = []
        
        # Links
        links = [
            ("SYN_D001", [f"SYN_C{j:03d}" for j in range(1, 7)]),
            ("SYN_D002", [f"SYN_C{j:03d}" for j in range(3, 9)]),
            ("SYN_D003", [f"SYN_C{j:03d}" for j in range(5, 11)])
        ]
        
        for din, cins in links:
            dir_name = next(d["name"] for d in syn_directors if d["din"] == din)
            for cin in cins:
                rel = DirectorRelationship(
                    din=din,
                    director_name=dir_name,
                    cin=cin,
                    designation="Director",
                    appointment_date=start_date
                )
                links_to_insert.append(rel)
                
        db.bulk_save_objects(links_to_insert)
        db.commit()
        print(f"Successfully planted {len(links_to_insert)} director-company associations.")
        
    except Exception as e:
        db.rollback()
        print(f"Error planting synthetic ring: {e}")
    finally:
        db.close()
        
    print("Synthetic fraud ring planting complete.")

if __name__ == "__main__":
    plant_fraud_ring()
