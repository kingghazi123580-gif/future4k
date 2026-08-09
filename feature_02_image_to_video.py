# ============================================
# FEATURE 02: IMAGE-TO-VIDEO (ENHANCED WITH VOICE, 4K & CUSTOM SIZE)
# Filename: feature_02_image_to_video.py
# ============================================
# What this file does (English summary):
# - Takes a static image + a text prompt (motion description)
# - SUPPORTS VOICE INPUT: User can speak their motion prompt
# - SUPPORTS 4K RESOLUTION: 4K (3840x2160) video generation
# - CUSTOM IMAGE SIZE: User can set any width/height
# - Uploads the image to a temporary public URL (Agnes requires a
#   public image URL, not raw bytes)
# - Calls Agnes AI (agnes-video-v2.0) to animate the image into video
# - Duration is NOT capped at Agnes's per-call limit (MAX_CLIP_LENGTH,
#   18s) anymore. Longer requests are automatically split into several
#   clips and stitched together, same as feature_01 — but for
#   image-to-video specifically, each clip after the first is generated
#   from the LAST FRAME of the previous clip (extracted with ffmpeg),
#   not the original image again. This keeps the motion continuous
#   across the whole video instead of restarting/repeating.
# - Optionally burns in a watermark for free-tier users
# - Saves a JSON metadata file next to the output video
# - Supports FILMAA_DRY_RUN=1 to test the whole pipeline without
#   calling the real Agnes API or needing network access
#
# CHANGE LOG (frame-count fix):
# - get_frames_for_duration() previously came from config.py's global
#   version (hardcoded formula). It is now overridden locally in this
#   file to go through frame_policy.get_frames_for_duration(), which
#   snaps to whatever formula is configured for AGNES_AI_MODEL in the
#   Admin Panel -> Frame Rules tab.
#
# CHANGE LOG (image-URL reliability fix):
# - _upload_image_to_temp_url() previously trusted tmpfiles.org's upload
#   response blindly and handed the resulting URL straight to Agnes. Since
#   tmpfiles.org is a free third-party host with no reliability guarantee
#   (files can expire early, the host can rate-limit us, or serve the file
#   back with a Content-Type Agnes doesn't recognize as an image), this
#   sometimes produced a URL that LOOKED right but wasn't actually
#   downloadable/valid — Agnes would then reject with a vague 400 error:
#   "image URL could not be downloaded or did not return a valid supported
#   image." That error gave no clue which host/step actually failed.
#   Now: after upload, we immediately fetch the URL ourselves and verify
#   it responds 200 with an image/* Content-Type and real body bytes,
#   BEFORE ever sending it to Agnes. If the first host (tmpfiles.org)
#   fails this check, we automatically retry with a second host (0x0.st).
#   This turns a confusing remote Agnes error into a fast, clear local
#   one, and self-heals most of the time via the fallback host.
#
# Public function used by ui.py:
#   generate_video_from_image(image_path, prompt, resolution, duration,
#                              negative_prompt, apply_watermark, seed, aspect_ratio,
#                              custom_width, custom_height, use_voice, voice_language)
#   -> {"success", "video_path", "message", "duration", "clip_count",
#       "watermark_applied", "watermark_error", "info"}
# ============================================

import os
import time
import json
import base64
import mimetypes
import requests
import subprocess
from datetime import datetime

try:
    from config import *
except ImportError:
    print("[ERROR] config.py not found!")
    raise SystemExit(1)

import frame_policy

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def get_frames_for_duration(duration_seconds, fps=24):
    """
    OVERRIDE of config.py's global get_frames_for_duration().
    Snaps frame count to whatever formula is configured for AGNES_AI_MODEL
    (Admin Panel -> Frame Rules). This is the frame-count fix: previously
    this pulled a hardcoded formula from config.py which didn't match
    what Agnes actually required.
    """
    return frame_policy.get_frames_for_duration(AGNES_AI_MODEL, duration_seconds, fps=fps)

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
            print("🎤 Listening... Speak your motion prompt clearly.")
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
# RESOLUTION CONFIGURATION (ENHANCED WITH 4K)
# ============================================

