import os
import uuid
import subprocess
import time
import threading
import PIL.Image

# Monkeypatch PIL.Image.ANTIALIAS for compatibility with moviepy and newer Pillow versions
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

from flask import Flask, request, jsonify, send_from_directory, render_template

from utils.audio_engine import (
    generate_speech, create_mixed_audio, generate_preview,
    generate_ai_video,
    VOICES, VOICE_STYLES, MOOD_LABELS, AGE_PRESETS
)
from utils.video_effects import concatenate_clips, apply_copyright_filters, slice_video

app = Flask(__name__, static_folder='static', static_url_path='')

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Background Cleanup Thread (30-minute expiration) ──
def start_cleanup_thread():
    def cleanup_loop():
        # wait a bit for startup to complete before the first sweep
        time.sleep(10)
        while True:
            try:
                now = time.time()
                for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
                    if not os.path.exists(folder):
                        continue
                    for f in os.listdir(folder):
                        if f.startswith('.') or f == '.gitkeep':
                            continue
                        fp = os.path.join(folder, f)
                        if os.path.isfile(fp):
                            mtime = os.path.getmtime(fp)
                            # 1800 seconds = 30 minutes
                            if now - mtime > 1800:
                                try:
                                    os.remove(fp)
                                    print(f"[background-cleanup] Removed expired file: {f}")
                                except Exception as err:
                                    print(f"[background-cleanup] Failed to delete {f}: {err}")
            except Exception as e:
                print(f"[background-cleanup] Error: {e}")
            time.sleep(300) # Run every 5 minutes

    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()

start_cleanup_thread()

# ── Clean up any leftover temp/partial files on startup ──
for _f in os.listdir(OUTPUT_FOLDER):
    if '.temp' in _f or 'TEMP_MPY' in _f or _f.endswith('.part'):
        try:
            os.remove(os.path.join(OUTPUT_FOLDER, _f))
            print(f'[cleanup] Removed temp file: {_f}')
        except Exception:
            pass


# ── Helper to locate external executables ──
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


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# CVOICE Caching
cvoice_cached_voices = []
from utils.cvoice_engine import fetch_cvoice_voices
import threading

def bg_fetch_cvoice():
    global cvoice_cached_voices
    cvoice_cached_voices = fetch_cvoice_voices()
threading.Thread(target=bg_fetch_cvoice, daemon=True).start()

