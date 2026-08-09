# ============================================================
# FEATURE 22 — FRAME-TO-FRAME CONTROL
# ============================================================
# LTX 2.3 image-to-video endpoint supports `last_frame_uri`: give it a FIRST
# frame (image_uri) and a LAST frame (last_frame_uri), and the model
# generates everything in between. ONLY supported by ltx-2-3-fast /
# ltx-2-3-pro (not older ltx-2 models — those are deprecated anyway).
#
# CHANGE LOG (frame/duration fix):
# - Requested `duration` is now clamped via frame_policy.get_valid_duration()
#   using this model's rule (Admin Panel -> Frame Rules), instead of being
#   sent to LTX unchecked.
# ============================================================

import os
import time
import requests

try:
    import config
    LTX_API_KEY = getattr(config, "LTX_API_KEY", "")
    LTX_BASE_URL = getattr(config, "LTX_BASE_URL", "https://api.ltx.video")
    PATHS = getattr(config, "PATHS", {"temp": "temp", "output": "output"})
except ImportError:
    LTX_API_KEY = os.environ.get("LTX_API_KEY", "")
    LTX_BASE_URL = "https://api.ltx.video"
    PATHS = {"temp": "temp", "output": "output"}

import frame_policy

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

VALID_MODELS = ("ltx-2-3-fast", "ltx-2-3-pro")


def generate_frame_interpolation(first_frame_path, last_frame_path, prompt,
                                  model="ltx-2-3-pro", duration=5,
                                  resolution="1920x1080", apply_watermark=True,
                                  generate_audio=True):
    if model not in VALID_MODELS:
        return {"success": False, "message": f"❌ Frame interpolation only works with {VALID_MODELS}."}
    if not first_frame_path or not os.path.exists(first_frame_path):
        return {"success": False, "message": "❌ First frame image not found."}
    if not last_frame_path or not os.path.exists(last_frame_path):
        return {"success": False, "message": "❌ Last frame image not found."}
    if not prompt or len(prompt.strip()) < 3:
        return {"success": False, "message": "❌ Prompt required (describe the motion between frames)."}

    # Clamp duration to this model's configured range (Admin Panel -> Frame
    # Rules) instead of trusting the caller blindly.
    original_duration = duration
    duration = frame_policy.get_valid_duration(model, duration)
    if duration != original_duration:
        print(f"  [frame_policy] {model}: requested {original_duration}s clamped to {duration}s")

    if DRY_RUN:
        return {"success": True, "message": f"[DRY_RUN] Would interpolate {first_frame_path} -> {last_frame_path}",
                "video_path": os.path.join(PATHS.get("output", "output"), "dry_run_frame_interp.mp4")}

    if not LTX_API_KEY:
        return {"success": False, "message": "❌ LTX_API_KEY not set in config.py."}

    try:
        first_uri = _upload_to_ltx(first_frame_path)
        last_uri = _upload_to_ltx(last_frame_path)
        if not first_uri or not last_uri:
            return {"success": False, "message": "❌ Failed to upload one or both frames to LTX."}

        payload = {
            "image_uri": first_uri,
            "last_frame_uri": last_uri,
            "prompt": prompt,
            "model": model,
            "duration": duration,
            "resolution": resolution,
            "generate_audio": generate_audio,
        }
        headers = {"Authorization": f"Bearer {LTX_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(f"{LTX_BASE_URL}/v1/image-to-video", json=payload, headers=headers, timeout=300)
        resp.raise_for_status()

        out_path = os.path.join(PATHS.get("output", "output"), f"frame_interp_{int(time.time())}.mp4")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(resp.content)

        if apply_watermark:
            try:
                import feature_08_watermark as feat08
                wm_result = feat08.add_text_watermark_ffmpeg(out_path, "Filmaa", "bottom-right", 24, "#FFFFFF", 0.7)
                if wm_result.get("success"):
                    out_path = wm_result["video_path"]
            except Exception:
                pass

        return {"success": True, "message": "✅ Frame-to-frame video generated.", "video_path": out_path}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"❌ LTX API error: {e}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Unexpected error: {e}"}


def _upload_to_ltx(local_path):
    headers = {"Authorization": f"Bearer {LTX_API_KEY}"}
    with open(local_path, "rb") as f:
        resp = requests.post(f"{LTX_BASE_URL}/v1/upload", headers=headers, files={"file": f}, timeout=120)
    resp.raise_for_status()
    return resp.json().get("uri") or resp.json().get("url")


if __name__ == "__main__":
    os.environ["FILMAA_DRY_RUN"] = "1"
    print(generate_frame_interpolation("frame_a.jpg", "frame_b.jpg", "Smooth transition, camera holds steady"))