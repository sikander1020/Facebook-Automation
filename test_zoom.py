from PIL import Image
import numpy as np
import imageio
import os

def create_ken_burns_video(image_path, output_path, duration_sec=5, fps=24, zoom_factor=0.15):
    """
    Creates a smooth Ken Burns (slow zoom) effect video from an image using imageio and PIL.
    """
    try:
        print(f"Creating {duration_sec}s zoom video from {image_path}...")
        img = Image.open(image_path).convert('RGB')
        w, h = img.size
        
        num_frames = duration_sec * fps
        
        # We will write frames to imageio
        # imageio uses ffmpeg backend automatically if available, but if not we can use imageio's built-in writer
        writer = imageio.get_writer(output_path, fps=fps, codec='libx264', quality=8)
        
        for i in range(num_frames):
            # Calculate current zoom factor (from 0 to max_zoom)
            progress = i / float(num_frames)
            current_zoom = 1.0 + (zoom_factor * progress)
            
            # Calculate crop box
            new_w = w / current_zoom
            new_h = h / current_zoom
            
            left = (w - new_w) / 2
            top = (h - new_h) / 2
            right = w - left
            bottom = h - top
            
            cropped = img.crop((left, top, right, bottom))
            resized = cropped.resize((w, h), Image.Resampling.LANCZOS)
            
            # Write to video
            frame = np.array(resized)
            writer.append_data(frame)
            
        writer.close()
        print(f"Video saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error creating zoom video: {e}")
        return False

if __name__ == "__main__":
    # Test it
    import urllib.request
    req = urllib.request.Request("https://image.pollinations.ai/prompt/a%20cute%20cat?width=1024&height=576", headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        with open("test_cat.jpg", "wb") as f:
            f.write(response.read())
    create_ken_burns_video("test_cat.jpg", "test_cat_zoom.mp4")
