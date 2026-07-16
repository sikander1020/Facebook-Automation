import os
import random
import subprocess
import tempfile


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

def crop_to_aspect_ratio(clip, target_w, target_h):
    """
    Crops a video clip from its center to match the target aspect ratio,
    then resizes it to the target dimensions.
    (Kept for any remaining moviepy usage, but concatenate_clips no longer uses this.)
    """
    from moviepy.editor import VideoFileClip
    w, h = clip.size
    target_aspect = target_w / target_h
    current_aspect = w / h
    
    if current_aspect > target_aspect:
        new_w = int(h * target_aspect)
        x1 = (w - new_w) // 2
        x2 = x1 + new_w
        clip_cropped = clip.crop(x1=x1, y1=0, x2=x2, y2=h)
    else:
        new_h = int(w / target_aspect)
        y1 = (h - new_h) // 2
        y2 = y1 + new_h
        clip_cropped = clip.crop(x1=0, y1=y1, x2=w, y2=y2)
        
    return clip_cropped.resize(newsize=(target_w, target_h))

def concatenate_clips(video_paths, aspect_ratio="vertical", output_path=None):
    """
    Concatenates multiple video files using pure FFmpeg (no moviepy).
    Each clip is normalized to the target resolution before joining.
    Returns the total duration in seconds.
    """
    if not video_paths:
        raise ValueError("No video paths provided to concatenate.")

    existing = [p for p in video_paths if os.path.exists(p) and os.path.getsize(p) > 0]
    if not existing:
        raise ValueError("None of the provided video paths exist or could be loaded.")

    target_w, target_h = (1080, 1920) if aspect_ratio == "vertical" else (1920, 1080)

    # ── Step 1: Normalize every clip to target resolution ────────────
    norm_dir = tempfile.mkdtemp(prefix="concat_norm_")
    normalized = []

    ffmpeg_bin = get_pip_binary("ffmpeg")
    ffprobe_bin = get_pip_binary("ffprobe")

    for i, path in enumerate(existing):
        norm_path = os.path.join(norm_dir, f"norm_{i}.mp4")
        # scale+pad to target size, keep audio, re-encode to uniform codec
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:-1:-1:color=black,"
            f"fps=30"
        )
        cmd = [
            ffmpeg_bin, "-y", "-i", path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            norm_path
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode == 0 and os.path.exists(norm_path) and os.path.getsize(norm_path) > 0:
            normalized.append(norm_path)
        else:
            print(f"[concat] Warning: failed to normalize {path}, skipping.")

    if not normalized:
        raise RuntimeError("All clips failed to normalize — cannot concatenate.")

    # ── Step 2: Write concat list file ───────────────────────────────
    concat_list = os.path.join(norm_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for p in normalized:
            f.write(f"file '{p}'\n")

    # ── Step 3: Get total duration via ffprobe ────────────────────────
    total_duration = 0.0
    for p in normalized:
        probe = subprocess.run(
            [ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", p],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            total_duration += float(probe.stdout.strip())
        except Exception:
            pass

    # ── Step 4: Concatenate ───────────────────────────────────────────
    if output_path:
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy",
            output_path
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            err = r.stderr.decode("utf-8", errors="ignore")[-500:]
            raise RuntimeError(f"FFmpeg concat failed: {err}")

    # ── Cleanup temp normalized clips ─────────────────────────────────
    for p in normalized:
        try:
            os.remove(p)
        except Exception:
            pass
    try:
        os.remove(concat_list)
        os.rmdir(norm_dir)
    except Exception:
        pass

    return total_duration


def pitch_shift_audio(input_audio_path, output_audio_path, semitones=0.8):
    """
    Pitch shifts an audio file using FFmpeg's asetrate and atempo filters.
    semitones: shift amount (positive = higher, negative = lower).
    """
    multiplier = 2.0 ** (semitones / 12.0)
    sample_rate = 44100
    new_rate = int(sample_rate * multiplier)
    tempo = 1.0 / multiplier
    
    ffmpeg_bin = get_pip_binary("ffmpeg")
    cmd = [
        ffmpeg_bin, "-y", "-i", input_audio_path,
        "-filter_complex", f"asetrate={new_rate},atempo={tempo}",
        output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def apply_copyright_filters(input_path, output_path, options):
    """
    Applies visual and audio transformations to bypass copyright filters.
    Uses pure FFmpeg subprocess for reliability — no moviepy silent failures.

    Filters applied:
    - Aspect Ratio (vertical 9:16, horizontal 16:9, or original)
    - Horizontal mirror (hflip)
    - 5% center zoom-in (crop + scale)
    - Speed adjustment (setpts + atempo)
    - Audio pitch shift (asetrate + atempo correction)
    - [NEW] Metadata/Fingerprint Deletion (map_metadata -1, map_chapters -1)
    - [NEW] Codec Binary Fingerprint Randomization (random GOP, B-frames, CRF, noise grain)
    - [NEW] Color LUT — invisible random color channel + hue shift (changes perceptual hash)
    """
    aspect       = options.get("aspect_ratio", "original")
    do_mirror    = options.get("mirror", True)
    do_zoom      = options.get("zoom", True)
    speed_factor = float(options.get("speed", 1.04))
    pitch_semi   = float(options.get("pitch_shift", 0.8))

    border_color = options.get("border_color", "none")
    try:
        border_width = int(options.get("border_width", 0))
    except ValueError:
        border_width = 0
    text_overlay = options.get("text_overlay", "")
    anti_watermark   = options.get("anti_watermark", True)
    color_shift      = options.get("color_shift", False)
    strip_metadata   = options.get("strip_metadata", True)   # NEW: delete fingerprint metadata
    randomize_codec  = options.get("randomize_codec", True)  # NEW: randomize codec binary pattern
    add_noise        = options.get("add_noise", True)         # NEW: add subtle film grain
    color_lut        = options.get("color_lut", True)          # NEW: invisible color channel shift
    if isinstance(color_shift, str):
        color_shift = color_shift.lower() == "true"
    if isinstance(strip_metadata, str):
        strip_metadata = strip_metadata.lower() == "true"
    if isinstance(randomize_codec, str):
        randomize_codec = randomize_codec.lower() == "true"
    if isinstance(add_noise, str):
        add_noise = add_noise.lower() == "true"
    if isinstance(color_lut, str):
        color_lut = color_lut.lower() == "true"

    # ── Check if the source has an audio stream ──────────────────────
    ffmpeg_bin = get_pip_binary("ffmpeg")
    ffprobe_bin = get_pip_binary("ffprobe")
    probe = subprocess.run(
        [ffprobe_bin, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name",
         "-of", "default=noprint_wrappers=1:nokey=1", input_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    has_audio = bool(probe.stdout.strip())

    # ── Build video filter chain ──────────────────────────────────────
    vf = []

    if aspect == "vertical":
        # Fill 9:16 screen (Crop sides of horizontal video). This naturally removes side watermarks.
        vf.append("scale=1080:1920:force_original_aspect_ratio=increase,"
                  "crop=1080:1920")
    elif aspect == "horizontal":
        vf.append("scale=1920:1080:force_original_aspect_ratio=decrease,"
                  "pad=1920:1080:-1:-1:color=black")

    if border_color != "none" and border_width > 0:
        # Pad with border color
        vf.append(f"pad=iw+2*{border_width}:ih+2*{border_width}:{border_width}:{border_width}:color={border_color}")

    if do_mirror:
        vf.append("hflip")

    if do_zoom:
        # Scale up 5% (reverted) to avoid blurring the video.
        vf.append("scale=iw*1.05:ih*1.05,crop='trunc(iw/1.05/2)*2':'trunc(ih/1.05/2)*2'")

    if color_shift:
        # Slightly shift color metrics
        vf.append("eq=contrast=1.03:brightness=0.02:saturation=1.08")

    # ── [NEW] Color LUT — invisible perceptual hash breaker ──────────
    # Randomly shifts individual R/G/B channels by ±2% and hue by 1-4°.
    # Human eyes cannot detect changes < 5% per channel or < 5° hue shift.
    # Facebook PDQ hash and YouTube Content-ID visual hash will differ.
    if color_lut:
        rr = round(random.uniform(0.98, 1.02), 4)
        gg = round(random.uniform(0.97, 1.02), 4)
        bb = round(random.uniform(0.98, 1.03), 4)
        hue_deg = round(random.uniform(1.0, 4.0), 2)
        # colorchannelmixer: rr:rg:rb:ra:gr:gg:gb:ga:br:bg:bb:ba
        vf.append(f"colorchannelmixer={rr}:0:0:0:0:{gg}:0:0:0:0:{bb}:0")
        vf.append(f"hue=h={hue_deg}")

    if anti_watermark:
        # Interpolate the 4 corners to remove standard TV logos and social media watermarks
        # Use larger boxes (320x140 max) for 1080p videos since logos can be big.
        vf.append("delogo=x=10:y=10:w='min(320, w/2.8)':h='min(140, h/3.5)'")
        vf.append("delogo=x='max(10, w-w/2.8-10)':y=10:w='min(320, w/2.8)':h='min(140, h/3.5)'")
        vf.append("delogo=x=10:y='max(10, h-h/3.5-10)':w='min(320, w/2.8)':h='min(140, h/3.5)'")
        vf.append("delogo=x='max(10, w-w/2.8-10)':y='max(10, h-h/3.5-10)':w='min(320, w/2.8)':h='min(140, h/3.5)'")

    if text_overlay:
        # Check if drawtext filter is available in the host FFmpeg build
        drawtext_available = False
        try:
            filters_probe = subprocess.run([ffmpeg_bin, "-filters"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "drawtext" in filters_probe.stdout:
                drawtext_available = True
        except Exception:
            pass

        if drawtext_available:
            import re
            # sanitize text to prevent filter injection issues
            clean_text = re.sub(r"[^a-zA-Z0-9\s.,!?-]", "", text_overlay)
            clean_text = clean_text.replace("'", "'\\''").replace(":", "\\:")
            
            # Resolve standard font paths for macOS/Linux compatibility
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ]
            fontfile_param = ""
            for p in font_paths:
                if os.path.exists(p):
                    fontfile_param = f":fontfile='{p}'"
                    break
            vf.append(f"drawtext=text='{clean_text}'{fontfile_param}:x=(w-text_w)/2:y=100:fontsize=36:fontcolor=white:box=1:boxcolor=black@0.4:boxborderw=6")
        else:
            print("[video_effects] Warning: 'drawtext' filter is not supported by this FFmpeg build. Skipping text overlay.")

    if speed_factor != 1.0:
        vf.append(f"setpts=PTS/{speed_factor:.4f}")

    # ── [NEW] Film Grain Noise — changes pixel-level fingerprint ─────────
    # Adds 1-3 strength invisible noise so binary hash never matches original
    if add_noise:
        noise_strength = random.randint(1, 3)
        vf.append(f"noise=alls={noise_strength}:allf=t")

    # Always force even dimensions at the end for libx264 compatibility
    vf.append("scale='trunc(iw/2)*2':'trunc(ih/2)*2'")


    # ── Build audio filter chain ──────────────────────────────────────
    af = []

    if has_audio:
        if speed_factor != 1.0:
            af.append(f"atempo={speed_factor:.4f}")

        if pitch_semi != 0.0:
            # asetrate shifts pitch; atempo corrects back to original speed
            multiplier = 2.0 ** (pitch_semi / 12.0)
            new_rate   = int(44100 * multiplier)
            tempo_corr = 1.0 / multiplier
            af.append(f"asetrate={new_rate},atempo={tempo_corr:.6f}")

    # ── [NEW] Randomize Codec Parameters (changes binary fingerprint) ────
    # Each clip gets a unique GOP size, B-frame count, and CRF so the
    # encoded bitstream never matches the original or a previous export.
    if randomize_codec:
        gop_size   = random.randint(24, 60)   # keyframe every 24-60 frames
        b_frames   = random.randint(1, 3)      # 1-3 B-frames
        crf_value  = random.randint(21, 26)    # CRF 21-26 (still high quality)
        codec_flags = [
            "-c:v", "libx264", "-preset", "fast",
            "-g",   str(gop_size),
            "-bf",  str(b_frames),
            "-crf", str(crf_value),
            "-movflags", "+faststart"
        ]
    else:
        codec_flags = ["-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart"]

    # ── [NEW] Metadata / Fingerprint Deletion ────────────────────────────
    # Strips ALL MP4 container metadata (encoder, creation_time, title, ISRC,
    # copyright tags, UUID atoms) that platforms read for content-ID matching.
    metadata_flags = []
    if strip_metadata:
        metadata_flags = [
            "-map_metadata", "-1",    # delete all global metadata tags
            "-map_chapters", "-1",    # delete chapter markers
            "-fflags", "+bitexact",   # suppress encoder/muxer identification strings
        ]

    # ── Assemble FFmpeg command ───────────────────────────────────────
    cmd = [ffmpeg_bin, "-y", "-i", input_path]

    if vf:
        cmd += ["-vf", ",".join(vf)]

    cmd += codec_flags
    cmd += metadata_flags

    if has_audio:
        if af:
            cmd += ["-af", ",".join(af)]
        cmd += ["-c:a", "aac"]
    else:
        cmd += ["-an"]   # no audio stream in source — don't try to encode one

    cmd.append(output_path)

    # ── Run ───────────────────────────────────────────────────────────
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        err = result.stderr.decode("utf-8", errors="ignore")[-600:]
        raise RuntimeError(f"FFmpeg filter failed for {os.path.basename(input_path)}: {err}")


def slice_video(input_path, output_dir, mode="auto", intervals=8, custom_ranges=None):
    """
    Slices a video into multiple segments.
    mode: "auto" (split every N seconds) or "timestamps" (split by custom list of ranges).
    intervals: number of seconds per slice in auto mode.
    custom_ranges: list of tuples/lists e.g. [[10, 20], [35, 45]] (in seconds).
    Returns a list of created file paths.
    """
    duration = 0.0
    ffmpeg_bin = get_pip_binary("ffmpeg")
    ffprobe_bin = get_pip_binary("ffprobe")
    try:
        cmd = [
            ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", input_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            duration = float(res.stdout.strip())
    except Exception as e:
        print(f"[slice_video] ffprobe failed to get duration: {e}")

    if duration <= 0.0:
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(input_path)
            duration = clip.duration
            clip.close()
        except Exception as e:
            print(f"[slice_video] moviepy fallback also failed: {e}")
            raise RuntimeError("Could not determine video duration.")
    
    slices = []
    if mode == "auto":
        start = 0
        idx = 1
        while start < duration:
            end = min(start + intervals, duration)
            # Avoid tiny trailing clips less than 1 second
            if duration - end < 1.0:
                end = duration
            slices.append((start, end, f"clip_{idx}.mp4"))
            idx += 1
            if end == duration:
                break
            start = end
    elif mode == "timestamps" and custom_ranges:
        for idx, r in enumerate(custom_ranges, 1):
            start = r[0]
            end = min(r[1], duration)
            if start < duration:
                slices.append((start, end, f"clip_{idx}.mp4"))
                
    output_files = []
    for start, end, filename in slices:
        out_path = os.path.join(output_dir, filename)
        # Use FFmpeg directly for fast lossless seeking and cutting
        cmd = [
            ffmpeg_bin, "-y", "-ss", str(start), "-to", str(end),
            "-i", input_path, "-c", "copy", out_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            output_files.append(out_path)
            
    return output_files
