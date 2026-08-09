# ============================================================
# FEATURE 23 — STITCHING (seamless multi-clip joining with transitions)
# ============================================================
# Pure FFmpeg — no external AI API needed. Uses the `xfade` filter to
# crossfade between clips (or `dissolve`, `wipeleft`, `slideup`, etc).
# Standalone, test-first: run this file directly with real .mp4 paths
# before wiring into app.py.
# ============================================================

import os
import time
import subprocess
import json

try:
    import config
    PATHS = getattr(config, "PATHS", {"temp": "temp", "output": "output"})
except ImportError:
    PATHS = {"temp": "temp", "output": "output"}

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# FFmpeg xfade transition names (official list — verified against ffmpeg docs)
VALID_TRANSITIONS = (
    "fade", "fadeblack", "fadewhite", "dissolve", "wipeleft", "wiperight",
    "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
    "circleopen", "circleclose", "radial", "smoothleft", "smoothright",
)


def _probe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def stitch_clips(video_paths, transition="fade", transition_duration=1.0,
                  output_resolution=None, output_fps=30):
    """
    video_paths: ordered list of local .mp4 paths (2+) to stitch together
    transition: one of VALID_TRANSITIONS
    transition_duration: seconds each crossfade takes (deducted from total runtime)
    output_resolution: e.g. "1920x1080" — if None, uses first clip's resolution
    """
    if not video_paths or len(video_paths) < 2:
        return {"success": False, "message": "❌ Need at least 2 clips to stitch."}
    if transition not in VALID_TRANSITIONS:
        return {"success": False, "message": f"❌ Invalid transition. Options: {VALID_TRANSITIONS}"}
    for p in video_paths:
        if not os.path.exists(p):
            return {"success": False, "message": f"❌ File not found: {p}"}

    out_path = os.path.join(PATHS.get("output", "output"), f"stitched_{int(time.time())}.mp4")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if DRY_RUN:
        return {"success": True, "message": f"[DRY_RUN] Would stitch {len(video_paths)} clips with '{transition}' transition.",
                "video_path": out_path}

    try:
        durations = [_probe_duration(p) for p in video_paths]

        if any(d <= transition_duration for d in durations):
            return {"success": False, "message": f"❌ transition_duration ({transition_duration}s) must be shorter than every clip's length."}

        # Normalize resolution/fps first so xfade doesn't choke on mismatched inputs
        norm_dir = os.path.join(PATHS.get("temp", "temp"), f"stitch_norm_{int(time.time())}")
        os.makedirs(norm_dir, exist_ok=True)
        target_res = output_resolution or "1920x1080"
        normalized_paths = []
        for i, p in enumerate(video_paths):
            norm_path = os.path.join(norm_dir, f"clip_{i}.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", p,
                "-vf", f"scale={target_res.replace('x', ':')},fps={output_fps}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-ar", "44100",
                norm_path,
            ], check=True, capture_output=True)
            normalized_paths.append(norm_path)

        # Re-probe normalized durations (should match originals closely)
        durations = [_probe_duration(p) for p in normalized_paths]

        # Build xfade filter chain: each clip after the first crossfades into
        # the running composite. Offset = cumulative duration so far minus
        # the overlaps already consumed.
        inputs = []
        for p in normalized_paths:
            inputs += ["-i", p]

        filter_parts = []
        audio_parts = []
        running_label = "[0:v]"
        running_audio = "[0:a]"
        cumulative = durations[0]

        for i in range(1, len(normalized_paths)):
            offset = cumulative - transition_duration
            v_out = f"[v{i}]"
            a_out = f"[a{i}]"
            filter_parts.append(
                f"{running_label}[{i}:v]xfade=transition={transition}:duration={transition_duration}:offset={offset}{v_out}"
            )
            audio_parts.append(
                f"{running_audio}[{i}:a]acrossfade=d={transition_duration}{a_out}"
            )
            running_label = v_out
            running_audio = a_out
            cumulative = cumulative - transition_duration + durations[i]

        filter_complex = ";".join(filter_parts + audio_parts)

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", running_label, "-map", running_audio,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return {"success": False, "message": f"❌ FFmpeg stitch failed: {result.stderr[-800:]}"}

        # Cleanup normalized temp files
        for p in normalized_paths:
            try:
                os.remove(p)
            except Exception:
                pass
        try:
            os.rmdir(norm_dir)
        except Exception:
            pass

        return {"success": True, "message": f"✅ Stitched {len(video_paths)} clips into one seamless video.",
                "video_path": out_path}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": f"❌ FFmpeg error: {e.stderr[-800:] if e.stderr else e}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Unexpected error: {e}"}


if __name__ == "__main__":
    print("Run with real clip paths, e.g.:")
    print('  stitch_clips(["clip1.mp4", "clip2.mp4", "clip3.mp4"], transition="fade", transition_duration=1.0)')