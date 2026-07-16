import urllib.request
import json
from gradio_client import Client
import concurrent.futures

def check_space(space_id):
    try:
        client = Client(space_id, timeout=10) # short timeout
        api_info = client.view_api(return_format="dict")
        # Ensure it has an endpoint that looks like video generation
        for ep_name, ep_data in api_info.get('named_endpoints', {}).items():
            for ret in ep_data.get('returns', []):
                if 'Video' in ret.get('component', ''):
                    return f"[SUCCESS] {space_id} has a Video endpoint!"
        return f"[NO_VIDEO_EP] {space_id}"
    except Exception as e:
        return f"[FAILED] {space_id}: {str(e)[:50]}"

def main():
    queries = ["video", "text-to-video", "stable-video-diffusion", "ltx-video", "hunyuan", "mochi"]
    space_ids = set()
    
    for q in queries:
        try:
            url = f"https://huggingface.co/api/spaces?search={q}&limit=20"
            req = urllib.request.Request(url)
            data = json.loads(urllib.request.urlopen(req).read().decode())
            for x in data:
                if x.get('runtime', {}).get('stage') == 'RUNNING' or not x.get('runtime', {}).get('stage'):
                    space_ids.add(x['id'])
        except Exception:
            pass

    print(f"Testing {len(space_ids)} spaces...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_space, list(space_ids))
        
    for res in results:
        if "[SUCCESS]" in res:
            print(res)

if __name__ == "__main__":
    main()
