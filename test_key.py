import os
import urllib.request
import json

key = "YOUR_API_KEY"

# Test Gemini
print("Testing Gemini...")
try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    req = urllib.request.Request(url)
    res = urllib.request.urlopen(req).read()
    print("Gemini: SUCCESS")
except Exception as e:
    print("Gemini:", e)

# Test Fal
print("Testing Fal...")
try:
    url = "https://fal.run/fal-ai/fast-svd"
    req = urllib.request.Request(url, headers={"Authorization": f"Key {key}"}, data=b'{"image_url":"https://example.com"}')
    res = urllib.request.urlopen(req).read()
    print("Fal: SUCCESS")
except Exception as e:
    print("Fal:", e)
