import os
import csv
import random
from datetime import datetime, timedelta

# Output directories
RAW_DIR = r"f:\SIH\data\raw"
os.makedirs(RAW_DIR, exist_ok=True)

COMPANY_FILE = os.path.join(RAW_DIR, "company_master.csv")
DIRECTOR_FILE = os.path.join(RAW_DIR, "director_registry.csv")

# Seed for reproducibility
random.seed(42)

# Lists for generating realistic Indian names and terms
FIRST_NAMES = ["Rajesh", "Amit", "Sanjay", "Vijay", "Sunil", "Anil", "Pankaj", "Deepak", "Ramesh", "Suresh",
               "Priya", "Anjali", "Ritu", "Neha", "Karan", "Rahul", "Vikram", "Ajay", "Arun", "Manoj",
               "Ketan", "Harish", "Gaurav", "Nitin", "Pradeep", "Sandeep", "Alok", "Abhishek", "Vivek", "Dinesh"]
LAST_NAMES = ["Sharma", "Gupta", "Verma", "Mehra", "Singh", "Kumar", "Jalan", "Agarwal", "Goel", "Bansal",
              "Sen", "Roy", "Das", "Chatterjee", "Mukherjee", "Banerjee", "Deora", "Gupta", "Sinha", "Prasad"]

COMP_KEYWORDS = ["Tech", "Enterprises", "Industries", "Holdings", "Solutions", "Ventures", "Trading", "Logistics",
                 "Infrastructures", "Fintech", "Consultancy", "Agro", "Metals", "Power", "Chemicals", "Textiles"]
COMP_PREFIXES = ["Apex", "Nova", "Shree", "Balaji", "Krishna", "Dynamic", "Global", "Eastern", "Matrix", "Zenith",
                 "Horizon", "Alpha", "Radiant", "Vanguard", "Pioneer", "Sterling", "Kolkata", "Jharkhand", "Ranchi"]

ROC_CODES = ["ROC-RANCHI", "ROC-KOLKATA"]
STATES = ["Jharkhand", "West Bengal"]
STATE_CODES = {"ROC-RANCHI": "JH", "ROC-KOLKATA": "WB"}
STATE_NAMES = {"ROC-RANCHI": "Jharkhand", "ROC-KOLKATA": "West Bengal"}

def generate_cin(roc, year, seq):
    state_code = STATE_CODES[roc]
    nic = f"{random.randint(10, 99)}{random.randint(100, 999)}"
    class_code = "PTC" if random.random() < 0.85 else "PLC"
    return f"U{nic}{state_code}{year}{class_code}{seq:06d}"

def generate_din(seq):
    return f"{seq:08d}"

def generate_address(roc):
    state = STATE_NAMES[roc]
    if roc == "ROC-RANCHI":
        street = random.choice(["Bistupur Main Road", "Sakchi Boulevard", "Main Road Ranchi", "Lalpur Chowk", "Adityapur Industrial Area"])
        city = random.choice(["Jamshedpur", "Ranchi", "Dhanbad", "Bokaro"])
        pin = f"83{random.randint(100, 999)}"
    else:
        street = random.choice(["Park Street", "Salt Lake Sector V", "Howrah Industrial Estate", "Barabazar Main St", "Camac Street"])
        city = random.choice(["Kolkata", "Howrah", "Durgapur", "Asansol"])
        pin = f"70{random.randint(100, 999)}"
    
    building = f"{random.randint(1, 450)}, {random.choice(['Flat A', 'Suite 101', 'Chamber 2B', 'G/F', 'Building 12'])}"
    return f"{building}, {street}, {city}, {state} - {pin}"

