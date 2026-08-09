# ============================================================
# BACKGROUND WORKER — polls job_queue.py for pending jobs
# Filename: background_worker.py
# ============================================================
# Run this as a SEPARATE, always-on process — independent of Streamlit:
#     python background_worker.py
#
# Deploy it as a systemd service or its own Docker container. It has
# nothing to do with any user's browser tab being open — it just keeps
# polling the jobs DB forever and grinding through whatever is queued.
#
# This file wires together modules you've already built:
#   feature_20_id_embedding   (character-consistent generation)
#   feature_21_camera_motion  (camera-motion generation)
#   feature_23_stitching      (multi-clip stitch)
#   feature_25_scene_planner  (optional — auto scene breakdown, if present)
#   otp_service                (reused for email notifications)
#
# Currently registered job type: "long_form_video"
# Add more by writing a handler function and adding it to JOB_HANDLERS.
# ============================================================

import json
import os
import subprocess
import sys
import time
import traceback

import job_queue
import otp_service

import feature_20_id_embedding as feat20
import feature_21_camera_motion as feat21
import feature_23_stitching as feat23

try:
    import feature_25_scene_planner as scene_planner
    _SCENE_PLANNER_AVAILABLE = True
except ImportError:
    scene_planner = None
    _SCENE_PLANNER_AVAILABLE = False

try:
    import config
    PATHS = getattr(config, "PATHS", {})
except ImportError:
    PATHS = {}

POLL_INTERVAL_SECONDS = int(os.environ.get("WORKER_POLL_INTERVAL", "5"))
WORKER_ID = f"worker-{os.getpid()}"
APP_NAME = "FUTURE 4K"


# ============================================================
# HELPERS
# ============================================================

def _temp_dir() -> str:
    d = PATHS.get("temp", "temp")
    os.makedirs(d, exist_ok=True)
    return d


