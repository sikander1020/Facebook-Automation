import os
import shutil
from gradio_client import Client

def generate_svd_video(prompt: str, output_folder: str, hf_token: str = None) -> str:
    """
    Generates a video using THUDM/CogVideoX-5B-Space on Hugging Face.
    Generates a video using LTX-Video-Distilled on Hugging Face.
    Requires a free Hugging Face token to avoid GPU quota errors.
    """
    print(f"[HuggingFace Engine] Generating video for prompt: '{prompt}'...")
    
    try:
        # Initialize client with optional HF token for better quota
        client = Client("Lightricks/ltx-video-distilled", token=hf_token)
        
        # Predict API call for LTX-Video-Distilled
        result = client.predict(
            prompt=prompt,
            negative_prompt="worst quality, inconsistent motion, blurry, jittery, distorted",
            input_image_filepath=None,
            input_video_filepath=None,
            height_ui=512,
            width_ui=704,
            mode="text-to-video",
            duration_ui=2,
            ui_frames_to_use=9,
            seed_ui=42,
            randomize_seed=True,
            ui_guidance_scale=1.5,
            improve_texture_flag=True,
            api_name="/text_to_video"
        )
        
        # result is a tuple: (generated_video_dict, seed)
        # generated_video_dict has 'video': filepath
        video_info = result[0]
        video_path = video_info.get("video") if isinstance(video_info, dict) else video_info
        
        if not video_path or not os.path.exists(video_path):
            print("[HuggingFace Engine] Video generation returned empty path.")
            return None
            
        # Move the video to the output folder
        import uuid
        filename = f"cogvideox_{uuid.uuid4().hex[:8]}.mp4"
        final_path = os.path.join(output_folder, filename)
        
        shutil.copy(video_path, final_path)
        print(f"[HuggingFace Engine] Success! Video saved at: {final_path}")
        
        return filename
        
    except Exception as e:
        print(f"[HuggingFace Engine] Error generating video: {e}")
        import traceback
        traceback.print_exc()
        return None
