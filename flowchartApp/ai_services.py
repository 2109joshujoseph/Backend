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
        
        
        try:
            return response.json().get("response", "")
        except json.JSONDecodeError:
            
            full_response = []
            for line in response.text.strip().split('\n'):
                if line.strip():
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            full_response.append(obj["response"])
                    except json.JSONDecodeError:
                        continue 
            
            if full_response:
                return "".join(full_response)
            
          
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
       
        raise e

  
    steps = []
    for line in raw_text.splitlines():
        
        match = re.match(r"^\s*(\d+)\.\s*(?:\((Yes|No|Else)\))?\s*(.*)", line, re.IGNORECASE)
        if match:
            step_num = match.group(1)
            branch_type = match.group(2) 
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

 
    
    last_node_id = None
    last_decision_id = None
    
   
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
            "branch": branch
        })

    
    decision_stack = [] 
    
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
             
             found_decision = None
             for j in range(i-1, -1, -1):
                 if nodes[j]["type"] == "decision":
                     found_decision = nodes[j]
                     break
             
             if found_decision:
                 source_id = found_decision["id"]
                 label = branch_type.capitalize()
                 
                 
        else:
           
            
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
