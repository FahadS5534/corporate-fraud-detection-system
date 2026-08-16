import os
import sys
import json
import networkx as nx

# Add root folder to sys.path
sys.path.append(r"f:\SIH")

from backend.app.services.graph_service import GraphService

def build_interactive_html():
    print("Building interactive network graph data...")
    service = GraphService()
    graph = service.build_graph()
    
    # Identify high-risk companies (and edge cases) and their connected neighbors to declutter graph
    high_risk_companies = set()
    for node_id, data in graph.nodes(data=True):
        if data.get("type") == "company":
            label = data.get("ground_truth_label", "normal")
            is_defaulter = data.get("wilful_defaulter_flag", False)
            if "fraud_ring" in label or is_defaulter or label == "legit_edge_case":
                high_risk_companies.add(node_id)
                
    nodes_to_keep = set(high_risk_companies)
    for u, v in graph.edges():
        if u in high_risk_companies:
            nodes_to_keep.add(v)
        if v in high_risk_companies:
            nodes_to_keep.add(u)

    nodes = []
    edges = []
    
    # Node formatting
    for node_id, data in graph.nodes(data=True):
        if node_id not in nodes_to_keep:
            continue
        ntype = data.get("type", "unknown")
        name = data.get("name", node_id)
        
        # Determine color and size
        if ntype == "company":
            label = data.get("ground_truth_label", "normal")
            is_defaulter = data.get("wilful_defaulter_flag", False)
            
            if "fraud_ring" in label or is_defaulter:
                color = "#EF4444"  # Red for high risk / defaulters
                size = 30
                title = f"<b>Company: {name}</b><br/>CIN: {node_id}<br/>Status: {data.get('status')}<br/><b>ALERT: High Risk/Defaulter</b>"
            elif label == "legit_edge_case":
                color = "#EC4899"  # Pink for legit office hubs
                size = 25
                title = f"<b>Company: {name}</b><br/>CIN: {node_id}<br/>Status: {data.get('status')}<br/>Shared Registered Agent Hub"
            else:
                color = "#3B82F6"  # Blue for normal company (connected to high risk)
                size = 20
                title = f"<b>Company: {name}</b><br/>CIN: {node_id}<br/>Status: {data.get('status')}"
        elif ntype == "director":
            color = "#10B981"  # Green for Director
            size = 15
            title = f"<b>Director: {name}</b><br/>DIN: {node_id}"
        elif ntype == "address":
            color = "#F59E0B"  # Amber for Address
            size = 18
            title = f"<b>Address:</b> {data.get('raw_address', node_id)}"
        elif ntype == "lender":
            color = "#8B5CF6"  # Purple for Lender
            size = 22
            title = f"<b>Lender:</b> {name}"
        else:
            color = "#9CA3AF"  # Gray fallback
            size = 12
            title = name
            
        nodes.append({
            "id": node_id,
            "label": name if ntype != "address" else (node_id[:25] + "..."),
            "color": color,
            "size": size,
            "title": title,
            "group": ntype,
            "properties": {k: str(v) for k, v in data.items()}
        })
        
    for u, v, data in graph.edges(data=True):
        if u not in nodes_to_keep or v not in nodes_to_keep:
            continue
        relation = data.get("relation", "LINKED")
        edges.append({
            "from": u,
            "to": v,
            "label": relation,
            "title": relation,
            "color": "#4B5563"
        })
        
    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Proactive Fraud Intelligence Network Workspace</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #0B0F19;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #E2E8F0;
        }}
        #network {{
            width: 100%;
            height: 100%;
            position: absolute;
            top: 0;
            left: 0;
        }}
        .overlay {{
            position: absolute;
            z-index: 10;
            pointer-events: auto;
        }}
        .header {{
            top: 20px;
            left: 20px;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 15px 25px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
        }}
        .header h1 {{
            margin: 0;
            font-size: 1.25rem;
            font-weight: 700;
            color: #F8FAFC;
            letter-spacing: 0.5px;
        }}
        .header p {{
            margin: 4px 0 0 0;
            font-size: 0.85rem;
            color: #94A3B8;
        }}
        .control-panel {{
            bottom: 20px;
            left: 20px;
            width: 320px;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
        }}
        .control-panel input {{
            width: 100%;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            background: rgba(30, 41, 59, 0.5);
            color: #F8FAFC;
            font-size: 0.85rem;
            box-sizing: border-box;
        }}
        .control-panel input:focus {{
            outline: none;
            border-color: #3B82F6;
        }}
        .legend {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 0.85rem;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .detail-panel {{
            top: 20px;
            right: 20px;
            width: 340px;
            max-height: calc(100% - 80px);
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
            overflow-y: auto;
            display: none;
        }}
        .detail-panel h2 {{
            margin-top: 0;
            font-size: 1.1rem;
            color: #F8FAFC;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 10px;
        }}
        .prop-row {{
            display: flex;
            flex-direction: column;
            gap: 3px;
            margin-bottom: 12px;
            font-size: 0.85rem;
        }}
        .prop-label {{
            color: #94A3B8;
            font-weight: 500;
        }}
        .prop-value {{
            color: #E2E8F0;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <div id="network"></div>
    
    <div class="overlay header">
        <h1>Multi-Source Corporate Relationship Graph</h1>
        <p>Ingesting MCA21, CERSAI Security Interests & RBI Wilful Defaulters</p>
    </div>
    
    <div class="overlay control-panel">
        <div style="display: flex; gap: 6px; margin-bottom: 12px;">
            <input list="node-options" id="search" placeholder="Search Company or Director..." onchange="searchNode()" style="flex: 1; min-width: 0;">
            <datalist id="node-options"></datalist>
            <button onclick="toggleFullscreen()" style="background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 6px; color: white; padding: 0 10px; cursor: pointer; font-size: 0.95rem; font-weight: bold;" title="Toggle Fullscreen">⛶</button>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; background: rgba(0, 0, 0, 0.2); padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.05);">
            <span style="font-size: 0.75rem; color: #94A3B8; font-weight: 600;">Physics Layout</span>
            <button id="physicsToggle" onclick="togglePhysics()" style="background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; color: #F8FAFC; padding: 3px 8px; cursor: pointer; font-size: 0.7rem; font-weight: 700; transition: all 0.2s;">Disabled (Static)</button>
        </div>
        <div class="legend">
            <div class="legend-item">
                <div class="legend-dot" style="background-color: #EF4444;"></div>
                <span>High Risk Company / Defaulter</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background-color: #EC4899;"></div>
                <span>Shared Registered Office Case</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background-color: #3B82F6;"></div>
                <span>Legitimate Company</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background-color: #10B981;"></div>
                <span>Director Node</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background-color: #F59E0B;"></div>
                <span>Address Office Node</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background-color: #8B5CF6;"></div>
                <span>Lender Bank Node</span>
            </div>
        </div>
    </div>
    
    <div class="overlay detail-panel" id="detailPanel">
        <h2 id="nodeName">Selected Entity</h2>
        <div id="propertiesList"></div>
    </div>

    <script type="text/javascript">
        var rawNodes = {nodes_json};
        var rawEdges = {edges_json};
        
        // Convert string titles to rich HTML tooltips
        rawNodes.forEach(function(n) {{
            if (n.title && typeof n.title === 'string') {{
                var el = document.createElement('div');
                el.style.fontFamily = 'Inter, sans-serif';
                el.style.fontSize = '11px';
                el.style.color = '#F8FAFC';
                el.style.lineHeight = '1.4';
                el.style.padding = '4px 8px';
                el.innerHTML = n.title;
                n.title = el;
            }}
        }});
        
        var container = document.getElementById('network');
        var data = {{
            nodes: new vis.DataSet(rawNodes),
            edges: new vis.DataSet(rawEdges)
        }};
        
        var options = {{
            nodes: {{
                shape: 'dot',
                font: {{
                    color: '#F8FAFC',
                    size: 11
                }},
                borderWidth: 2,
                borderColor: '#1E293B'
            }},
            edges: {{
                width: 1.5,
                arrows: {{
                    to: {{ enabled: false }}
                }},
                font: {{
                    size: 9,
                    color: '#94A3B8',
                    align: 'middle'
                }},
                smooth: {{
                    type: 'continuous'
                }}
            }},
            physics: {{
                solver: 'barnesHut',
                barnesHut: {{
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04,
                    damping: 0.09,
                    avoidOverlap: 0.5
                }},
                stabilization: {{
                    enabled: true,
                    iterations: 50,
                    updateInterval: 10
                }}
            }},
            groups: {{
                company: {{ shape: 'dot' }},
                director: {{ shape: 'dot' }},
                address: {{ shape: 'square' }},
                lender: {{ shape: 'triangle' }}
            }}
        }};
        
        var network = new vis.Network(container, data, options);
        var detailPanel = document.getElementById('detailPanel');
        var nodeName = document.getElementById('nodeName');
        var propertiesList = document.getElementById('propertiesList');
        
        network.on("selectNode", function (params) {{
            var nodeId = params.nodes[0];
            var nodeData = data.nodes.get(nodeId);
            
            nodeName.innerText = nodeData.label;
            propertiesList.innerHTML = '';
            
            // Add ID prop
            addProperty("ID / Registration", nodeId);
            addProperty("Entity Type", nodeData.group.toUpperCase());
            
            // Add custom attributes
            if (nodeData.properties) {{
                for (var key in nodeData.properties) {{
                    if (key !== 'type' && key !== 'name' && key !== 'id') {{
                        addProperty(key.replace(/_/g, ' '), nodeData.properties[key]);
                    }}
                }}
            }}
            
            detailPanel.style.display = 'block';
        }});
        
        network.on("deselectNode", function (params) {{
            detailPanel.style.display = 'none';
        }});
        
        function addProperty(label, val) {{
            var row = document.createElement('div');
            row.className = 'prop-row';
            
            var lbl = document.createElement('span');
            lbl.className = 'prop-label';
            lbl.innerText = label;
            
            var valSpan = document.createElement('span');
            valSpan.className = 'prop-value';
            valSpan.innerText = val;
            
            row.appendChild(lbl);
            row.appendChild(valSpan);
            propertiesList.appendChild(row);
        }}
        
        var physicsEnabled = false;

        network.once("stabilizationIterationsDone", function () {{
            network.setOptions({{ physics: false }});
            physicsEnabled = false;
            document.getElementById("physicsToggle").innerText = "Disabled (Static)";
            document.getElementById("physicsToggle").style.background = "rgba(255, 255, 255, 0.1)";
        }});

        function togglePhysics() {{
            physicsEnabled = !physicsEnabled;
            network.setOptions({{ physics: physicsEnabled }});
            var btn = document.getElementById("physicsToggle");
            if (physicsEnabled) {{
                btn.innerText = "Enabled (Active)";
                btn.style.background = "#10B981";
                btn.style.borderColor = "#10B981";
            }} else {{
                btn.innerText = "Disabled (Static)";
                btn.style.background = "rgba(255, 255, 255, 0.1)";
                btn.style.borderColor = "rgba(255, 255, 255, 0.2)";
            }}
        }}

        function toggleFullscreen() {{
            if (!document.fullscreenElement) {{
                document.documentElement.requestFullscreen().catch(function(err) {{
                    console.error("Error attempting to enable fullscreen:", err);
                }});
            }} else {{
                document.exitFullscreen();
            }}
        }}

        // Populate search Suggestions Dropdown (Datalist)
        var datalist = document.getElementById('node-options');
        rawNodes.forEach(function(n) {{
            if (n.group === 'company' || n.group === 'director') {{
                var option = document.createElement('option');
                option.value = n.label;
                datalist.appendChild(option);
            }}
        }});

        function searchNode() {{
            var val = document.getElementById('search').value;
            if (!val) return;
            
            var matched = rawNodes.find(function(n) {{
                return n.label.toLowerCase() === val.toLowerCase() || n.id.toLowerCase() === val.toLowerCase();
            }});
            
            // Fallback to partial match if exact match not found
            if (!matched) {{
                matched = rawNodes.find(function(n) {{
                    return n.label.toLowerCase().includes(val.toLowerCase()) || n.id.toLowerCase().includes(val.toLowerCase());
                }});
            }}
            
            if (matched) {{
                network.focus(matched.id, {{
                    scale: 1.2,
                    animation: {{
                        duration: 1000,
                        easingFunction: 'easeInOutQuad'
                    }}
                }});
                network.selectNodes([matched.id]);
                nodeName.innerText = matched.label;
                propertiesList.innerHTML = '';
                addProperty("ID / Registration", matched.id);
                addProperty("Entity Type", matched.group.toUpperCase());
                if (matched.properties) {{
                    for (var key in matched.properties) {{
                        if (key !== 'type' && key !== 'name' && key !== 'id') {{
                            addProperty(key.replace(/_/g, ' '), matched.properties[key]);
                        }}
                    }}
                }}
                detailPanel.style.display = 'block';
            }}
        }}
    </script>
</body>
</html>
"""
    
    output_path = r"f:\SIH\backend\static\pyvis_graph.html"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Pre-rendered interactive network graph saved to {output_path}")

if __name__ == "__main__":
    build_interactive_html()