def generate_data():
    print("Generating baseline background dataset...")
    
    companies = []
    directors = []
    
    # 1. Generate active unique address list
    # ~800 unique addresses for 1000 background companies
    addresses_by_roc = {
        "ROC-RANCHI": [generate_address("ROC-RANCHI") for _ in range(400)],
        "ROC-KOLKATA": [generate_address("ROC-KOLKATA") for _ in range(400)]
    }
    
    # 2. Pre-generate large pool of unique directors to prevent random high-degree collisions
    director_pool = []
    for i in range(1, 2500):
        din = generate_din(i)
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        director_pool.append((din, name))
        
    director_index = 0
    
    # 3. Create Legitimate Edge Cases (Planted in background data)
    # Edge Case A: Shared CA Office Address (Legitimate high company count)
    ca_address_roc = "ROC-KOLKATA"
    ca_address = "SUITE 504, 5TH FLOOR, MERLIN CHAMBERS, PARK STREET, KOLKATA, WEST BENGAL - 700016"
    addresses_by_roc[ca_address_roc].append(ca_address)
    
    # Let's assign 35 companies to this CA address
    # They should have completely independent directors and staggered incorporation dates
    ca_companies_count = 35
    
    # Edge Case B: Legitimate Holding Company with subsidiaries
    # They share a few directors (holding directors sit on subsidiary boards), but have staggered dates and high capital
    holding_roc = "ROC-RANCHI"
    holding_cin = generate_cin(holding_roc, 2005, 99999)
    holding_name = "TATA STEEL HOLDINGS LIMITED"
    holding_address = "1, GENERAL OFFICE BUILDING, BISTUPUR, JAMSHEDPUR, JHARKHAND - 831001"
    
    # Let's generate the holding company
    companies.append({
        "cin": holding_cin,
        "company_name": holding_name,
        "roc_code": holding_roc,
        "company_status": "Active",
        "date_of_incorporation": "2005-04-12",
        "company_class": "PLC",
        "company_category": "Company limited by Shares",
        "authorized_capital": 500000000.0,
        "paidup_capital": 450000000.0,
        "registered_office_address": holding_address,
        "filing_status": "Filed"
    })
    
    # Define holding directors (common directors)
    holding_dins = []
    for _ in range(3):
        din, name = director_pool[director_index]
        director_index += 1
        holding_dins.append((din, name))
        # Link to holding company
        directors.append({
            "din": din,
            "director_name": name,
            "cin": holding_cin,
            "designation": "Director",
            "appointment_date": "2005-04-12"
        })
        
    # Generate 12 subsidiaries
    for i in range(12):
        sub_roc = holding_roc
        sub_year = random.randint(2008, 2022)
        sub_cin = generate_cin(sub_roc, sub_year, 80000 + i)
        sub_name = f"TATA STEEL SUBSIDIARY {chr(65+i)} PRIVATE LIMITED"
        sub_address = generate_address(sub_roc) # Independent addresses
        sub_auth = float(random.randint(10, 50) * 1000000)
        sub_paid = sub_auth * random.uniform(0.8, 1.0)
        
        companies.append({
            "cin": sub_cin,
            "company_name": sub_name,
            "roc_code": sub_roc,
            "company_status": "Active",
            "date_of_incorporation": f"{sub_year}-06-{random.randint(1,28):02d}",
            "company_class": "PTC",
            "company_category": "Company limited by Shares",
            "authorized_capital": sub_auth,
            "paidup_capital": sub_paid,
            "registered_office_address": sub_address,
            "filing_status": "Filed"
        })
        
        # Link 1-2 common directors from holding company
        for din, name in random.sample(holding_dins, k=random.randint(1, 2)):
            directors.append({
                "din": din,
                "director_name": name,
                "cin": sub_cin,
                "designation": "Director",
                "appointment_date": f"{sub_year}-07-01"
            })
        # Link 1 unique director
        din, name = director_pool[director_index]
        director_index += 1
        directors.append({
            "din": din,
            "director_name": name,
            "cin": sub_cin,
            "designation": "Managing Director",
            "appointment_date": f"{sub_year}-07-01"
        })

    # 4. Generate the rest of the 1,000 background companies
    # Total background companies targets ~1000
    remaining_count = 1000 - len(companies) - ca_companies_count
    
    # We will generate the 35 CA companies first
    for i in range(ca_companies_count):
        year = random.randint(2010, 2023)
        cin = generate_cin(ca_address_roc, year, 70000 + i)
        name = f"{random.choice(COMP_PREFIXES)} {random.choice(COMP_KEYWORDS)} {random.choice(['India', 'Global', 'LTD'])} PRIVATE LIMITED"
        auth = float(random.choice([100000, 500000, 1000000]))
        paid = auth * random.uniform(0.5, 1.0)
        
        companies.append({
            "cin": cin,
            "company_name": name,
            "roc_code": ca_address_roc,
            "company_status": "Active",
            "date_of_incorporation": f"{year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "company_class": "PTC",
            "company_category": "Company limited by Shares",
            "authorized_capital": auth,
            "paidup_capital": paid,
            "registered_office_address": ca_address,
            "filing_status": random.choice(["Filed", "Filed", "Filed", "Defaulter"])
        })
        
        # Link 2 unique directors to each CA company
        for _ in range(2):
            din, dname = director_pool[director_index]
            director_index += 1
            directors.append({
                "din": din,
                "director_name": dname,
                "cin": cin,
                "designation": "Director",
                "appointment_date": f"{year}-08-15"
            })

    # Now generate the remaining general background companies
    for i in range(remaining_count):
        roc = random.choice(ROC_CODES)
        year = random.randint(2005, 2024)
        cin = generate_cin(roc, year, 10000 + i)
        name = f"{random.choice(COMP_PREFIXES)} {random.choice(COMP_KEYWORDS)} PRIVATE LIMITED"
        
        # Address assignment (some random sharing, but mostly unique)
        if random.random() < 0.1: # 10% chance to share one of the existing addresses
            address = random.choice(addresses_by_roc[roc])
        else:
            address = generate_address(roc)
            addresses_by_roc[roc].append(address)
            
        auth = float(random.choice([100000, 500000, 1000000, 2000000, 5000000]))
        # Small percentage have unpaid/low capital
        if random.random() < 0.05:
            paid = 0.0
        else:
            paid = auth * random.uniform(0.1, 1.0)
            
        status = random.choice(["Active", "Active", "Active", "Active", "Inactive", "Struck Off"])
        filing = random.choice(["Filed", "Filed", "Filed", "Nil Filed", "Defaulter"]) if status == "Active" else "Defaulter"
        
        companies.append({
            "cin": cin,
            "company_name": name,
            "roc_code": roc,
            "company_status": status,
            "date_of_incorporation": f"{year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "company_class": "PTC",
            "company_category": "Company limited by Shares",
            "authorized_capital": auth,
            "paidup_capital": paid,
            "registered_office_address": address,
            "filing_status": filing
        })
        
        # Assign 2-3 directors
        num_dirs = random.choice([2, 2, 3])
        comp_dirs = []
        for _ in range(num_dirs):
            # 5% chance to share a director with another company (simulating normal business directors)
            if random.random() < 0.03 and director_index > 10:
                # Pick a random director already allocated (but not from the CA or Tatas to prevent contamination)
                prev_dir = random.choice(directors[50:director_index])
                din = prev_dir["din"]
                dname = prev_dir["director_name"]
            else:
                din, dname = director_pool[director_index]
                director_index += 1
                
            directors.append({
                "din": din,
                "director_name": dname,
                "cin": cin,
                "designation": "Director",
                "appointment_date": f"{year}-06-30"
            })
            
    # Write to CSV
    with open(COMPANY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=companies[0].keys())
        writer.writeheader()
        writer.writerows(companies)
        
    with open(DIRECTOR_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=directors[0].keys())
        writer.writeheader()
        writer.writerows(directors)
        
    print(f"Generated {len(companies)} companies in {COMPANY_FILE}")
    print(f"Generated {len(directors)} director-company links in {DIRECTOR_FILE}")
    print("Baseline generation complete.")

if __name__ == "__main__":
    generate_data()
