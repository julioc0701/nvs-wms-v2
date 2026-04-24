import urllib.request
import json

BASE_URL = "https://nvs-producao.up.railway.app/api"

def req(path, method="GET", body=None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as resp:
        return json.loads(resp.read().decode())

def test_workflow():
    print("1. Listing sessions...")
    sessions = req("/sessions/")
    if not sessions:
        print("No sessions found. Can't test.")
        return
    
    sid = sessions[0]["id"]
    print(f"Using session ID: {sid}")
    
    print("2. Getting items...")
    items = req(f"/sessions/{sid}/items")
    if not items:
        print("No items found.")
        return
    sku = items[0]["sku"]
    print(f"Using SKU: {sku}")
    
    print("3. Creating a test print job...")
    job = req("/print-jobs", method="POST", body={
        "session_id": sid,
        "sku": sku,
        "zpl_content": "^XA^FO50,50^A0N,50,50^FDTESTE PRODUCAO^FS^XZ",
        "operator_id": 1
    })
    print(f"Job Created: ID={job['id']}, Status={job['status']}")
    
    print("4. Checking pending queue...")
    pending = req("/print-jobs/pending")
    found = any(j["id"] == job["id"] for j in pending)
    print(f"Job found in pending queue: {found}")
    
    if found:
        print("BACKEND IS WORKING PERFECTLY.")
    else:
        print("BACKEND ERROR: Job created but not appearing in pending queue.")

if __name__ == "__main__":
    try:
        test_workflow()
    except Exception as e:
        print(f"TEST FAILED: {e}")
