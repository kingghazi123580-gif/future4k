# ============================================
# FEATURE 01: TEXT-TO-VIDEO (ENHANCED WITH VOICE & 4K)
# Filename: feature_01_text_to_video.py
# ============================================
# What this file does (English summary):
# - Takes a text prompt from the user (Urdu / Hindi / English)
# - SUPPORTS VOICE INPUT: User can speak their prompt via microphone
# - SUPPORTS 4K RESOLUTION: 4K (3840x2160) video generation
# - QUALITY OPTIONS: Standard, High, Premium quality presets
# - Calls the Agnes AI video model (agnes-video-v2.0) to generate video
# - If requested duration > MAX_CLIP_LENGTH (18s), splits the job into
#   multiple shorter clips, generates each one, then stitches them
#   together into a single file using ffmpeg
# - Optionally burns in a watermark for free-tier users
# - Saves a JSON metadata file alongside the video (prompt, resolution,
#   duration, timestamp, etc.)
# - Supports FILMAA_DRY_RUN=1 env var to test the whole pipeline
#   (validation, splitting, stitching, watermarking) WITHOUT calling
#   the real Agnes API or needing network access
#
# CHANGE LOG (frame-count fix):
# - Frame count for Agnes is no longer computed with a hardcoded formula.
#   It now goes through frame_policy.get_frames_for_duration(), which
#   snaps to whatever valid formula is configured for AGNES_AI_MODEL in
#   the Admin Panel -> Frame Rules tab. No code change needed if Agnes's
#   frame requirements change, or if this file is ever pointed at a
#   different model.
#
# Public function used by ui.py:
#   generate_video(prompt, resolution, duration, negative_prompt, apply_watermark, quality="standard")
#   -> {"success": bool, "video_path": str|None, "message": str, ...}
# ============================================

import sys
import io
import os
import time
import json
import subprocess
import requests
from datetime import datetime

# ============================================
# FORCE UTF-8 ENCODING — FIXES UNICODE ERROR
# ============================================
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from config import *
except ImportError:
    print("[ERROR] config.py not found!")
    raise SystemExit(1)

import frame_policy

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# ============================================
# VOICE INPUT SUPPORT
# ============================================

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

def speech_to_text(language="en-US", timeout=5, phrase_time_limit=30):
    """
    Convert speech to text using microphone.
    
    Parameters:
    - language (str): Language code (en-US, ur-PK, hi-IN)
    - timeout (int): Max seconds to wait for speech
    - phrase_time_limit (int): Max seconds for phrase
    
    Returns:
    - dict: {"success": bool, "text": str, "message": str}
    """
    if not SPEECH_RECOGNITION_AVAILABLE:
        return {
            "success": False, 
            "text": "", 
            "message": "Speech recognition not installed. Install with: pip install SpeechRecognition pyaudio"
        }
    
    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("🎤 Listening... Speak your prompt clearly.")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            
        print("🔄 Processing speech...")
        text = recognizer.recognize_google(audio, language=language)
        
        return {
            "success": True,
            "text": text,
            "message": f"Speech recognized: {text}"
        }
    except sr.WaitTimeoutError:
        return {"success": False, "text": "", "message": "No speech detected. Please try again."}
    except sr.UnknownValueError:
        return {"success": False, "text": "", "message": "Could not understand audio. Please speak clearly."}
    except sr.RequestError as e:
        return {"success": False, "text": "", "message": f"Speech recognition service error: {e}"}
    except Exception as e:
        return {"success": False, "text": "", "message": f"Error: {e}"}

# ============================================
# RESOLUTION & QUALITY CONFIGURATION
# ============================================

# Extended resolution options with 4K
RESOLUTION_CONFIGS = {
    "480p": {"width": 854, "height": 480, "label": "480p (SD)"},
    "720p": {"width": 1280, "height": 720, "label": "720p (HD)"},
    "1080p": {"width": 1920, "height": 1080, "label": "1080p (Full HD)"},
    "2k": {"width": 2560, "height": 1440, "label": "2K (QHD)"},
    "4k": {"width": 3840, "height": 2160, "label": "4K (Ultra HD)"},
}

