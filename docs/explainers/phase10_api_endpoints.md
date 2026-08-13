# Phase 10 Explainer: FastAPI Backend APIs

## 1. Concepts & Architecture
To power the React Investigator Dashboard, we build a REST API backend using **FastAPI** and **Pydantic**. 

FastAPI is highly performant (built on Starlette and Uvicorn) and provides automatic OpenAPI (Swagger) documentation, making it extremely easy to test and debug endpoints during live SIH presentations.

---

### REST API Endpoints Specification

1. **`GET /api/health`**:
   - Returns API status and database connectivity indicator.

2. **`GET /api/dashboard/summary`**:
   - Returns aggregated metrics: total companies, directors, addresses, number of detected clusters, and number of high-risk clusters (those with risk score $\ge 75$).

3. **`GET /api/clusters`**:
   - Returns the ranked list of communities detected by Louvain, sorted by cluster risk score descending. Includes size, density, and average risk.

4. **`GET /api/clusters/{cluster_id}`**:
   - Returns the detailed listing of companies, directors, and addresses belonging to a specific cluster.

5. **`GET /api/clusters/{cluster_id}/graph`**:
   - Returns the Cytoscape-formatted JSON elements (nodes and edges) for that specific community's subgraph. The frontend uses this directly to render the interactive network visualization.

6. **`GET /api/companies/{cin}/evidence`**:
   - Returns the specific score breakdown (Address, Director, Burst, Mismatch) and explanation trail for a company.

7. **`GET /api/evaluation`**:
   - Runs and returns the results of the evaluation suite (detection rate, false positive rate, ranks, status).

---

## 2. Phase 10 Self-Assessment Quiz

### Question 1:
Why do we separate cluster listing (`/api/clusters`) from the cluster graph elements (`/api/clusters/{cluster_id}/graph`) instead of sending everything in one endpoint?
<details>
<summary><b>Show Answer</b></summary>
To optimize network payload size and loading speed. The list of all clusters contains summary statistics (like risk score and company count) which is lightweight. Graph visualization data (Cytoscape JSON nodes, edges, and coordinates) is heavier. Fetching the graph dynamically only when an investigator clicks on a specific cluster prevents loading lag in the dashboard.
</details>

### Question 2:
How does FastAPI's automatic OpenAPI documentation (Swagger UI) help during a hackathon evaluation?
<details>
<summary><b>Show Answer</b></summary>
It allows judges to see and interactively test the backend API layer directly from the browser (usually at <code>http://localhost:8000/docs</code>) without writing any frontend code. This proves that the backend is a real, modular REST service rather than a mocked system.
</details>

### Question 3:
What is the purpose of using Pydantic models in our FastAPI routes?
<details>
<summary><b>Show Answer</b></summary>
Pydantic enforces strict data validation and type checking on API requests and responses. If our DB returns a null value where the API expects a float, or if a frontend input is malformed, Pydantic immediately catches it and returns a clean, descriptive error. This prevents runtime crashes in the client interface.
</details>
