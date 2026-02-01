import streamlit as st
import streamlit.components.v1 as components
import copy

from ai_services import generate_flowchart_with_ai


# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="Joe's Prompt2Flow",
    layout="wide"
)

st.markdown(
    """
    <style>
        body {
            background-color: #0e1117;
            color: white;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Joe's Prompt2Flow")
st.caption("From problem to process in minutes")


import streamlit as st
import streamlit.components.v1 as components
import copy
import textwrap

from ai_services import generate_flowchart_with_ai

# -----------------------------
# Layout & Rendering Engine
# -----------------------------

def wrap_text(text, width=20):
    return textwrap.wrap(text, width=width)

def calculate_node_height(text, width=20, line_height=18, min_height=40):
    lines = wrap_text(text, width)
    return min_height + (len(lines) * line_height)

def calculate_layout(nodes, edges):
    """
    Tree-like layout with dynamic vertical spacing to prevent overlaps.
    """
    positions = {}
    
    # helper to fast-lookup node props
    node_map = {n["id"]: n for n in nodes}
    
    # Initialize all to center spine
    for node in nodes:
        positions[node["id"]] = {"x": 500, "y": 0}

    # Build adjacency list
    adj = {n["id"]: [] for n in nodes}
    for edge in edges:
        if edge["from"] in adj:
            adj[edge["from"]].append(edge)

    # 1. Identify "levels" or just traverse and push down? 
    # To handle overlaps properly in a flexible graph is hard.
    # But since AI usually gives a "spine" with branches, we can traverse DFS/BFS.
    
    start_node = next((n for n in nodes if n["type"] == "start"), nodes[0])
    
    # Queue: (node_id, x, y_top) 
    # y_top is where the node STARTS. center_y will be y_top + height/2
    queue = [(start_node["id"], 500, 50)] 
    visited = set()
    
    min_gap_y = 60 # Minimum gap between nodes
    
    while queue:
        curr_id, cx, cy_start = queue.pop(0)
        
        if curr_id in visited:
            continue
        visited.add(curr_id)
        
        # Calculate height of current node
        curr_node = node_map[curr_id]
        h = calculate_node_height(curr_node["text"])
        
        # Center Y for SVG positioning (since rects are drawn centered or top-left? 
        # My renderer draws rects centered: y - box_height/2)
        # So "y" in positions should be the CENTER.
        
        center_y = cy_start + h/2
        positions[curr_id] = {"x": cx, "y": center_y, "height": h}
        
        children_edges = adj.get(curr_id, [])
        if not children_edges:
            continue
            
        # Calculate where the NEXT layer should start
        next_y_start = cy_start + h + min_gap_y
        
        if len(children_edges) == 1:
            next_id = children_edges[0]["to"]
            queue.append((next_id, cx, next_y_start))
        
        else:
            # Branching
            count = len(children_edges)
            span = 300 
            
            for i, edge in enumerate(children_edges):
                child_id = edge["to"]
                lbl = (edge.get("label") or "").lower()
                
                if "yes" in lbl: nx = cx - 180
                elif "no" in lbl: nx = cx + 180
                else:
                    # Distribute
                    # If 2 nodes: -150, +150
                    offset = -180 if i == 0 else 180
                    nx = cx + offset
                
                queue.append((child_id, nx, next_y_start))

    # Fallback for disconnected
    max_y = max((p["y"] + p["height"]/2 for p in positions.values() if "height" in p), default=0)
    for node in nodes:
         if node["id"] not in visited:
             h = calculate_node_height(node["text"])
             positions[node["id"]] = {"x": 500, "y": max_y + 100, "height": h}
             max_y += h + 100
             
    return positions

def render_flowchart(flowchart):
    fc = copy.deepcopy(flowchart)
    nodes = fc["nodes"]
    edges = fc["edges"]
    
    positions = calculate_layout(nodes, edges)
    
    # Calculate SVG dimensions dynamically
    max_y = max((p["y"] for p in positions.values()), default=800) + 150
    min_x = min((p["x"] for p in positions.values()), default=0) - 100
    max_x = max((p["x"] for p in positions.values()), default=1000) + 100
    svg_width = max(1000, max_x - min_x)
    
    # Offset everything if min_x is negative
    x_offset = abs(min(0, min_x)) 
    svg_width += x_offset

    svg = f"""
    <div style="width: 100%; overflow-x: auto; overflow-y: hidden; text-align: center; background: #0e1117; border-radius: 10px; padding: 20px;">
    <svg width="{svg_width}" height="{max_y}" style="font-family: 'Segoe UI', sans-serif;">
      <defs>
        <marker id="arrow" markerWidth="12" markerHeight="12"
          refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" fill="#a0a0a0"/>
        </marker>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2" result="blur"/>
          <feComposite in="SourceGraphic" in2="blur" operator="over"/>
        </filter>
        <linearGradient id="nodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#2b313e;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#1e2330;stop-opacity:1" />
        </linearGradient>
      </defs>
    """

    # Edges first (so they are behind nodes)
    for edge in edges:
        if edge["from"] not in positions or edge["to"] not in positions:
            continue

        p1 = positions[edge["from"]]
        p2 = positions[edge["to"]]
        
        x1, y1 = p1["x"] + x_offset, p1["y"]
        x2, y2 = p2["x"] + x_offset, p2["y"]

        # Orthogonal routing for cleaner look? Or straight?
        # Straight is safer for now.
        
        color = "#a0a0a0"
        if "Yes" in str(edge.get("label")): color = "#4caf50" # Green
        if "No" in str(edge.get("label")): color = "#ff5252" # Red

        svg += f"""
        <line x1="{x1}" y1="{y1+35}"
              x2="{x2}" y2="{y2-35}"
              stroke="{color}" stroke-width="2" marker-end="url(#arrow)"/>
        """
        
        # Edge Label
        if edge.get("label"):
            mx, my = (x1+x2)/2, (y1+y2)/2
            svg += f"""
            <rect x="{mx-15}" y="{my-10}" width="30" height="20" fill="#0e1117" rx="4"/>
            <text x="{mx}" y="{my+4}" fill="{color}" text-anchor="middle" font-size="11" font-weight="bold">
                {edge["label"]}
            </text>
            """

    # Draw nodes
    for node in nodes:
        pid = node["id"]
        pos = positions[pid]
        x, y = pos["x"] + x_offset, pos["y"]
        text_lines = wrap_text(node["text"], width=20)
        node_type = node["type"]
        
        # Dynamic height based on lines
        line_height = 18
        box_height = 40 + (len(text_lines) * line_height)
        box_width = 180
        
        # Color coding
        stroke_color = "#4fd1c5" # Default Teal
        if node_type == "start": stroke_color = "#f6e05e"
        if node_type == "end": stroke_color = "#f6e05e"
        if node_type == "decision": stroke_color = "#ff79c6" # Pink

        # Shape rendering
        if node_type in ("start", "end"):
            svg += f"""
            <rect x="{x-80}" y="{y-box_height/2}" rx="25" ry="25"
              width="160" height="{box_height}"
              stroke="{stroke_color}" stroke-width="2" fill="url(#nodeGrad)" filter="url(#glow)"/>
            """
        elif node_type == "decision":
             svg += f"""
            <path d="M{x},{y-box_height/2 - 10} L{x+100},{y} L{x},{y+box_height/2 + 10} L{x-100},{y} Z"
              stroke="{stroke_color}" stroke-width="2" fill="url(#nodeGrad)" />
            """
        else:
            svg += f"""
            <rect x="{x-box_width/2}" y="{y-box_height/2}" rx="6"
              width="{box_width}" height="{box_height}"
              stroke="{stroke_color}" stroke-width="2" fill="url(#nodeGrad)"/>
            """

        # Text rendering
        start_text_y = y - ((len(text_lines)-1) * line_height) / 2 + 5
        for i, line in enumerate(text_lines):
            svg += f"""
            <text x="{x}" y="{start_text_y + (i*line_height)}"
              fill="white" text-anchor="middle" font-size="14" font-weight="500">{line}</text>
            """

    svg += "</svg></div>"

    # Toolbar and Container
    unique_id = f"flowchart_{id(flowchart)}"
    
    html_content = f"""
    <div id="container_{unique_id}" style="
        position: relative; 
        width: 100%; 
        border-radius: 10px; 
        overflow: hidden; 
        background: #0e1117; 
        border: 1px solid #2b313e;">
        
        <!-- Toolbar -->
        <div style="
            position: absolute; 
            top: 10px; 
            right: 10px; 
            display: flex; 
            gap: 10px; 
            z-index: 100;">
            
            <button onclick="downloadSVG_{unique_id}()" title="Download SVG" style="
                background: #1f2937; color: white; border: 1px solid #374151; 
                padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 12px;">
                SVG ⬇️
            </button>
            <button onclick="downloadPNG_{unique_id}()" title="Download PNG" style="
                background: #1f2937; color: white; border: 1px solid #374151; 
                padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 12px;">
                PNG ⬇️
            </button>
            <button onclick="openNewTab_{unique_id}()" title="Open in New Tab (Fullscreen)" style="
                background: #1f2937; color: white; border: 1px solid #374151; 
                padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 12px;">
                Open ↗️
            </button>
        </div>

        <!-- Scrollable SVG Content -->
        <div id="scroll_area_{unique_id}" style="
            overflow: auto; 
            max-height: 500px; 
            padding: 20px; 
            text-align: center;
            border-top: 1px solid #2b313e;"> 
            {svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ')}
        </div>
        
    </div>

    <!-- Hidden Canvas for PNG conversion -->
    <canvas id="canvas_{unique_id}" style="display:none;"></canvas>

    <script>
        function downloadSVG_{unique_id}() {{
            try {{
                const svgElement = document.querySelector("#container_{unique_id} svg");
                if (!svgElement) {{ alert("SVG not found"); return; }}
                
                const svgData = svgElement.outerHTML;
                const blob = new Blob([svgData], {{type: "image/svg+xml;charset=utf-8"}});
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "flowchart.svg";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }} catch (e) {{
                alert("Error downloading SVG: " + e.message);
            }}
        }}

        function downloadPNG_{unique_id}() {{
            try {{
                const svgElement = document.querySelector("#container_{unique_id} svg");
                if (!svgElement) {{ alert("SVG not found"); return; }}

                const canvas = document.getElementById("canvas_{unique_id}");
                const ctx = canvas.getContext("2d");
                
                // Get data
                const svgData = new XMLSerializer().serializeToString(svgElement);
                const img = new Image();
                
                // Add explicit size to ensure high res
                const width = parseInt(svgElement.getAttribute("width")) || 1000;
                const height = parseInt(svgElement.getAttribute("height")) || 800;
                canvas.width = width;
                canvas.height = height;

                img.onload = function() {{
                    ctx.fillStyle = "#0e1117"; // Dark background
                    ctx.fillRect(0, 0, width, height);
                    ctx.drawImage(img, 0, 0);
                    const pngFile = canvas.toDataURL("image/png");
                    
                    const link = document.createElement("a");
                    link.download = "flowchart.png";
                    link.href = pngFile;
                    link.click();
                }};
                
                img.onerror = function() {{
                   alert("Error converting SVG to Image.");
                }};
                
                img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
            }} catch (e) {{
                alert("Error downloading PNG: " + e.message);
            }}
        }}

        function openNewTab_{unique_id}() {{
            try {{
                const svgElement = document.querySelector("#container_{unique_id} svg");
                if (!svgElement) {{ alert("SVG not found"); return; }}
                
                const svgData = new XMLSerializer().serializeToString(svgElement);
                const blob = new Blob([svgData], {{type: "image/svg+xml;charset=utf-8"}});
                const url = URL.createObjectURL(blob);
                window.open(url, '_blank');
            }} catch (e) {{
                alert("Error opening new tab: " + e.message);
            }}
        }}
    </script>
    """
    
    return html_content


# -----------------------------
# UI
# -----------------------------
prompt = st.text_area(
    "Enter your problem statement",
    placeholder="Example: Check whether a number is even or odd"
)

if st.button("Generate Flowchart"):
    if not prompt.strip():
        st.warning("Please enter a problem statement")
    else:
        try:
            with st.spinner("Generating flowchart..."):
                flowchart = generate_flowchart_with_ai(prompt)

            components.html(render_flowchart(flowchart), height=750)

        except Exception as e:
            st.error("Error generating flowchart")
            st.code(str(e))

# -----------------------------
# Footer
# -----------------------------
st.markdown(
    """
    <div style="
        position: fixed; 
        bottom: 0; 
        left: 0; 
        width: 100%; 
        background-color: #0e1117; 
        padding: 15px; 
        text-align: center; 
        border-top: 1px solid #2b313e;
        z-index: 9999;
        font-family: 'Segoe UI', sans-serif;
    ">
        <p style="margin: 0; color: #8b949e; font-size: 14px;">
            Created by <b style="color: #cbd5e1;">Joshu Joseph</b> 
            &nbsp; | &nbsp; 
            <a href="https://www.linkedin.com/in/joshu-joseph-374a101bb" target="_blank" style="text-decoration: none; color: #58a6ff; font-weight: 500;">
                <img src="https://cdn-icons-png.flaticon.com/512/174/174857.png" width="16" height="16" style="vertical-align: middle; margin-right: 5px; filter: invert(1);">
                Connect on LinkedIn
            </a>
        </p>
    </div>
    <div style="height: 60px;"></div> <!-- Spacer -->
    """,
    unsafe_allow_html=True
)