@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Returns voices + style + age metadata."""
    import copy
    all_voices = copy.deepcopy(VOICES)
    
    if cvoice_cached_voices:
        cvoice_dict = {}
        for cv in cvoice_cached_voices:
            cvoice_dict[cv["FriendlyName"]] = cv["ShortName"]
            
        # Add as a pseudo-language category for the UI
        all_voices["CVoice Premium"] = cvoice_dict
            
    return jsonify({
        'voices': all_voices,
        'voice_styles': VOICE_STYLES,
        'mood_labels': MOOD_LABELS,
        'age_presets': AGE_PRESETS,
    })


@app.route('/api/preview-voice', methods=['POST'])
def preview_voice():
    """
    Generate a short voice preview sample and stream it back as audio/mpeg.
    Body: { voice, lang, style, style_degree, rate, pitch }
    """
    import tempfile
    from flask import send_file

    voice        = request.form.get('voice', 'en-US-EmmaMultilingualNeural')
    lang         = request.form.get('lang', 'en-US')
    style        = request.form.get('style', '')
    style_degree = float(request.form.get('style_degree', 1.0))
    rate         = request.form.get('rate', '+0%')
    pitch        = request.form.get('pitch', '+0Hz')

    # Write to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, dir=UPLOAD_FOLDER)
    tmp.close()
    out_path = tmp.name

    ok = generate_preview(voice=voice, lang_prefix=lang,
                          style=style, style_degree=style_degree,
                          rate=rate, pitch=pitch,
                          output_path=out_path)
    if not ok or not os.path.exists(out_path):
        return jsonify({'error': 'Preview generation failed'}), 500

    return send_file(out_path, mimetype='audio/mpeg',
                     as_attachment=False,
                     download_name='preview.mp3')


@app.route('/api/clear-library', methods=['POST'])
def clear_library():
    """Delete all exported files from the outputs folder."""
    deleted, failed = [], []
    for f in os.listdir(OUTPUT_FOLDER):
        if f.endswith('.mp4') or f.endswith('.mp3'):
            try:
                os.remove(os.path.join(OUTPUT_FOLDER, f))
                deleted.append(f)
            except Exception as ex:
                failed.append({'file': f, 'error': str(ex)})
    return jsonify({'deleted': len(deleted), 'failed': failed})

@app.route('/api/merge', methods=['POST'])
def merge_videos():
    """
    Merge uploaded video clips and overlay generated/uploaded audio.
    Supports style, rate, pitch, style_degree for TTS voices.
    """
    try:
        aspect_ratio  = request.form.get('aspect_ratio', 'vertical')
        audio_source  = request.form.get('audio_source', 'script')
        language      = request.form.get('language', 'ur-PK')
        voice_id      = request.form.get('voice', 'ur-PK-UzmaNeural')
        script_text   = request.form.get('script_text', '')
        trim_audio    = request.form.get('trim_audio', 'true') == 'true'
        # Voice style / mood params
        voice_style        = request.form.get('style', '')
        voice_style_degree = float(request.form.get('style_degree', 1.0))
        voice_rate         = request.form.get('rate', '+0%')
        voice_pitch        = request.form.get('pitch', '+0Hz')
        
        # Handle video uploads
        uploaded_videos = request.files.getlist('videos')
        if not uploaded_videos or len(uploaded_videos) == 0 or uploaded_videos[0].filename == '':
            return jsonify({'success': False, 'error': 'No video files uploaded.'}), 400
            
        video_paths = []
        job_id = str(uuid.uuid4())
        
        # Save video uploads
        for idx, file in enumerate(uploaded_videos):
            filename = f"{job_id}_video_{idx}.mp4"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            video_paths.append(filepath)
            
        # 1. Merge videos together
        merged_temp_video = os.path.join(UPLOAD_FOLDER, f"{job_id}_merged_raw.mp4")
        duration = concatenate_clips(video_paths, aspect_ratio=aspect_ratio, output_path=merged_temp_video)
        
        # 2. Process / Generate audio
        final_audio_path = None
        speech_path = None
        bg_music_path = None
        
        if audio_source == 'script' and script_text.strip():
            # Generate speech audio
            speech_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_speech.mp3")
            generate_speech(script_text, voice_id, speech_path,
                            rate=voice_rate, pitch=voice_pitch,
                            style=voice_style, style_degree=voice_style_degree)
            
        elif audio_source == 'upload':
            uploaded_audio = request.files.get('audio_file')
            if uploaded_audio and uploaded_audio.filename != '':
                speech_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_user_audio.mp3")
                uploaded_audio.save(speech_path)
                
        # Handle optional background music upload
        bg_music_file = request.files.get('bg_music_file')
        if bg_music_file and bg_music_file.filename != '':
            bg_music_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_bg_music.mp3")
            bg_music_file.save(bg_music_path)
            
        # Mix audio tracks if we have speech or background music
        if speech_path or bg_music_path:
            mixed_audio = os.path.join(UPLOAD_FOLDER, f"{job_id}_mixed.mp3")
            ok = create_mixed_audio(
                voiceover_path=speech_path,
                bg_music_path=bg_music_path,
                target_duration=duration,
                output_path=mixed_audio
            )
            if ok and os.path.exists(mixed_audio):
                final_audio_path = mixed_audio
            
        # 3. Combine merged video and final audio
        output_filename = f"merged_{job_id[:8]}.mp4"
        final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        if final_audio_path and os.path.exists(final_audio_path):
            # Combine via FFmpeg for speed and precision
            ffmpeg_bin = get_pip_binary("ffmpeg")
            cmd = [
                ffmpeg_bin, "-y", "-i", merged_temp_video, "-i", final_audio_path,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                "-shortest" if trim_audio else "", final_output_path
            ]
            # Remove empty arguments from command
            cmd = [c for c in cmd if c != ""]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        else:
            # No audio overlay, rename raw merged video
            os.rename(merged_temp_video, final_output_path)
            
        # Cleanup temp upload files
        for p in video_paths + [merged_temp_video, speech_path, bg_music_path, final_audio_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
                    
        return jsonify({
            'success': True,
            'message': 'Videos merged successfully!',
            'filename': output_filename,
            'duration': f"{duration:.2f}s"
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/clip', methods=['POST'])
def clip_youtube_video():
    """
    Downloads a YouTube video, cuts it into clips, and applies anti-copyright filters.
    """
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({'success': False, 'error': 'Video URL is required.'}), 400
            
        mode = request.form.get('slicing_method', 'auto') # 'auto' or 'timestamps'
        interval = int(request.form.get('interval', 8))
        timestamps_str = request.form.get('timestamps', '')
        
        # Filter options
        try:
            b_width = int(request.form.get('border_width', 0))
        except ValueError:
            b_width = 0
            
        filters = {
            'aspect_ratio': request.form.get('aspect_ratio', 'original'),
            'mirror': request.form.get('mirror', 'true') == 'true',
            'zoom': request.form.get('zoom', 'true') == 'true',
            'speed': float(request.form.get('speed', 1.04)),
            'pitch_shift': float(request.form.get('pitch_shift', 0.8)),
            'border_color': request.form.get('border_color', 'none'),
            'border_width': b_width,
            'text_overlay': request.form.get('text_overlay', ''),
            'color_shift': request.form.get('color_shift', 'false') == 'true',
            'anti_watermark': request.form.get('anti_watermark', 'false') == 'true',
            'color_lut': True,      # always on: invisible color channel shift
            'strip_metadata': True, # always on: delete encoder/title/ISRC tags
            'randomize_codec': True, # always on: random GOP/B-frames/CRF
            'add_noise': True,      # always on: subtle film grain
        }

        # Scene shuffle setting (from form, default True for multi-clip modes)
        shuffle_scenes = request.form.get('shuffle_scenes', 'true') == 'true'
        
        job_id = str(uuid.uuid4())
        raw_download_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_raw.mp4")
        
        # 1. Download Video using yt-dlp
        ytdlp_bin = get_pip_binary('yt-dlp')
        
        print(f"Downloading video from {url}...")

        # Check if curl-cffi is available for --impersonate support
        try:
            import curl_cffi
            has_curl_cffi = True
        except ImportError:
            has_curl_cffi = False

        download_cmd = [
            ytdlp_bin,
            # Quality: max 720p
            "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "--merge-output-format", "mp4",
            # Player client: ios/android work for most videos without embedding restrictions
            # tv_embedded is intentionally excluded — it fails for non-embeddable videos
            "--extractor-args", "youtube:player_client=ios,android,mweb,web",
            # Geo-bypass
            "--geo-bypass",
            # SSL resilience
            "--no-check-certificates",
            "--socket-timeout", "60",
            # Retry logic
            "--retries", "10",
            "--fragment-retries", "10",
            "--retry-sleep", "exp=1:30",
            # Output
            "-o", raw_download_path,
            url
        ]

        # Only add --impersonate if curl-cffi is installed
        if has_curl_cffi:
            download_cmd.insert(3, "chrome")
            download_cmd.insert(3, "--impersonate")

        result = subprocess.run(download_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=480)
        stderr_text = result.stderr.decode('utf-8', errors='ignore')
        
        if result.returncode != 0 or not os.path.exists(raw_download_path) or os.path.getsize(raw_download_path) == 0:
            # Check impersonation error FIRST before generic "unavailable"
            if 'impersonate' in stderr_text.lower() or ('curl' in stderr_text.lower() and 'cffi' in stderr_text.lower()):
                err = 'Browser impersonation library missing. Try again (it will retry without impersonation).'
            elif 'SSL' in stderr_text or 'EOF' in stderr_text:
                err = 'YouTube SSL error. Try a different video or try again in a few seconds.'
            elif 'Private' in stderr_text or 'members-only' in stderr_text:
                err = 'This video is private or members-only.'
            elif 'Sign in' in stderr_text:
                err = 'YouTube requires sign-in for this video. Try a fully public video.'
            elif 'removed' in stderr_text or 'unavailable' in stderr_text or 'not available' in stderr_text:
                err = 'This video is unavailable or has been removed from YouTube.'
            elif 'bot' in stderr_text.lower() or 'detected' in stderr_text.lower():
                err = 'YouTube detected bot activity. Try a different video.'
            else:
                # Show raw error so we can diagnose
                err = f'yt-dlp error: {stderr_text[-800:]}' if stderr_text else 'Unknown download error'
            return jsonify({'success': False, 'error': f'Download failed: {err}'}), 500

            
        # 2. Slice downloaded video
        temp_clips_dir = os.path.join(UPLOAD_FOLDER, f"{job_id}_slices")
        os.makedirs(temp_clips_dir, exist_ok=True)
        
        if mode == 'full':
            # Bypass slicing completely for 'Full Video' mode
            sliced_files = [raw_download_path]
        else:
            custom_ranges = []
            if mode == 'timestamps' and timestamps_str:
                def parse_time_to_seconds(t_str):
                    t_str = t_str.strip()
                    if not t_str: return 0.0
                    if ':' in t_str:
                        parts = t_str.split(':')
                        if len(parts) == 3: return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
                        elif len(parts) == 2: return float(parts[0])*60 + float(parts[1])
                    return float(t_str)
    
                # Parse timestamps "10-20, 30-45" or "01:00-01:28, 01:29-02:48"
                parts = timestamps_str.split(',')
                for part in parts:
                    subparts = part.strip().split('-')
                    if len(subparts) == 2:
                        try:
                            start_t = parse_time_to_seconds(subparts[0])
                            end_t = parse_time_to_seconds(subparts[1])
                            custom_ranges.append([start_t, end_t])
                        except Exception:
                            pass
                            
            sliced_files = slice_video(
                raw_download_path,
                temp_clips_dir,
                mode=mode,
                intervals=interval,
                custom_ranges=custom_ranges
            )
            
            if not sliced_files:
                return jsonify({'success': False, 'error': 'No clips generated during slicing.'}), 500

            # ── [NEW] Scene Shuffle ────────────────────────────────────────
            # Shuffles clip ORDER only — content inside each clip stays 100% intact.
            # Breaks sequential scene pattern detection used by Content-ID.
            # Only applies when there are 2+ clips (no effect on single/full video).
            if shuffle_scenes and len(sliced_files) > 1:
                import random as _rnd
                _rnd.shuffle(sliced_files)
                print(f"[clipper] Shuffled {len(sliced_files)} clips for anti-detection.")
            
        # 3. Apply safety filters to each clip and save to outputs
        processed_files = []
        for idx, file_path in enumerate(sliced_files, 1):
            out_filename = f"clip_{job_id[:8]}_{idx}.mp4"
            out_path = os.path.join(OUTPUT_FOLDER, out_filename)
            
            apply_copyright_filters(file_path, out_path, filters)
            if os.path.exists(out_path):
                processed_files.append(out_filename)
                
        # Cleanup raw downloaded file & sliced folder
        if os.path.exists(raw_download_path):
            os.remove(raw_download_path)
            
        import shutil
        if os.path.exists(temp_clips_dir):
            shutil.rmtree(temp_clips_dir)
            
        return jsonify({
            'success': True,
            'message': f'YouTube video processed into {len(processed_files)} clips!',
            'filenames': processed_files
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

def get_video_duration(path):
    try:
        ffprobe_bin = get_pip_binary("ffprobe")
        cmd = [
            ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            duration = float(res.stdout.strip())
            return f"{duration:.1f}s"
    except Exception:
        pass
    return "unknown"

@app.route('/api/outputs', methods=['GET'])
def get_outputs():
    """Lists all real (non-temp) output files, newest first."""
    SKIP_PATTERNS = ('.temp', 'TEMP_MPY', '.part', '.tmp')
    files = []
    for f in os.listdir(OUTPUT_FOLDER):
        # Only include clean .mp4 files — skip any temp/partial artifacts
        if not f.endswith('.mp4'):
            continue
        if any(pat in f for pat in SKIP_PATTERNS):
            # Also delete them from disk so they don't pile up
            try:
                os.remove(os.path.join(OUTPUT_FOLDER, f))
            except Exception:
                pass
            continue
        path = os.path.join(OUTPUT_FOLDER, f)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        files.append({
            'filename': f,
            'size': f"{size_mb:.2f} MB",
            'duration': get_video_duration(path)
        })
    # Sort newest first
    files.sort(
        key=lambda x: os.path.getmtime(os.path.join(OUTPUT_FOLDER, x['filename'])),
        reverse=True
    )
    return jsonify(files)

@app.route('/api/generate-video', methods=['POST'])
def generate_video():
    """
    End-to-end AI script-to-video generation route.
    """
    try:
        script_text   = request.form.get('script_text', '')
        theme         = request.form.get('theme', 'auto')
        aspect_ratio  = request.form.get('aspect_ratio', 'vertical')
        voice_id      = request.form.get('voice', 'ur-PK-UzmaNeural')
        voice_rate    = request.form.get('rate', '+0%')
        voice_pitch   = request.form.get('pitch', '+0Hz')
        trim_audio    = request.form.get('trim_audio', 'true') == 'true'
        
        if not script_text.strip():
            return jsonify({'success': False, 'error': 'Script text is required.'}), 400
            
        bg_music_file = request.files.get('bg_music_file')
        
        job_id = str(uuid.uuid4())
        output_filename = f"ai_video_{job_id[:8]}.mp4"
        final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        res = generate_ai_video(
            script_text=script_text,
            theme=theme,
            aspect_ratio=aspect_ratio,
            voice_id=voice_id,
            rate=voice_rate,
            pitch=voice_pitch,
            bg_music_file=bg_music_file,
            trim_audio=trim_audio,
            output_path=final_output_path
        )
        
        if res.get('success'):
            return jsonify({
                'success': True,
                'message': 'AI Video generated successfully!',
                'filename': output_filename,
                'duration': f"{res.get('duration'):.2f}s",
                'slides': res.get('sentences_count')
            })
        else:
            return jsonify({'success': False, 'error': 'Video generation failed.'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dub-video', methods=['POST'])
def dub_video():
    """Endpoint for AI Video Dubber."""
    try:
        input_method = request.form.get('dub_input_method', 'url')
        target_lang = request.form.get('target_lang', 'ur-PK')
        target_lang_short = target_lang.split('-')[0]
        voice_id = request.form.get('voice', 'ur-PK-UzmaNeural')
        
        job_id = str(uuid.uuid4())
        temp_dir = os.path.join(UPLOAD_FOLDER, f"{job_id}_dubbing")
        os.makedirs(temp_dir, exist_ok=True)
        
        source_path = None
        
        if input_method == 'library':
            source_file = request.form.get('source_file')
            if not source_file:
                return jsonify({'success': False, 'error': 'Source file is required.'}), 400
            source_path = os.path.join(OUTPUT_FOLDER, source_file)
            if not os.path.exists(source_path):
                return jsonify({'success': False, 'error': 'Source file not found in library.'}), 404
                
        elif input_method == 'upload':
            if 'source_upload' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded.'}), 400
            file = request.files['source_upload']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected.'}), 400
            from werkzeug.utils import secure_filename
            filename = secure_filename(file.filename)
            source_path = os.path.join(temp_dir, filename)
            file.save(source_path)
            
        elif input_method == 'url':
            source_url = request.form.get('source_url')
            if not source_url:
                return jsonify({'success': False, 'error': 'Video URL is required.'}), 400
            
            # Use yt-dlp to download the video
            import yt_dlp
            source_path = os.path.join(temp_dir, 'downloaded_video.mp4')
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': source_path,
                'quiet': True,
                'no_warnings': True
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([source_url])
            except Exception as e:
                return jsonify({'success': False, 'error': f"Failed to download URL: {str(e)}"}), 500
                
            if not os.path.exists(source_path):
                return jsonify({'success': False, 'error': 'Video download failed entirely.'}), 500
                
        else:
            return jsonify({'success': False, 'error': 'Invalid input method.'}), 400
            
        output_filename = f"dubbed_{job_id[:8]}.mp4"
        final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        from utils.dubbing_engine import dub_video_pipeline
        
        # In a production app, run this async. For simplicity here, we block.
        success = dub_video_pipeline(
            video_path=source_path,
            output_video_path=final_output_path,
            target_lang=target_lang_short,
            voice_id=voice_id,
            temp_dir=temp_dir
        )
        
        # Cleanup
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
        if success and os.path.exists(final_output_path):
            return jsonify({
                'success': True,
                'message': 'Video dubbed successfully!',
                'filename': output_filename
            })
        else:
            return jsonify({'success': False, 'error': 'Dubbing process failed.'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-script', methods=['POST'])
def generate_script():
    from utils.studio_engine import generate_studio_project
    
    topic = request.form.get('topic', '')
    if not topic:
        return jsonify({'success': False, 'error': 'Topic is required'}), 400
        
    result = generate_studio_project(topic)
    if result.get("success"):
        return jsonify({'success': True, 'studio_data': result["data"]})
    else:
        return jsonify({'success': False, 'error': result.get("error", "Unknown error")}), 500

@app.route('/api/autodraft-script', methods=['POST'])
def autodraft_script():
    import urllib.request
    import urllib.parse
    import json
    topic = request.form.get('topic', '')
    style = request.form.get('style', '3d pixar style')
    duration = request.form.get('duration', 'Medium')
    lang = request.form.get('language', 'English')
    
    if not topic:
        return jsonify({'success': False, 'error': 'Topic is required'}), 400
        
    scene_count = 6
    if "Short" in duration: scene_count = 5
    if "Long" in duration: scene_count = 12
        
    if "cvoice" in lang.lower():
        lang = "English"
        
    lang_instruction = f"The dialogue MUST be written in {lang}. Make the story highly engaging, logical, and fun with a clear beginning, middle, and end."
    if lang == "Urdu":
        lang_instruction = "The dialogue MUST be written in ROMAN URDU (Urdu written in English alphabets, e.g., 'Kya haal hai?'). Make it sound very natural, conversational, and fun like a Pakistani/Indian cartoon. Ensure the story has a proper logical flow, a clear plot, and a satisfying ending."
        
    prompt = f'''You are an expert AI Video Director. I will give you a topic. You must output ONLY a script in the following strict format for a {scene_count} scene video.
{lang_instruction}

[Character: Name = Detailed Visual Description of age, clothes, hair, colors]
[Scene: Visual description of the environment, lighting, cinematic camera movement, and character action]
Narrator: engaging voiceover narration text for this scene in {lang}

Topic: {topic}

Output the script:'''

    encoded_prompt = urllib.parse.quote(prompt)
    url = 'https://text.pollinations.ai/'
    data = json.dumps({
        'messages': [{'role': 'user', 'content': prompt}],
        'model': 'openai'
    }).encode('utf-8')
    
    import time
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                generated_text = response.read().decode('utf-8')
                return jsonify({'success': True, 'script': generated_text})
        except Exception as e:
            import traceback
            traceback.print_exc()
            if attempt == 2:
                return jsonify({'success': False, 'error': f"AI Service Error after 3 attempts: {str(e)}"}), 500
            time.sleep(2)

@app.route('/api/generate-cartoon-video', methods=['POST'])
def generate_cartoon_video():
    """Generates a 2D Cartoon Video from a plain text script."""
    import re
    try:
        script_text_raw = request.form.get('script_text', '')
        aspect_ratio    = request.form.get('cartoon_aspect_ratio', 'horizontal')
        voice_id        = request.form.get('voice', 'en-US-EmmaMultilingualNeural')
        voice_rate      = request.form.get('rate', '+0%')
        voice_pitch     = request.form.get('pitch', '+0Hz')
        pro_motion_mode = request.form.get('pro_motion_mode') == 'on'
        
        if not script_text_raw.strip():
            return jsonify({'success': False, 'error': 'Script text is required.'}), 400
            
        # Parse the plain text script into scene dicts
        script_data = []
        current_scene = None
        
        lines = script_text_raw.split('\n')
        
        # 1. First pass: extract character definitions
        character_map = {}
        for line in lines:
            line = line.strip()
            char_match = re.match(r'^\[Character:\s*([^=]+?)\s*=\s*(.+?)\]$', line, re.IGNORECASE)
            if char_match:
                character_map[char_match.group(1).strip()] = char_match.group(2).strip()

        # 2. Second pass: build scenes
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip character definition lines
            if re.match(r'^\[Character:\s*[^=]+?\s*=\s*.+?\]$', line, re.IGNORECASE):
                continue
                
            # More robust scene match (e.g. [Scene: A dark forest], Scene 1: forest, [A dark forest])
            scene_match = re.match(r'^\[?(?:Scene|Image|Visual|Background|منظر)[^:]*:\s*(.*?)\]?$', line, re.IGNORECASE)
            
            if scene_match:
                prompt_raw = scene_match.group(1).strip()
                # Substitute {CharacterName} with their description
                for char_name, char_desc in character_map.items():
                    # Match {Name} or just the name if we want, but {} is safer
                    prompt_raw = re.sub(r'\{' + re.escape(char_name) + r'\}', char_desc, prompt_raw, flags=re.IGNORECASE)
                
                current_scene = {
                    "scene_prompt": prompt_raw,
                    "script": []
                }
                script_data.append(current_scene)
                continue
                
            # If line is entirely in brackets without a colon, treat it as a scene prompt (e.g. [A dark forest])
            if line.startswith('[') and line.endswith(']') and ':' not in line:
                current_scene = {
                    "scene_prompt": line.strip('[]').strip(),
                    "script": []
                }
                script_data.append(current_scene)
                continue
                
            # Match Dialogue "Name: text" or "نام: text"
            dialogue_match = re.match(r'^([^:]+):\s*(.*)$', line)
            if dialogue_match:
                speaker = dialogue_match.group(1).strip()
                text_to_speak = dialogue_match.group(2).strip()
                type_ = "narration" if speaker.lower() in ['narrator', 'راوی', 'voiceover', 'v.o.'] else "dialogue"
            else:
                speaker = "Narrator"
                text_to_speak = line # Plain narration
                type_ = "narration"
                
            if current_scene is None:
                current_scene = {"scene_prompt": "Beautiful stylized cartoon scene", "script": []}
                script_data.append(current_scene)
                
            current_scene["script"].append({
                "speaker": speaker,
                "text": text_to_speak,
                "type": type_
            })
            
        # 3. Inject Quality Suffix for LTX-Video
        for scene in script_data:
            sp = scene.get("scene_prompt", "").lower()
            if sp:
                scene["scene_prompt"] = scene["scene_prompt"].strip() + ", cinematic lighting, highly detailed, 8k resolution, masterpiece, motion"
                    
        job_id = str(uuid.uuid4())
        output_filename = f"video_{job_id[:8]}.mp4"
        final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        from utils.ltx_pipeline import generate_ltx_pipeline
        
        res = generate_ltx_pipeline(
            script_data=script_data,
            voice_id=voice_id,
            rate=voice_rate,
            pitch=voice_pitch,
            output_path=final_output_path,
            upload_folder=UPLOAD_FOLDER
        )
        
        if res.get('success'):
            return jsonify({
                'success': True,
                'message': 'AI Video generated successfully using LTX-Video!',
                'filename': output_filename,
                'duration': f"{res.get('duration', 0):.2f}s",
                'images': []
            })
        else:
            return jsonify({'success': False, 'error': 'Video generation failed.'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-ai-studio', methods=['POST'])
def generate_ai_studio():
    try:
        from utils.ai_studio import generate_studio_media
        
        media_type = request.form.get('media_type', 'image')
        prompt = request.form.get('prompt', '')
        model = request.form.get('model', 'flux')
        style = request.form.get('style', 'none')
        duration = int(request.form.get('duration', '5'))
        aspect_ratio = request.form.get('aspect_ratio', '16:9')
        count = int(request.form.get('count', '1'))
        
        if not prompt.strip():
            return jsonify({'success': False, 'error': 'Prompt is required.'}), 400
            
        # Handle reference image if we want to add image-to-video later
        # ref_file = request.files.get('reference_image')
        
        filenames = generate_studio_media(
            media_type=media_type,
            prompt=prompt,
            model=model,
            style=style,
            duration=duration,
            aspect_ratio=aspect_ratio,
            count=count,
            upload_folder=OUTPUT_FOLDER
        )
        
        if filenames:
            return jsonify({
                'success': True,
                'filenames': filenames
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to generate media.'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/outputs/<filename>', methods=['GET'])
def download_file(filename):
    """Serves file from outputs folder."""
    return send_from_directory(OUTPUT_FOLDER, filename)


@app.route('/api/auto-upload', methods=['POST'])
def auto_upload():
    """Endpoint for One-Click Auto Uploader (YouTube Shorts, Insta Reels, TikTok)"""
    try:
        topic = request.form.get('topic', 'My Awesome Video')
        video_file = request.files.get('video_file')
        
        config = {
            "youtube_enabled": request.form.get('youtube_enabled') == 'true',
            "insta_enabled": request.form.get('insta_enabled') == 'true',
            "tiktok_enabled": request.form.get('tiktok_enabled') == 'true',
            "insta_username": request.form.get('insta_username', ''),
            "insta_password": request.form.get('insta_password', ''),
            "insta_session_id": request.form.get('insta_session_id', ''),
            "tiktok_session_id": request.form.get('tiktok_session_id', '')
        }

        if not video_file or video_file.filename == '':
            return jsonify({'success': False, 'error': 'No video file provided.'}), 400
            
        job_id = str(uuid.uuid4())
        video_path = os.path.join(UPLOAD_FOLDER, f"upload_{job_id[:8]}.mp4")
        video_file.save(video_path)
        
        from utils.seo_engine import generate_seo_metadata
        from utils.uploader_engine import process_auto_uploads
        
        # 1. Generate SEO Metadata
        seo_data = generate_seo_metadata(topic)
        
        # 2. Start Upload Process (Synchronous for now to return results to UI, but can be made async)
        results = process_auto_uploads(video_path, seo_data, config, None)
        
        # Cleanup uploaded file
        if os.path.exists(video_path):
            try: os.remove(video_path) 
            except: pass
            
        return jsonify({
            'success': True,
            'message': 'Uploads processed successfully',
            'seo_generated': seo_data,
            'upload_results': results
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# Google Vids Extension Automation Queue
# ==========================================
EXTENSION_JOBS = []

@app.route('/api/extension/job', methods=['GET'])
def get_extension_job():
    # Provide the next pending job to the extension
    for job in EXTENSION_JOBS:
        if job['status'] == 'pending':
            job['status'] = 'processing'
            return jsonify({'job_id': job['job_id'], 'prompt': job['prompt']})
    return jsonify({'job_id': None})

@app.route('/api/extension/complete', methods=['POST'])
def complete_extension_job():
    data = request.json
    job_id = data.get('job_id')
    success = data.get('success', False)
    message = data.get('message', '')
    
    for job in EXTENSION_JOBS:
        if job['job_id'] == job_id:
            job['status'] = 'completed' if success else 'failed'
            job['message'] = message
            break
            
    return jsonify({'status': 'ok'})


@app.route('/api/muapi-generate', methods=['POST'])
def muapi_generate():
    try:
        print(f"[MuAPI-Generate] Form Data: {dict(request.form)}", flush=True)
        from utils.muapi_engine import generate_muapi_image, generate_muapi_video
        
        type_ = request.form.get('type') or request.form.get('media_type', 'image')
        prompt = request.form.get('prompt', '')
        model = request.form.get('model', 'flux-dev')
        api_key = request.form.get('api_key', '')
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400
            
        job_id = str(uuid.uuid4())
        ext = 'mp4' if type_ == 'video' else 'png'
        filename = f"muapi_{job_id[:8]}.{ext}"
        output_path = os.path.join(OUTPUT_FOLDER, filename)
        
        if type_ == 'image':
            success = generate_muapi_image(prompt, model, output_path, api_key)
        else:
            if model == "cogvideox":
                print("[MuAPI-Generate] Routing to HuggingFace Engine LTX-Video", flush=True)
                from utils.huggingface_engine import generate_svd_video
                hf_token = os.environ.get("HF_TOKEN", "YOUR_HF_TOKEN")
                video_filename = generate_svd_video(prompt, OUTPUT_FOLDER, hf_token)
                if video_filename:
                    # Rename the downloaded file to the expected output_path or just override the expected variables
                    import shutil
                    shutil.move(os.path.join(OUTPUT_FOLDER, video_filename), output_path)
                    success = True
                else:
                    print("[MuAPI-Generate] HuggingFace Engine returned None", flush=True)
                    success = False
            elif model == "zoom":
                from utils.ai_studio import generate_zoom_video
                # Just mock or handle zoom logic properly, or fail gracefully
                success = False
            elif model == "google_vids":
                print("[MuAPI-Generate] Routing to Google Vids Extension Queue", flush=True)
                EXTENSION_JOBS.append({
                    'job_id': job_id,
                    'prompt': prompt,
                    'status': 'pending',
                    'message': ''
                })
                # We return success immediately so the frontend knows it was queued.
                # In a real app, frontend would poll for status.
                return jsonify({
                    'success': True,
                    'filename': filename, # dummy filename for now
                    'message': 'Job sent to Chrome Extension!'
                })
            else:
                print(f"[MuAPI-Generate] Routing to MuAPI for model: {model}", flush=True)
                success = generate_muapi_video(prompt, model, output_path, api_key)
            
        if success and os.path.exists(output_path):
            return jsonify({
                'success': True,
                'filename': filename,
                'message': 'Generated via MuAPI successfully!'
            })
        else:
            print("[MuAPI-Generate] Success=False or file missing.", flush=True)
            return jsonify({'success': False, 'error': 'Generation failed. Check API key or prompt.'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)
