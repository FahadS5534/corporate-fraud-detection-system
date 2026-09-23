import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Vercel functions have an ephemeral, read-only deployment filesystem. This app
# only reads its pre-seeded database at runtime, so point SQLAlchemy at the
# bundled database in read-only URI mode when running there.
if os.environ.get("VERCEL") == "1":
    repo_root = Path(__file__).resolve().parents[2]
    database_path = (repo_root / "data" / "sih_fraud_detection.db").as_posix()
    DEFAULT_SQLITE_URL = f"sqlite:///file:{database_path}?mode=ro&uri=true"
elif os.path.exists("f:\\SIH"):
    # Local Windows development path used by the original project setup.
    DEFAULT_SQLITE_URL = "sqlite:///f:/SIH/data/sih_fraud_detection.db"
    os.makedirs(r"f:\SIH\data", exist_ok=True)
else:
    # Local development and container-relative fallback.
    DEFAULT_SQLITE_URL = "sqlite:///data/sih_fraud_detection.db"
    os.makedirs("data", exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

# configure connect_args only for SQLite to allow multi-threaded access
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception as e:
    print(f"Warning: Failed to connect to DATABASE_URL: {DATABASE_URL}. Error: {e}")
    print("Falling back to local SQLite database...")
    engine = create_engine(DEFAULT_SQLITE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
