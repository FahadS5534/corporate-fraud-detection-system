import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Default to SQLite fallback. If f:\SIH exists, use local absolute path, otherwise use container-relative path.
if os.path.exists("f:\\SIH"):
    DEFAULT_SQLITE_URL = "sqlite:///f:/SIH/data/sih_fraud_detection.db"
    os.makedirs(r"f:\SIH\data", exist_ok=True)
else:
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
