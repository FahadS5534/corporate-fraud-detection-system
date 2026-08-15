"""
Linked synthetic dataset generator: MCA + CERSAI + RBI Wilful Defaulter List
=============================================================================
v2 - Now generates MULTIPLE distinct fraud-ring networks (not just one), so the
final ranked watchlist shows several genuinely different suspicious clusters
for an investigator to review - not a single hardcoded example.

Output files:
  mca_companies.csv              - company master data (MCA-style)
  mca_directors.csv              - director-company linkage (MCA21 V3-style)
  cersai_security_interests.csv  - loan/security-interest records
  rbi_wilful_defaulters.csv      - wilful defaulter classification records
  ground_truth.csv               - labels (ONLY for evaluation, never fed to the algorithm)

Total companies: ~465 (within the 400-600 target range)
  - ~440 background (realistic, independent, non-uniform)
  - 7    legitimate high-degree edge case (false-positive test)
  - 3 DISTINCT fraud-ring networks of varying size and "flavor":
      Ring A "Classic dense ring"     - 9 companies, Kolkata, 3 shared directors,
                                        shared fictional lender, 6/9 already flagged defaulter
      Ring B "Subtler ring"           - 6 companies, Pune, 2 shared directors,
                                        partial address overlap, only 2/6 flagged defaulter
                                        (tests whether weaker signals still get caught)
      Ring C "Defaulter-heavy ring"   - 5 companies, Ahmedabad, tight incorporation burst,
                                        ALL 5 already flagged defaulter, different lender
                                        (tests a different signal combination)

Design principles preserved:
  - Real Indian first/last name pools -> no placeholder-style fake names
  - CIN/DIN follow correct real-world structural format (synthetic values, valid shape)
  - Background population is realistic and non-uniform, not designed to be "easy to catch"
  - Each ring only partially appears in the wilful-defaulter layer (realism), except Ring C
  - A deliberate legitimate high-degree edge case is included (false-positive test)
  - Thresholds must be computed from BACKGROUND stats only (see your scoring script)
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)  # reproducibility - document this seed in your report

# --------------------------------------------------------------------------
# 1. REALISTIC NAME POOLS (Indian names, not placeholders)
# --------------------------------------------------------------------------

FIRST_NAMES = [
    "Rajesh", "Suresh", "Amit", "Vikram", "Anil", "Sunil", "Rakesh", "Deepak",
    "Sanjay", "Ashok", "Ramesh", "Mahesh", "Prakash", "Vinod", "Manoj",
    "Priya", "Anita", "Sunita", "Kavita", "Rekha", "Neha", "Pooja", "Meena",
    "Shalini", "Nisha", "Geeta", "Kiran", "Rohit", "Ankit", "Nitin",
    "Arjun", "Sandeep", "Vivek", "Ajay", "Vijay", "Ravi", "Naveen", "Gaurav",
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Agarwal", "Singh", "Kumar", "Mehta", "Shah",
    "Patel", "Jain", "Malhotra", "Chopra", "Kapoor", "Reddy", "Iyer",
    "Nair", "Menon", "Rao", "Desai", "Joshi", "Bhatt", "Trivedi", "Pandey",
    "Mishra", "Tiwari", "Chauhan", "Yadav", "Saxena", "Bansal", "Goyal",
]

COMPANY_SUFFIXES = ["Pvt Ltd", "Private Limited", "Enterprises Pvt Ltd", "Industries Pvt Ltd",
                     "Trading Co Pvt Ltd", "Exports Pvt Ltd", "Ventures Pvt Ltd"]

COMPANY_WORDS = [
    "Shree", "Shri", "Om", "Jai", "Bharat", "National", "Universal", "Global",
    "Prime", "Metro", "Royal", "Elite", "Sunrise", "Silver", "Golden", "Vishwa",
    "Ganga", "Sagar", "Krishna", "Laxmi", "Saraswati", "Vardhman", "Balaji",
    "Aditya", "Shakti", "Vishal", "Continental", "Pioneer", "Everest", "Orion",
]

COMPANY_SECTORS = [
    "Textiles", "Steel", "Chemicals", "Logistics", "Infrastructure", "Traders",
    "Agro", "Pharma", "Plastics", "Electronics", "Constructions", "Foods",
]

CITIES = [
    ("Mumbai", "MH", "27"), ("Delhi", "DL", "07"), ("Bengaluru", "KA", "29"),
    ("Kolkata", "WB", "19"), ("Chennai", "TN", "33"), ("Pune", "MH", "27"),
    ("Ahmedabad", "GJ", "24"), ("Jaipur", "RJ", "08"), ("Surat", "GJ", "24"),
    ("Lucknow", "UP", "09"),
]

BANKS = [
    "State Bank of India", "Punjab National Bank", "Bank of Baroda",
    "Canara Bank", "Union Bank of India", "HDFC Bank", "ICICI Bank",
    "Axis Bank", "IDBI Bank", "Indian Overseas Bank",
]

used_names = set()
mca_companies, mca_directors, cersai_records, wilful_records, ground_truth = [], [], [], [], []
_used_cins, _used_dins = set(), set()


def random_company_name():
    while True:
        name = f"{random.choice(COMPANY_WORDS)} {random.choice(COMPANY_SECTORS)} {random.choice(COMPANY_SUFFIXES)}"
        if name not in used_names:
            used_names.add(name)
            return name


def random_person_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_address(city, state):
    plot = random.randint(1, 400)
    area = random.choice(["Industrial Area", "MIDC", "Sector", "Estate", "Colony", "Road"])
    return f"Plot {plot}, {area}, {city}, {state}"


def generate_cin(state_code, year):
    while True:
        industry = f"{random.randint(10000, 99999)}"
        seq = f"{random.randint(1, 999999):06d}"
        cin = f"U{industry}{state_code}{year}PTC{seq}"
        if cin not in _used_cins:
            _used_cins.add(cin)
            return cin


def generate_din():
    while True:
        din = f"{random.randint(10000000, 99999999)}"
        if din not in _used_dins:
            _used_dins.add(din)
            return din


def add_company(cin, name, address, city, state, incorp_date, auth_cap, paidup_cap, status, label):
    mca_companies.append({
        "CIN": cin, "COMPANY_NAME": name, "REGISTERED_OFFICE_ADDRESS": address,
        "CITY": city, "STATE": state, "DATE_OF_REGISTRATION": incorp_date.strftime("%Y-%m-%d"),
        "AUTHORIZED_CAPITAL": auth_cap, "PAIDUP_CAPITAL": paidup_cap,
        "COMPANY_STATUS": status,
    })
    ground_truth.append({"CIN": cin, "label": label})


def add_director(cin, din, director_name):
    mca_directors.append({"CIN": cin, "DIN": din, "DIRECTOR_NAME": director_name})


def add_cersai(cin, name, lender, sec_type, asset, amount, date):
    cersai_records.append({
        "CIN": cin, "BORROWER_NAME": name, "LENDER_NAME": lender,
        "SECURITY_TYPE": sec_type, "ASSET_DESCRIPTION": f"{asset} - {name}",
        "CHARGE_AMOUNT": amount, "CHARGE_REGISTRATION_DATE": date.strftime("%Y-%m-%d"),
    })


def add_wilful(cin, name, lender, amount, date, reason="Diversion of funds"):
    wilful_records.append({
        "CIN": cin, "COMPANY_NAME": name, "LENDER_NAME": lender,
        "DEFAULT_AMOUNT": amount, "CLASSIFICATION_DATE": date.strftime("%Y-%m-%d"),
        "WILFUL_DEFAULT_REASON": reason,
    })


# --------------------------------------------------------------------------
# 2. BACKGROUND POPULATION (realistic, non-uniform, real-world-like)
# --------------------------------------------------------------------------

N_BACKGROUND = 440
N_LEGIT_EDGE_CASE = 7

for i in range(N_BACKGROUND):
    city, state, state_code = random.choice(CITIES)
    year = random.randint(2005, 2024)
    cin = generate_cin(state_code, year)
    name = random_company_name()
    address = random_address(city, state)
    incorp_date = datetime(year, random.randint(1, 12), random.randint(1, 28))
    auth_cap = random.choice([100000, 500000, 1000000, 2500000, 5000000, 10000000])
    paidup_cap = int(auth_cap * random.uniform(0.3, 1.0))
    status = random.choices(["Active", "Active", "Active", "Dormant", "Strike Off"], weights=[70, 15, 5, 5, 5])[0]

    add_company(cin, name, address, city, state, incorp_date, auth_cap, paidup_cap, status, "normal")

    n_dir = random.choices([1, 2], weights=[70, 30])[0]
    for _ in range(n_dir):
        add_director(cin, generate_din(), random_person_name())

    if random.random() < 0.18:
        add_cersai(cin, name, random.choice(BANKS),
                   random.choice(["hypothecation", "mortgage", "pledge"]),
                   random.choice(["Plant & Machinery", "Land & Building", "Inventory"]),
                   random.choice([500000, 1200000, 2000000, 3000000]),
                   incorp_date + timedelta(days=random.randint(90, 1500)))
        if random.random() < 0.04:
            add_wilful(cin, name, random.choice(BANKS),
                       random.choice([1500000, 2800000]),
                       incorp_date + timedelta(days=random.randint(1200, 2500)),
                       random.choice(["Diversion of funds", "Siphoning of funds"]))

# Deliberate legitimate high-degree edge case: shared address, but DIFFERENT directors each
REGISTERED_AGENT_ADDRESS = "Plot 88, Nariman Point Business Centre, Mumbai, MH"
for i in range(N_LEGIT_EDGE_CASE):
    year = random.randint(2010, 2022)
    cin = generate_cin("27", year)
    name = random_company_name()
    incorp_date = datetime(year, random.randint(1, 12), random.randint(1, 28))  # spread out, NOT bursty
    auth_cap = random.choice([500000, 1000000, 2000000])
    paidup_cap = int(auth_cap * random.uniform(0.4, 1.0))

    add_company(cin, name, REGISTERED_AGENT_ADDRESS, "Mumbai", "MH", incorp_date,
                auth_cap, paidup_cap, "Active", "legit_edge_case")
    add_director(cin, generate_din(), random_person_name())


# --------------------------------------------------------------------------
# 3. MULTIPLE DISTINCT FRAUD-RING NETWORKS
# --------------------------------------------------------------------------

def build_ring(ring_id, n_companies, city, state, state_code, base_year, base_month,
                n_shared_directors, lender_name, n_defaulters, burst_days, address_variants=1):
    """
    Builds one fraud-ring network with configurable characteristics, so each
    ring has a genuinely different structural "flavor" rather than being a
    copy-pasted clone of the same pattern.
    """
    ring_din_pool = [generate_din() for _ in range(n_shared_directors)]
    ring_director_names = [random_person_name() for _ in range(n_shared_directors)]
    base_date = datetime(base_year, base_month, random.randint(1, 10))

    addresses = [random_address(city, state) for _ in range(address_variants)]

    ring_cins = []
    for i in range(n_companies):
        cin = generate_cin(state_code, base_year)
        ring_cins.append(cin)
        name = random_company_name()
        incorp_date = base_date + timedelta(days=random.randint(0, burst_days))
        auth_cap = random.choice([1000000, 2500000, 5000000])
        paidup_cap = 0

        address = addresses[i % len(addresses)]
        add_company(cin, name, address, city, state, incorp_date, auth_cap, paidup_cap,
                    "Active", f"fraud_ring_{ring_id}")

        din = random.choice(ring_din_pool)
        dname = ring_director_names[ring_din_pool.index(din)]
        add_director(cin, din, dname)

        add_cersai(cin, name, lender_name, "hypothecation", "Plant & Machinery",
                   random.choice([2000000, 3500000, 5000000]),
                   incorp_date + timedelta(days=random.randint(30, 90)))

        if i < n_defaulters:
            add_wilful(cin, name, lender_name,
                       random.choice([2500000, 4000000, 4800000]),
                       incorp_date + timedelta(days=random.randint(400, 600)))

    return ring_cins


ring_a = build_ring(
    ring_id="A", n_companies=9, city="Kolkata", state="WB", state_code="19",
    base_year=2021, base_month=6, n_shared_directors=3,
    lender_name="Vardhman Cooperative Bank Ltd", n_defaulters=6, burst_days=12,
    address_variants=1,
)

ring_b = build_ring(
    ring_id="B", n_companies=6, city="Pune", state="MH", state_code="27",
    base_year=2022, base_month=2, n_shared_directors=2,
    lender_name="Continental Urban Cooperative Bank", n_defaulters=2, burst_days=25,
    address_variants=2,
)

ring_c = build_ring(
    ring_id="C", n_companies=5, city="Ahmedabad", state="GJ", state_code="24",
    base_year=2020, base_month=11, n_shared_directors=2,
    lender_name="Orion Multistate Cooperative Bank", n_defaulters=5, burst_days=6,
    address_variants=1,
)

# --------------------------------------------------------------------------
# 4. WRITE OUTPUT FILES
# --------------------------------------------------------------------------

def write_csv(filename, rows, fieldnames):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {filename}")


write_csv("mca_companies.csv", mca_companies,
          ["CIN", "COMPANY_NAME", "REGISTERED_OFFICE_ADDRESS", "CITY", "STATE",
           "DATE_OF_REGISTRATION", "AUTHORIZED_CAPITAL", "PAIDUP_CAPITAL", "COMPANY_STATUS"])

write_csv("mca_directors.csv", mca_directors, ["CIN", "DIN", "DIRECTOR_NAME"])

write_csv("cersai_security_interests.csv", cersai_records,
          ["CIN", "BORROWER_NAME", "LENDER_NAME", "SECURITY_TYPE", "ASSET_DESCRIPTION",
           "CHARGE_AMOUNT", "CHARGE_REGISTRATION_DATE"])

write_csv("rbi_wilful_defaulters.csv", wilful_records,
          ["CIN", "COMPANY_NAME", "LENDER_NAME", "DEFAULT_AMOUNT",
           "CLASSIFICATION_DATE", "WILFUL_DEFAULT_REASON"])

write_csv("ground_truth.csv", ground_truth, ["CIN", "label"])

total = N_BACKGROUND + N_LEGIT_EDGE_CASE + len(ring_a) + len(ring_b) + len(ring_c)
print(f"\nSummary: {N_BACKGROUND} background + {N_LEGIT_EDGE_CASE} legit-edge-case "
      f"+ Ring A({len(ring_a)}) + Ring B({len(ring_b)}) + Ring C({len(ring_c)}) = {total} total companies")
print(f"CERSAI records: {len(cersai_records)} | Wilful defaulter records: {len(wilful_records)}")
print("\nThree distinct suspicious networks are now embedded:")
print("  Ring A - classic dense ring (9 cos, 3 directors, 1 address, 6/9 defaulters)")
print("  Ring B - subtler ring (6 cos, 2 directors, 2 address variants, 2/6 defaulters)")
print("  Ring C - defaulter-heavy ring (5 cos, 2 directors, tight 6-day burst, 5/5 defaulters)")
print("\nIMPORTANT: ground_truth.csv is for YOUR evaluation only.")
print("Never feed the 'label' column into the detection algorithm - that would invalidate the test.")
