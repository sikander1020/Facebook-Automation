import os
import uuid
import subprocess
import urllib.request
import urllib.parse
import PIL.Image
from PIL import ImageDraw, ImageFont
import numpy as np
from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips, ImageClip, VideoFileClip

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    BIDI_AVAILABLE = True
except ImportError:
    BIDI_AVAILABLE = False

def get_pip_binary(binary_name):
    paths = {
        "yt-dlp": r"G:\youtube videos\yt-dlp.exe",
        "ffmpeg": r"G:\youtube videos\ffmpeg.exe",
        "ffprobe": r"G:\youtube videos\ffprobe.exe",
    }
    exe = paths.get(binary_name)
    if exe and os.path.exists(exe):
        return exe
    return binary_name

def download_cartoon_image(prompt: str, width: int, height: int, dest_path: str) -> bool:
    """Generate a high-quality 2D cartoon image using Pollinations."""
    style_prompt = f"{prompt}, 2d flat vector cartoon illustration, studio ghibli animation style, vibrant colors, highly detailed, masterpiece, beautiful scenery, no text"
    try:
        import random
        import time
        encoded_prompt = urllib.parse.quote(style_prompt)
        
        for attempt in range(3):
            seed = random.randint(1, 999999)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true&model=flux"
            
            print(f"Downloading cartoon image from Pollinations for prompt (Attempt {attempt+1}): {prompt}")
            try:
                # Add 1.5s delay to prevent server rate-limiting our IP
                time.sleep(1.5)
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as response:
                    with open(dest_path, 'wb') as f:
                        f.write(response.read())
                
                if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                    return True
            except Exception as inner_e:
                print(f"Attempt {attempt+1} failed: {inner_e}")
                time.sleep(2)
                continue
                
        return False
    except Exception as e:
        print(f"Error downloading cartoon image: {e}")
        return False

def make_ken_burns_frame(img_obj, target_w, target_h, t, duration, zoom_ratio=0.12):
    """Crop and zoom a frame dynamically to create a smooth Ken Burns effect."""
    img_w, img_h = img_obj.size
    scale = 1.0 - (zoom_ratio * (t / duration))
    target_aspect = target_w / target_h
    img_aspect = img_w / img_h
    
    if img_aspect > target_aspect:
        crop_h = img_h * scale
        crop_w = crop_h * target_aspect
    else:
        crop_w = img_w * scale
        crop_h = crop_w / target_aspect
        
    left = (img_w - crop_w) / 2
    top = (img_h - crop_h) / 2
    cropped = img_obj.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((target_w, target_h), PIL.Image.Resampling.LANCZOS)

def draw_subtitle_with_stroke(draw, text, x, y, font, fill_color, stroke_color, stroke_width=2):
    # If text contains Arabic/Urdu characters, reshape it for correct rendering
    if BIDI_AVAILABLE and any("\u0600" <= c <= "\u06FF" for c in text):
        reshaped_text = arabic_reshaper.reshape(text)
        text = get_display(reshaped_text)
        
    lines = text.split('\n')
    for line in lines:
        if stroke_width > 0:
            for offset_x in range(-stroke_width, stroke_width + 1):
                for offset_y in range(-stroke_width, stroke_width + 1):
                    if offset_x != 0 or offset_y != 0:
                        draw.text((x + offset_x, y + offset_y), line, font=font, fill=stroke_color)
        draw.text((x, y), line, font=font, fill=fill_color)

