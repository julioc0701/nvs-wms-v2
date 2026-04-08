import urllib.request
import json
import socket
import time

URLS = [
    "https://nvs-producao.up.railway.app/api/health",
    "https://nvs-producao.up.railway.app/api/print-jobs/pending"
]

def test_url(url):
    print(f"\nTesting: {url}")
    try:
        start_time = time.time()
        req = urllib.request.Request(url)
        # Simulating agent headers
        req.add_header("User-Agent", "NVS-Diagnostic-Agent/1.0")
        
        with urllib.request.urlopen(req, timeout=10) as response:
            duration = time.time() - start_time
            print(f"Status CODE: {response.getcode()}")
            print(f"Time Taken: {duration:.2f}s")
            data = response.read().decode('utf-8')
            print(f"Response (first 100 chars): {data[:100]}...")
            return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

if __name__ == "__main__":
    print("=== NVS CONNECTION DIAGNOSTIC ===")
    print(f"Hostname: {socket.gethostname()}")
    
    results = []
    for url in URLS:
        results.append(test_url(url))
    
    print("\n" + "="*30)
    if all(results):
        print("RESULT: Network can reach production successfully.")
    else:
        print("RESULT: Connectivity issues detected.")
    print("="*30)