# Quality presets for Agnes API
QUALITY_PRESETS = {
    "standard": {
        "label": "Standard",
        "description": "Balanced quality and speed",
        "steps": 30,
        "cfg_scale": 7.0,
        "scheduler": "EulerAncestralDiscrete"
    },
    "high": {
        "label": "High",
        "description": "Better quality, slower generation",
        "steps": 50,
        "cfg_scale": 8.0,
        "scheduler": "DPM++2M"
    },
    "premium": {
        "label": "Premium",
        "description": "Best quality, longest generation",
        "steps": 70,
        "cfg_scale": 9.0,
        "scheduler": "DPM++2M"
    }
}

def get_agnes_resolution(resolution_key):
    """Get resolution dimensions for Agnes API."""
    config = RESOLUTION_CONFIGS.get(resolution_key, RESOLUTION_CONFIGS["720p"])
    return {"width": config["width"], "height": config["height"]}

def get_resolution_label(resolution_key):
    """Get human-readable resolution label."""
    config = RESOLUTION_CONFIGS.get(resolution_key, RESOLUTION_CONFIGS["720p"])
    return config["label"]

def get_quality_preset(quality_key):
    """Get quality preset for Agnes API."""
    return QUALITY_PRESETS.get(quality_key, QUALITY_PRESETS["standard"])

def get_frames_for_duration(duration_seconds, fps=24):
    """
    Calculate number of frames for given duration, SNAPPED to whatever
    frame formula is configured for AGNES_AI_MODEL (Admin Panel -> Frame
    Rules). This replaces the old hardcoded `int(duration_seconds * fps)`
    which is what was producing frame counts Agnes rejected.
    """
    return frame_policy.get_frames_for_duration(AGNES_AI_MODEL, duration_seconds, fps=fps)

# ============================================
# INTERNAL HELPERS
# ============================================

def _prepare_prompt(prompt):
    """Currently a passthrough."""
    return prompt.strip()

def _agnes_headers():
    return {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json",
    }

def _create_agnes_task(prompt, width, height, num_frames, frame_rate, 
                       negative_prompt=None, quality="standard"):
    """Create a video generation task on Agnes with quality settings."""
    
    # Get quality preset
    quality_config = get_quality_preset(quality)
    
    payload = {
        "model": AGNES_AI_MODEL,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
        "steps": quality_config["steps"],
        "cfg_scale": quality_config["cfg_scale"],
        "scheduler": quality_config["scheduler"]
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    url = f"{AGNES_AI_BASE_URL}/videos"

    last_error = None
    max_attempts = max(API.get("retry_count", 3), AGNES_429_MAX_RETRIES)
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, headers=_agnes_headers(), json=payload, timeout=30)
            if resp.status_code == 401:
                raise RuntimeError("Agnes API rejected the key (401). Check AGNES_API_KEY.")
            if resp.status_code == 400:
                raise RuntimeError(f"Agnes rejected the request (400): {resp.text}")
            if resp.status_code == 429:
                if "Retry-After" in resp.headers:
                    wait_s = int(resp.headers["Retry-After"])
                else:
                    wait_s = min(AGNES_429_BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)),
                                 AGNES_429_MAX_BACKOFF_SECONDS)
                if attempt < max_attempts:
                    print(f"  [retry {attempt}/{max_attempts}] 429 rate limited — "
                          f"waiting {wait_s}s before retrying")
                    time.sleep(wait_s)
                    continue
                raise RuntimeError(
                    "Agnes rejected the request (429 - rate limited) after repeated "
                    "backoff. Check platform.agnes-ai.com dashboard for your actual "
                    "usage/quota."
                )
            resp.raise_for_status()
            data = resp.json()
            return data["video_id"]
        except (requests.RequestException, KeyError, RuntimeError) as e:
            last_error = e
            if attempt < max_attempts:
                print(f"  [retry {attempt}/{max_attempts}] task creation failed: {e}")
                time.sleep(API.get("retry_delay", 5))
            else:
                raise RuntimeError(f"Agnes task creation failed after {max_attempts} attempts: {last_error}")