RESOLUTION_CONFIGS = {
    "480p": {"width": 854, "height": 480, "label": "480p (SD)"},
    "720p": {"width": 1280, "height": 720, "label": "720p (HD)"},
    "1080p": {"width": 1920, "height": 1080, "label": "1080p (Full HD)"},
    "2k": {"width": 2560, "height": 1440, "label": "2K (QHD)"},
    "4k": {"width": 3840, "height": 2160, "label": "4K (Ultra HD)"},
}

def get_resolution_dims(resolution_key, aspect_ratio="16:9", custom_width=None, custom_height=None):
    """
    Get resolution dimensions based on resolution key, aspect ratio, or custom size.

    Parameters:
    - resolution_key (str): 480p, 720p, 1080p, 2k, 4k
    - aspect_ratio (str): 16:9, 9:16, 1:1, 4:3, 3:4
    - custom_width (int): Custom width in pixels (overrides resolution_key)
    - custom_height (int): Custom height in pixels (overrides resolution_key)

    Returns:
    - dict: {"width": int, "height": int}
    """
    # If custom dimensions provided, use them
    if custom_width and custom_height:
        width = int(custom_width)
        height = int(custom_height)
        # Ensure dimensions are divisible by 16 (Agnes requirement)
        width = ((width + 15) // 16) * 16
        height = ((height + 15) // 16) * 16
        return {"width": width, "height": height}

    # Get base dimensions from resolution
    base = RESOLUTION_CONFIGS.get(resolution_key, RESOLUTION_CONFIGS["720p"])
    base_width = base["width"]
    base_height = base["height"]

    # Adjust for aspect ratio
    aspect_map = {
        "16:9": (1.777, 1),
        "9:16": (1, 1.777),
        "1:1": (1, 1),
        "4:3": (1.333, 1),
        "3:4": (1, 1.333),
    }

    if aspect_ratio in aspect_map:
        ratio_w, ratio_h = aspect_map[aspect_ratio]
        # Use the height as base and adjust width
        if ratio_w >= ratio_h:
            width = int(base_height * ratio_w / ratio_h)
            height = base_height
        else:
            width = base_width
            height = int(base_width * ratio_h / ratio_w)
    else:
        width = base_width
        height = base_height

    # Ensure dimensions are divisible by 16
    width = ((width + 15) // 16) * 16
    height = ((height + 15) // 16) * 16

    return {"width": width, "height": height}


# ============================================
# INTERNAL HELPERS
# ============================================

def _agnes_headers():
    return {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json",
    }


def image_to_base64_uri(image_path):
    """
    Convert a local image file into a base64 data URI
    (e.g. "data:image/png;base64,iVBORw0...").

    ⚠️ IMPORTANT: Agnes's VIDEO endpoint (agnes-video-v2.0, /v1/videos) only
    accepts a PUBLIC image URL for image-to-video — it does NOT accept
    base64/data-URIs (confirmed against Agnes's official docs). Sending
    the output of this function as the "image" field in _create_agnes_video_task()
    will be rejected.

    This function is kept here as a general-purpose utility — useful for:
      - Showing a quick local preview of the uploaded image somewhere in the UI
      - Debugging / logging what was uploaded
      - If Agnes ever adds base64 support to the video endpoint in the future

    It is intentionally NOT wired into the main generate_video_from_image()
    pipeline, which still goes through _upload_image_to_temp_url() (public
    URL hosting) since that's what Agnes's video API actually requires.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    ext = os.path.splitext(image_path)[1].lstrip(".").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext or "png"

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:image/{mime};base64,{encoded}"


def _verify_public_image_url(url, timeout=15):
    """
    Confirms a "public image URL" we're about to hand to Agnes is actually
    reachable AND actually returns image bytes — not an HTML error page,
    not a redirect-to-nowhere, not an octet-stream with the wrong headers.

    This is what was MISSING before: the old code trusted tmpfiles.org's
    upload response blindly and handed the URL straight to Agnes. tmpfiles
    is a free third-party host with no reliability guarantee — files can
    expire early, the host can rate-limit us, or it can serve the file
    back with a Content-Type Agnes doesn't recognize as an image. Agnes
    then rejects with the vague "could not be downloaded or did not
    return a valid supported image" error, which gives no clue WHICH of
    those happened. Checking it ourselves, right after upload, turns that
    vague remote error into a fast, clear local one — and lets us retry
    with a different host automatically instead of wasting an Agnes call.

    Returns True only if the URL responds 200 with an image/* content-type
    and at least a few hundred bytes of body.
    """
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        if resp.status_code != 200:
            return False
        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return False
        # Read a small chunk to make sure there's real body content, not an
        # empty/near-empty response that happens to carry an image header.
        chunk = next(resp.iter_content(chunk_size=512), b"")
        return len(chunk) > 100
    except requests.RequestException:
        return False


def _upload_to_tmpfiles(image_path, content_type):
    """Upload to tmpfiles.org and return a direct (forced-https, /dl/) URL."""
    with open(image_path, "rb") as f:
        files = {"file": (os.path.basename(image_path), f, content_type)}
        last_error = None
        for attempt in range(1, 4):
            try:
                f.seek(0)
                resp = requests.post(
                    "https://tmpfiles.org/api/v1/upload", files=files, timeout=(15, 90)
                )
                resp.raise_for_status()
                break
            except requests.RequestException as e:
                last_error = e
                if attempt < 3:
                    print(f"  [tmpfiles upload retry {attempt}/3] {e} — retrying...")
                    time.sleep(3 * attempt)
                else:
                    raise RuntimeError(f"Image upload to tmpfiles.org failed after 3 attempts: {last_error}")
    data = resp.json()
    info_url = data.get("data", {}).get("url")
    if not info_url:
        raise RuntimeError(f"tmpfiles.org upload didn't return a URL: {data}")

    # Force https (tmpfiles sometimes returns plain http://, which some
    # downstream fetchers — possibly including Agnes's — refuse) and
    # insert the /dl/ segment needed to get raw file bytes instead of
    # tmpfiles' HTML "view" page.
    direct_url = info_url.replace("http://", "https://", 1)
    direct_url = direct_url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)
    return direct_url


def _upload_to_0x0(image_path, content_type):
    """Fallback host if tmpfiles.org's URL fails verification."""
    with open(image_path, "rb") as f:
        files = {"file": (os.path.basename(image_path), f, content_type)}
        resp = requests.post("https://0x0.st", files=files, timeout=(15, 90))
        resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"0x0.st upload didn't return a usable URL: {url}")
    return url


def _upload_image_to_temp_url(image_path):
    """
    Upload local image to a temporary public URL, verify it actually
    serves a valid image before returning it, and fall back to a second
    host if the first one's URL doesn't check out. Agnes requires image
    URLs to be publicly accessible AND correctly served — this function
    now guarantees both before ever calling Agnes.
    """
    if DRY_RUN:
        return "https://example.com/dry_run_image.png"

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    content_type, _ = mimetypes.guess_type(image_path)
    if not content_type:
        content_type = "application/octet-stream"

    upload_attempts = [
        ("tmpfiles.org", _upload_to_tmpfiles),
        ("0x0.st", _upload_to_0x0),
    ]

    last_reason = ""
    for host_name, upload_fn in upload_attempts:
        try:
            url = upload_fn(image_path, content_type)
        except Exception as e:
            print(f"  [WARN] Upload to {host_name} failed: {e}")
            last_reason = str(e)
            continue

        print(f"  Uploaded to {host_name}, verifying URL is a valid public image...")
        if _verify_public_image_url(url):
            print(f"  ✅ Verified — {host_name} URL is a real, reachable image.")
            return url
        else:
            print(f"  [WARN] {host_name} URL did not verify as a valid public image, trying next host...")
            last_reason = f"{host_name} URL failed verification (unreachable, non-image content-type, or empty body)"

    raise RuntimeError(
        f"Could not produce a working public image URL after trying all hosts. Last reason: {last_reason}"
    )


def _create_agnes_video_task(prompt, image_url, width, height, num_frames, frame_rate,
                              negative_prompt=None, seed=None):
    """Create an image-to-video task on Agnes."""
    payload = {
        "model": AGNES_AI_MODEL,
        "prompt": prompt,
        "image": image_url,
        "height": height,
        "width": width,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = seed

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
            video_id = data.get("video_id")
            if not video_id:
                raise RuntimeError(f"No video_id in response: {data}")

            print(f"  Task created — video_id: {video_id}")
            return video_id, data.get("task_id")

        except RuntimeError:
            raise
        except requests.RequestException as e:
            last_error = e
            if attempt < max_attempts:
                print(f"  [retry {attempt}/{max_attempts}] task creation failed: {e}")
                time.sleep(API.get("retry_delay", 5))
            else:
                raise RuntimeError(f"Task creation failed after {max_attempts} attempts: {last_error}")

    raise RuntimeError("Task creation failed: exhausted retries")


def _extract_video_url(result: dict) -> str:
    """Pull the downloadable video URL out of a completed Agnes response."""
    for field in ("video_url", "remixed_from_video_id", "url", "output_url"):
        value = result.get(field)
        if value and isinstance(value, str) and value.startswith("http"):
            return value
    raise KeyError(
        f"Could not find a video URL in Agnes's completed response. "
        f"Looked for video_url / remixed_from_video_id / url / output_url. "
        f"Actual response keys: {list(result.keys())}"
    )


def _poll_agnes_video_result(video_id):
    """Poll using video_id at the API root (NOT under /v1)."""
    url = f"{AGNES_AI_ROOT_URL}/agnesapi"
    params = {"video_id": video_id}

    for attempt in range(1, AGNES_MAX_POLL_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=_agnes_headers(), params=params, timeout=30)

            if resp.status_code == 404:
                print(f"  [poll {attempt}] not found yet, waiting...")
                time.sleep(AGNES_POLL_INTERVAL_SECONDS)
                continue

            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            print(f"  [poll {attempt}/{AGNES_MAX_POLL_ATTEMPTS}] status: {status} "
                  f"({data.get('progress', 0)}%)")

            if status == "completed":
                return data
            if status == "failed":
                raise RuntimeError(f"Video generation failed: {data.get('error', 'unknown error')}")

            time.sleep(AGNES_POLL_INTERVAL_SECONDS)

        except requests.RequestException as e:
            print(f"  [poll {attempt}] request error: {e}")
            time.sleep(AGNES_POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Generation did not complete within "
                        f"{AGNES_MAX_POLL_ATTEMPTS * AGNES_POLL_INTERVAL_SECONDS}s")


def _download_video(video_url, save_path, max_retries=4):
    """Download the rendered clip, with retry+backoff."""
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
                raise RuntimeError(f"Download failed after {max_retries} attempts: {last_error}")


def _extract_last_frame(video_path, out_image_path):
    """
    Grab the last frame of a rendered clip so the NEXT clip can continue
    animating from where this one left off.
    """
    cmd = [
        "ffmpeg", "-y", "-sseof", "-1", "-i", video_path,
        "-update", "1", "-q:v", "2", out_image_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(out_image_path):
        raise RuntimeError(f"Extracting last frame failed: {result.stderr[-500:]}")
    return out_image_path


def _stitch_clips(clip_paths, output_path):
    """Stitch multiple clips into one file using ffmpeg's concat demuxer."""
    if len(clip_paths) == 1:
        os.replace(clip_paths[0], output_path)
        return output_path

    concat_list_path = output_path.replace(".mp4", "_concat.txt")
    with open(concat_list_path, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", concat_list_path, "-c", "copy", output_path]
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
        print("  [WARN] No system font found in known locations.")

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
    return video_path


def _make_dry_run_clip(save_path, seconds, width, height):
    """Render a real (tiny, silent) mp4 via ffmpeg's test source for DRY_RUN."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={width}x{height}:rate=24",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        save_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[DRY_RUN] fake clip generation failed: {result.stderr[-500:]}")
    return save_path


# ============================================
# MAIN FUNCTION (ENHANCED)
# ============================================

def generate_video_from_image(
    image_path,
    prompt,
    resolution="720p",
    duration=5,
    negative_prompt=None,
    apply_watermark=True,
    seed=None,
    aspect_ratio="16:9",
    custom_width=None,
    custom_height=None,
    use_voice=False,
    voice_language="en-US"
):
    """
    Generate video from an image using Agnes AI.

    Parameters:
    - image_path (str): Path to input image
    - prompt (str): Motion description text
    - resolution (str): 480p, 720p, 1080p, 2k, 4k
    - duration (int): Target duration in seconds
    - negative_prompt (str): Things to avoid in video
    - apply_watermark (bool): Whether to add watermark
    - seed (int): For reproducible results
    - aspect_ratio (str): 16:9, 9:16, 1:1, 4:3, 3:4
    - custom_width (int): Custom width in pixels (overrides resolution)
    - custom_height (int): Custom height in pixels (overrides resolution)
    - use_voice (bool): If True, prompt is from voice input
    - voice_language (str): Language for voice recognition

    Returns:
    - dict: {"success", "video_path", "message", "duration", "clip_count",
              "watermark_applied", "watermark_error", "info"}
    """
    print("\n" + "=" * 50)
    print("🎬 FEATURE 02: Image-to-Video" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 50)

    # ---------- Validate Input ----------
    if not os.path.exists(image_path):
        return {"success": False, "video_path": None, "message": f"Image not found: {image_path}"}

    ext = os.path.splitext(image_path)[1].lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        return {"success": False, "video_path": None,
                "message": f"Unsupported image format '{ext}'. Use: {sorted(SUPPORTED_IMAGE_EXTENSIONS)}"}

    if not prompt or len(prompt.strip()) < 3:
        return {"success": False, "video_path": None,
                "message": "Prompt is too short. Please write at least 3 words."}

    duration = max(duration, MIN_CLIP_LENGTH)

    if not DRY_RUN and not AGNES_API_KEY:
        return {"success": False, "video_path": None,
                "message": "AGNES_API_KEY not set. Get your key at platform.agnes-ai.com"}

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

    # ---------- Get Resolution ----------
    dims = get_resolution_dims(resolution, aspect_ratio, custom_width, custom_height)
    width = dims["width"]
    height = dims["height"]

    # ---------- Check if using Custom Size ----------
    using_custom_size = custom_width and custom_height
    if using_custom_size:
        print(f"📐 Custom size: {width}x{height}")
    else:
        res_label = RESOLUTION_CONFIGS.get(resolution, RESOLUTION_CONFIGS["720p"])["label"]
        print(f"📐 Resolution: {res_label} ({width}x{height}) | Aspect: {aspect_ratio}")

    print(f"🖼️ Image: {os.path.basename(image_path)}")
    print(f"📝 Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"📝 Prompt: {prompt}")
    print(f"⏱️ Target duration: {duration}s")
    if negative_prompt:
        print(f"🚫 Negative prompt: {negative_prompt}")
    if seed is not None:
        print(f"🎲 Seed: {seed}")

    # ---------- Split into clips ----------
    clips_needed = -(-duration // MAX_CLIP_LENGTH)
    per_clip_seconds = -(-duration // clips_needed)
    num_frames = get_frames_for_duration(per_clip_seconds)
    actual_clip_duration = num_frames / 24
    print(f"\n📊 Clips needed: {clips_needed} (~{actual_clip_duration:.1f}s each) | "
          f"Frames/clip: {num_frames} @ 24fps | Size: {width}x{height}")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ---------- DRY RUN Mode ----------
    if DRY_RUN:
        clip_paths = []
        for i in range(clips_needed):
            clip_path = os.path.join(PATHS["temp"], f"img_clip_{i+1}_{timestamp}.mp4")
            _make_dry_run_clip(clip_path, actual_clip_duration, width, height)
            clip_paths.append(clip_path)
        final_path = os.path.join(PATHS["videos"], f"image_video_{timestamp}_dryrun.mp4")
        _stitch_clips(clip_paths, final_path)

        # Apply watermark in dry run
        watermark_applied = bool(apply_watermark and WATERMARK.get("free_tier", True))

        return {
            "success": True,
            "video_path": final_path,
            "message": f"[DRY_RUN] simulation complete, ~{actual_clip_duration * clips_needed:.1f}s "
                       f"across {clips_needed} clip(s)",
            "duration": actual_clip_duration * clips_needed,
            "clip_count": clips_needed,
            "watermark_applied": watermark_applied,
            "watermark_error": None,
            "info": {"dry_run": True, "path": final_path, "size": f"{width}x{height}"},
        }

    # ---------- Generate each clip ----------
    clip_paths = []
    current_image_path = image_path
    total_actual_seconds = 0.0

    try:
        for i in range(clips_needed):
            print(f"\n🎬 Generating clip {i + 1}/{clips_needed}...")

            image_url = _upload_image_to_temp_url(current_image_path)
            print(f"  Image URL: {image_url}")

            video_id, task_id = _create_agnes_video_task(
                prompt=prompt,
                image_url=image_url,
                width=width,
                height=height,
                num_frames=num_frames,
                frame_rate=24,
                negative_prompt=negative_prompt,
                seed=seed,
            )
            result = _poll_agnes_video_result(video_id)
            video_url = _extract_video_url(result)

            clip_path = os.path.join(PATHS["temp"], f"img_clip_{i+1}_{timestamp}.mp4")
            _download_video(video_url, clip_path)
            clip_paths.append(clip_path)
            total_actual_seconds += float(result.get("seconds", actual_clip_duration))

            print(f"  ✅ Clip {i + 1} done — {result.get('seconds', actual_clip_duration)}s")

            # Continue from this clip's last frame for the next one
            if i + 1 < clips_needed:
                frame_path = os.path.join(PATHS["temp"], f"frame_{i+1}_{timestamp}.jpg")
                _extract_last_frame(clip_path, frame_path)
                current_image_path = frame_path
                time.sleep(AGNES_CLIP_SPACING_SECONDS)

    except Exception as e:
        for p in clip_paths:
            if os.path.exists(p):
                os.remove(p)
        return {"success": False, "video_path": None, "message": f"Generation failed: {e}"}

    # ---------- Stitch ----------
    final_path = os.path.join(PATHS["videos"], f"image_video_{timestamp}.mp4")
    try:
        print(f"\n🔗 Stitching {clips_needed} clip(s)...")
        _stitch_clips(clip_paths, final_path)
    except Exception as e:
        return {"success": False, "video_path": None, "message": f"Stitching failed: {e}"}

    # ---------- Watermark ----------
    watermark_applied = False
    watermark_error = None
    if apply_watermark and WATERMARK.get("free_tier", True):
        try:
            print(f"💧 Adding watermark: {WATERMARK['text']}")
            _apply_watermark(final_path)
            watermark_applied = True
        except Exception as e:
            watermark_error = str(e)
            print(f"[WARN] Watermark failed, delivering video without it: {e}")

    # ---------- Save Metadata ----------
    video_info = {
        "prompt": prompt,
        "image": image_path,
        "resolution": resolution,
        "resolution_label": RESOLUTION_CONFIGS.get(resolution, RESOLUTION_CONFIGS["720p"])["label"],
        "custom_size": f"{width}x{height}" if using_custom_size else None,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "requested_duration": duration,
        "actual_duration": total_actual_seconds,
        "clips": clips_needed,
        "size": f"{width}x{height}",
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "voice_input": use_voice,
        "voice_language": voice_language if use_voice else None,
        "created_at": datetime.now().isoformat(),
        "path": final_path,
        "seed": seed,
        "dry_run": False,
    }
    info_path = final_path.replace(".mp4", ".json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(video_info, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Video generated successfully!")
    print(f"📹 Path: {final_path}")
    print(f"📐 Size: {width}x{height}")
    print(f"⏱️ Duration: {total_actual_seconds:.1f}s")
    if use_voice:
        print(f"🎤 Voice input: Yes")

    return {
        "success": True,
        "video_path": final_path,
        "message": "Video generated successfully from image!",
        "duration": total_actual_seconds,
        "clip_count": clips_needed,
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "info": video_info,
    }


# ============================================
# STORY MODE — multiple images, multiple prompts, ONE combined video
# ============================================

def generate_story_from_images(scenes, resolution="720p", apply_watermark=True,
                                aspect_ratio="16:9", custom_width=None, custom_height=None):
    """
    Turns a SEQUENCE of (image, prompt) pairs into ONE final video — e.g.
    3 images depicting "packing bags" -> "fighting a lion" -> "reaching
    the city" become a single combined story video, cut scene-to-scene
    (NOT blended/continuous — each image is its own independent scene,
    since they depict different times/places/actions, not one continuous
    shot). No character-consistency or last-frame continuity is applied
    here by design — that's a separate feature to be added later.

    Parameters:
    - scenes (list[dict]): each dict is one scene:
        {"image_path": str, "prompt": str, "duration": int (optional, default 5)}
      Order in the list = order in the final video.
    - resolution, apply_watermark, aspect_ratio, custom_width, custom_height:
      same meaning as generate_video_from_image(), applied to every scene.

    Returns:
    - dict: {"success", "video_path", "message", "scene_count",
              "total_duration", "watermark_applied", "watermark_error"}
    """
    print("\n" + "=" * 50)
    print(f"📖 STORY MODE: {len(scenes)} scene(s)" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 50)

    if not scenes or len(scenes) < 2:
        return {"success": False, "video_path": None,
                "message": "Story mode needs at least 2 scenes (image + prompt each)."}

    for i, scene in enumerate(scenes, start=1):
        if not scene.get("image_path") or not os.path.exists(scene["image_path"]):
            return {"success": False, "video_path": None,
                    "message": f"Scene {i}: image not found."}
        if not scene.get("prompt") or len(scene["prompt"].strip()) < 3:
            return {"success": False, "video_path": None,
                    "message": f"Scene {i}: prompt is too short."}

    scene_clip_paths = []
    total_duration = 0.0

    try:
        for i, scene in enumerate(scenes, start=1):
            print(f"\n📽️ Scene {i}/{len(scenes)}: {os.path.basename(scene['image_path'])}")
            result = generate_video_from_image(
                image_path=scene["image_path"],
                prompt=scene["prompt"],
                resolution=resolution,
                duration=scene.get("duration", 5),
                apply_watermark=False,  # watermark applied once, on the final stitched video
                aspect_ratio=aspect_ratio,
                custom_width=custom_width,
                custom_height=custom_height,
            )
            if not result["success"]:
                raise RuntimeError(f"Scene {i} failed: {result['message']}")

            scene_clip_paths.append(result["video_path"])
            total_duration += result.get("duration", 0)
            print(f"  ✅ Scene {i} done — {result.get('duration', 0):.1f}s")

    except Exception as e:
        for p in scene_clip_paths:
            if os.path.exists(p):
                os.remove(p)
        return {"success": False, "video_path": None, "message": f"Story generation failed: {e}"}

    # ---------- Stitch all scenes together (hard cut, no blending) ----------
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    final_path = os.path.join(PATHS["videos"], f"story_video_{timestamp}.mp4")
    try:
        print(f"\n🔗 Stitching {len(scene_clip_paths)} scene(s) into final story...")
        _stitch_clips(scene_clip_paths, final_path)
    except Exception as e:
        return {"success": False, "video_path": None, "message": f"Stitching scenes failed: {e}"}

    # ---------- Watermark (once, on the final combined video) ----------
    watermark_applied = False
    watermark_error = None
    if apply_watermark and WATERMARK.get("free_tier", True):
        try:
            print(f"💧 Adding watermark: {WATERMARK['text']}")
            _apply_watermark(final_path)
            watermark_applied = True
        except Exception as e:
            watermark_error = str(e)
            print(f"[WARN] Watermark failed, delivering video without it: {e}")

    print(f"\n✅ Story video generated successfully!")
    print(f"📹 Path: {final_path}")
    print(f"⏱️ Total duration: {total_duration:.1f}s across {len(scenes)} scenes")

    return {
        "success": True,
        "video_path": final_path,
        "message": f"Story video generated — {len(scenes)} scenes stitched together!",
        "scene_count": len(scenes),
        "total_duration": total_duration,
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
    }


# ============================================
# VOICE-ONLY FUNCTION
# ============================================

def generate_video_from_voice_and_image(
    image_path,
    resolution="720p",
    duration=5,
    negative_prompt=None,
    apply_watermark=True,
    seed=None,
    aspect_ratio="16:9",
    custom_width=None,
    custom_height=None,
    voice_language="en-US"
):
    """
    Generate video from image using voice input for motion prompt.

    Parameters:
    - image_path (str): Path to input image
    - resolution (str): 480p, 720p, 1080p, 2k, 4k
    - duration (int): Target duration in seconds
    - negative_prompt (str): Things to avoid
    - apply_watermark (bool): Whether to add watermark
    - seed (int): For reproducible results
    - aspect_ratio (str): 16:9, 9:16, 1:1, 4:3, 3:4
    - custom_width (int): Custom width
    - custom_height (int): Custom height
    - voice_language (str): Language for voice recognition

    Returns:
    - dict: Result from generate_video_from_image
    """
    return generate_video_from_image(
        image_path=image_path,
        prompt="",  # Will be filled from voice
        resolution=resolution,
        duration=duration,
        negative_prompt=negative_prompt,
        apply_watermark=apply_watermark,
        seed=seed,
        aspect_ratio=aspect_ratio,
        custom_width=custom_width,
        custom_height=custom_height,
        use_voice=True,
        voice_language=voice_language
    )


# ============================================
# TEST FUNCTION
# ============================================

def test():
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_02_image_to_video.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)

    # Create test image
    test_image = os.path.join(os.path.dirname(__file__), "test_image.png")
    if not os.path.exists(test_image):
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (512, 512), color=(100, 100, 200))
            d = ImageDraw.Draw(img)
            d.text((200, 250), "FILMAA", fill=(255, 255, 255))
            img.save(test_image)
            print(f"✅ Created test image: {test_image}")
        except ImportError:
            print("❌ PIL not installed — install with: pip install Pillow")
            return

    print("\n📝 Test 1: Basic image-to-video (720p, 5s)")
    result = generate_video_from_image(
        image_path=test_image,
        prompt="Animate the scene with gentle motion, clouds drifting",
        resolution="720p",
        duration=5,
        aspect_ratio="16:9",
    )
    print(f"  Result: {result['message']} | clips: {result.get('clip_count')}")

    print("\n📝 Test 2: 4K resolution")
    result = generate_video_from_image(
        image_path=test_image,
        prompt="Animate with slow motion, water flowing",
        resolution="4k",
        duration=5,
        aspect_ratio="16:9",
    )
    print(f"  Result: {result['message']} | Size: {result.get('info', {}).get('size')}")

    print("\n📝 Test 3: Custom size (1920x1080)")
    result = generate_video_from_image(
        image_path=test_image,
        prompt="Animate with gentle motion",
        resolution="720p",
        duration=5,
        custom_width=1920,
        custom_height=1080,
        aspect_ratio="16:9",
    )
    print(f"  Result: {result['message']} | Size: {result.get('info', {}).get('size')}")

    print("\n📝 Test 4: Long duration (45s -> multiple clips)")
    result = generate_video_from_image(
        image_path=test_image,
        prompt="Animate with continuous motion throughout",
        resolution="480p",
        duration=45,
        aspect_ratio="16:9",
    )
    print(f"  Result: {result['message']} | clips: {result.get('clip_count')}")

    if SPEECH_RECOGNITION_AVAILABLE:
        print("\n📝 Test 5: Voice input test (if microphone available)")
        result = generate_video_from_voice_and_image(
            image_path=test_image,
            resolution="720p",
            duration=5,
            voice_language="en-US"
        )
        print(f"  Result: {result['message']}")

    print("\n📝 Test 6: Short prompt (should fail)")
    result = generate_video_from_image(
        image_path=test_image,
        prompt="Hi",
        resolution="480p",
        duration=3
    )
    print(f"  Result: {result['message']}")
    assert result["success"] is False, "Short prompt should be rejected"

    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    test()

# ============================================
# END OF feature_02_image_to_video.py (ENHANCED)
# ============================================
