import os
import time
import sys
import uuid

# We no longer need script.py / WavespeedClient
from utils.huggingface_engine import generate_svd_video

def generate_studio_media(media_type: str, prompt: str, model: str, style: str, duration: int, aspect_ratio: str, count: int, upload_folder: str):
    filenames = []
    
    # Setup aspect ratio
    if aspect_ratio == "16:9":
        width, height = 1280, 720
    elif aspect_ratio == "9:16":
        width, height = 720, 1280
    elif aspect_ratio == "1:1":
        width, height = 1024, 1024
    elif aspect_ratio == "4:3":
        width, height = 1024, 768
    elif aspect_ratio == "21:9":
        width, height = 1280, 544
    else:
        width, height = 1280, 720
        
    # Style modifier
    final_prompt = prompt
    if style == "realistic":
        final_prompt = f"{prompt}, cinematic realistic, highly detailed, photorealistic, 8k"
    elif style == "cartoon":
        final_prompt = f"{prompt}, flat 2d cartoon illustration, vivid colors"
    elif style == "3d":
        final_prompt = f"{prompt}, 3d animation, pixar style, disney style, highly detailed render"
    elif style == "anime":
        final_prompt = f"{prompt}, anime style, studio ghibli, makoto shinkai"
    elif style == "watercolor":
        final_prompt = f"{prompt}, watercolor painting, artistic"
        
    for i in range(count):
        job_id = uuid.uuid4().hex[:8]
        try:
            if media_type == "image":
                import urllib.request
                import urllib.parse
                
                ext = ".jpg"
                filename = f"studio_{media_type}_{job_id}{ext}"
                output_path = os.path.join(upload_folder, filename)
                
                print(f"[AI Studio] Generating image using Pollinations (Flux)...")
                
                import random
                seed = random.randint(1, 10000000)
                encoded_prompt = urllib.parse.quote(final_prompt)
                url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true"
                
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=60) as response:
                    with open(output_path, 'wb') as f:
                        f.write(response.read())
                        
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    filenames.append(filename)
                else:
                    print("Download failed for Pollinations image.")
                
                continue # Skip the wavespeed video logic
            else:
                ext = ".mp4"
                filename = f"studio_video_{job_id}{ext}"
                output_path = os.path.join(upload_folder, filename)

                if model == "zoom":
                    print("[AI Studio] User selected Cinematic Zoom Effect. Using FLUX + Zoom...")
                    from utils.huggingface_engine import generate_zoom_video
                    import urllib.request
                    import urllib.parse
                    
                    temp_img_path = os.path.join(upload_folder, f"temp_{job_id}.jpg")
                    import random
                    seed = random.randint(1, 10000000)
                    encoded_prompt = urllib.parse.quote(final_prompt)
                    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true"
                    
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=60) as response:
                        with open(temp_img_path, 'wb') as f:
                            f.write(response.read())
                            
                    if os.path.exists(temp_img_path) and os.path.getsize(temp_img_path) > 0:
                        zoom_success = generate_zoom_video(temp_img_path, output_path, duration_sec=duration)
                        if zoom_success and os.path.exists(output_path):
                            filenames.append(filename)
                        try: os.remove(temp_img_path)
                        except: pass

                else:
                    # Video generation using CogVideoX
                    from utils.huggingface_engine import generate_svd_video
                    print(f"[AI Studio] Generating video using CogVideoX (Free Open-Source)...")
                    
                    # You can pass HF_TOKEN from environment if available
                    hf_token = os.environ.get("HF_TOKEN", None)
                    
                    video_filename = generate_svd_video(
                        prompt=final_prompt,
                        output_folder=upload_folder,
                        hf_token=hf_token
                    )
                    
                    if video_filename and os.path.exists(os.path.join(upload_folder, video_filename)):
                        filenames.append(video_filename)
                    else:
                        print("[AI Studio] CogVideoX generation failed.")
                
        except Exception as e:
            print(f"[AI Studio] Error generating {media_type}: {e}")
            
    return filenames
