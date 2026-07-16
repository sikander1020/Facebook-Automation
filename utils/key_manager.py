"""
API Key Manager - Auto rotation with fallback
Manages WaveSpeed.ai API keys pool
"""
import json
import os
import requests
from datetime import datetime

KEYS_FILE = "wavespeed_keys.json"

def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    return []

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

def add_key_manually(api_key, email="manual"):
    """Manually add a key to the pool"""
    keys = load_keys()
    keys.append({
        "key": api_key,
        "email": email,
        "active": True,
        "credits_used": 0,
        "added_at": datetime.now().isoformat()
    })
    save_keys(keys)
    print(f"Key added! Total keys: {len(keys)}")

def check_key_valid(api_key):
    """Check if a WaveSpeed key still has credits"""
    try:
        resp = requests.get(
            "https://api.wavespeed.ai/api/v2/user/balance",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            balance = data.get("data", {}).get("balance", 0)
            return float(balance) > 0
        return False
    except:
        return False

def get_active_key():
    """Get next available active key, auto-rotate if exhausted"""
    keys = load_keys()
    
    if not keys:
        return None, "No keys in pool! Run: python utils/wavespeed_signup.py"
    
    for i, key_data in enumerate(keys):
        if not key_data.get("active", True):
            continue
        
        api_key = key_data["key"]
        
        # Check if key still works
        if check_key_valid(api_key):
            return api_key, None
        else:
            # Mark as exhausted
            print(f"Key {i+1} exhausted, rotating to next...")
            keys[i]["active"] = False
            save_keys(keys)
    
    # All keys exhausted
    active_count = sum(1 for k in keys if k.get("active", True))
    return None, f"All {len(keys)} keys exhausted! Create more accounts."

def get_balance(api_key):
    """Get current balance for a key"""
    try:
        resp = requests.get(
            "https://api.wavespeed.ai/api/v2/user/balance",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("balance", 0)
        return 0
    except:
        return 0

def show_pool_status():
    """Show status of all keys"""
    keys = load_keys()
    if not keys:
        print("No keys in pool!")
        return
    
    print(f"\n=== Key Pool Status ({len(keys)} keys) ===")
    for i, k in enumerate(keys):
        status = "ACTIVE" if k.get("active", True) else "EXHAUSTED"
        balance = get_balance(k["key"]) if k.get("active", True) else 0
        print(f"Key {i+1}: {k['key'][:15]}... | {status} | Balance: ${balance:.4f} | {k.get('email', 'unknown')}")
    print("="*50)

if __name__ == "__main__":
    show_pool_status()