def draw_wrapped_text(draw, text, font, max_width, center_x, center_y, fill_color, stroke_color, stroke_width):
    """Draw wrapped caption text with a clean dark border/stroke."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        try:
            w = font.getlength(line_str)
        except AttributeError:
            w, _ = draw.textsize(line_str, font=font) if hasattr(draw, 'textsize') else (font.getmask(line_str).getbbox()[2], 0)
            
        if w > max_width:
            if len(current_line) > 1:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(line_str)
                current_line = []
                
    if current_line:
        lines.append(" ".join(current_line))
        
    y = center_y - (len(lines) * font.size * 1.25) / 2
    for line in lines:
        try:
            line_w = font.getlength(line)
        except AttributeError:
            line_w, _ = draw.textsize(line, font=font) if hasattr(draw, 'textsize') else (font.getmask(line).getbbox()[2], 0)
            
        x = center_x - line_w / 2
        draw_subtitle_with_stroke(draw, line, x, y, font, fill_color, stroke_color, stroke_width)
        y += font.size * 1.30

def get_font_for_lang(lang_code):
    from utils.audio_engine import get_font_for_lang as audio_get_font
    return audio_get_font(lang_code)

def generate_cartoon_pipeline(script_data, aspect_ratio, voice_id, rate, pitch, output_path, upload_folder, pro_motion_mode=False):
    """
    script_data: list of dicts [{"scene_prompt": "...", "dialogue": "..."}]
    """
    from utils.audio_engine import generate_speech
    from utils.huggingface_engine import generate_flux_image, generate_svd_video
    
    if aspect_ratio == 'vertical':
        target_w, target_h = 1080, 1920
        font_size = 65
    else:
        target_w, target_h = 1920, 1080
        font_size = 80
        
    lang_code = "en"
    if voice_id.startswith("gtts-"):
        parts = voice_id.split("-")
        if len(parts) > 1:
            lang_code = parts[1]
    elif len(voice_id) >= 5:
        lang_code = voice_id[:2]
        
    font_path = get_font_for_lang(lang_code)
    
    job_id = str(uuid.uuid4())
    video_clips = []
    temp_files = []
    storyboard_images = []
    output_dir = os.path.dirname(output_path)
    
    try:
        speaker_voice_map = {}
        speaker_count = 0
        
        def get_voice_for_speaker(speaker, base_voice, base_rate, base_pitch):
            nonlocal speaker_count
            if speaker.lower() in ['narrator', 'راوی', 'voiceover', 'v.o.']:
                return base_voice, base_rate, base_pitch
                
            if speaker not in speaker_voice_map:
                speaker_count += 1
                pitch_variations = ['+30Hz', '-30Hz', '+60Hz', '-60Hz', '+0Hz']
                p_var = pitch_variations[(speaker_count - 1) % len(pitch_variations)]
                
                speaker_voice_map[speaker] = {
                    'voice': base_voice,
                    'rate': base_rate,
                    'pitch': p_var
                }
            
            mapping = speaker_voice_map[speaker]
            return mapping['voice'], mapping['rate'], mapping['pitch']
            
        for idx, scene in enumerate(script_data):
            scene_prompt = scene.get('scene_prompt', '')
            
            script_lines = scene.get('script', [])
            if not script_lines and 'dialogue' in scene:
                # Fallback for old single-string format
                script_lines = [{'speaker': 'Narrator', 'text': scene['dialogue'], 'type': 'narration'}]
                
            # Skip empty scenes
            if not scene_prompt and not any(line.get('text', '').strip() for line in script_lines):
                continue
                
            # 1. Generate Voiceover
            audio_path = os.path.join(upload_folder, f"{job_id}_cartoon_voice_{idx}.mp3")
            
            scene_audio_files = []
            full_dialogue_text = []
            
            for line_idx, line_data in enumerate(script_lines):
                speaker = line_data.get('speaker', 'Narrator')
                text = line_data.get('text', '')
                if not text.strip():
                    continue
                    
                spk_voice, spk_rate, spk_pitch = get_voice_for_speaker(speaker, voice_id, rate, pitch)
                
                line_audio_path = os.path.join(upload_folder, f"{job_id}_cartoon_voice_{idx}_{line_idx}.mp3")
                ok = generate_speech(text, spk_voice, line_audio_path, rate=spk_rate, pitch=spk_pitch)
                if ok and os.path.exists(line_audio_path):
                    scene_audio_files.append(line_audio_path)
                    full_dialogue_text.append(text)
                    temp_files.append(line_audio_path)
                    
            if scene_audio_files:
                from moviepy.editor import concatenate_audioclips, AudioFileClip
                clips = [AudioFileClip(f) for f in scene_audio_files]
                final_audio = concatenate_audioclips(clips)
                final_audio.write_audiofile(audio_path, fps=44100, logger=None)
                for c in clips:
                    c.close()
                final_audio.close()
            else:
                # Fallback silent audio
                ffmpeg_bin = get_pip_binary("ffmpeg")
                subprocess.run([ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "3", "-q:a", "9", "-acodec", "libmp3lame", audio_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
            temp_files.append(audio_path)
            dialogue = "\n".join(full_dialogue_text)
            
            # Standardize audio to prevent concat glitches
            std_audio_path = os.path.join(upload_folder, f"{job_id}_cartoon_std_voice_{idx}.mp3")
            ffmpeg_bin = get_pip_binary("ffmpeg")
            subprocess.run([ffmpeg_bin, "-y", "-i", audio_path, "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k", std_audio_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            temp_files.extend([audio_path, std_audio_path])
            
            audio_clip = AudioFileClip(std_audio_path)
            duration = audio_clip.duration + 0.5 # Add small pad
            
            # 2. Generate Image
            image_path = os.path.join(upload_folder, f"{job_id}_cartoon_img_{idx}.jpg")
            ok = False
            if scene_prompt.strip():
                if pro_motion_mode:
                    ok = generate_flux_image(scene_prompt, image_path)
                    # If FLUX fails, fallback to standard Pollinations
                    if not ok or not os.path.exists(image_path):
                         ok = download_cartoon_image(scene_prompt, target_w, target_h, image_path)
                else:
                    ok = download_cartoon_image(scene_prompt, target_w, target_h, image_path)
                
            if not ok or not os.path.exists(image_path):
                img = PIL.Image.new('RGB', (target_w, target_h), color=(50, 100, 150))
                img.save(image_path)
                
            temp_files.append(image_path)
            
            # Copy to output folder for storyboard preview
            import shutil
            sb_filename = f"{job_id}_storyboard_{idx}.jpg"
            sb_path = os.path.join(output_dir, sb_filename)
            try:
                shutil.copy2(image_path, sb_path)
                storyboard_images.append(sb_filename)
            except Exception as e:
                print("Failed to save storyboard image:", e)
            
            # 3. Create Static Image with Overlay text (Transparent PNG)
            overlay = PIL.Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
            if dialogue.strip():
                try:
                    font = ImageFont.truetype(font_path, font_size)
                except Exception:
                    font = ImageFont.load_default()
                    
                draw_overlay = ImageDraw.Draw(overlay)
                draw_overlay.rectangle([0, int(target_h * 0.70), target_w, target_h], fill=(0, 0, 0, 140))
                draw = ImageDraw.Draw(overlay)
                draw_wrapped_text(
                    draw=draw,
                    text=dialogue,
                    font=font,
                    max_width=int(target_w * 0.85),
                    center_x=target_w / 2,
                    center_y=target_h * 0.85,
                    fill_color=(255, 255, 255),
                    stroke_color=(0, 0, 0),
                    stroke_width=3
                )
            
            overlay_path = os.path.join(upload_folder, f"{job_id}_cartoon_overlay_{idx}.png")
            overlay.save(overlay_path)
            temp_files.append(overlay_path)
            
            # Use ffmpeg for scene creation
            clip_video_path = os.path.join(upload_folder, f"{job_id}_cartoon_scene_{idx}.mp4")
            frames = int(duration * 24)
            ffmpeg_bin = get_pip_binary("ffmpeg")
            
            if pro_motion_mode:
                # Generate base motion video from image using SVD
                base_motion_video = os.path.join(upload_folder, f"{job_id}_base_motion_{idx}.mp4")
                svd_ok = generate_svd_video(image_path, base_motion_video)
                
                if svd_ok and os.path.exists(base_motion_video):
                    temp_files.append(base_motion_video)
                    # SVD generates a ~4 second video. We need to loop it or stretch it to match audio duration.
                    # ffmpeg complex filter to loop the video, scale it, and add the text overlay.
                    subprocess.run([
                        ffmpeg_bin, "-y",
                        "-stream_loop", "-1", "-i", base_motion_video,
                        "-i", overlay_path,
                        "-i", std_audio_path,
                        "-filter_complex", f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2[bg];[bg][1:v]overlay=0:0:shortest=1[v]",
                        "-map", "[v]",
                        "-map", "2:a",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
                        "-c:a", "aac", "-b:a", "192k",
                        "-t", str(duration),
                        clip_video_path
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    # Fallback to static if SVD fails
                    subprocess.run([
                        ffmpeg_bin, "-y", "-loop", "1", "-i", image_path,
                        "-i", overlay_path,
                        "-i", std_audio_path,
                        "-filter_complex", f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2[bg];[bg][1:v]overlay=0:0[v]",
                        "-map", "[v]",
                        "-map", "2:a",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
                        "-c:a", "aac", "-b:a", "192k",
                        "-t", str(duration),
                        clip_video_path
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                # Simple static scale effect instead of buggy zoompan that crops images in half
                vf_filter = f"[0:v]scale={target_w}:{target_h}[scaled];[scaled][1:v]overlay=0:0[outv]"
                
                cmd = [
                    ffmpeg_bin, "-y",
                    "-loop", "1", "-framerate", "24", "-i", image_path,
                    "-loop", "1", "-framerate", "24", "-i", overlay_path,
                    "-i", std_audio_path,
                    "-filter_complex", vf_filter,
                    "-map", "[outv]", "-map", "2:a",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-t", str(duration),
                    clip_video_path
                ]
                
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            temp_files.append(clip_video_path)
            
            vclip = VideoFileClip(clip_video_path)
            if idx > 0:
                vclip = vclip.crossfadein(0.5)
            video_clips.append(vclip)
            
        # Merge all scenes
        if video_clips:
            final_clip = concatenate_videoclips(video_clips, method="compose")
            final_clip.write_videofile(
                output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac",
                preset="ultrafast",
                threads=4,
                logger=None
            )
            
            for vc in video_clips:
                vc.close()
            final_clip.close()
            
            total_duration = sum(c.duration for c in video_clips)
            
            # Clean up temps
            for tf in temp_files:
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except Exception:
                        pass
                        
            return {'success': True, 'duration': total_duration, 'images': storyboard_images}
        else:
            return {'success': False, 'error': 'No scenes were successfully generated.'}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
