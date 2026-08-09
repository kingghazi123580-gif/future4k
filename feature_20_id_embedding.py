# ============================================================
# FEATURE 20 — ID-EMBEDDING / CHARACTER CONSISTENCY
# ============================================================
# HOW CONSISTENCY IS ACTUALLY ACHIEVED (read before using):
#
# LTX 2.3 has NO dedicated "ID-embedding" endpoint. Consistency comes from
# image-to-video reference conditioning (image_uri) — the model preserves
# the visual identity of whatever image you feed it. Good for ONE character,
# ONE reference image, single clip.
# WAN 2.6 Pro DOES have a purpose-built endpoint for this: Reference-to-Video
# (R2V). You upload 1-3 short reference videos (or stills), each showing one
# character, and refer to them in the prompt as "character1", "character2",
# "character3". WAN extracts appearance (and voice, if audio present) and
# keeps it stable across the new generation. This is the stronger option
# for multi-character consistency and is what this module defaults to.
#
# CHANGE LOG (frame/duration-count fix):
# - The old hardcoded check `if duration not in (5, 10): return error` is
#   replaced with frame_policy.get_valid_duration("wan-2.6-r2v", duration),
#   which snaps the requested duration to the nearest allowed value instead
#   of just rejecting it. WAN's allowed duration list now lives in the
#   Admin Panel -> Frame Rules tab, not hardcoded here.
# - LTX's duration is similarly clamped via frame_policy using the model
#   name, so future LTX duration limits can be updated without touching
#   this file.
#
# Standalone module. Test with DRY_RUN=1 before wiring into app.py.
# ============================================================

import os
import time
import requests

try:
    import config
    LTX_API_KEY = getattr(config, "LTX_API_KEY", "")
    LTX_BASE_URL = getattr(config, "LTX_BASE_URL", "https://api.ltx.video")
    WAN_API_KEY = getattr(config, "WAN_API_KEY", "")
    WAN_BASE_URL = getattr(config, "WAN_BASE_URL", "https://fal.run")
    PATHS = getattr(config, "PATHS", {"temp": "temp", "output": "output"})
except ImportError:
    LTX_API_KEY = os.environ.get("LTX_API_KEY", "")
    LTX_BASE_URL = "https://api.ltx.video"
    WAN_API_KEY = os.environ.get("WAN_API_KEY", "")
    WAN_BASE_URL = "https://fal.run"
    PATHS = {"temp": "temp", "output": "output"}

import frame_policy

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"


# ------------------------------------------------------------
# WAN 2.6 R2V — multi-character consistency (recommended path)
# ------------------------------------------------------------
def generate_with_character_wan(prompt, reference_paths, resolution="1080p",
                                 duration=10, apply_watermark=True, seed=None):
    """
    reference_paths: list of 1-3 local file paths (video or image), each ONE character.
    In `prompt`, refer to them as character1 / character2 / character3, e.g.:
        "character1 sings on the roadside while character2 dances beside them."
    """
    if not reference_paths or len(reference_paths) > 3:
        return {"success": False, "message": "❌ Provide 1 to 3 reference files (one character each)."}
    if not prompt or len(prompt.strip()) < 3:
        return {"success": False, "message": "❌ Prompt required."}

    # Snap requested duration to WAN's allowed list (Admin Panel -> Frame Rules).
    # Previously this hard-rejected anything except exactly 5 or 10 — now it
    # auto-corrects to the nearest allowed value, driven by config not code.
    original_duration = duration
    duration = frame_policy.get_valid_duration("wan-2.6-r2v", duration)
    if duration != original_duration:
        print(f"  [frame_policy] WAN 2.6 R2V: requested {original_duration}s snapped to {duration}s")

    if DRY_RUN:
        return {"success": True, "message": f"[DRY_RUN] WAN R2V would run with {len(reference_paths)} refs.",
                "video_path": os.path.join(PATHS.get("output", "output"), "dry_run_wan_r2v.mp4")}

    if not WAN_API_KEY:
        return {"success": False, "message": "❌ WAN_API_KEY not set in config.py."}

    try:
        # fal.ai expects reference files as public/uploaded URLs, not raw bytes.
        # Upload each local file first via fal's storage endpoint.
        ref_urls = []
        for path in reference_paths:
            uploaded = _upload_to_fal(path)
            if not uploaded:
                return {"success": False, "message": f"❌ Failed to upload reference file: {path}"}
            ref_urls.append(uploaded)

        payload = {
            "prompt": prompt,
            "reference_video_urls": ref_urls,  # confirm exact field name against your fal model page before first run
            "resolution": resolution,
            "duration": duration,
            "seed": seed,
        }
        headers = {"Authorization": f"Key {WAN_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(f"{WAN_BASE_URL}/wan/v2.6/reference-to-video", json=payload, headers=headers, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        video_url = data.get("video", {}).get("url") or data.get("video_url")
        if not video_url:
            return {"success": False, "message": f"❌ No video URL in response: {data}"}

        out_path = _download_video(video_url, "wan_r2v")
        if apply_watermark:
            try:
                import feature_08_watermark as feat08
                wm_result = feat08.add_text_watermark_ffmpeg(out_path, "Filmaa", "bottom-right", 24, "#FFFFFF", 0.7)
                if wm_result.get("success"):
                    out_path = wm_result["video_path"]
            except Exception:
                pass
        return {"success": True, "message": "✅ Character-consistent video generated (WAN 2.6 R2V).", "video_path": out_path}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"❌ WAN API error: {e}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Unexpected error: {e}"}


