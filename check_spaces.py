import urllib.request
import json
try:
    response = urllib.request.urlopen("https://huggingface.co/api/spaces?search=stable-video-diffusion&limit=20")
    data = json.loads(response.read())
    for x in data:
        stage = x.get('runtime', {}).get('stage')
        if stage == "RUNNING":
            print(f"{x['id']}: {stage}")
except Exception as e:
    print(e)
