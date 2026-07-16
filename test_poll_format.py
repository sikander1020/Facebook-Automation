import urllib.request, urllib.parse, json

topic = 'A funny story about a smart dog trying to steal a cookie from the kitchen'
MASTER_PROMPT = "You are a Senior AI Software Architect."

url = "https://text.pollinations.ai/"
payload = {
    "messages": [
        {"role": "user", "content": f"{MASTER_PROMPT}\nTopic: {topic}"}
    ],
    "jsonMode": True,
    "model": "openai"
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
try:
    res = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    with open('pollinations_test.json', 'w', encoding='utf-8') as f:
        f.write(res)
    print("Done writing to pollinations_test.json")
except Exception as e:
    print(f'Error: {e}')
