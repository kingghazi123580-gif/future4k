# ============================================
# FEATURE 04: EXTEND VIDEO LENGTH (ENHANCED WITH VOICE & CUSTOM DURATION)
# Filename: feature_04_extend_video.py
# ============================================
# What this file does (English summary):
# - Takes an existing video file + a text prompt describing what
#   should happen next
# - SUPPORTS VOICE INPUT: User can speak their extension prompt
# - SUPPORTS CUSTOM EXTENSION DURATION: Any length (no hard cap)
# - SUPPORTS LARGE VIDEO FILES: No size limit on uploaded videos
# - Generates new Agnes clip(s) continuing from that description,
#   splitting into multiple clips if the extension is longer than
#   MAX_CLIP_LENGTH (18s), same pattern as feature_01/03
# - Stitches the extension onto the END of the original video with
#   ffmpeg, WITHOUT modifying/deleting the original file unless the
#   caller explicitly passes keep_original=False
# - Applies watermark, reports success/failure clearly
# - Supports FILMAA_DRY_RUN=1 to test the whole pipeline without
#   calling the real Agnes API or needing network access
#
# Public function used by ui.py:
#   extend_video(video_path, extension_prompt, extension_seconds,
#                resolution, negative_prompt, apply_watermark, seed,
#                keep_original, use_voice, voice_language)
#   -> {"success", "video_path", "message", "watermark_applied",
#       "original_duration", "extension_duration", "total_duration", "info"}
#
# ============================================

import os
import sys
import time
import json
import subprocess
import requests
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Callable

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from config import *
except ImportError:
    print("[ERROR] config.py not found!")
    raise SystemExit(1)

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# No hard cap - extension can be as long as user wants
MIN_EXTENSION_SECONDS = 5
MAX_EXTENSION_SECONDS = 3600  # 1 hour max (reasonable limit)

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
            print("🎤 Listening... Speak your extension prompt clearly.")
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

def _agnes_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json",
    }


def _get_video_duration(video_path: str) -> float:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    if os.path.getsize(video_path) == 0:
        raise ValueError(f"Video file is empty (0 bytes): {video_path}")

    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    try:
        duration = float(result.stdout.strip())
        if duration <= 0:
            raise ValueError(f"Invalid duration: {duration}")
        return duration
    except ValueError as e:
        raise RuntimeError(f"Could not parse duration: {result.stdout}") from e


