# Project Specification: Graph-Based Proactive Shell Company & Corporate Fraud Detection System

This specification is extracted from the *Tech Team Execution Brief* and serves as the primary source of truth for the system's problem statement, data assumptions, methodology, and limitations.

## 1. Problem Statement
The system aims to proactively screen corporate relationship networks from the Registrar of Companies (ROC) MCA21 filings and identify structurally anomalous clusters of companies. 

**Core Framing:** The system **proactively screens corporate relationship networks and flags structurally anomalous clusters for human investigation**. It does **NOT** definitively determine fraud or automatically label companies as shell companies.

## 2. Real Case Study Context: ₹734 Crore GST ITC Fraud
- **Entities Involved:** ~135 shell companies across Jharkhand and West Bengal.
- **Key Masterminds:** 4 individuals (Shiva Kumar Deora, Mohit Deora, Amit Kumar Gupta, and Amit Agarwal) who controlled the network using accomplices' identities as directors.
- **Modus Operandi:** Circular trading and Input Tax Credit (ITC) fraud by issuing fake invoices worth ~₹5,000 crore without actual supply of goods/services.
- **Structural Pattern:** A large number of companies (135) controlled by a small, overlapping set of directors, sharing physical addresses, coordinated registration dates, and nil/missing filing records.

## 3. Data Profile & Assumptions
1. **Real Data (data.gov.in):** Bulk company-level records containing `CIN`, `company name`, `status`, `incorporation date`, `authorized capital`, `paid-up capital`, `ROC`, `registered state`, `registered office address`, and `filing status`.
2. **Director Lookup Data (MCA21 V3 Portal):** Per-company lookup providing director names, `DIN` (Director Identification Number), and each director's linked companies. This is non-bulk, single-lookup data.
3. **Synthetic Augmentation:** Required because confirmed shell-company labels are not public. Real company records will serve as the background distribution, and a synthetic ring modeled on the case study will be planted.

## 4. Graph Architecture
Built using NetworkX:
- **Node Types:** 
  - `Company` (Key: `CIN`)
  - `Director` (Key: `DIN`)
  - `Address` (Key: Normalized Address String)
- **Edge Types:**
  - `DIRECTOR_OF` (`Director` -> `Company`)
  - `REGISTERED_AT` (`Company` -> `Address`)

## 5. The Four Risk Signals
1. **Signal A (Address Clustering Density):** Evaluates if an unusually high number of companies are registered at a single physical address.
2. **Signal B (Director Degree/Centrality):** Measures the number of companies linked to a single director (`DIN`). High degree centrality relative to the background indicates anomaly.
3. **Signal C (Incorporation Burst):** Detects batches of companies incorporated within a short, configurable time window (`INCORPORATION_WINDOW_DAYS`).
4. **Signal D (Capital/Filing Mismatch):** Detects companies with significant capital declared on paper but filing "nil" returns or failing to file altogether.

## 6. Thresholding & Scoring Methodology
1. **Freeze Thresholds First:** Calculate the mean, standard deviation, and z-score of features on the **real background data only** before adding/evaluating the synthetic fraud ring.
2. **Composite Likelihood Score:** A configurable weighted sum (initially 25% each) from 0 to 100 representing the **Shell Likelihood / Network Risk screening score**.
3. **Louvain Community Detection:** Groups connected companies into communities to identify network structures.
4. **Cluster Risk Score:** Computed based on average member risk, size, density, shared addresses/directors, and incorporation date variance.

## 7. Synthetic Scenarios for Evaluation
1. **Planted Fraud Ring:** 8–10 synthetic companies sharing 2–3 directors, 1 shared address, tightly clustered incorporation dates, low/nil filings, and capital/filing mismatch.
2. **Legitimate Edge Case:** A high-degree pattern representing a genuine holding company with subsidiaries, or a shared corporate agent/Chartered Accountant address. The detector must separate this from the fraud ring (i.e., not rank it as high-risk).

## 8. Limitations & Constraints
- The system flags structural anomalies for review; it does not represent legal proof of fraud.
- Direct bulk access to director mappings is not public; a simulated lookup registry is used to build relationships.
- Runs locally on CPU (ARM64 Windows compatible), utilizing NetworkX, Pandas, NumPy, and SciPy.
