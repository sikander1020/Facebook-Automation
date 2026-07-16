import urllib.request
import urllib.parse
prompt = urllib.parse.quote('Write a short 2 scene story about a magical cat in JSON format: [{"scene_prompt": "...", "dialogue": "..."}]')
req = urllib.request.Request(f'https://text.pollinations.ai/{prompt}', headers={'User-Agent': 'Mozilla/5.0'})
res = urllib.request.urlopen(req)
print(res.read().decode('utf-8'))
