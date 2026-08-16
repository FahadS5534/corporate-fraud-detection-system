import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_cell_background(cell, fill_hex):
    """Sets background color of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets cell margins in dxas (1/20th of a point)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_report():
    doc = docx.Document()
    
    # Page setup
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Styling helper
    def add_custom_heading(text, level, space_before=12, space_after=6):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(space_before)
        h.paragraph_format.space_after = Pt(space_after)
        h.paragraph_format.keep_with_next = True
        
        run = h.add_run(text)
        run.font.name = 'Arial'
        run.font.bold = True
        
        if level == 1:
            run.font.size = Pt(18)
            run.font.color.rgb = RGBColor(15, 23, 42) # Slate 900
            # Add a bottom border or divider line by paragraph format in Word if possible, otherwise we use space
        elif level == 2:
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(30, 41, 59) # Slate 800
        else:
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(71, 85, 105) # Slate 600
        return h

    def add_body_paragraph(text, bold_prefix="", space_after=6):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        
        if bold_prefix:
            run_p = p.add_run(bold_prefix)
            run_p.font.name = 'Arial'
            run_p.font.size = Pt(10.5)
            run_p.font.bold = True
            run_p.font.color.rgb = RGBColor(15, 23, 42)
            
        run = p.add_run(text)
        run.font.name = 'Arial'
        run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(51, 65, 85) # Slate 700
        return p

    def add_bullet_point(text, bold_prefix=""):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        
        if bold_prefix:
            run_p = p.add_run(bold_prefix)
            run_p.font.name = 'Arial'
            run_p.font.size = Pt(10.5)
            run_p.font.bold = True
            run_p.font.color.rgb = RGBColor(15, 23, 42)
            
        run = p.add_run(text)
        run.font.name = 'Arial'
        run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(51, 65, 85)
        return p

    # --- Title Page / Header ---
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(36)
    title_p.paragraph_format.space_after = Pt(6)
    run_title = title_p.add_run("MCA21 RISK INTELLIGENCE PORTAL")
    run_title.font.name = 'Arial'
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(15, 23, 42)

    subtitle_p = doc.add_paragraph()
    subtitle_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_p.paragraph_format.space_after = Pt(36)
    run_sub = subtitle_p.add_run("Technical Documentation: Scoring Engine & Louvain Clustering")
    run_sub.font.name = 'Arial'
    run_sub.font.size = Pt(12)
    run_sub.font.color.rgb = RGBColor(100, 116, 139) # Slate 500

    # Horizontal Divider Line
    divider = doc.add_paragraph()
    divider.alignment = WD_ALIGN_PARAGRAPH.CENTER
    divider.paragraph_format.space_after = Pt(24)
    run_div = divider.add_run("__________________________________________________________________")
    run_div.font.color.rgb = RGBColor(226, 232, 240)

    # --- Section 1 ---
    add_custom_heading("1. Executive Summary", level=1)
    add_body_paragraph(
        "The MCA21 Risk Intelligence Portal is an advanced decision-support platform designed to screen, "
        "identify, and visualize corporate shell companies and complex loan-siphoning networks. By integrating "
        "relational data, bank charges (CERSAI), and default records (RBI) into a unified heterogeneous network graph, "
        "the portal provides investigators with automated, mathematical indicators of corporate collusion. The system "
        "leverages two core technologies to achieve high-accuracy screening: the Louvain Community Detection algorithm "
        "for syndicate grouping, and a Z-Score calibrated 5-Factor Risk Engine for entity profiling."
    )

    # --- Section 2 ---
    add_custom_heading("2. Z-Score Calibrated 5-Factor Risk Engine", level=1)
    add_body_paragraph(
        "Standard heuristic screening models often suffer from high false-positive rates when encountering legitimate "
        "business edge cases, such as corporate service providers or Chartered Accountants hosting hundreds of clean businesses. "
        "To mitigate this, the scoring engine runs a two-step normalization and weighting process."
    )
    
    add_custom_heading("2.1 Baseline Calibration (Z-Score Normalization)", level=2)
    add_body_paragraph(
        "First, the scoring engine analyzes the background dataset of normal/legitimate companies to determine typical "
        "statistics (mean and standard deviation) for network connectivity. For any target company, its raw signal values "
        "(e.g., number of co-registered companies, director degrees) are compared using a Z-score calculation. If the Z-score "
        "does not exceed the designated threshold (e.g., Z = 2.0), the company receives a risk score of 0. This ensures "
        "that ordinary shared resources are not flagged as anomalous."
    )

    add_custom_heading("2.2 5-Factor Composite Score Calculation", level=2)
    add_body_paragraph(
        "For companies deviating from the baseline statistics, a composite screening score (0 to 100) is calculated "
        "using a weighted average of five distinct network and registry metrics:"
    )

    # Create Table
    table = doc.add_table(rows=6, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    headers = ["Risk Factor", "Weight", "Detection Objective"]
    col_widths = [Inches(1.8), Inches(0.8), Inches(3.9)]
    
    # Set headers
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "0F172A") # Slate 900
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=180, right=180)
        
        # Style header text
        p = hdr_cells[i].paragraphs[0]
        run = p.runs[0]
        run.font.name = 'Arial'
        run.font.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(255, 255, 255)
        
    # Table data
    data = [
        ("Address Centrality Risk", "25%", "Identifies addresses sharing an anomalous number of registered corporate entities based on background stats."),
        ("Director Boarding Degree", "25%", "Detects nominee directors serving on an excessive number of boards, exceeding statutory or practical limits."),
        ("Incorporation Burst", "15%", "Identifies clusters of entities registered within a tight temporal window (e.g. 30 days) sharing registered addresses."),
        ("Lender Charge Density", "15%", "Flags high-density lending activities (CERSAI) indicating bank-fund routing loops or parallel siphoning."),
        ("Wilful Defaulter Status", "20%", "Direct registry cross-check flagging matches in RBI or credit registry wilful defaulter lists.")
    ]
    
    for row_idx, (factor, weight, obj) in enumerate(data, start=1):
        row_cells = table.rows[row_idx].cells
        row_cells[0].text = factor
        row_cells[1].text = weight
        row_cells[2].text = obj
        
        bg_color = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF" # Alternating row colors
        
        for col_idx in range(3):
            cell = row_cells[col_idx]
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
            p = cell.paragraphs[0]
            run = p.runs[0]
            run.font.name = 'Arial'
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(51, 65, 85)
            if col_idx == 1:
                run.font.bold = True
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
    doc.add_paragraph().paragraph_format.space_before = Pt(12) # Spacer

    # --- Section 3 ---
    add_custom_heading("3. Louvain Community Detection Algorithm", level=1)
    add_body_paragraph(
        "Modern financial fraud rarely involves isolated entities. Rather, siphoning and laundering schemes "
        "utilize multi-layered networks (syndicates) of shell companies to cycle funds. To group these entities "
        "automatically, the portal utilizes the Louvain Community Detection algorithm."
    )
    
    add_custom_heading("3.1 Modularity Optimization", level=2)
    add_body_paragraph(
        "The Louvain algorithm is a heuristic method that partitions a graph into communities by maximizing the "
        "overall Modularity. Modularity measures the strength of the division of a network into clusters. "
        "High modularity indicates that nodes within a community have dense connections among themselves, but sparse "
        "connections with nodes in other communities. The algorithm runs in two repeating phases: (1) local optimization "
        "of modularity where nodes are shifted into neighboring groups, and (2) graph aggregation where identified "
        "communities are condensed into single super-nodes."
    )

    add_custom_heading("3.2 Application in Fraud Intelligence", level=2)
    add_body_paragraph(
        "Within the portal, the Louvain algorithm partitions a heterogeneous network representing 3,789 nodes into "
        "562 distinct communities. The pipeline executes as follows:"
    )
    add_bullet_point("Groups companies that share common physical addresses, directors, and active lenders into separate clusters.", bold_prefix="Community Partitioning: ")
    add_bullet_point("Aggregates the individual 5-factor risk scores of all companies within the community to calculate a collective Cluster Risk Score.", bold_prefix="Cluster Risk Aggregation: ")
    add_bullet_point("Assigns a severity label based on the score: clusters with a score >= 75.0 are flagged as active 'Syndicates', intermediate clusters as 'Risk Networks', and clean clusters as 'Groups'.", bold_prefix="Syndicate Flagging: ")

    # --- Section 4 ---
    add_custom_heading("4. Performance & Accuracy Validation", level=1)
    add_body_paragraph(
        "The calibrated scoring and Louvain detection model was validated against a 1,000-company synthetic "
        "benchmark set containing 115 known shell companies structured into 16 distinct fraud rings, alongside "
        "legitimate edge cases. The results demonstrated high precision and recall:"
    )
    add_bullet_point("All 115 target shell companies were successfully identified by the pipeline.", bold_prefix="Shell Detection Rate: 100.0% ")
    add_bullet_point("No normal background companies were incorrectly classified as high-risk, achieving complete baseline separation.", bold_prefix="False Positive Rate: 0.0% ")
    add_bullet_point("The target rings (Rings A, B, and C) ranked #1, #2, and #3 respectively in the cluster risk registry.", bold_prefix="Fraud Ring Ranks: Top 3 ")
    add_bullet_point("The 7 legitimate companies sharing a common office address were successfully scored as low-risk (ranking #6) and segregated from the active fraud syndicates.", bold_prefix="Legitimate Hub Segregation: ")

    # --- Section 5 ---
    add_custom_heading("5. Frontend-to-Backend Data Integration Map", level=1)
    add_body_paragraph(
        "For the presentation panel, understanding how the user interface maps to the underlying FastAPI "
        "endpoints and database structures is critical. Below is the mapping of all frontend components to their "
        "respective backend services:"
    )
    add_bullet_point("Mapped to '/api/dashboard/summary'. Displays total metrics such as the 1,007 loaded companies, "
                     "2,313 director edges, and active investigations. Under the hood, this performs quick SQL aggregate queries "
                     "(`SELECT count(*) FROM companies`).", bold_prefix="Dashboard Summary Cards: ")
    add_bullet_point("Mapped to '/api/clusters'. It aggregates communities identified by the Louvain clustering and groups "
                     "them into high risk (composite >= 75), medium risk (30-74), and low risk (<30).", bold_prefix="Cluster Risk Modularity Donut Chart: ")
    add_bullet_point("Mapped to the dynamic list of high-risk clusters returned by '/api/clusters' sorted by "
                     "`cluster_risk_score` in descending order. Selecting a row pulls detailed community info via `/api/clusters/{id}`.", bold_prefix="Risk Rankings Table: ")
    add_bullet_point("Mapped to `/api/clusters/{id}/graph` which generates the JSON formatted graph structure (nodes and edges) "
                     "containing companies, directors, and lenders in that specific community. By requesting subgraphs dynamically, "
                     "the frontend stays responsive instead of trying to render all 3,789 nodes.", bold_prefix="Interactive Cytoscape workspace: ")
    add_bullet_point("Mapped to `/backend/static/pyvis_graph.html`, pre-rendered by `scripts/build_pyvis_graph.py` to show "
                     "the global cluster visualization using a physics-driven layout in a static iframe.", bold_prefix="Global Network Visualization (Pyvis): ")

    # --- Section 6 ---
    add_custom_heading("6. Technical Q&A & Defense Sheet (Jury Q&A)", level=1)
    
    add_custom_heading("Q1: How does the model distinguish between a genuine CA firm hosting 100+ clients and an actual shell company address hub?", level=3)
    add_body_paragraph(
        "A: The scoring engine uses a weighted composite average. While both will have a high Address Centrality Risk (S_addr = 100), "
        "a genuine CA firm's hosted companies will have clean profiles: their directors won't board multiple other clients (Director Degree = 0), "
        "incorporations will be staggered over years (Burst Risk = 0), they will have active MCA filings (Filing Risk = 0), and they won't share "
        "loan charge patterns or defaults (Lender/Defaulter Risk = 0). As a result, the CA firm's clients will score only "
        "around 25/100, while the shell ring companies will score >= 75/100."
    )
    
    add_custom_heading("Q2: How does the system scale to handle millions of companies registered under the MCA registry?", level=3)
    add_body_paragraph(
        "A: The system uses a frozen-baseline architecture. Z-score parameters are computed once on normal background "
        "data. When new companies are added, their risk scores are calculated in O(1) time by comparing their raw metrics directly against "
        "these frozen parameters, rather than recalculating the entire graph statistics. Community detection (Louvain) is run "
        "as an asynchronous batch job (e.g. nightly) to update cluster divisions, ensuring no real-time performance bottleneck on the API server."
    )

    add_custom_heading("Q3: What database schema supports these network connections?", level=3)
    add_body_paragraph(
        "A: The backend uses a relational SQLite database (SQLAlchemy ORM) containing six key tables: "
        "(1) 'companies' storing CIN, paid-up capital, and MCA status; (2) 'directors' storing DIN and name; "
        "(3) 'company_directors' linking directors to companies; (4) 'addresses' mapping registration coordinates; "
        "(5) 'loans' tracking active CERSAI borrowing registrations; and (6) 'defaulters' tracking RBI wilful default records."
    )

    add_custom_heading("Q4: Why was the Louvain algorithm chosen over other community algorithms like K-Means or Infomap?", level=3)
    add_body_paragraph(
        "A: K-Means is a distance-based clustering algorithm requiring a vector space, which is not suitable for complex graph topologies "
        "with multiple relationship types (directors, addresses, lenders). Louvain is specifically designed for complex network graphs. "
        "It optimizes Modularity directly, which is ideal for finding cohesive communities where the number of clusters is unknown beforehand. "
        "Infomap relies on flow dynamics (random walks), which is less effective than Modularity when identifying resource-sharing groups like shell rings."
    )

    # Save document
    output_path = r"f:\SIH\document\Scoring_and_Louvain_Explainer.docx"
    doc.save(output_path)
    print(f"Report successfully saved to {output_path}")

if __name__ == "__main__":
    create_report()
