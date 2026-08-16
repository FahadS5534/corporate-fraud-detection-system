from sqlalchemy import Column, String, Date, Numeric, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Company(Base):
    __tablename__ = "companies"

    cin = Column(String(21), primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    registered_office_address = Column(String, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    date_of_registration = Column(Date, nullable=False)
    authorized_capital = Column(Numeric(15, 2), nullable=False)
    paidup_capital = Column(Numeric(15, 2), nullable=False)
    company_status = Column(String(50), nullable=False)
    filing_status = Column(String(50), nullable=False)

    # Relationships
    directors = relationship("DirectorRelationship", back_populates="company", cascade="all, delete-orphan")
    loans = relationship("CersaiSecurityInterest", back_populates="company", cascade="all, delete-orphan")
    defaults = relationship("RbiWilfulDefaulter", back_populates="company", cascade="all, delete-orphan")

class DirectorRelationship(Base):
    __tablename__ = "director_relationships"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    din = Column(String(10), index=True, nullable=False)
    director_name = Column(String(255), nullable=False)
    cin = Column(String(21), ForeignKey("companies.cin"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="directors")

class CersaiSecurityInterest(Base):
    __tablename__ = "cersai_security_interests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cin = Column(String(21), ForeignKey("companies.cin"), nullable=False)
    borrower_name = Column(String(255), nullable=True)
    lender_name = Column(String(255), nullable=False)
    security_type = Column(String(150), nullable=True)
    asset_description = Column(String, nullable=True)
    charge_amount = Column(Numeric(15, 2), nullable=False)
    charge_registration_date = Column(Date, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="loans")

class RbiWilfulDefaulter(Base):
    __tablename__ = "rbi_wilful_defaulters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cin = Column(String(21), ForeignKey("companies.cin"), nullable=False)
    company_name = Column(String(255), nullable=True)
    lender_name = Column(String(255), nullable=False)
    default_amount = Column(Numeric(15, 2), nullable=False)
    classification_date = Column(Date, nullable=True)
    wilful_default_reason = Column(String, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="defaults")

class GroundTruth(Base):
    __tablename__ = "ground_truth"

    cin = Column(String(21), primary_key=True, index=True)
    label = Column(String(50), nullable=False)