# ------------------------------------------------------------
# LTX 2.3 — single-character consistency via image conditioning
# ------------------------------------------------------------
def generate_with_character_ltx(prompt, reference_image_path, model="ltx-2-3-pro",
                                 resolution="1920x1080", duration=8, apply_watermark=True):
    if not reference_image_path or not os.path.exists(reference_image_path):
        return {"success": False, "message": "❌ Reference image not found."}

    # Clamp duration to whatever range is configured for this LTX model
    # (Admin Panel -> Frame Rules), instead of trusting the caller blindly.
    duration = frame_policy.get_valid_duration(model, duration)

    if DRY_RUN:
        return {"success": True, "message": "[DRY_RUN] LTX image-to-video (identity-preserving) would run.",
                "video_path": os.path.join(PATHS.get("output", "output"), "dry_run_ltx_id.mp4")}

    if not LTX_API_KEY:
        return {"success": False, "message": "❌ LTX_API_KEY not set in config.py."}

    try:
        image_uri = _upload_to_ltx(reference_image_path)
        if not image_uri:
            return {"success": False, "message": "❌ Failed to upload reference image to LTX."}

        payload = {
            "image_uri": image_uri,
            "prompt": prompt,
            "model": model,
            "duration": duration,
            "resolution": resolution,
        }
        headers = {"Authorization": f"Bearer {LTX_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(f"{LTX_BASE_URL}/v1/image-to-video", json=payload, headers=headers, timeout=300)
        resp.raise_for_status()

        out_path = os.path.join(PATHS.get("output", "output"), f"ltx_id_{int(time.time())}.mp4")
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
        return {"success": True, "message": "✅ Identity-preserving video generated (LTX 2.3).", "video_path": out_path}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"❌ LTX API error: {e}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Unexpected error: {e}"}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _upload_to_ltx(local_path):
    """LTX has a /v1/upload endpoint that returns a signed URL — use it for local files."""
    headers = {"Authorization": f"Bearer {LTX_API_KEY}"}
    with open(local_path, "rb") as f:
        resp = requests.post(f"{LTX_BASE_URL}/v1/upload", headers=headers, files={"file": f}, timeout=120)
    resp.raise_for_status()
    return resp.json().get("uri") or resp.json().get("url")


def _upload_to_fal(local_path):
    """fal.ai storage upload — confirm exact endpoint/field names in fal docs for your account tier."""
    headers = {"Authorization": f"Key {WAN_API_KEY}"}
    with open(local_path, "rb") as f:
        resp = requests.post("https://fal.run/storage/upload", headers=headers, files={"file": f}, timeout=120)
    resp.raise_for_status()
    return resp.json().get("url")


def _download_video(url, prefix):
    out_path = os.path.join(PATHS.get("output", "output"), f"{prefix}_{int(time.time())}.mp4")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path


# ------------------------------------------------------------
# Standalone test (run: python feature_20_id_embedding.py)
# ------------------------------------------------------------
if __name__ == "__main__":
    os.environ["FILMAA_DRY_RUN"] = "1"
    print(generate_with_character_wan("character1 waves at the camera", ["fake_ref.mp4"]))
    print(generate_with_character_ltx("A woman smiles and turns her head", "fake_ref.jpg"))