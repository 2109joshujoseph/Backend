import requests

try:
    print("Checking Ollama tags...")
    resp = requests.get("http://localhost:11434/api/tags")
    print(f"Tags Status: {resp.status_code}")
    print(f"Tags Content: {resp.text[:200]}")

    print("\nTesting Generate Endpoint with REAL prompt...")
    
    prompt = """
Return ONLY a numbered list of flowchart steps.
Do NOT explain.
Do NOT output JSON.
Do NOT use markdown.

Rules:
- Each line MUST start with a number and a dot (example: 1. Start)
- Use 'Decision:' for decision steps

Problem:
Find whether a number is palindrome or not

Example:
1. Start
2. Input number
3. Decision: Is number even?
4. Output even
5. Output odd
6. End
"""

    payload = {
        "model": "phi3",
        "prompt": prompt,
        "stream": False
    }
    resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
    print(f"Generate Status: {resp.status_code}")
    print("Raw Response Length:", len(resp.text))
    print("Raw Response First 1000 chars:")
    print(resp.text[:1000])
    
    print("\nAttempting JSON decode:")
    try:
        data = resp.json()
        print("JSON Decode Success")
        print(data.get("response"))
    except Exception as e:
        print(f"JSON Decode Failed: {e}")

except Exception as e:
    print(f"Connection Failed: {e}")
