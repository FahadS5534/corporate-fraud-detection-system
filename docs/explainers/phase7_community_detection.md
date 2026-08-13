# Phase 7 Explainer: Louvain Community Detection

## 1. Concepts & Architecture
Evaluating companies individually is not enough to uncover structured tax evasion rings. Syndicate operators establish networks that coordinate with each other. To detect these networks, we use **Louvain Community Detection**.

---

### What is Louvain Community Detection?
The Louvain algorithm is an unsupervised graph clustering method that partitions a network into distinct communities (or clusters). It does this by maximizing the graph's **Modularity** ($Q$).

- **Modularity**: A measure of the density of edges inside communities compared to edges between communities. High modularity means nodes within a community have many links among themselves, but very few links to nodes in other communities.
- **Why Louvain?**: It is extremely fast ($O(V \log V)$ average time complexity) and scales to millions of nodes, making it ideal for large-scale corporate relationship networks.

---

### Per-Cluster Metrics
Once the Louvain algorithm divides the graph into communities, we compute statistics for each community to assess its collective risk:

1. **Cluster Size**: Number of companies in the community.
2. **Average Company Risk**: The mean composite score of all member companies.
3. **Shared Address Count**: Number of distinct registered office addresses in the cluster (a value of 1 means all companies share the exact same address).
4. **Shared Director Count**: Number of overlapping director nodes in the cluster.
5. **Incorporation Date Variance**: The variance of incorporation dates (measured in days). A low variance indicates a coordinated burst of registrations.
6. **Network Density**: The ratio of actual edges to maximum possible edges within the cluster. High density indicates close relationships.
7. **Cluster Risk Score**: A composite of average member risk, size, and date concentration.

---

## 2. Phase 7 Self-Assessment Quiz

### Question 1:
What does "Modularity maximization" mean in the context of Louvain clustering?
<details>
<summary><b>Show Answer</b></summary>
Modularity maximization means partitioning the graph such that the number of internal connections within communities is maximized, while the number of cross-community connections is minimized. This groups tightly connected clusters (like overlapping company-director-address rings) together, separating them from the general, sparse background network.
</details>

### Question 2:
How does Louvain community detection help expose a 135-company GST fraud syndicate?
<details>
<summary><b>Show Answer</b></summary>
Instead of showing an investigator 135 separate alerts (which causes review fatigue), Louvain clusters these 135 companies together because they share the same pool of directors and addresses. The system then presents the investigator with <b>one single high-risk cluster containing all 135 companies</b>. Tracing the structure of the community immediately reveals the size and shape of the syndicate.
</details>

### Question 3:
If a Louvain cluster has a high average company risk but a very high incorporation date variance (e.g. 5,000 days), what does this tell an investigator?
<details>
<summary><b>Show Answer</b></summary>
It suggests that while the companies in this cluster share directors or addresses (causing a high average risk), they were registered gradually over a span of many years (high date variance). This is typical of a legitimate corporate holding structure or CA registry, rather than a coordinated "fly-by-night" shell ring that was floated in a short window.
</details>
