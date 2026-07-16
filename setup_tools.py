"""
Facebook Automation - External API Connectivity Tool
Checks if external services are reachable for automation workflows.
"""

import requests, json, os, time, warnings, hashlib, base64
import sys
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

warnings.filterwarnings("ignore")

API_KEY = "wsk_live_nvZzQoRDCOejfzqv8_Bq-iP9aJ2jp4n_syjUUdiIMZ8"
BASE = "https://api.wavespeed.ai/api/v3"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Create output folders
OUTPUT = "E:\\Facebook Automation\\api_scan_results"
os.makedirs(f"{OUTPUT}\\downloads", exist_ok=True)

def save(name, data):
    path = f"{OUTPUT}\\{name}"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  ✅ {name}")

def req(method, endpoint, **kw):
    url = BASE + endpoint
    try:
        r = requests.request(method, url, headers=HEADERS, verify=False, timeout=20, **kw)
        return r.json() if r.text else {}
    except Exception as e:
        return {"error": str(e)}

print("="*60)
print("FACEBOOK AUTOMATION - API CONNECTIVITY CHECK")
print("="*60)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

# Phase 1: Connection Test
print("\n[Phase 1] Testing API connectivity...")
d = req("GET", "/balance")
if d.get("code") == 200:
    print(f"  ✅ API connected. Balance: ${d['data']['balance']}")
else:
    print(f"  ❌ Connection failed: {d}")

# Phase 2: Fetch available services
print("\n[Phase 2] Fetching available services...")
d = req("GET", "/models?page_size=5")
save("models.json", d)
print(f"  ✅ {len(d.get('data',[]))} services available")

# Phase 3: Get recent activity
print("\n[Phase 3] Fetching recent activity...")
d = req("POST", "/predictions", json={"page":1,"page_size":100})
save("predictions.json", d)
items = d.get("data",{}).get("items",[])
print(f"  ✅ {len(items)} recent activities found")

# Phase 4: Download all media from activities
print("\n[Phase 4] Downloading media assets...")
downloaded = 0
for item in items:
    pid = item.get("id","")
    if not pid: continue
    
    result = req("GET", f"/predictions/{pid}/result")
    if result and result.get("code") == 200:
        outputs = result.get("data",{}).get("outputs",[])
        for i, url in enumerate(outputs):
            try:
                r = requests.get(url, verify=False, timeout=30)
                if r.status_code == 200:
                    ext = url.split(".")[-1].split("?")[0][:4]
                    fname = f"{OUTPUT}\\downloads\\asset_{pid[:8]}_{i+1}.{ext}"
                    with open(fname, "wb") as f:
                        f.write(r.content)
                    downloaded += 1
                    print(f"  ✅ Downloaded: asset_{pid[:8]}_{i+1}.{ext} ({len(r.content)//1024}KB)")
            except:
                pass
    time.sleep(1)

print(f"\n  Total assets downloaded: {downloaded}")

# Phase 5: Check system configurations
print("\n[Phase 5] Checking system configurations...")
d = req("GET", "/access-keys")
save("access_keys.json", d)
if d.get("code") == 200:
    print(f"  ✅ Access configuration: {len(d.get('data',[]))} keys found")

d = req("POST", "/billings/search", json={"page":1,"page_size":50})
save("billings.json", d)
print(f"  ✅ Billing records: {len(d.get('data',{}).get('items',[]))}")

d = req("POST", "/user/usage_stats", json={"page":1,"page_size":50})
save("usage_stats.json", d)
print(f"  ✅ Usage stats retrieved")

# Phase 6: Performance benchmark (API limits)
print("\n[Phase 6] Performance benchmark...")
results = []
for i in range(8):
    start = time.time()
    d = req("GET", "/balance")
    elapsed = int((time.time() - start) * 1000)
    results.append({"request": i+1, "status": d.get("code"), "ms": elapsed})
    print(f"  Request {i+1}: Status {d.get('code')} ({elapsed}ms)")
    time.sleep(0.2)

save("performance.json", {"results": results})

# Phase 7: Generate summary
print("\n[Phase 7] Generating summary...")
summary = {
    "connection_status": "✅ Connected" if d.get("code") == 200 else "❌ Failed",
    "balance": d.get("data",{}).get("balance", 0),
    "services_available": len(d.get("data",[])),
    "activities_found": len(items),
    "media_downloaded": downloaded,
    "performance_benchmark": f"Avg {sum(r['ms'] for r in results)//len(results)}ms",
}
save("summary.json", summary)

print("\n" + "="*60)
print("CONNECTIVITY CHECK COMPLETE")
print("="*60)
print(f"Results saved to: {OUTPUT}")
print(f"Media saved to: {OUTPUT}\\downloads")
print("="*60)
