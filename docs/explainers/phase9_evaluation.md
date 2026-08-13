# Phase 9 Explainer: The Evaluation Suite

## 1. Concepts & Architecture
To verify that the graph analytics pipeline is functional, robust, and mathematically valid, we implement an automated **Evaluation Suite**.

The evaluation is executed via:
```bash
python scripts/run_detection.py --evaluation
```

### The Evaluation Metrics

1. **Planted Ring Detection Rate**:
   $$\text{Detection Rate} = \frac{\text{Planted companies correctly detected inside high-risk clusters}}{\text{Total planted companies (10)}} \times 100\%$$
   - *Target*: 100% (All 10 planted companies should be grouped together and flagged).

2. **Detection Rank of the Planted Ring**:
   - The position of the planted community in the list of clusters ranked by risk.
   - *Target*: Rank #1 (The planted fraud ring should be the most suspicious cluster in the network).

3. **False Positive Rate (FPR)**:
   $$\text{FPR} = \frac{\text{Background companies flagged as high-risk (Score } \ge 75\text{)}}{\text{Total background companies (1,000)}} \times 100\%$$
   - *Target*: $< 2.0\%$ (Minimal false alarms on the clean background data).

4. **Legitimate Edge Case Separation (Qualitative Check)**:
   - Verify that the **CA Address Cluster** (35 companies) and **Tata Subsidiaries** (13 companies) are ranked far below the planted ring, demonstrating that the system differentiates between structured coordination and normal commercial setups.

---

## 2. Phase 9 Self-Assessment Quiz

### Question 1:
Why is the "Detection Rank" of the fraud ring one of the most critical evaluation metrics for an investigator?
<details>
<summary><b>Show Answer</b></summary>
In a real-world enforcement agency (like GST Intelligence or ED), investigators have limited time and bandwidth. They cannot review thousands of alerts. If the true fraud ring is flagged but ranked at #45, it will likely never be reviewed. The true value of the system lies in its ability to bubbles up the most critical threats to <b>Rank #1 or #2</b>, optimizing investigator resources.
</details>

### Question 2:
How does a low False Positive Rate (FPR) impact the credibility of the fraud detection system?
<details>
<summary><b>Show Answer</b></summary>
A high false positive rate (e.g., 20%) means the system "cries wolf" constantly, flooding investigators with false alerts for legitimate firms. This leads to alert fatigue, causing investigators to ignore the system altogether. Keeping the FPR in the single digits is essential to building user trust and system credibility.
</details>

### Question 3:
If the evaluation script reports a 100% detection rate but ranks the CA Office address at Rank #1 instead of the fraud ring, what is failing, and how do we fix it?
<details>
<summary><b>Show Answer</b></summary>
The scoring weights or z-score thresholds are tuned incorrectly. It means the system is over-valuing the <b>Address Clustering Signal</b> (assigning too much risk to shared locations) and under-valuing director overlap and incorporation bursts. To fix this, we adjust the weights in the <code>.env</code> file, increasing the impact of director centrality and registration bursts.
</details>
