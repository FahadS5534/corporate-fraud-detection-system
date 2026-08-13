from sqlalchemy import Column, String, Date, Numeric, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Company(Base):
    __tablename__ = "companies"

    cin = Column(String(21), primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    roc_code = Column(String(50), nullable=False)
    company_status = Column(String(50), nullable=False)
    date_of_incorporation = Column(Date, nullable=False)
    company_class = Column(String(50), nullable=False)
    company_category = Column(String(100), nullable=False)
    authorized_capital = Column(Numeric(15, 2), nullable=False)
    paidup_capital = Column(Numeric(15, 2), nullable=False)
    registered_office_address = Column(String, nullable=False)
    filing_status = Column(String(50), nullable=False)

    # Relationships
    directors = relationship("DirectorRelationship", back_populates="company", cascade="all, delete-orphan")

class DirectorRelationship(Base):
    __tablename__ = "director_relationships"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    din = Column(String(8), index=True, nullable=False)
    director_name = Column(String(255), nullable=False)
    cin = Column(String(21), ForeignKey("companies.cin"), nullable=False)
    designation = Column(String(100), nullable=True)
    appointment_date = Column(Date, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="directors")
