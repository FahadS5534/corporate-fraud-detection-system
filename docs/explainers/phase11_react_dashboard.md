# Phase 11 Explainer: React Investigator Dashboard

## 1. Concepts & Architecture
The final interface is a premium React dashboard built with **TypeScript**, **Vite**, **Cytoscape.js** (for relationship graphs), and **Recharts** (for interactive risk distribution charts).

---

### Dashboard Sections & Features

1. **Aggregated Summary Banner**:
   - Displays KPIs like Total Companies, Total Directors, Total Addresses, total communities discovered, and a red alert badge for high-risk clusters.

2. **Cluster Risk Rankings (The Investigator Table)**:
   - A searchable, paginated table of communities, ranked by risk score. Key columns: Rank, Cluster ID, Size, Average Risk, and Core Signals. Clicking a row loads that community's detail.

3. **Interactive Graph Explorer (Cytoscape.js)**:
   - Renders the selected cluster's network graph. 
   - **Visual Styling**:
     - *Company nodes*: Blue hexagons with label matching Company Name/CIN.
     - *Director nodes*: Green circles with label matching Director Name.
     - *Address nodes*: Orange rectangles with label matching street names.
     - *Edges*: Dotted grey for registration office links; solid dark-grey for director-of board links.
   - **Interactivity**: Support zoom, pan, node selection, neighbor highlighting, and popups with details (capital, DIN, date).

4. **The Evidence & Explanation Panel**:
   - Lists the direct compliance and graph signals that generated the risk score. Translates mathematical values into human-readable warnings (e.g. *"This cluster shares 1 address and has a registration burst of 10 companies registered within 14 days"*).

---

## 2. Phase 11 Self-Assessment Quiz

### Question 1:
Why is Cytoscape.js selected for the network visualization layer instead of standard SVG/CSS charts?
<details>
<summary><b>Show Answer</b></summary>
Cytoscape.js is a high-performance, canvas-based graph visualization library designed specifically for complex network analysis. Standard HTML SVGs suffer from major performance degradation when drawing hundreds of nodes and edges, causing lag and UI freezes. Cytoscape.js supports custom layouts (like force-directed CoSE or circle layouts), efficient viewport caching, and built-in zoom/pan controls, delivering a premium interactive user experience.
</details>

### Question 2:
How do color-coding and distinct node shapes in Cytoscape.js improve an investigator's cognitive speed?
<details>
<summary><b>Show Answer</b></summary>
By visual categorisation. An investigator looking at a dense network can immediately identify "hubs" (a single orange rectangle connected to 10 blue hexagons represents a shared address hub, and a single green circle connected to 6 blue hexagons represents a shared director hub). This allows them to read and interpret the network structure in split-seconds without having to inspect text tags manually.
</details>

### Question 3:
How does the frontend implement real-time interactive node inspection?
<details>
<summary><b>Show Answer</b></summary>
By binding click events in Cytoscape.js. Clicking a node triggers a callback that updates the React component state with that node's data (e.g. CIN, authorized capital, status, or DIN). This state update triggers a re-render of the sidebar detail panel, pulling additional info from the cached database models.
</details>
