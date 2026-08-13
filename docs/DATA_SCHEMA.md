# Data Schema Specification

This document details the schema of the raw, processed, and synthetic datasets used by the fraud detection system.

## 1. Company Master Dataset (Raw & Processed)

Source: `data.gov.in` bulk exports (simulated baseline background data).

| Field Name | Type | Description | Validation / Constraints |
| :--- | :--- | :--- | :--- |
| `cin` | VARCHAR(21) | Corporate Identification Number (Primary Key) | Exactly 21 chars, alphanumeric. |
| `company_name` | VARCHAR(255) | Registered legal name of the company | Cannot be empty. |
| `roc_code` | VARCHAR(50) | Registrar of Companies code (e.g., ROC-RANCHI) | Valid ROC code. |
| `company_status` | VARCHAR(50) | Status (Active, Struck Off, Liquidated) | Enumerated set. |
| `date_of_incorporation` | DATE | Date the company was registered | YYYY-MM-DD, cannot be in future. |
| `company_class` | VARCHAR(50) | Class of company (Public, Private, Private(One Person Company)) | Enumerated set. |
| `company_category` | VARCHAR(100) | Category (Company limited by Shares, Company limited by Guarantee) | Enumerated. |
| `authorized_capital` | NUMERIC(15,2) | Maximum capital company is authorized to raise | >= 0. |
| `paidup_capital` | NUMERIC(15,2) | Actual capital paid by shareholders | >= 0 and <= authorized_capital. |
| `registered_office_address` | TEXT | Official registered address | Text string, must contain state/PIN. |
| `filing_status` | VARCHAR(50) | Recent filing status (Filed, Nil Filed, Defaulter) | Enumerated set. |

## 2. Director Registry Dataset (MCA21 V3 Lookup Model)

Because company-director links are not part of the bulk open-data downloads, we model this registry as if it were compiled from the V3 Portal lookup.

| Field Name | Type | Description | Validation / Constraints |
| :--- | :--- | :--- | :--- |
| `din` | VARCHAR(8) | Director Identification Number (Primary Key) | Exactly 8 digits, numeric string. |
| `director_name` | VARCHAR(255) | Name of the Director | Title-cased. |
| `cin` | VARCHAR(21) | Linked company's CIN (Foreign Key) | References `companies.cin`. |
| `designation` | VARCHAR(100) | Role (Director, Managing Director, Alternate Director) | Text. |
| `appointment_date` | DATE | Date of appointment | YYYY-MM-DD. |

## 3. Normalized Address Model

To prevent minor spelling differences or formatting from creating duplicate physical locations, addresses are cleaned and hashed.

| Field Name | Type | Description | Normalization Rules |
| :--- | :--- | :--- | :--- |
| `address_id` | VARCHAR(64) | SHA-256 hash of normalized address text | Unique ID for graph. |
| `raw_address` | TEXT | Original registered office address | Unaltered. |
| `normalized_address` | TEXT | Standardized address string | Uppercase, punctuation removed, spacing normalized. |
| `pin_code` | VARCHAR(6) | extracted Indian PIN code | 6 digits, if present. |
| `state` | VARCHAR(50) | Registered state (e.g. West Bengal, Jharkhand) | Standard state name. |
