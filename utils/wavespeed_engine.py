"""
WaveSpeed.ai Engine - Image & Video Generation
Auto-rotates API keys from pool
Supports: Kling, Wan, Seedance, Flux, Veo
"""
import requests
import time
import os
from utils.key_manager import get_active_key

WAVESPEED_API = "https://api.wavespeed.ai/api/v2"

# Model IDs
MODELS = {
    # Image models (fast, free credits)
    "flux":         "wavespeed-ai/flux-dev",
    "flux_fast":    "wavespeed-ai/flux-schnell",
    "seedream":     "wavespeed-ai/seedream-3-0",
    
    # Video models
    "wan_t2v":      "wan-ai/wan2.1-t2v-720p",
    "wan_i2v":      "wan-ai/wan2.1-i2v-720p",
    "kling_t2v":    "kuaishou/kling-v2-master-t2v",
    "kling_i2v":    "kuaishou/kling-v2-master-i2v",
    "seedance":     "bytedance/seedance-1-0-lite-t2v-480p",
}

def generate_image(prompt, model="flux", width=1024, height=1024):
    """Generate image using WaveSpeed API"""
    api_key, error = get_active_key()
    if not api_key:
        return {"success": False, "error": error}
    
    payload = {
        "prompt": prompt,
        "size": f"{width}*{height}",
        "num_inference_steps": 4 if "schnell" in model else 28,
    }
    
    model_id = MODELS.get(model, MODELS["flux"])
    
    try:
        resp = requests.post(
            f"{WAVESPEED_API}/{model_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60
        )
        data = resp.json()
        
        if resp.status_code == 200 and data.get("data", {}).get("outputs"):
            outputs = data["data"]["outputs"]
            if outputs:
                return {"success": True, "url": outputs[0], "type": "image"}
        
        # Check if credits exhausted
        if "insufficient" in str(data).lower() or "balance" in str(data).lower():
            from utils.key_manager import load_keys, save_keys
            # Will auto-rotate on next call
            return {"success": False, "error": "Credits exhausted, rotating key..."}
        
        return {"success": False, "error": str(data)}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_video(prompt, model="wan_t2v", duration=5, image_url=None):
    """Generate video using WaveSpeed API"""
    api_key, error = get_active_key()
    if not api_key:
        return {"success": False, "error": error}
    
    model_id = MODELS.get(model, MODELS["wan_t2v"])
    
    # Use image-to-video if image provided
    if image_url and "i2v" not in model:
        model = model.replace("t2v", "i2v")
        model_id = MODELS.get(model, MODELS.get("wan_i2v"))
    
    payload = {
        "prompt": prompt,
        "duration": duration,
    }
    
    if image_url:
        payload["image"] = image_url
    
    try:
        # Submit generation request
        resp = requests.post(
            f"{WAVESPEED_API}/{model_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        data = resp.json()
        
        if resp.status_code != 200:
            return {"success": False, "error": str(data)}
        
        request_id = data.get("data", {}).get("id")
        if not request_id:
            return {"success": False, "error": "No request ID received"}
        
        # Poll for result
        print(f"Video submitted (ID: {request_id}), polling...")
        for attempt in range(60):
            time.sleep(5)
            status_resp = requests.get(
                f"{WAVESPEED_API}/predictions/{request_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15
            )
            status_data = status_resp.json()
            status = status_data.get("data", {}).get("status", "")
            
            if status == "completed":
                outputs = status_data["data"].get("outputs", [])
                if outputs:
                    return {"success": True, "url": outputs[0], "type": "video"}
            elif status == "failed":
                return {"success": False, "error": "Generation failed"}
            
            print(f"  Status: {status} (attempt {attempt+1}/60)")
        
        return {"success": False, "error": "Timeout waiting for video"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_media(prompt, media_type="image", **kwargs):
    """Unified media generation - auto picks image or video"""
    if media_type == "video":
        return generate_video(prompt, **kwargs)
    else:
        return generate_image(prompt, **kwargs)

if __name__ == "__main__":
    # Quick test
    print("Testing WaveSpeed image generation...")
    result = generate_image("a beautiful mountain landscape at sunset")
    print(f"Result: {result}")
