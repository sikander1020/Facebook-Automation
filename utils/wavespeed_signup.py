"""
WaveSpeed.ai Auto Signup Bot using Playwright
Auto creates accounts with temp emails and extracts API keys
"""
import asyncio
import random
import string
import json
import os
from playwright.async_api import async_playwright
from utils.temp_mail import get_temp_email, check_inbox

KEYS_FILE = "wavespeed_keys.json"

def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    return []

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

def random_password():
    chars = string.ascii_letters + string.digits + "!@#$"
    return ''.join(random.choices(chars, k=14))

async def create_wavespeed_account():
    """Auto create WaveSpeed account and return API key"""
    
    # Step 1: Get temp email
    print("[1/5] Generating temp email...")
    mail_info = get_temp_email()
    email = mail_info["email"]
    sid = mail_info["sid_token"]
    password = random_password()
    print(f"  Email: {email}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Step 2: Go to signup page
            print("[2/5] Opening WaveSpeed signup page...")
            await page.goto("https://www.wavespeed.ai/sign-up", timeout=30000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # Step 3: Fill signup form
            print("[3/5] Filling signup form...")
            
            # Try to find email field
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="Email" i]',
            ]
            for sel in email_selectors:
                try:
                    await page.fill(sel, email, timeout=3000)
                    print(f"  Filled email with selector: {sel}")
                    break
                except:
                    continue
            
            # Fill password
            pwd_selectors = [
                'input[type="password"]',
                'input[name="password"]',
            ]
            pwd_filled = 0
            for sel in pwd_selectors:
                try:
                    fields = await page.query_selector_all(sel)
                    for field in fields:
                        await field.fill(password)
                        pwd_filled += 1
                    if pwd_filled:
                        print(f"  Filled {pwd_filled} password field(s)")
                        break
                except:
                    continue
            
            await asyncio.sleep(1)
            
            # Click signup/register button
            btn_selectors = [
                'button[type="submit"]',
                'button:has-text("Sign up")',
                'button:has-text("Register")',
                'button:has-text("Create")',
                'button:has-text("Continue")',
            ]
            for sel in btn_selectors:
                try:
                    await page.click(sel, timeout=3000)
                    print(f"  Clicked button: {sel}")
                    break
                except:
                    continue
            
            await asyncio.sleep(3)
            
            # Step 4: Verify email
            print("[4/5] Waiting for verification email...")
            verify_link = check_inbox(sid, timeout=120)
            
            if verify_link:
                print(f"  Verification link found! Clicking...")
                await page.goto(verify_link, timeout=30000)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(3)
            else:
                print("  No verification email found, trying to proceed...")
            
            # Step 5: Login and get API key
            print("[5/5] Getting API key from dashboard...")
            
            # Try to login if needed
            await page.goto("https://www.wavespeed.ai/login", timeout=30000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            for sel in email_selectors:
                try:
                    await page.fill(sel, email, timeout=3000)
                    break
                except:
                    continue
            
            for sel in pwd_selectors:
                try:
                    await page.fill(sel, password, timeout=3000)
                    break
                except:
                    continue
            
            for sel in btn_selectors:
                try:
                    await page.click(sel, timeout=3000)
                    break
                except:
                    continue
            
            await asyncio.sleep(3)
            
            # Go to API keys page
            api_key_urls = [
                "https://www.wavespeed.ai/api-keys",
                "https://www.wavespeed.ai/settings/api-keys",
                "https://www.wavespeed.ai/dashboard/api-keys",
                "https://www.wavespeed.ai/account/api-keys",
            ]
            
            api_key = None
            for url in api_key_urls:
                try:
                    await page.goto(url, timeout=15000)
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)
                    
                    # Look for API key on page
                    content = await page.content()
                    
                    # Try to find create key button
                    create_btns = [
                        'button:has-text("Create")',
                        'button:has-text("Generate")',
                        'button:has-text("New API Key")',
                        'button:has-text("Add")',
                    ]
                    for btn in create_btns:
                        try:
                            await page.click(btn, timeout=3000)
                            await asyncio.sleep(2)
                            break
                        except:
                            continue
                    
                    # Find key in input or text
                    key_selectors = [
                        'input[readonly]',
                        'input[type="text"]',
                        'code',
                        '[class*="api-key"]',
                        '[class*="apikey"]',
                        '[class*="key"]',
                    ]
                    for ksel in key_selectors:
                        try:
                            elements = await page.query_selector_all(ksel)
                            for el in elements:
                                text = await el.input_value() if await el.get_attribute("tagName") == "INPUT" else await el.inner_text()
                                text = text.strip()
                                # WaveSpeed keys start with "ws_" or are long alphanumeric strings
                                if len(text) > 20 and (" " not in text):
                                    api_key = text
                                    break
                        except:
                            pass
                        if api_key:
                            break
                    
                    if api_key:
                        break
                except Exception as e:
                    print(f"  URL {url} failed: {e}")
                    continue
            
            await browser.close()
            
            if api_key:
                print(f"\n✓ SUCCESS! API Key: {api_key[:20]}...")
                # Save to keys pool
                keys = load_keys()
                keys.append({
                    "key": api_key,
                    "email": email,
                    "active": True,
                    "credits_used": 0
                })
                save_keys(keys)
                return api_key
            else:
                print("  Could not extract API key automatically.")
                print(f"  Please manually check: https://www.wavespeed.ai/api-keys")
                print(f"  Email: {email} | Password: {password}")
                return None
                
        except Exception as e:
            print(f"Error during signup: {e}")
            await browser.close()
            return None

async def create_multiple_accounts(count=5):
    """Create multiple accounts and fill the key pool"""
    print(f"\n=== Creating {count} WaveSpeed accounts ===\n")
    success = 0
    for i in range(count):
        print(f"\n--- Account {i+1}/{count} ---")
        key = await create_wavespeed_account()
        if key:
            success += 1
        await asyncio.sleep(5)  # Small delay between signups
    
    print(f"\n=== Done! {success}/{count} accounts created successfully ===")
    keys = load_keys()
    print(f"Total keys in pool: {len(keys)}")
    return success

if __name__ == "__main__":
    # Create 3 accounts by default
    asyncio.run(create_multiple_accounts(3))
