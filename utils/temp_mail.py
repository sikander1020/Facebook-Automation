"""
Temp Mail Generator using GuerrillaMail API (Free, No Key Needed)
"""
import requests
import time
import re

GUERRILLA_API = "https://api.guerrillamail.com/ajax.php"

def get_temp_email():
    """Generate a fresh temp email address"""
    resp = requests.get(GUERRILLA_API, params={"f": "get_email_address"})
    data = resp.json()
    return {
        "email": data["email_addr"],
        "sid_token": data["sid_token"]
    }

def check_inbox(sid_token, timeout=120):
    """Poll inbox for new email (verification link)"""
    print(f"  Waiting for verification email...")
    for _ in range(timeout // 5):
        time.sleep(5)
        resp = requests.get(GUERRILLA_API, params={
            "f": "get_email_list",
            "offset": 0,
            "sid_token": sid_token
        })
        data = resp.json()
        emails = data.get("list", [])
        if emails:
            # Get first email content
            mail_id = emails[0]["mail_id"]
            mail_resp = requests.get(GUERRILLA_API, params={
                "f": "fetch_email",
                "email_id": mail_id,
                "sid_token": sid_token
            })
            mail_data = mail_resp.json()
            body = mail_data.get("mail_body", "")
            
            # Find verification link
            links = re.findall(r'https?://[^\s"<>]+', body)
            verify_links = [l for l in links if "verify" in l.lower() or "confirm" in l.lower() or "activate" in l.lower()]
            if verify_links:
                return verify_links[0]
            # Return any link from wavespeed
            wavespeed_links = [l for l in links if "wavespeed" in l.lower()]
            if wavespeed_links:
                return wavespeed_links[0]
    return None

if __name__ == "__main__":
    print("Testing temp mail...")
    result = get_temp_email()
    print(f"Generated email: {result['email']}")
    print(f"SID Token: {result['sid_token']}")
