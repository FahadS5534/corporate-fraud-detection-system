# Phase 3 Explainer: Graph Construction with NetworkX

## 1. Concepts & Architecture
To model the complex relationships between companies, directors, and physical addresses, we use a **bipartite/multipartite relationship graph**. Standard relational tables are inefficient at querying deep, multi-level relationship paths (such as finding circular director structures or shared addresses across many entities).

### Graph Elements
Our network graph consists of three node types and two edge types:

```text
    [Director Node: DIN] --(DIRECTOR_OF)--> [Company Node: CIN] --(REGISTERED_AT)--> [Address Node: AddressText]
```

- **Nodes**:
  - `Company` nodes (represented by `cin`, e.g., `U12345JH2020PTC001234`)
  - `Director` nodes (represented by `din`, e.g., `00123456`)
  - `Address` nodes (represented by the cleaned, uppercase normalized address text)
- **Edges**:
  - `DIRECTOR_OF` connects a `Director` to a `Company`.
  - `REGISTERED_AT` connects a `Company` to an `Address`.

### Using NetworkX
We use the **NetworkX** library in Python to build and analyze this graph structure. NetworkX stores the graph in-memory as adjacency dictionaries, allowing rapid traversal and structural query capabilities.

### Key Graph Queries We Support
1. **Neighborhood**: Find all directors or addresses connected to a given company, or all companies connected to an address.
2. **Degree**: Find the count of connections (e.g., an address degree of 35 means 35 companies share it).
3. **Connected Components**: Find isolated subgraphs where entities have no outside links.

---

## 2. Phase 3 Self-Assessment Quiz

### Question 1:
What are the node types and edge types in our MCA network graph, and how are they directed?
<details>
<summary><b>Show Answer</b></summary>
The nodes are <b>Company</b> (CIN), <b>Director</b> (DIN), and <b>Address</b> (Normalized Address string). The edges are <b>DIRECTOR_OF</b> (connecting Director to Company) and <b>REGISTERED_AT</b> (connecting Company to Address). Although edges represent relations, we typically model this as an undirected graph or bi-directional graph in NetworkX to make traversal in both directions (e.g., Company to Director, and Director to Company) equally fast.
</details>

### Question 2:
Why do we choose NetworkX over a standalone graph database (like Neo4j) for the initial prototype phase?
<details>
<summary><b>Show Answer</b></summary>
NetworkX operates entirely in-memory using Python data structures, which eliminates the system dependencies and overhead of running a separate database server. For a prototype scale of 1,000–5,000 entities, NetworkX is extremely fast, uses minimal memory, and runs out-of-the-box on standard CPU configurations (including ARM64 Windows laptops).
</details>

### Question 3:
How does a bipartite relationship graph help in detecting GST or tax fraud over standard SQL tables?
<details>
<summary><b>Show Answer</b></summary>
In SQL, finding shared associations requires writing complex, expensive self-joins (e.g. joining the company table to itself via directors, then to itself via addresses). In a graph, relationships are first-class citizens. We can trace associations of any length (e.g., Company A -> Director X -> Company B -> Address Y -> Company C) using simple path traversal algorithms (like BFS or shortest path), making network-based pattern discovery simple and fast.
</details>
