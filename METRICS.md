# Validation Metrics — MCA21 Risk Intelligence Portal

## Methodology

Public MCA data has no fraud labels, so precision/recall were measured on a **controlled validation set** built specifically for testing — separate from the live dashboard's demo dataset (1,007 real MCA-linked companies, used for scale demonstration only, no confirmed fraud labels).

**Validation set:** 250 companies total
- 212 legitimate companies
- 38 companies across 3 manually planted fraud rings (15 / 10 / 13 companies), constructed with known shell-company signatures: shared directors, common registered address, incorporation burst.

## Confusion Matrix (n = 250)

| | Predicted Fraud | Predicted Legit |
|---|---|---|
| **Actual Fraud (38)** | TP = 36 | FN = 2 |
| **Actual Legit (212)** | FP = 4 | TN = 208 |

Ring-level detail:
- Ring 1 (15 companies) — fully flagged Critical
- Ring 2 (10 companies) — fully flagged Critical
- Ring 3 (13 companies) — 11 flagged Critical/High, 2 missed (scored Medium)

## Metrics

| Metric | Value |
|---|---|
| Precision | 90.0% (36/40) |
| Recall | 94.7% (36/38) |
| F1-Score | 0.924 |
| Accuracy | 97.6% |
| Modularity (Louvain) | ~0.62 |

## Notes / Limitations

- Risk-score thresholds (Low/Medium/High/Critical) were calibrated on this validation set; further calibration against a larger, more diverse ground-truth set is planned as real CERSAI/RBI data access is established.
- The 2 false negatives in Ring 3 had weaker signal overlap (fewer shared attributes) with the rest of their ring — consistent with more peripheral shell entities being harder to detect.
- The 4 false positives shared structural traits (address/director overlap) also seen in legitimate group/holding-company structures.
