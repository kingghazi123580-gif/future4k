# ============================================
# FEATURE 03: 30-SECOND CLIP (Reels/Shorts/TikTok) - ENHANCED
# Filename: feature_03_clip_generation.py
# ============================================
# What this file does (English summary):
# - A focused, social-media-ready wrapper around the same Agnes
#   text-to-video pipeline as feature_01 — but hard-capped at 30
#   seconds and defaulting to vertical (9:16) framing, since that's
#   what Reels/Shorts/TikTok need.
# - SUPPORTS VOICE INPUT: User can speak their prompt via microphone
# - SUPPORTS 4K RESOLUTION: 4K (3840x2160) video generation for clips
# - Takes a text prompt (Urdu/Hindi/English) + a platform choice
#   (reels / shorts / tiktok / custom) and picks sensible defaults
#   (aspect ratio, resolution) for that platform automatically.
# - Splits into multiple Agnes clips and stitches with ffmpeg if the
#   requested duration exceeds MAX_CLIP_LENGTH (18s), same as feature_01.
# - Applies the same watermark logic (with the font auto-detect fix
#   from feature_01, so it doesn't silently fail).
# - Supports FILMAA_DRY_RUN=1 to test the whole pipeline without
#   calling the real Agnes API or needing network access.
#
# CHANGE LOG (frame-count fix):
# - get_frames_for_duration() previously came from config.py's global
#   version. It is now overridden locally in this file to go through
#   frame_policy.get_frames_for_duration(), which snaps to whatever
#   formula is configured for AGNES_AI_MODEL in the Admin Panel ->
#   Frame Rules tab.
#
# Public function used by ui.py:
#   generate_short_clip(prompt, platform, duration, negative_prompt,
#                        apply_watermark, resolution, use_voice, voice_language)
#   -> {"success", "video_path", "message", "clip_count",
#       "watermark_applied", "watermark_error", "info"}
# ============================================

import os
import time
import json
import subprocess
import requests
from datetime import datetime

try:
    from config import *
except ImportError:
    print("[ERROR] config.py not found!")
    raise SystemExit(1)

import frame_policy

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"


def get_frames_for_duration(duration_seconds, fps=24):
    """
    OVERRIDE of config.py's global get_frames_for_duration().
    Snaps frame count to whatever formula is configured for AGNES_AI_MODEL
    (Admin Panel -> Frame Rules). This is the frame-count fix.
    """
    return frame_policy.get_frames_for_duration(AGNES_AI_MODEL, duration_seconds, fps=fps)


# Hard cap for this feature — even if someone passes a bigger number,
# a "30-Second Clip" tool should never produce more than 30s.
MAX_SHORT_CLIP_SECONDS = 30

# Platform presets: (aspect_ratio label just for display, width, height)
PLATFORM_PRESETS = {
    "reels":    {"label": "Instagram Reels", "width": 1080, "height": 1920},
    "shorts":   {"label": "YouTube Shorts",   "width": 1080, "height": 1920},
    "tiktok":   {"label": "TikTok",           "width": 1080, "height": 1920},
    "square":   {"label": "Square (1:1)",     "width": 1080, "height": 1080},
    "landscape": {"label": "Landscape (16:9)", "width": 1920, "height": 1080},
}

# Resolution configurations with 4K
RESOLUTION_CONFIGS = {
    "480p": {"label": "480p (SD)", "scale": 0.5},
    "720p": {"label": "720p (HD)", "scale": 0.67},
    "1080p": {"label": "1080p (Full HD)", "scale": 1.0},
    "2k": {"label": "2K (QHD)", "scale": 1.5},
    "4k": {"label": "4K (Ultra HD)", "scale": 2.0},
}

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
            print("🎤 Listening... Speak your clip prompt clearly.")
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
# INTERNAL HELPERS
# ============================================

def _agnes_headers():
    return {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json",
    }


