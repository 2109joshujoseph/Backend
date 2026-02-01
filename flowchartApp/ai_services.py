import requests
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi3"


import json

def _ollama_call(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        
        # Try standard JSON first
        try:
            return response.json().get("response", "")
        except json.JSONDecodeError:
            # Fallback: Handle potential NDJSON (newline delimited JSON) if stream=False was ignored
            # or if the response is multiple JSON objects for some reason.
            full_response = []
            for line in response.text.strip().split('\n'):
                if line.strip():
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            full_response.append(obj["response"])
                    except json.JSONDecodeError:
                        continue # Skip invalid lines
            
            if full_response:
                return "".join(full_response)
            
            # If we're here, we couldn't parse it at all.
            # Raise an error with a snippet of the response for debugging.
            raise ValueError(f"Failed to parse Ollama response. Raw text snippet: {response.text[:200]}")
            
    except Exception as e:
        raise Exception(f"Ollama API Error: {str(e)}")


def generate_flowchart_with_ai(user_prompt: str):
    """
    BULLETPROOF STRATEGY:
    - LLM gives ONLY a numbered list
    - Python extracts ONLY valid numbered steps
    - Python builds nodes + edges
    - NO JSON parsing from AI
    """

    prompt = f"""
Return ONLY a numbered list of flowchart steps.
Do NOT explain.
Do NOT output JSON.
Do NOT use markdown.

Rules:
1. Each line MUST start with a number and a dot.
2. For DECISIONS, use the format: "StepNumber. Decision: Question?"
3. For BRANCHES, use the format: "StepNumber. (Yes) Action" or "StepNumber. (No) Action" or "StepNumber. (Else) Action"
4. For normal steps, just "StepNumber. Action"
5. End the process with "End"

Problem:
{user_prompt}

Example:
1. Start
2. Input number
3. Decision: Is number even?
4. (Yes) Print "Even"
5. (No) Print "Odd"
6. End
"""

    try:
        raw_text = _ollama_call(prompt)
    except Exception as e:
        # Fallback for simple errors
        raise e

    # STRICT extraction
    steps = []
    for line in raw_text.splitlines():
        # Match "1. Text", "1. (Yes) Text", etc.
        # Group 1: Number
        # Group 2: (Yes)/(No) (optional)
        # Group 3: Text
        match = re.match(r"^\s*(\d+)\.\s*(?:\((Yes|No|Else)\))?\s*(.*)", line, re.IGNORECASE)
        if match:
            step_num = match.group(1)
            branch_type = match.group(2) # Yes, No, or None
            text = match.group(3).strip()
            
            steps.append({
                "id": step_num,
                "branch": branch_type.lower() if branch_type else None,
                "text": text,
                "raw": line
            })

    if len(steps) < 2:
        raise ValueError("AI did not return a valid step list")

    nodes = []
    edges = []

    # Map step IDs to index in our list for easier processing
    # But wait, step IDs from AI might be 1, 2, 3...
    
    # We need to build the graph.
    # Linear flow is default.
    # If a step has (Yes)/(No), it connects to the NEAREST PREVIOUS DECISION? 
    # OR, it just connects to the previous step logically?
    
    # Actually, the AI usually outputs:
    # 3. Decision
    # 4. (Yes) Do X
    # 5. (No) Do Y
    
    # In this list, 4 comes after 3. 5 comes after 4 (linearly in text).
    # But logically, 4 and 5 both branch FROM 3.
    
    # Heuristic:
    # Track the `last_decision_id`.
    # If we see (Yes) or (No), we attach to `last_decision_id`.
    # If we see a normal step, we attach to `last_node_id`.
    
    # BUT, if 4 is (Yes), and 5 is (No), 5 shouldn't attach to 4.
    
    last_node_id = None
    last_decision_id = None
    
    # For keeping track of where "normal" nodes should attach if we just finished a branch
    # This is complex for a simple script. Let's try a simplified approach:
    # If current is (Yes)/(No), attach to last_decision_id.
    # If current is Normal, attach to last_node_id (unless last_node_id was a branch end? No, just linear).
    
    # Better Heuristic for "Numbered List" to "Graph":
    # 1. Start -> 2
    # 2. Input -> 3
    # 3. Decision -> 4 (Yes), 5 (No)
    # 4. Print Even -> ?
    # 5. Print Odd -> ?
    # 6. End -> (Both 4 and 5 should ideally point here if implied, but AI text is linear)
    
    # Let's just link strictly based on the list, but redirect the source for branches.
    
    # Pass 1: Create Nodes
    for step in steps:
        node_id = step["id"]
        text = step["text"]
        branch = step["branch"]
        
        node_type = "process"
        if "start" in text.lower():
            node_type = "start"
            text = "Start"
        elif "end" in text.lower():
            node_type = "end"
            text = "End"
        elif text.lower().startswith("decision") or "?" in text:
            node_type = "decision"
            text = text.replace("Decision:", "").strip()
            
        nodes.append({
            "id": node_id,
            "type": node_type,
            "text": text,
            "branch": branch # logic helper
        })

    # Pass 2: Create Edges
    # We iterate and link i to i+1, UNLESS logic dictates otherwise.
    
    # Actually, let's use the Heuristic:
    # If Step is (Yes/No), Parent is the most recent Decision.
    # If Step is Normal, Parent is the immediately preceding step.
    
    # We need to handle the case where "Yes" branch ends and "No" branch starts.
    # "No" branch shouldn't attach to "Yes" branch's end.
    
    decision_stack = [] # Stack of decision IDs
    
    previous_step = None
    
    for i, node in enumerate(nodes):
        if i == 0:
            previous_step = node
            continue
            
        current_node = node
        branch_type = current_node["branch"]
        
        source_id = None
        label = None
        
        if branch_type:
             # It's a branch! Find the parent decision.
             # In a simple list from AI, the decision is usually immediately before the first branch,
             # or a few steps back for the second branch.
             
             # Search backwards for the nearest decision
             # This is a bit weak but often works for GPT-3.5/Phi3 linear output
             found_decision = None
             for j in range(i-1, -1, -1):
                 if nodes[j]["type"] == "decision":
                     found_decision = nodes[j]
                     break
             
             if found_decision:
                 source_id = found_decision["id"]
                 label = branch_type.capitalize()
                 
                 # If this is a "No" branch, we don't want to link from the previous "Yes" block.
                 # So we rely ONLY on the source_id being the decision.
        else:
            # Normal step. Link from previous step.
            # CAUTION: If previous step was a "branch end" (like step 4 print even), 
            # and now we have step 5 (No branch - print odd), we assume 5 links from decision? 
            # NO, if 5 has "branch=no", it's covered above.
            
            # What if we have:
            # 3. Decision
            # 4. (Yes) Do X
            # 5. End (Normal)
            # Link 4 -> 5? Yes.
            
            if previous_step:
                source_id = previous_step["id"]

        if source_id:
            edges.append({
                "from": source_id,
                "to": current_node["id"],
                "label": label
            })
            
        previous_step = current_node

    return {
        "nodes": nodes,
        "edges": edges
    }