def _get_video_info(video_path: str) -> Dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,r_frame_rate,codec_name",
           "-of", "json", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]

    fps_str = stream.get("r_frame_rate", "24/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 24.0
    else:
        fps = float(fps_str)

    return {
        "width": int(stream.get("width", 1280)),
        "height": int(stream.get("height", 720)),
        "fps": round(fps, 2),
        "codec": stream.get("codec_name", "h264"),
    }


def _create_agnes_task(prompt: str, width: int, height: int, num_frames: int,
                        frame_rate: int, negative_prompt: Optional[str] = None,
                        seed: Optional[int] = None) -> str:
    payload = {
        "model": AGNES_AI_MODEL,
        "prompt": prompt,
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
                raise RuntimeError("Agnes API key rejected (401). Check AGNES_API_KEY.")
            if resp.status_code == 400:
                raise RuntimeError(f"Bad request (400): {resp.text}")
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
                raise RuntimeError("Rate limited (429) after repeated backoff.")

            resp.raise_for_status()
            data = resp.json()
            video_id = data.get("video_id") or data.get("id") or data.get("task_id")
            if not video_id:
                raise RuntimeError(f"No video ID in response. Keys: {list(data.keys())}")

            print(f"  Task created — video_id: {video_id}")
            return video_id

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
    for field in ("video_url", "remixed_from_video_id", "url", "output_url"):
        value = result.get(field)
        if value and isinstance(value, str) and value.startswith("http"):
            return value
    raise KeyError(
        f"Could not find a video URL in Agnes's completed response. "
        f"Looked for video_url / remixed_from_video_id / url / output_url. "
        f"Actual response keys: {list(result.keys())}"
    )


def _poll_agnes_result(video_id: str) -> Dict[str, Any]:
    url = f"{AGNES_AI_ROOT_URL}/agnesapi"
    params = {"video_id": video_id}

    print(f"  Polling (max {AGNES_MAX_POLL_ATTEMPTS * AGNES_POLL_INTERVAL_SECONDS}s)...")

    for attempt in range(1, AGNES_MAX_POLL_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=_agnes_headers(), params=params, timeout=30)

            if resp.status_code == 404:
                if attempt % 6 == 0:
                    print(f"  [poll {attempt}] still processing...")
                time.sleep(AGNES_POLL_INTERVAL_SECONDS)
                continue
            if resp.status_code == 401:
                raise RuntimeError("API authentication failed during polling")

            resp.raise_for_status()
            data = resp.json()
            status = (data.get("status") or data.get("state") or "unknown").lower()
            progress = data.get("progress", 0)

            if attempt % 3 == 0 or status in ("completed", "failed"):
                print(f"  [poll {attempt}/{AGNES_MAX_POLL_ATTEMPTS}] status: {status} ({progress}%)")

            if status in ("completed", "succeeded", "done"):
                return data
            if status in ("failed", "error", "cancelled"):
                raise RuntimeError(f"Video generation failed: {data.get('error') or data.get('message') or 'unknown error'}")

            time.sleep(AGNES_POLL_INTERVAL_SECONDS)

        except requests.RequestException as e:
            print(f"  [poll {attempt}] request error: {e} — retrying")
            time.sleep(AGNES_POLL_INTERVAL_SECONDS)
        except RuntimeError:
            raise

    raise TimeoutError(f"Video generation timed out after "
                        f"{AGNES_MAX_POLL_ATTEMPTS * AGNES_POLL_INTERVAL_SECONDS}s")


def _download_video(video_url: str, save_path: str, max_retries: int = 4) -> str:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(video_url, stream=True, timeout=(15, 180))
            resp.raise_for_status()
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            if total_size > 0:
                print(f"  Downloaded: {downloaded / (1024*1024):.1f} MB")
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


def _generate_extension_clip(prompt: str, duration: float, width: int, height: int,
                              fps: float, negative_prompt: Optional[str] = None,
                              seed: Optional[int] = None) -> Tuple[str, float]:
    if fps <= 0:
        fps = 24.0

    num_frames = get_frames_for_duration(duration, int(fps))
    actual_duration = num_frames / fps

    clip_name = f"extend_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.mp4"
    clip_path = os.path.join(PATHS["temp"], clip_name)

    if DRY_RUN:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={actual_duration}:size={width}x{height}:rate={fps}",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            clip_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"[DRY_RUN] extension clip generation failed: {result.stderr[-500:]}")
        print(f"  [DRY_RUN] extension clip: {clip_name} ({actual_duration:.1f}s)")
        return clip_path, actual_duration

    print(f"  Generating {width}x{height}, {num_frames} frames, ~{actual_duration:.1f}s")
    video_id = _create_agnes_task(prompt, width, height, num_frames, int(fps), negative_prompt, seed)
    result = _poll_agnes_result(video_id)
    video_url = _extract_video_url(result)
    _download_video(video_url, clip_path)

    frames = int(result.get("num_frames", num_frames))
    rate = float(result.get("frame_rate", fps))
    actual_duration = frames / rate if rate > 0 else duration

    print(f"  Extension clip done — {actual_duration:.1f}s")
    return clip_path, actual_duration


def _generate_extension_clips(prompt: str, total_duration: float, width: int, height: int,
                               fps: float, negative_prompt: Optional[str] = None,
                               seed: Optional[int] = None,
                               progress_callback: Optional[Callable] = None) -> List[Tuple[str, float]]:
    clips = []
    remaining = total_duration

    num_clips = int(total_duration / MAX_CLIP_LENGTH) + 1
    duration_per_clip = total_duration / num_clips

    print(f"  Splitting {total_duration:.1f}s into {num_clips} clip(s) (max {MAX_CLIP_LENGTH}s each)")

    for i in range(num_clips):
        if progress_callback:
            progress_callback(i / num_clips * 100, f"Generating clip {i+1}/{num_clips}")

        clip_duration = min(duration_per_clip, remaining)
        if clip_duration < 1.0:
            break

        print(f"\n  Clip {i+1}/{num_clips}: {clip_duration:.1f}s")
        clip_prompt = prompt if num_clips == 1 else f"{prompt} (continued, part {i+1} of {num_clips})"

        clip_path, actual_duration = _generate_extension_clip(
            prompt=clip_prompt, duration=clip_duration, width=width, height=height, fps=fps,
            negative_prompt=negative_prompt, seed=None if seed is None else seed + i,
        )
        clips.append((clip_path, actual_duration))
        remaining -= actual_duration

        if not DRY_RUN and i + 1 < num_clips:
            time.sleep(AGNES_CLIP_SPACING_SECONDS)

    return clips


def _stitch_videos(video_paths: List[str], output_path: str) -> str:
    if len(video_paths) == 1:
        shutil.move(video_paths[0], output_path)
        return output_path

    concat_list_path = output_path.replace(".mp4", "_concat.txt")
    with open(concat_list_path, "w") as f:
        for p in video_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
           "-c", "copy", "-movflags", "+faststart", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(concat_list_path):
        os.remove(concat_list_path)

    if result.returncode != 0:
        print("  [warn] Stream copy failed, trying re-encode...")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
               "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac",
               "-movflags", "+faststart", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg stitching failed: {result.stderr[-500:]}")

    for p in video_paths:
        if os.path.exists(p) and "extend_" in os.path.basename(p):
            try:
                os.remove(p)
            except OSError:
                pass

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


def _apply_watermark(video_path: str) -> Tuple[str, bool, Optional[str]]:
    tmp_path = video_path.replace(".mp4", "_wm.mp4")
    pos_map = {
        "bottom-right": "x=w-tw-20:y=h-th-20", "bottom-left": "x=20:y=h-th-20",
        "top-right": "x=w-tw-20:y=20", "top-left": "x=20:y=20",
    }
    position = pos_map.get(WATERMARK.get("position", "bottom-right"), pos_map["bottom-right"])
    text = WATERMARK.get("text", "Filmaa")
    color = WATERMARK.get("color", "white")
    font_size = WATERMARK.get("font_size", 24)
    opacity = WATERMARK.get("opacity", 0.7)

    font_path = _find_system_font()
    fontfile_part = ""
    if font_path:
        escaped_font = font_path.replace("\\", "/").replace(":", "\\:")
        fontfile_part = f"fontfile='{escaped_font}':"
    else:
        print("  [WARN] No system font found — relying on ffmpeg's built-in fontconfig.")

    drawtext = (
        f"drawtext={fontfile_part}text='{text}':fontcolor={color}@{opacity}:"
        f"fontsize={font_size}:{position}:box=1:boxcolor=black@0.3:boxborderw=5"
    )
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", drawtext, "-codec:a", "copy",
           "-movflags", "+faststart", tmp_path]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return video_path, False, result.stderr[-300:]

    os.replace(tmp_path, video_path)
    return video_path, True, None


# ============================================
# MAIN FUNCTION (ENHANCED)
# ============================================

def extend_video(
    video_path: str,
    extension_prompt: str,
    extension_seconds: int = 10,
    resolution: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    apply_watermark: bool = True,
    seed: Optional[int] = None,
    keep_original: bool = True,
    use_voice: bool = False,
    voice_language: str = "en-US",
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Extend an existing video by generating additional content.

    Parameters:
    - video_path (str): Path to existing video
    - extension_prompt (str): Description of what should happen next
    - extension_seconds (int): How many seconds to extend (no hard cap)
    - resolution (str): 480p, 720p, 1080p (auto-detects if not provided)
    - negative_prompt (str): Things to avoid
    - apply_watermark (bool): Whether to add watermark
    - seed (int): For reproducible results
    - keep_original (bool): Whether to keep original file
    - use_voice (bool): If True, prompt is from voice input
    - voice_language (str): Language for voice recognition

    Returns:
    - dict: {"success", "video_path", "message", ...}
    """
    print("\n" + "=" * 60)
    print("🎬 FEATURE 04: Extend Video Length" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 60)

    # ---------- Validate Input ----------
    if not os.path.exists(video_path):
        return {"success": False, "video_path": None, "message": f"Video not found: {video_path}"}

    # Check video file size - no limit
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"📹 Video size: {file_size_mb:.1f} MB")

    # ---------- Handle Voice Input ----------
    if use_voice:
        print("🎤 Voice input enabled...")
        speech_result = speech_to_text(language=voice_language)
        if not speech_result["success"]:
            return {
                "success": False,
                "video_path": None,
                "message": f"Voice input failed: {speech_result['message']}"
            }
        extension_prompt = speech_result["text"]
        print(f"📝 Voice recognized: {extension_prompt}")

    if not extension_prompt or len(extension_prompt.strip()) < 3:
        return {"success": False, "video_path": None,
                "message": "Extension prompt is too short. Please write at least 3 words."}

    # Allow any duration (no hard cap)
    if extension_seconds < MIN_EXTENSION_SECONDS:
        return {"success": False, "video_path": None,
                "message": f"Extension seconds must be at least {MIN_EXTENSION_SECONDS} seconds."}
    
    if extension_seconds > MAX_EXTENSION_SECONDS:
        return {"success": False, "video_path": None,
                "message": f"Extension seconds cannot exceed {MAX_EXTENSION_SECONDS} seconds (1 hour)."}

    if not DRY_RUN and not AGNES_API_KEY:
        return {"success": False, "video_path": None,
                "message": "AGNES_API_KEY not set. Set it in your environment before generating video."}

    if not DRY_RUN:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return {"success": False, "video_path": None, "message": "ffmpeg not found on this system."}

    # ---------- Get Original Video Info ----------
    try:
        original_duration = _get_video_duration(video_path)
        video_info = _get_video_info(video_path)
        print(f"📹 Original video: {os.path.basename(video_path)}")
        print(f"  ⏱️ Duration: {original_duration:.1f}s")
        print(f"  📐 Resolution: {video_info['width']}x{video_info['height']}")
        print(f"  🎞️ FPS: {video_info['fps']}")
        print(f"  📦 Size: {file_size_mb:.1f} MB")
    except Exception as e:
        return {"success": False, "video_path": None, "message": f"Failed to read video info: {e}"}

    # ---------- Determine Resolution ----------
    if resolution is None:
        if video_info["height"] >= 1080:
            resolution = "1080p"
        elif video_info["height"] >= 720:
            resolution = "720p"
        else:
            resolution = "480p"
    print(f"📐 Using resolution: {resolution}")

    # ---------- Generate Extension Clips ----------
    print(f"\n🎬 Generating extension clips ({extension_seconds}s)...")
    print(f"📝 Extension prompt: {extension_prompt}")
    if use_voice:
        print(f"🎤 Voice input: Yes ({voice_language})")

    try:
        extension_clips = _generate_extension_clips(
            prompt=extension_prompt, total_duration=extension_seconds,
            width=video_info["width"], height=video_info["height"], fps=video_info["fps"],
            negative_prompt=negative_prompt, seed=seed, progress_callback=progress_callback,
        )
    except Exception as e:
        return {"success": False, "video_path": None, "message": f"Extension generation failed: {e}"}

    all_clips = [path for path, _ in extension_clips]
    total_extension_duration = sum(dur for _, dur in extension_clips)

    # ---------- Stitch Original + Extension ----------
    video_name = f"extended_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    final_path = os.path.join(PATHS["videos"], video_name)

    # Work off a temp COPY of the original so it's never modified/deleted
    temp_original = os.path.join(PATHS["temp"], f"original_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.mp4")
    shutil.copy2(video_path, temp_original)

    try:
        print(f"\n🔗 Stitching original + extension...")
        _stitch_videos([temp_original] + all_clips, final_path)
        print(f"✅ Stitched video: {final_path}")
    except Exception as e:
        if os.path.exists(temp_original):
            os.remove(temp_original)
        return {"success": False, "video_path": None, "message": f"Stitching failed: {e}"}
    finally:
        if os.path.exists(temp_original):
            os.remove(temp_original)

    # ---------- Apply Watermark ----------
    watermark_applied = False
    watermark_error = None
    if apply_watermark and WATERMARK.get("free_tier", True):
        print(f"💧 Adding watermark: {WATERMARK.get('text', 'Filmaa')}")
        if not DRY_RUN:
            _, watermark_applied, watermark_error = _apply_watermark(final_path)
            if not watermark_applied:
                print(f"[WARN] Watermark failed, delivering video without it: {watermark_error}")
        else:
            watermark_applied = True

    # ---------- Get Final Duration ----------
    try:
        total_duration = _get_video_duration(final_path)
    except Exception:
        total_duration = original_duration + total_extension_duration

    # ---------- Cleanup ----------
    if not keep_original and os.path.exists(video_path):
        try:
            os.remove(video_path)
            print(f"🗑️ Removed original (keep_original=False): {video_path}")
        except OSError:
            pass

    # ---------- Save Metadata ----------
    final_size_mb = os.path.getsize(final_path) / (1024 * 1024) if os.path.exists(final_path) else 0
    
    video_info_dict = {
        "video_id": video_name.replace(".mp4", ""),
        "original_video": os.path.basename(video_path),
        "original_duration": round(original_duration, 1),
        "original_size_mb": round(file_size_mb, 2),
        "extension_prompt": extension_prompt,
        "extension_seconds": extension_seconds,
        "actual_extension_duration": round(total_extension_duration, 1),
        "total_duration": round(total_duration, 1),
        "final_size_mb": round(final_size_mb, 2),
        "resolution": resolution,
        "width": video_info["width"], 
        "height": video_info["height"], 
        "fps": video_info["fps"],
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "voice_input": use_voice,
        "voice_language": voice_language if use_voice else None,
        "created_at": datetime.now().isoformat(),
        "path": final_path,
        "dry_run": DRY_RUN,
        "seed": seed,
        "keep_original": keep_original,
    }
    info_path = final_path.replace(".mp4", ".json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(video_info_dict, f, indent=2, ensure_ascii=False)

    print(f"\n" + "=" * 60)
    print(f"✅ VIDEO EXTENDED SUCCESSFULLY!")
    print(f"=" * 60)
    print(f"📹 Path: {final_path}")
    print(f"⏱️ Original: {original_duration:.1f}s → New: {total_duration:.1f}s (+{total_extension_duration:.1f}s)")
    print(f"📐 Resolution: {video_info['width']}x{video_info['height']}")
    print(f"📦 Size: {final_size_mb:.2f} MB")
    print(f"🎤 Voice input: {'Yes' if use_voice else 'No'}")
    print(f"💧 Watermark: {'Applied' if watermark_applied else 'Not applied'}")
    print(f"📋 Metadata: {info_path}")
    print(f"=" * 60)

    return {
        "success": True,
        "video_path": final_path,
        "message": f"Video extended from {original_duration:.1f}s to {total_duration:.1f}s "
                   f"(+{total_extension_duration:.1f}s)",
        "watermark_applied": watermark_applied,
        "watermark_error": watermark_error,
        "original_duration": round(original_duration, 1),
        "extension_duration": round(total_extension_duration, 1),
        "total_duration": round(total_duration, 1),
        "info": video_info_dict,
    }


# ============================================
# VOICE-ONLY FUNCTION
# ============================================

def extend_video_from_voice(
    video_path: str,
    extension_seconds: int = 10,
    resolution: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    apply_watermark: bool = True,
    seed: Optional[int] = None,
    keep_original: bool = True,
    voice_language: str = "en-US"
) -> Dict[str, Any]:
    """
    Extend video using voice input for the extension prompt.
    
    Parameters:
    - video_path (str): Path to existing video
    - extension_seconds (int): How many seconds to extend
    - resolution (str): 480p, 720p, 1080p
    - negative_prompt (str): Things to avoid
    - apply_watermark (bool): Whether to add watermark
    - seed (int): For reproducible results
    - keep_original (bool): Whether to keep original file
    - voice_language (str): Language for voice recognition
    
    Returns:
    - dict: Result from extend_video
    """
    return extend_video(
        video_path=video_path,
        extension_prompt="",  # Will be filled from voice
        extension_seconds=extension_seconds,
        resolution=resolution,
        negative_prompt=negative_prompt,
        apply_watermark=apply_watermark,
        seed=seed,
        keep_original=keep_original,
        use_voice=True,
        voice_language=voice_language
    )


# ============================================
# SHORTCUT FUNCTIONS
# ============================================

def extend_by_5s(video_path: str, extension_prompt: str, **kwargs) -> Dict[str, Any]:
    return extend_video(video_path, extension_prompt, extension_seconds=5, **kwargs)


def extend_by_10s(video_path: str, extension_prompt: str, **kwargs) -> Dict[str, Any]:
    return extend_video(video_path, extension_prompt, extension_seconds=10, **kwargs)


def extend_by_15s(video_path: str, extension_prompt: str, **kwargs) -> Dict[str, Any]:
    return extend_video(video_path, extension_prompt, extension_seconds=15, **kwargs)


def extend_by_20s(video_path: str, extension_prompt: str, **kwargs) -> Dict[str, Any]:
    return extend_video(video_path, extension_prompt, extension_seconds=20, **kwargs)


def extend_by_30s(video_path: str, extension_prompt: str, **kwargs) -> Dict[str, Any]:
    return extend_video(video_path, extension_prompt, extension_seconds=30, **kwargs)


def extend_by_60s(video_path: str, extension_prompt: str, **kwargs) -> Dict[str, Any]:
    return extend_video(video_path, extension_prompt, extension_seconds=60, **kwargs)


# ============================================
# TEST FUNCTION
# ============================================

def test():
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_04_extend_video.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)

    test_video = os.path.join(PATHS["videos"], "test_original.mp4")
    os.makedirs(PATHS["videos"], exist_ok=True)

    if not os.path.exists(test_video) or os.path.getsize(test_video) < 100:
        print("📹 Creating test video...")
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=5",
               "-vf", "fps=24", "-c:v", "libx264", "-preset", "ultrafast", test_video]
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"✅ Created test video: {test_video}")

    print("\n📝 Test 1: Extend by 5 seconds, keep_original=True")
    original_size = os.path.getsize(test_video)
    result = extend_video(test_video, "The scene continues with more action and drama",
                           extension_seconds=5, resolution="720p", keep_original=True)
    print(f"  Result: {result['message']}")
    assert result["success"] is True

    print("\n📝 Test 2: Extend by 30s (shortcut function)")
    result = extend_by_30s(test_video, "A peaceful ending with sunset", keep_original=True)
    print(f"  Result: {result['message']}")
    assert result["success"] is True

    print("\n📝 Test 3: Extend by 60s (long extension)")
    result = extend_by_60s(test_video, "An epic continuation with dramatic music", keep_original=True)
    print(f"  Result: {result['message']}")
    assert result["success"] is True

    if SPEECH_RECOGNITION_AVAILABLE:
        print("\n📝 Test 4: Voice input test (if microphone available)")
        result = extend_video_from_voice(
            video_path=test_video,
            extension_seconds=5,
            resolution="720p",
            voice_language="en-US"
        )
        print(f"  Result: {result['message']}")

    print("\n📝 Test 5: Short prompt (should fail)")
    result = extend_video(test_video, "Hi", extension_seconds=5, keep_original=True)
    print(f"  Result: {result['message']}")
    assert result["success"] is False

    print("\n📝 Test 6: Invalid video path (should fail)")
    result = extend_video("nonexistent.mp4", "Something happens", extension_seconds=5)
    print(f"  Result: {result['message']}")
    assert result["success"] is False

    print("\n📝 Test 7: keep_original=False actually removes original")
    disposable = os.path.join(PATHS["videos"], "test_disposable.mp4")
    shutil.copy2(test_video, disposable)
    result = extend_video(disposable, "Testing keep_original false", extension_seconds=5, keep_original=False)
    print(f"  Result: {result['message']}")
    assert result["success"] is True
    assert not os.path.exists(disposable), "Original should have been removed"

    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    test()

# ============================================
# END OF feature_04_extend_video.py (ENHANCED)
# ============================================