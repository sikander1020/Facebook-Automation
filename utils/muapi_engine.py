import os
import subprocess
import json
import uuid
import shutil

def configure_muapi(api_key):
    """Configures the API key for muapi-cli"""
    try:
        muapi_cmd = shutil.which("muapi") or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'Python', 'Python314', 'Scripts', 'muapi.exe')
        subprocess.run([muapi_cmd, "auth", "configure", "--api-key", api_key], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"[MuAPI] Error configuring API key: {e}")
        return False

def generate_muapi_image(prompt, model="flux-dev", output_path=None, api_key=None):
    """
    Generates an image using MuAPI via muapi-cli.
    """
    api_key = api_key or "b7307275ecc1fdc23b3d42d497886cbaf9d3bcb0781a48810d9cc1e657e1d735"
    if api_key:
        configure_muapi(api_key)
        
    try:
        print(f"[MuAPI] Generating image with model {model}...")
        muapi_cmd = shutil.which("muapi") or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'Python', 'Python314', 'Scripts', 'muapi.exe')
        cmd = [muapi_cmd, "image", "generate", prompt, "--model", model, "--output-json"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"[MuAPI] Error: {result.stderr}")
            return False
            
        data = json.loads(result.stdout)
        
        # muapi-cli typically returns a url or a local file path in the JSON output
        media_url = data.get("url") or data.get("file_path") or data.get("result")
        
        if not media_url:
            print(f"[MuAPI] No result found in output: {data}")
            return False
            
        if str(media_url).startswith("http"):
            import urllib.request
            urllib.request.urlretrieve(media_url, output_path)
        else:
            shutil.copy2(media_url, output_path)
            
        return True
        
    except Exception as e:
        print(f"[MuAPI] Exception generating image: {e}")
        return False

def generate_muapi_video(prompt, model="veo3-fast", output_path=None, api_key=None):
    """
    Generates a video using MuAPI via muapi-cli.
    """
    api_key = api_key or "b7307275ecc1fdc23b3d42d497886cbaf9d3bcb0781a48810d9cc1e657e1d735"
    if api_key:
        configure_muapi(api_key)
        
    try:
        print(f"[MuAPI] Generating video with model {model}...")
        muapi_cmd = shutil.which("muapi") or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'Python', 'Python314', 'Scripts', 'muapi.exe')
        cmd = [muapi_cmd, "video", "generate", prompt, "--model", model, "--output-json"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            print(f"[MuAPI] Error: {result.stderr}")
            return False
            
        data = json.loads(result.stdout)
        
        media_url = data.get("url") or data.get("file_path") or data.get("result")
        
        if not media_url:
            print(f"[MuAPI] No result found in output: {data}")
            return False
            
        if str(media_url).startswith("http"):
            import urllib.request
            urllib.request.urlretrieve(media_url, output_path)
        else:
            shutil.copy2(media_url, output_path)
            
        return True
        
    except Exception as e:
        print(f"[MuAPI] Exception generating video: {e}")
        return False