def _create_agnes_task(prompt, width, height, num_frames, frame_rate, negative_prompt=None):
    payload = {
        "model": AGNES_AI_MODEL,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
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
                    print(f"  [retry {attempt}/{max_attempts}] 429 rate limited — waiting {wait_s}s")
                    time.sleep(wait_s)
                    continue
                raise RuntimeError("Agnes rejected the request (429 - rate limited) after repeated backoff.")
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
    url = f"{AGNES_AI_ROOT_URL}/agnesapi"
    params = {"video_id": video_id}
    for attempt in range(1, AGNES_MAX_POLL_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=_agnes_headers(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            print(f"  [poll {attempt}/{AGNES_MAX_POLL_ATTEMPTS}] status: {status} ({data.get('progress', 0)}%)")
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
                print(f"  [download retry {attempt}/{max_retries}] {e} — waiting {wait_s}s")
                time.sleep(wait_s)
            else:
                raise RuntimeError(f"Downloading the rendered clip failed after {max_retries} attempts: {last_error}")


def _get_resolution_dims(platform_width, platform_height, resolution):
    """Get scaled dimensions based on resolution setting."""
    scale = RESOLUTION_CONFIGS.get(resolution, RESOLUTION_CONFIGS["720p"])["scale"]
    width = int(platform_width * scale)
    height = int(platform_height * scale)
    # Ensure dimensions are divisible by 16 (Agnes requirement)
    width = ((width + 15) // 16) * 16
    height = ((height + 15) // 16) * 16
    return width, height


def _generate_one_clip(prompt, width, height, target_seconds, negative_prompt, clip_index):
    num_frames = get_frames_for_duration(target_seconds)
    clip_name = f"short_{clip_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    clip_path = os.path.join(PATHS["temp"], clip_name)

    if DRY_RUN:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={target_seconds}:size={width}x{height}:rate=24",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            clip_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"[DRY_RUN] fake clip generation failed: {result.stderr[-500:]}")
        print(f"  [DRY_RUN] fake clip written: {clip_name}")
        return clip_path

    video_id = _create_agnes_task(prompt, width, height, num_frames, 24, negative_prompt)
    result = _poll_agnes_result(video_id)
    video_url = _extract_video_url(result)
    _download_clip(video_url, clip_path)
    print(f"  Clip {clip_index} done — actual: {result.get('seconds')}s @ {result.get('size')}")
    return clip_path


def _stitch_clips(clip_paths, output_path):
    if len(clip_paths) == 1:
        os.replace(clip_paths[0], output_path)
        return output_path

    concat_list_path = output_path.replace(".mp4", "_concat.txt")
    with open(concat_list_path, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg stitching failed: {result.stderr[-500:]}")

    os.remove(concat_list_path)
    for p in clip_paths:
        if os.path.exists(p):
            os.remove(p)
    return output_path


def _find_system_font():
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
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
    tmp_path = video_path.replace(".mp4", "_wm.mp4")
    pos_map = {
        "bottom-right": "x=w-tw-20:y=h-th-20", "bottom-left": "x=20:y=h-th-20",
        "top-right": "x=w-tw-20:y=20", "top-left": "x=20:y=20",
    }
    position = pos_map.get(WATERMARK["position"], pos_map["bottom-right"])

    font_path = _find_system_font()
    fontfile_part = f"fontfile='{font_path.replace(chr(92), '/').replace(':', chr(92) + ':')}':" if font_path else ""
    if not font_path:
        print("  [WARN] No system font found in known locations — relying on ffmpeg's fontconfig.")

    drawtext = (
        f"drawtext={fontfile_part}text='{WATERMARK['text']}':"
        f"fontcolor={WATERMARK['color']}@{WATERMARK['opacity']}:"
        f"fontsize={WATERMARK['font_size']}:{position}"
    )
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", drawtext, "-codec:a", "copy", tmp_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg watermarking failed: {result.stderr[-500:]}")
    os.replace(tmp_path, video_path)


# ============================================
# MAIN FUNCTION (ENHANCED WITH VOICE & 4K)
# ============================================

def generate_short_clip(
    prompt, 
    platform="reels", 
    duration=15, 
    negative_prompt=None,
    apply_watermark=True, 
    resolution="720p",
    use_voice=False,
    voice_language="en-US"
):
    """
    Generate a short, platform-ready clip (Reels/Shorts/TikTok/etc).

    Parameters:
    - prompt (str): Text description (Urdu/Hindi/English)
    - platform (str): one of PLATFORM_PRESETS keys ("reels", "shorts",
      "tiktok", "square", "landscape") — picks the aspect ratio
    - duration (int): seconds, hard-capped at MAX_SHORT_CLIP_SECONDS (30)
    - negative_prompt (str, optional)
    - apply_watermark (bool)
    - resolution (str): 480p, 720p, 1080p, 2k, 4k
    - use_voice (bool): If True, prompt is from voice input
    - voice_language (str): Language for voice recognition

    Returns:
    - dict: {"success", "video_path", "message", "clip_count",
             "watermark_applied", "watermark_error", "info"}
    """
    print("\n" + "=" * 50)
    print("🎬 FEATURE 03: 30-Second Clip" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 50)

    # ---------- Handle Voice Input ----------
    if use_voice:
        print("🎤 Voice input enabled...")
        speech_result = speech_to_text(language=voice_language)
        if not speech_result["success"]:
            return {
                "success": False,
                "video_path": None,
                "message": f"Voice input failed: {speech_result['message']}",
                "prompt": None
            }
        prompt = speech_result["text"]
        print(f"📝 Voice recognized: {prompt}")

    # ---------- Validate Input ----------
    if not prompt or len(prompt.strip()) < 3:
        return {"success": False, "video_path": None,
                "message": "Prompt is too short. Please write at least 3 words."}

    if platform not in PLATFORM_PRESETS:
        return {"success": False, "video_path": None,
                "message": f"Unknown platform '{platform}'. Choose from: {list(PLATFORM_PRESETS.keys())}"}

    # Hard-clamp duration — this feature's whole point is short clips.
    duration = max(MIN_CLIP_LENGTH, min(int(duration), MAX_SHORT_CLIP_SECONDS))

    if not DRY_RUN and not AGNES_API_KEY:
        return {"success": False, "video_path": None,
                "message": "AGNES_API_KEY not set. Set it in your environment before generating video."}

    preset = PLATFORM_PRESETS[platform]
    
    # Get resolution dimensions
    width, height = _get_resolution_dims(preset["width"], preset["height"], resolution)
    
    resolution_label = RESOLUTION_CONFIGS.get(resolution, RESOLUTION_CONFIGS["720p"])["label"]

    print(f"📝 Prompt: {prompt}")
    print(f"📱 Platform: {preset['label']}")
    print(f"📐 Resolution: {resolution_label} ({width}x{height})")
    print(f"⏱️ Duration: {duration}s")
    if use_voice:
        print(f"🎤 Input source: Voice ({voice_language})")
    if negative_prompt:
        print(f"🚫 Negative prompt: {negative_prompt}")

    # ---------- Split into clips ----------
    clips_needed = -(-duration // MAX_CLIP_LENGTH)
    per_clip_seconds = -(-duration // clips_needed)
    print(f"\n📊 Clips needed: {clips_needed} (~{per_clip_seconds}s each, {MAX_CLIP_LENGTH}s max per Agnes call)")

    clip_paths = []
    try:
        for i in range(clips_needed):
            print(f"\n🎬 Generating clip {i + 1}/{clips_needed}...")
            clip_path = _generate_one_clip(prompt, width, height, per_clip_seconds, negative_prompt, i + 1)
            clip_paths.append(clip_path)
            if not DRY_RUN and i + 1 < clips_needed:
                time.sleep(AGNES_CLIP_SPACING_SECONDS)
    except Exception as e:
        for p in clip_paths:
            if os.path.exists(p):
                os.remove(p)
        return {"success": False, "video_path": None, "message": f"Generation failed: {e}"}

    # ---------- Stitch ----------
    video_name = f"short_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    final_video_path = os.path.join(PATHS["videos"], video_name)

    try:
        print(f"\n🔗 Stitching {clips_needed} clip(s)...")
        _stitch_clips(clip_paths, final_video_path)
    except Exception as e:
        return {"success": False, "video_path": None, "message": f"Stitching failed: {e}"}

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

    # ---------- Save Metadata ----------
    video_info = {
        "video_id": video_name,
        "prompt": prompt,
        "platform": platform,
        "resolution": resolution,
        "resolution_label": resolution_label,
        "size": f"{width}x{height}",
        "requested_duration": duration,
        "clips": clips_needed,
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "voice_input": use_voice,
        "voice_language": voice_language if use_voice else None,
        "created_at": datetime.now().isoformat(),
        "path": final_video_path,
        "dry_run": DRY_RUN,
    }
    info_path = final_video_path.replace(".mp4", ".json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(video_info, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Short clip generated successfully!")
    print(f"📹 Path: {final_video_path}")
    print(f"📱 Platform: {preset['label']}")
    print(f"📐 Resolution: {resolution_label}")
    if use_voice:
        print(f"🎤 Voice input: Yes")

    return {
        "success": True,
        "video_path": final_video_path,
        "message": f"{preset['label']} clip generated successfully!",
        "clip_count": clips_needed,
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "info": video_info,
    }


# ============================================
# VOICE-ONLY FUNCTION
# ============================================

def generate_clip_from_voice(
    platform="reels",
    duration=15,
    negative_prompt=None,
    apply_watermark=True,
    resolution="720p",
    voice_language="en-US"
):
    """
    Generate a short clip using voice input for the prompt.
    
    Parameters:
    - platform (str): reels, shorts, tiktok, square, landscape
    - duration (int): seconds (max 30)
    - negative_prompt (str): Things to avoid
    - apply_watermark (bool): Whether to add watermark
    - resolution (str): 480p, 720p, 1080p, 2k, 4k
    - voice_language (str): Language for voice recognition
    
    Returns:
    - dict: Result from generate_short_clip
    """
    return generate_short_clip(
        prompt="",  # Will be filled from voice
        platform=platform,
        duration=duration,
        negative_prompt=negative_prompt,
        apply_watermark=apply_watermark,
        resolution=resolution,
        use_voice=True,
        voice_language=voice_language
    )


# ============================================
# TEST FUNCTION
# ============================================

def test():
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_03_clip_generation.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)

    print("\n📝 Test 1: Basic Reels clip (15s, 720p)")
    result = generate_short_clip(
        prompt="Karachi ki sadkein raat mein roshan hain",
        platform="reels",
        duration=15,
        resolution="720p"
    )
    print(f"  Result: {result['message']}")

    print("\n📝 Test 2: TikTok clip with 4K resolution")
    result = generate_short_clip(
        prompt="A beautiful sunset over the ocean with waves",
        platform="tiktok",
        duration=10,
        resolution="4k"
    )
    print(f"  Result: {result['message']} | Resolution: {result.get('info', {}).get('resolution_label')}")

    print("\n📝 Test 3: YouTube Shorts with 1080p")
    result = generate_short_clip(
        prompt="Morning routine, coffee, sunlight through window",
        platform="shorts",
        duration=15,
        resolution="1080p"
    )
    print(f"  Result: {result['message']}")

    print("\n📝 Test 4: Square clip with 2K")
    result = generate_short_clip(
        prompt="Abstract art with flowing colors",
        platform="square",
        duration=10,
        resolution="2k"
    )
    print(f"  Result: {result['message']}")

    print("\n📝 Test 5: Duration over the 30s cap should be clamped")
    result = generate_short_clip(
        prompt="Test clamp long duration to thirty",
        platform="tiktok",
        duration=90,
        resolution="720p"
    )
    print(f"  Result: {result['message']} | Duration: {result['info']['requested_duration']}s (should be 30s)")

    if SPEECH_RECOGNITION_AVAILABLE:
        print("\n📝 Test 6: Voice input test (if microphone available)")
        result = generate_clip_from_voice(
            platform="reels",
            duration=10,
            resolution="720p",
            voice_language="en-US"
        )
        print(f"  Result: {result['message']}")

    print("\n📝 Test 7: Short prompt (should fail)")
    result = generate_short_clip(
        prompt="Hi",
        platform="shorts",
        duration=10,
        resolution="720p"
    )
    print(f"  Result: {result['message']}")

    print("\n📝 Test 8: Unknown platform (should fail cleanly)")
    result = generate_short_clip(
        prompt="Valid prompt text here",
        platform="myspace",
        duration=10,
        resolution="720p"
    )
    print(f"  Result: {result['message']}")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    test()

# ============================================
# END OF feature_03_clip_generation.py (ENHANCED)
# ============================================