# Phase 2 Explainer: Database Integration

## 1. Concepts & Architecture
In a real enterprise environment (like MCA21), filing data is stored in relational databases. For our prototype, we persist the validated company master records and director associations into a relational database using **SQLAlchemy** (Python's Object-Relational Mapper) and support **PostgreSQL** for production/persistent data.

### Dual-Database Fallback Design (SQLite Fallback)
To ensure the prototype is 100% reproducible and runs immediately on any system (including Windows ARM64 laptops without a pre-configured PostgreSQL server), we implement a fallback to a local **SQLite** database (`data/sih_fraud_detection.db`) if the PostgreSQL connection string fails or is not provided. This ensures instant setup, while remaining fully compatible with PostgreSQL.

### Database Tables Schema
1. **`companies` Table**:
   - `cin` (Primary Key, VARCHAR(21))
   - `company_name` (VARCHAR(255))
   - `roc_code` (VARCHAR(50))
   - `company_status` (VARCHAR(50))
   - `date_of_incorporation` (DATE)
   - `company_class` (VARCHAR(50))
   - `company_category` (VARCHAR(100))
   - `authorized_capital` (DECIMAL)
   - `paidup_capital` (DECIMAL)
   - `registered_office_address` (TEXT)
   - `filing_status` (VARCHAR(50))

2. **`director_relationships` Table**:
   - `id` (Primary Key, Auto-increment Integer)
   - `din` (VARCHAR(8))
   - `director_name` (VARCHAR(255))
   - `cin` (Foreign Key referencing `companies.cin`)
   - `designation` (VARCHAR(100))
   - `appointment_date` (DATE)

---

## 2. Phase 2 Self-Assessment Quiz

### Question 1:
Why do we model directors and companies in separate, related tables rather than a single flat file?
<details>
<summary><b>Show Answer</b></summary>
Because the relationship is <b>many-to-many</b>: one director can be associated with multiple companies, and one company has multiple directors. A relational schema with foreign keys prevents duplicate data entries and maintains referential integrity.
</details>

### Question 2:
Why is it crucial to use `din` (Director Identification Number) rather than `director_name` as the foreign key/identifier when building associations?
<details>
<summary><b>Show Answer</b></summary>
Common Indian names (e.g., "Rajesh Sharma") are highly duplicated across the country. Matching by name strings would merge unrelated individuals into the same graph node, generating false positives. The DIN is a unique 8-digit identification number issued by the Ministry of Corporate Affairs, guaranteeing a single identity.
</details>

### Question 3:
What is the benefit of using an Object-Relational Mapper (ORM) like SQLAlchemy for database integration in this prototype?
<details>
<summary><b>Show Answer</b></summary>
An ORM abstracts raw SQL syntax, allowing the application code to remain database-agnostic. This is what enables our prototype to switch seamlessly between a local SQLite file (for quick offline demos) and PostgreSQL (for persistent scaling) with zero changes to our query code.
</details>
