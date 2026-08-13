# Phase 4 Explainer: The Four Risk Signal Engines

## 1. Concepts & Architecture
To proactively detect suspicious corporate networks, the system implements **four specific risk signal engines** grounded in real-world regulatory fraud investigations (such as GST invoice mills and shell syndicates). 

An individual signal firing is **not** evidence of fraud. Legitimate organizations can match single patterns (e.g., a shared address or a high director degree). The system uses these signals as raw risk inputs to compile a composite screening score.

---

### Signal A: Address Clustering Density
*   **Methodology**: Count the number of active companies registered at the exact same physical address.
*   **Formula**: For an Address node $A$, its degree in the bipartite graph represents the company count:
    $$\text{AddressDegree}(A) = \text{number of connected company nodes}$$
*   **Risk Scaling**: We normalize this degree count. If it exceeds a statistical threshold, it flags a high risk value.
*   **Grounding**: Syndicate orchestrators float multiple entities in the same room or CA office to minimize setup overhead.

---

### Signal B: Director Degree Centrality
*   **Methodology**: Count the number of companies a single Director (`DIN`) is on the board of.
*   **Formula**: For a Director node $D$, the degree represents:
    $$\text{DirectorDegree}(D) = \text{number of connected company nodes}$$
*   **Risk Scaling**: The higher the degree, the higher the anomaly score (since an individual is legally and practically restricted from managing dozens of active firms).
*   **Grounding**: Orchestrators use dummy directors (accomplices, employees, or stolen IDs) to register dozens of companies under a small pool of names.

---

### Signal C: Incorporation Burst Detection
*   **Methodology**: Identify clusters of companies registered in close chronological proximity (a temporal burst).
*   **Formula**: For a set of companies in a community/subgraph, we calculate the span of incorporation dates. If the time difference between consecutive incorporations is within a configurable window (e.g., `INCORPORATION_WINDOW_DAYS = 30`), we compute a high temporal risk.
*   **Grounding**: Fraud rings are floated in rapid batches to serve a specific tax cycle or invoice mill run before being abandoned or caught.

---

### Signal D: Capital & Filing Mismatch
*   **Methodology**: Evaluate company financial health and filing status to detect "paper-only" companies.
*   **Anomaly Flag**: High risk if the company has:
    1. **Zero Paid-up Capital**: Stated authorized capital exists, but paid-up capital is zero or near-zero, meaning no real capital ever arrived.
    2. **Filing Default**: Company filing status is "Defaulter" or "Nil Filed", meaning no real business activity is reported despite registration.
*   **Grounding**: Shell companies are initialized with minimal real cash and file no actual sales/tax returns, yet issue fake invoice transactions to external firms.

---

## 2. Phase 4 Self-Assessment Quiz

### Question 1:
Why is a shared registered address alone not sufficient to flag a company as a high-risk fraud suspect?
<details>
<summary><b>Show Answer</b></summary>
Many legitimate businesses share addresses. For instance, Chartered Accountant (CA) offices, legal agents, and corporate services firms act as the registered office address for hundreds of independent, genuine client companies. Flagging companies based solely on address sharing would create massive numbers of false positives.
</details>

### Question 2:
How do we handle director identification to prevent false matches due to identical names?
<details>
<summary><b>Show Answer</b></summary>
We map relationships using the <b>DIN (Director Identification Number)</b>. Matching by name strings is highly unreliable because common names (e.g., "Amit Kumar") occur thousands of times across unrelated people in India. Joining on DIN ensures that degree centrality accurately represents the behavior of a single unique individual.
</details>

### Question 3:
How does incorporation burst detection help identify organized tax fraud?
<details>
<summary><b>Show Answer</b></summary>
Legitimate businesses are typically established organically over years as market demand arises. Shell company rings, however, are usually registered in rapid batches (within days or weeks of each other) to execute a coordinated invoice-churning scheme. Finding a cluster of companies with highly concentrated registration dates points strongly to coordinated setup.
</details>
