# ============================================================
# FEATURE 21 — CAMERA MOTION CONTROL (2K / 4K)
# ============================================================
# LTX 2.3 text-to-video and image-to-video endpoints both accept a
# `camera_motion` enum parameter, and support resolution up to 4K
# (3840x2160) at 20 seconds max duration.
#
# ⚠️ IMPORTANT: LTX's docs page confirms `camera_motion` is an enum but does
# NOT publicly list the exact accepted string values on the page I could
# read. The list below (CAMERA_MOTIONS) are the industry-standard terms
# LTX Studio's marketing pages reference (pan/zoom/dolly/orbit/static).
# BEFORE relying on this in production: hit LTX's console/playground once,
# open dev tools on a manual generation, and confirm the exact enum strings
# it sends — then update CAMERA_MOTIONS below to match exactly. Do not ship
# to client without this one verification step (5 minutes, saves debugging
# later).
#
# CHANGE LOG (frame/duration fix):
# - Requested `duration` is now clamped via frame_policy.get_valid_duration()
#   using this model's rule (Admin Panel -> Frame Rules), instead of being
#   sent to LTX unchecked. If LTX's max/min duration ever changes, update it
#   in the admin panel — no code change needed here.
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

# ⚠️ VERIFY against LTX console before production use (see note above)
CAMERA_MOTIONS = {
    "static":      "No camera movement",
    "pan_left":    "Pan left",
    "pan_right":   "Pan right",
    "zoom_in":     "Zoom in",
    "zoom_out":    "Zoom out",
    "dolly_in":    "Dolly in (move toward subject)",
    "dolly_out":   "Dolly out (move away from subject)",
    "orbit_left":  "Orbit left around subject",
    "orbit_right": "Orbit right around subject",
    "crane_up":    "Crane up",
    "crane_down":  "Crane down",
}

RESOLUTION_2K_4K = {
    "2k": "2560x1440",
    "4k": "3840x2160",
}


def generate_with_camera_motion(prompt, camera_motion, resolution="4k", duration=8,
                                 model="ltx-2-3-pro", image_uri_local_path=None,
                                 apply_watermark=True, generate_audio=True):
    """
    prompt: scene description
    camera_motion: one of CAMERA_MOTIONS keys
    resolution: "2k" or "4k" (or pass a raw "WIDTHxHEIGHT" string directly)
    image_uri_local_path: optional — if given, uses image-to-video (animates that image
        with the requested camera motion) instead of pure text-to-video.
    """
    if camera_motion not in CAMERA_MOTIONS:
        return {"success": False, "message": f"❌ Unknown camera_motion '{camera_motion}'. Options: {list(CAMERA_MOTIONS)}"}
    if not prompt or len(prompt.strip()) < 3:
        return {"success": False, "message": "❌ Prompt required."}

    resolved_res = RESOLUTION_2K_4K.get(resolution, resolution)

    # Clamp duration to this model's configured range (Admin Panel -> Frame
    # Rules) instead of trusting the caller / UI slider blindly.
    original_duration = duration
    duration = frame_policy.get_valid_duration(model, duration)
    if duration != original_duration:
        print(f"  [frame_policy] {model}: requested {original_duration}s clamped to {duration}s")

    if DRY_RUN:
        return {"success": True,
                "message": f"[DRY_RUN] camera_motion={camera_motion} @ {resolved_res}",
                "video_path": os.path.join(PATHS.get("output", "output"), "dry_run_camera_motion.mp4")}

    if not LTX_API_KEY:
        return {"success": False, "message": "❌ LTX_API_KEY not set in config.py."}

    endpoint = "/v1/text-to-video"
    payload = {
        "prompt": prompt,
        "model": model,
        "duration": duration,
        "resolution": resolved_res,
        "camera_motion": camera_motion,
        "generate_audio": generate_audio,
    }

    try:
        if image_uri_local_path:
            if not os.path.exists(image_uri_local_path):
                return {"success": False, "message": "❌ Reference image not found."}
            uploaded_uri = _upload_to_ltx(image_uri_local_path)
            if not uploaded_uri:
                return {"success": False, "message": "❌ Failed to upload reference image."}
            payload["image_uri"] = uploaded_uri
            endpoint = "/v1/image-to-video"

        headers = {"Authorization": f"Bearer {LTX_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(f"{LTX_BASE_URL}{endpoint}", json=payload, headers=headers, timeout=300)
        resp.raise_for_status()

        out_path = os.path.join(PATHS.get("output", "output"), f"camera_motion_{int(time.time())}.mp4")
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

        return {"success": True, "message": f"✅ {resolution.upper()} video generated with '{camera_motion}' camera motion.",
                "video_path": out_path}
    except requests.exceptions.RequestException as e:
        # 422 here most likely means the camera_motion string doesn't match LTX's real enum —
        # see the verification note at the top of this file.
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
    print(generate_with_camera_motion("A car driving through a desert at sunset", "dolly_in", resolution="4k"))