def _poll_agnes_result(video_id):
    """Poll until the task completes, fails, or we exceed max attempts."""
    url = f"{AGNES_AI_ROOT_URL}/agnesapi"
    params = {"video_id": video_id}

    for attempt in range(1, AGNES_MAX_POLL_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=_agnes_headers(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")

            print(f"  [poll {attempt}/{AGNES_MAX_POLL_ATTEMPTS}] status: {status} "
                  f"({data.get('progress', 0)}%)")

            if status == "completed":
                return data
            if status == "failed":
                raise RuntimeError(f"Agnes generation failed: {data.get('error')}")

            time.sleep(AGNES_POLL_INTERVAL_SECONDS)

        except requests.RequestException as e:
            print(f"  [poll {attempt}] Request error: {e}")
            time.sleep(AGNES_POLL_INTERVAL_SECONDS)
            continue

    raise TimeoutError(f"Agnes generation did not complete within "
                        f"{AGNES_MAX_POLL_ATTEMPTS * AGNES_POLL_INTERVAL_SECONDS}s")

def _extract_video_url(result: dict) -> str:
    """Extract video URL from Agnes response."""
    for field in ("video_url", "remixed_from_video_id", "url", "output_url"):
        value = result.get(field)
        if value and isinstance(value, str) and value.startswith("http"):
            return value
    raise KeyError(
        f"Could not find a video URL in Agnes's completed response. "
        f"Looked for video_url / remixed_from_video_id / url / output_url. "
        f"Actual response keys: {list(result.keys())}"
    )

def _download_clip(video_url, save_path, max_retries=4):
    """Download the rendered clip from Agnes's storage/CDN host."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(video_url, stream=True, timeout=(15, 180))
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return save_path
        except requests.RequestException as e:
            last_error = e
            if os.path.exists(save_path):
                os.remove(save_path)
            if attempt < max_retries:
                wait_s = min(5 * (2 ** (attempt - 1)), 30)
                print(f"  [download retry {attempt}/{max_retries}] {e} — "
                      f"waiting {wait_s}s")
                time.sleep(wait_s)
            else:
                raise RuntimeError(
                    f"Downloading the rendered clip failed after {max_retries} "
                    f"attempts: {last_error}"
                )

def _generate_one_clip(prompt, resolution, target_seconds, negative_prompt, 
                       clip_index, quality="standard"):
    """Create + poll + download a single Agnes clip with quality settings."""
    dims = get_agnes_resolution(resolution)
    num_frames = get_frames_for_duration(target_seconds)

    clip_name = f"clip_{clip_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    clip_path = os.path.join(PATHS["temp"], clip_name)

    if DRY_RUN:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={target_seconds}:size={dims['width']}x{dims['height']}:rate=24",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            clip_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"[DRY_RUN] fake clip generation failed: {result.stderr[-500:]}")
        print(f"  [DRY_RUN] fake clip written: {clip_name}")
        return clip_path

    video_id = _create_agnes_task(
        prompt=prompt,
        width=dims["width"],
        height=dims["height"],
        num_frames=num_frames,
        frame_rate=24,
        negative_prompt=negative_prompt,
        quality=quality
    )
    result = _poll_agnes_result(video_id)
    video_url = _extract_video_url(result)
    _download_clip(video_url, clip_path)

    print(f"  Clip {clip_index} done — actual: {result.get('seconds')}s @ {result.get('size')}")
    return clip_path

def _stitch_clips(clip_paths, output_path):
    """Stitch multiple clips into one file using ffmpeg's concat demuxer."""
    if len(clip_paths) == 1:
        os.replace(clip_paths[0], output_path)
        return output_path

    concat_list_path = output_path.replace(".mp4", "_concat.txt")
    with open(concat_list_path, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path, "-c", "copy", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg stitching failed: {result.stderr[-500:]}")

    os.remove(concat_list_path)
    for p in clip_paths:
        if os.path.exists(p):
            os.remove(p)

    return output_path

def _find_system_font():
    """Locate a usable .ttf/.otf font on disk for ffmpeg's drawtext filter."""
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def _apply_watermark(video_path):
    """Burn in a text watermark using ffmpeg's drawtext filter."""
    tmp_path = video_path.replace(".mp4", "_wm.mp4")
    pos_map = {
        "bottom-right": "x=w-tw-20:y=h-th-20",
        "bottom-left": "x=20:y=h-th-20",
        "top-right": "x=w-tw-20:y=20",
        "top-left": "x=20:y=20",
    }
    position = pos_map.get(WATERMARK["position"], pos_map["bottom-right"])

    font_path = _find_system_font()
    fontfile_part = ""
    if font_path:
        escaped_font = font_path.replace("\\", "/").replace(":", "\\:")
        fontfile_part = f"fontfile='{escaped_font}':"
    else:
        print("  [WARN] No system font found in known locations — relying on "
              "ffmpeg's built-in fontconfig, which may not be available on "
              "all installs.")

    drawtext = (
        f"drawtext={fontfile_part}text='{WATERMARK['text']}':"
        f"fontcolor={WATERMARK['color']}@{WATERMARK['opacity']}:"
        f"fontsize={WATERMARK['font_size']}:{position}"
    )
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", drawtext,
           "-codec:a", "copy", tmp_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg watermarking failed: {result.stderr[-500:]}")

    os.replace(tmp_path, video_path)
    return video_path

# ============================================
# MAIN FUNCTION (ENHANCED)
# ============================================

def generate_video(prompt, resolution="720p", duration=10, negative_prompt=None, 
                   apply_watermark=True, quality="standard", use_voice=False):
    """
    Generate video from text prompt using Agnes AI.

    Parameters:
    - prompt (str): Text description in Urdu/Hindi/English
    - resolution (str): 480p, 720p, 1080p, 2k, 4k
    - duration (int): Target seconds
    - negative_prompt (str, optional): things to exclude from generation
    - apply_watermark (bool): whether to burn in the Filmaa watermark
    - quality (str): standard, high, premium
    - use_voice (bool): If True, prompt is from voice input

    Returns:
    - dict: {"success", "video_path", "message", "clip_count", "info"}
    """
    print("\n" + "=" * 50)
    print("🎬 FEATURE 01: Text-to-Video" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 50)

    # ---------- Validate input ----------
    if not prompt or len(prompt.strip()) < 3:
        return {"success": False, "video_path": None,
                "message": "Prompt is too short. Please write at least 3 words."}

    max_len = SHARED.get("max_prompt_length")
    if max_len and len(prompt) > max_len:
        return {"success": False, "video_path": None,
                "message": f"Prompt too long (max {max_len} characters)."}

    if duration < MIN_CLIP_LENGTH:
        return {"success": False, "video_path": None,
                "message": f"Duration must be at least {MIN_CLIP_LENGTH} seconds."}

    if not DRY_RUN and not AGNES_API_KEY:
        return {"success": False, "video_path": None,
                "message": "AGNES_API_KEY not set. Set it in your environment before generating video."}

    prompt = _prepare_prompt(prompt)

    print(f"📝 Prompt: {prompt}")
    print(f"📐 Resolution: {resolution} ({get_resolution_label(resolution)})")
    print(f"⏱️ Target duration: {duration}s")
    print(f"🎯 Quality: {quality.upper()} - {get_quality_preset(quality)['description']}")
    if use_voice:
        print("🎤 Input source: Voice")

    # ---------- Split into clips ----------
    clips_needed = -(-duration // MAX_CLIP_LENGTH)
    per_clip_seconds = -(-duration // clips_needed)
    print(f"\n📊 Clips needed: {clips_needed} (~{per_clip_seconds}s each, "
          f"{MAX_CLIP_LENGTH}s max per Agnes call)")

    clip_paths = []
    try:
        for i in range(clips_needed):
            print(f"\n🎬 Generating clip {i + 1}/{clips_needed}...")
            clip_path = _generate_one_clip(
                prompt, resolution, per_clip_seconds, negative_prompt, 
                i + 1, quality
            )
            clip_paths.append(clip_path)

            if not DRY_RUN and i + 1 < clips_needed:
                time.sleep(AGNES_CLIP_SPACING_SECONDS)
    except Exception as e:
        for p in clip_paths:
            if os.path.exists(p):
                os.remove(p)
        return {"success": False, "video_path": None,
                "message": f"Generation failed: {e}"}

    # ---------- Stitch ----------
    video_name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    final_video_path = os.path.join(PATHS["videos"], video_name)

    try:
        print(f"\n🔗 Stitching {clips_needed} clip(s)...")
        _stitch_clips(clip_paths, final_video_path)
    except Exception as e:
        return {"success": False, "video_path": None,
                "message": f"Stitching failed: {e}"}

    # ---------- Watermark ----------
    watermark_applied = False
    watermark_error = None
    if apply_watermark and WATERMARK.get("free_tier", True):
        print(f"💧 Adding watermark: {WATERMARK['text']}")
        if not DRY_RUN:
            try:
                _apply_watermark(final_video_path)
                watermark_applied = True
            except Exception as e:
                watermark_error = str(e)
                print(f"[WARN] Watermark failed, delivering video without it: {e}")
        else:
            watermark_applied = True

    # ---------- Save metadata ----------
    video_info = {
        "video_id": video_name,
        "prompt": prompt,
        "resolution": resolution,
        "resolution_label": get_resolution_label(resolution),
        "requested_duration": duration,
        "quality": quality,
        "quality_label": QUALITY_PRESETS[quality]["label"],
        "clips": clips_needed,
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "voice_input": use_voice,
        "created_at": datetime.now().isoformat(),
        "path": final_video_path,
        "dry_run": DRY_RUN,
    }
    info_path = final_video_path.replace(".mp4", ".json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(video_info, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Video generated successfully!")
    print(f"📹 Path: {final_video_path}")
    print(f"📐 Resolution: {get_resolution_label(resolution)}")
    print(f"🎯 Quality: {QUALITY_PRESETS[quality]['label']}")

    return {
        "success": True,
        "video_path": final_video_path,
        "message": "Video generated successfully!",
        "clip_count": clips_needed,
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "info": video_info,
    }

# ============================================
# VOICE PROMPT FUNCTION
# ============================================

def generate_video_from_voice(resolution="720p", duration=10, negative_prompt=None,
                              apply_watermark=True, quality="standard",
                              language="en-US"):
    """
    Generate video from voice input.
    
    Parameters:
    - resolution (str): 480p, 720p, 1080p, 2k, 4k
    - duration (int): Target seconds
    - negative_prompt (str, optional): things to exclude
    - apply_watermark (bool): whether to burn watermark
    - quality (str): standard, high, premium
    - language (str): en-US, ur-PK, hi-IN
    
    Returns:
    - dict: {"success", "video_path", "message", "prompt", ...}
    """
    # Get speech input
    speech_result = speech_to_text(language=language)
    
    if not speech_result["success"]:
        return {
            "success": False,
            "video_path": None,
            "message": speech_result["message"],
            "prompt": None
        }
    
    prompt = speech_result["text"]
    
    # Generate video from text
    return generate_video(
        prompt=prompt,
        resolution=resolution,
        duration=duration,
        negative_prompt=negative_prompt,
        apply_watermark=apply_watermark,
        quality=quality,
        use_voice=True
    )

# ============================================
# TEST FUNCTION
# ============================================

def test():
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_01_text_to_video.py")
    print(f"Mode: {'DRY_RUN (no real API calls)' if DRY_RUN else 'LIVE (calls real Agnes API)'}")
    print("=" * 60)

    print("\n📝 Test 1: Basic Urdu prompt (720p, Standard quality)")
    result = generate_video(
        prompt="ایک خوبصورت لڑکی باغ میں پھول چُن رہی ہے، سورج غروب ہو رہا ہے",
        resolution="720p",
        duration=10,
        quality="standard"
    )
    print(f"  Result: {result['message']}")

    print("\n📝 Test 2: 4K resolution with High quality")
    result = generate_video(
        prompt="A futuristic city at night with neon lights",
        resolution="4k",
        duration=10,
        quality="high"
    )
    print(f"  Result: {result['message']}")

    print("\n📝 Test 3: Premium quality")
    result = generate_video(
        prompt="A cinematic scene of mountains at sunrise",
        resolution="1080p",
        duration=10,
        quality="premium"
    )
    print(f"  Result: {result['message']}")

    print("\n📝 Test 4: Voice input test (if microphone available)")
    if SPEECH_RECOGNITION_AVAILABLE:
        result = generate_video_from_voice(
            resolution="720p",
            duration=10,
            quality="standard",
            language="en-US"
        )
        print(f"  Result: {result['message']}")
    else:
        print("  Skipped: Speech recognition not installed")

    print("\n📝 Test 5: Short prompt (should fail validation)")
    result = generate_video(prompt="Hi", resolution="480p", duration=5)
    print(f"  Result: {result['message']}")
    assert result["success"] is False, "Short prompt should have been rejected"

    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)

if __name__ == "__main__":
    test()

# ============================================
# END OF feature_01_text_to_video.py (ENHANCED)
# ============================================