import os
import uuid
import subprocess
import asyncio
from deep_translator import GoogleTranslator
from utils.audio_engine import get_pip_binary, _tts_async

def extract_audio_from_video(video_path, output_audio_path):
    """Extract standard 44.1kHz audio from the source video."""
    ffmpeg_bin = get_pip_binary("ffmpeg")
    cmd = [
        ffmpeg_bin, "-y", "-i", video_path,
        "-vn", "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k",
        output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def transcribe_audio(audio_path):
    """Transcribe audio using Whisper to get timestamps."""
    import whisper
    # Use the base model to balance speed and accuracy (requires ~1GB VRAM/RAM)
    print("Loading Whisper model (base)...")
    model = whisper.load_model("base")
    print("Transcribing...")
    result = model.transcribe(audio_path)
    segments = []
    for s in result['segments']:
        segments.append({
            'start': s['start'],
            'end': s['end'],
            'text': s['text'].strip()
        })
    return segments

def group_segments(segments, max_gap=1.5):
    """
    Groups rapid consecutive whisper segments together to form natural sentences/paragraphs.
    This helps the TTS read it with a continuous natural flow instead of robotic pauses.
    """
    if not segments:
        return []
        
    grouped = []
    current_group = {
        'start': segments[0]['start'],
        'end': segments[0]['end'],
        'text': segments[0]['text']
    }
    
    for seg in segments[1:]:
        # If the gap between current segment and previous is small, group them!
        gap = seg['start'] - current_group['end']
        
        # We also check if text isn't getting absurdly long, though Edge TTS can handle up to 3000 chars.
        if gap <= max_gap and len(current_group['text']) < 500:
            current_group['end'] = max(current_group['end'], seg['end'])
            current_group['text'] += " " + seg['text']
        else:
            grouped.append(current_group)
            current_group = {
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text']
            }
            
    grouped.append(current_group)
    print(f"Grouped {len(segments)} segments into {len(grouped)} natural paragraphs.")
    return grouped

def translate_segments(segments, target_lang='ur'):
    """Translate transcribed text using Google Translate via deep-translator."""
    print(f"Translating {len(segments)} segments to {target_lang}...")
    translator = GoogleTranslator(source='auto', target=target_lang)
    for seg in segments:
        if len(seg['text']) > 1:
            try:
                translated = translator.translate(seg['text'])
                seg['translated_text'] = translated
            except Exception as e:
                print(f"Translation error: {e}")
                seg['translated_text'] = seg['text']
        else:
            seg['translated_text'] = ""
    return segments

async def async_generate_tts_for_segments(segments, voice_id, temp_dir):
    """Generate TTS MP3 files asynchronously for each segment."""
    for idx, seg in enumerate(segments):
        text = seg.get('translated_text', '').strip()
        if not text:
            seg['audio_file'] = None
            continue
            
        output_mp3 = os.path.join(temp_dir, f"seg_{idx}.mp3")
        await _tts_async(text, voice=voice_id, output_path=output_mp3, rate="+0%", pitch="+0Hz")
        seg['audio_file'] = output_mp3 if os.path.exists(output_mp3) else None

def generate_tts_for_segments(segments, voice_id, temp_dir):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_generate_tts_for_segments(segments, voice_id, temp_dir))
    finally:
        loop.close()
        asyncio.set_event_loop(None)

def create_synchronized_audio(segments, output_audio_path, temp_dir, target_duration):
    """
    Stretch/compress TTS audio to fit segment durations and combine into one track.
    We use ffmpeg complex filters for precise positioning and speed adjustments.
    """
    ffmpeg_bin = get_pip_binary("ffmpeg")
    
    current_time = 0.0
    
    # Process each segment to exactly match its time window
    processed_files = []
    for idx, seg in enumerate(segments):
        if not seg.get('audio_file'):
            continue
            
        target_len = max(0.5, seg['end'] - seg['start'])
        orig_mp3 = seg['audio_file']
        
        # Get original duration
        try:
            cmd = [get_pip_binary("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", orig_mp3]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            orig_len = float(res.stdout.strip())
        except Exception:
            orig_len = target_len
            
        if orig_len <= 0.1:
            continue
            
        # Calculate speed modifier (atempo must be between 0.5 and 100.0)
        # We try to fit it into target_len, but limit the speedup to 1.6x so it doesn't sound like a chipmunk
        speed = 1.0
        if orig_len > target_len:
            speed = min(1.6, orig_len / target_len)
        elif orig_len < target_len:
            speed = max(0.85, orig_len / target_len)
        
        synced_mp3 = os.path.join(temp_dir, f"synced_{idx}.mp3")
        subprocess.run([
            ffmpeg_bin, "-y", "-i", orig_mp3,
            "-filter:a", f"atempo={speed}",
            "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k",
            synced_mp3
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(synced_mp3):
            # STRICT LIP-SYNC: Force the start time to be exactly what Whisper detected
            start_time = seg['start']
            processed_files.append({
                'path': synced_mp3,
                'start': start_time
            })
            
    # Now use adelay filter to combine them all into a single track
    if not processed_files:
        # Fallback empty audio
        subprocess.run([ffmpeg_bin, "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo", "-t", str(target_duration), output_audio_path])
        return

    # Create a complex filter string
    filter_complex = ""
    inputs = []
    
    for i, pfile in enumerate(processed_files):
        inputs.extend(["-i", pfile['path']])
        delay_ms = int(pfile['start'] * 1000)
        filter_complex += f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}];"
        
    concat_inputs = "".join([f"[a{i}]" for i in range(len(processed_files))])
    filter_complex += f"{concat_inputs}amix=inputs={len(processed_files)}:dropout_transition=0:normalize=0[out]"
    
    cmd = [ffmpeg_bin, "-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", "-t", str(target_duration), output_audio_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def dub_video_pipeline(video_path, output_video_path, target_lang, voice_id, temp_dir):
    """End-to-end video dubbing pipeline."""
    import time
    
    print("1. Extracting audio...")
    raw_audio_path = os.path.join(temp_dir, "raw_audio.mp3")
    extract_audio_from_video(video_path, raw_audio_path)
    
    # Get total video duration
    ffmpeg_bin = get_pip_binary("ffmpeg")
    try:
        cmd = [get_pip_binary("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", raw_audio_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        total_duration = float(res.stdout.strip())
    except:
        total_duration = 30.0

    print("2. Transcribing with Whisper...")
    segments = transcribe_audio(raw_audio_path)
    
    print("2.5 Grouping Segments for Natural Flow...")
    segments = group_segments(segments, max_gap=1.5)
    
    print("3. Translating...")
    segments = translate_segments(segments, target_lang)
    
    print("4. Generating TTS...")
    generate_tts_for_segments(segments, voice_id, temp_dir)
    
    print("5. Synchronizing & Mixing Audio...")
    dubbed_audio_path = os.path.join(temp_dir, "dubbed_audio.mp3")
    create_synchronized_audio(segments, dubbed_audio_path, temp_dir, total_duration)
    
    print("6. Merging Audio back into Video...")
    # Completely replace original audio with the new dubbed audio track
    cmd = [
        ffmpeg_bin, "-y",
        "-i", video_path,
        "-i", dubbed_audio_path,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_video_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return True