def extract_last_frame(video_path: str):
    """
    Pulls the final frame of a video as a .jpg for continuity carry-over
    into the next chunk (Section 3.3 of the plan — last-frame continuity).
    Requires ffmpeg on PATH. Returns None (non-fatal) if it fails —
    continuity is a nice-to-have, not a hard blocker for chunk generation.
    """
    out_path = os.path.join(_temp_dir(), f"lastframe_{int(time.time() * 1000)}.jpg")
    cmd = ["ffmpeg", "-y", "-sseof", "-1", "-i", video_path, "-update", "1", "-q:v", "2", out_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception as e:
        print(f"[worker] ⚠️ last-frame extraction failed (non-fatal): {e}")
    return None


def _notify_user(job: dict, success: bool, message: str) -> None:
    email = job.get("user_email")
    if not email:
        return
    subject = f"{APP_NAME} — Your video is ready!" if success else f"{APP_NAME} — Video generation failed"
    body_html = f"""
    <div style="font-family:Arial,sans-serif; max-width:480px; margin:auto;">
        <h2 style="color:#0FA968; margin-bottom:4px;">{APP_NAME}</h2>
        <p style="color:#14181F;">{message}</p>
    </div>
    """
    try:
        otp_service.send_email(email, subject, body_html)
    except Exception as e:
        print(f"[worker] ⚠️ notification email failed (non-fatal): {e}")


# ============================================================
# JOB HANDLERS
# ============================================================

def handle_long_form_video(job: dict) -> str:
    """
    Expected job['payload']:
      {
        "master_prompt": str,            # used only if 'scenes' isn't provided
        "total_duration": int,           # seconds, used only if 'scenes' isn't provided
        "chunk_duration": int,           # seconds per chunk, default 8
        "resolution": str,               # e.g. "1080p"
        "reference_paths": [str, ...],   # optional — 2+ enables character consistency
        "camera_motion": str,            # optional — used when no reference_paths
        "scenes": [str, ...]             # optional — pre-planned scene prompts;
                                          # if omitted, feature_25_scene_planner.plan_scenes()
                                          # is called to generate them
      }
    Returns the path to the final stitched video.
    """
    job_id = job["id"]
    payload = job["payload"] if isinstance(job["payload"], dict) else json.loads(job["payload"])

    scenes = payload.get("scenes")
    if not scenes:
        if not _SCENE_PLANNER_AVAILABLE:
            raise RuntimeError(
                "Job payload has no 'scenes' and feature_25_scene_planner.py isn't available. "
                "Either provide pre-planned scenes, or add that module."
            )
        job_queue.update_progress(job_id, current=0, total=1, label="Planning scenes...")
        scenes = scene_planner.plan_scenes(
            payload["master_prompt"],
            payload["total_duration"],
            payload.get("chunk_duration", 8),
        )

    total = len(scenes)
    if total == 0:
        raise RuntimeError("Scene planning produced zero scenes.")

    reference_paths = payload.get("reference_paths") or []
    camera_motion = payload.get("camera_motion", "None")
    resolution = payload.get("resolution", "1080p")
    chunk_duration = payload.get("chunk_duration", 8)
    use_character = len(reference_paths) >= 2

    job_queue.update_progress(job_id, current=0, total=total, label="Starting generation...")

    chunk_paths = []
    for idx, scene_prompt in enumerate(scenes, start=1):
        job_queue.update_progress(job_id, current=idx - 1, total=total, label=f"Generating scene {idx}/{total}")

        if use_character:
            result = feat20.generate_with_character_wan(
                prompt=scene_prompt,
                reference_paths=reference_paths,
                resolution=resolution,
                duration=chunk_duration,
                apply_watermark=True,
            )
        elif camera_motion and camera_motion != "None":
            result = feat21.generate_with_camera_motion(
                prompt=scene_prompt,
                camera_motion=camera_motion,
                resolution=resolution,
                duration=chunk_duration,
                apply_watermark=True,
            )
        else:
            raise RuntimeError(
                "Long-form job needs either 2+ reference_paths (character consistency) "
                "or a camera_motion value — plain no-character/no-motion chunking isn't "
                "wired here yet. Add a feat01-based branch if you need that path."
            )

        if not result.get("success"):
            raise RuntimeError(f"Scene {idx}/{total} generation failed: {result.get('message')}")

        chunk_path = result["video_path"]
        if not (os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 100):
            raise RuntimeError(f"Scene {idx}/{total} produced an empty/missing file: {chunk_path}")

        chunk_paths.append(chunk_path)
        extract_last_frame(chunk_path)  # kept for future continuation_frame wiring once your
                                         # generation functions accept a continuity image

        job_queue.update_progress(job_id, current=idx, total=total, label=f"Scene {idx}/{total} done")

    job_queue.update_progress(job_id, current=total, total=total, label="Stitching clips...")

    stitch_result = feat23.stitch_clips(
        video_paths=chunk_paths,
        transition="fade",
        transition_duration=1.0,
        output_resolution="1920x1080",
        output_fps=30,
    )
    if not stitch_result.get("success"):
        raise RuntimeError(f"Stitching failed: {stitch_result.get('message')}")

    return stitch_result["video_path"]


# Register every job type the worker knows how to run.
# Add new entries here as you build more job types.
JOB_HANDLERS = {
    "long_form_video": handle_long_form_video,
}


# ============================================================
# MAIN LOOP
# ============================================================

def process_job(job: dict) -> None:
    job_id = job["id"]
    job_type = job["job_type"]
    print(f"[worker] ▶ Processing job {job_id} ({job_type})")

    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        job_queue.mark_failed(job_id, f"No handler registered for job_type '{job_type}'.")
        print(f"[worker] ❌ Job {job_id}: unknown job_type '{job_type}'")
        return

    try:
        result_path = handler(job)
        job_queue.mark_done(job_id, result_path)
        _notify_user(job, True, f"Your video is ready! (Job #{job_id})")
        print(f"[worker] ✅ Job {job_id} done → {result_path}")
    except Exception as e:
        error_text = str(e)
        job_queue.mark_failed(job_id, error_text)
        _notify_user(job, False, f"Sorry, your video generation failed (Job #{job_id}): {error_text}")
        print(f"[worker] ❌ Job {job_id} failed: {error_text}\n{traceback.format_exc()}")


def main() -> None:
    print(f"[worker] {WORKER_ID} starting — polling every {POLL_INTERVAL_SECONDS}s. Press Ctrl+C to stop.")
    while True:
        try:
            job = job_queue.claim_next_job(WORKER_ID)
            if job:
                process_job(job)
            else:
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n[worker] Stopped by user.")
            sys.exit(0)
        except Exception as e:
            # Never let one bad iteration kill the whole worker process.
            print(f"[worker] ⚠️ Unexpected loop error: {e}\n{traceback.format_exc()}")
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()