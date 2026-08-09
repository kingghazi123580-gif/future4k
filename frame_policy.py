# ============================================================
# FRAME POLICY — central, config-driven frame/duration rules per model
# Filename: frame_policy.py
# ============================================================
# WHY THIS FILE EXISTS:
# Different video models require different frame counts:
#   - Some need frames = 8n+1  (temporal VAE compression, e.g. LTX-style)
#   - Some need frames = 4n+1  (e.g. some Wan variants)
#   - Some just need a duration in seconds (no raw frame count exposed)
#   - Some only accept a FIXED list of durations (e.g. WAN 2.6 R2V: 5 or 10s)
#
# Before this file, each feature-file assumed one hardcoded formula, so
# whenever a request produced a "wrong" frame count for a given model,
# Agnes/LTX/WAN rejected it with an error.
#
# Now: every model's rule lives in ONE place (a JSON file on disk, editable
# from the Admin Panel → "🖼️ Frame Rules" tab, no code changes needed).
# Feature files call the functions below instead of doing math themselves.
#
# Adding a brand-new model in the future = one admin panel entry.
# Zero feature-file edits required for that part.
# ============================================================

import os
import json

try:
    import config
    PATHS = getattr(config, "PATHS", {"temp": "temp", "output": "output"})
except ImportError:
    PATHS = {"temp": "temp", "output": "output"}

# Rules are stored as a flat JSON file — no DB needed for this, keeps it
# simple and consistent with Shan's flat-folder preference.
RULES_FILE = os.path.join("data", "frame_rules.json")

# ------------------------------------------------------------
# Sensible defaults — shown the FIRST time the app runs (before any
# admin edits). These match what we already know about our models today.
# Admin can change/add/remove any of these from the Frame Rules tab.
# ------------------------------------------------------------
DEFAULT_RULES = {
    "agnes-video-v2.0": {
        "formula": "8n+1",       # frames must be 8*n + 1
        "min_frames": 9,
        "max_frames": 480,
        "fps": 24,
    },
    "wan-2.6-r2v": {
        "formula": "fixed_durations",   # only exact durations allowed
        "allowed_durations": [5, 10],
        "fps": 24,
    },
    "wan-2.3": {
        "formula": "4n+1",
        "min_frames": 5,
        "max_frames": 320,
        "fps": 24,
    },
    "ltx-2-3-pro": {
        "formula": "any",        # takes duration directly, just clamp range
        "min_duration": 3,
        "max_duration": 20,
        "fps": 24,
    },
    "ltx-2-3-fast": {
        "formula": "any",
        "min_duration": 3,
        "max_duration": 20,
        "fps": 24,
    },
}

VALID_FORMULAS = ("8n+1", "4n+1", "multiple_of_8", "multiple_of_16", "fixed_durations", "any")


# ------------------------------------------------------------
# Storage helpers
# ------------------------------------------------------------
def _load_rules():
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                return data
        except Exception:
            pass
    return dict(DEFAULT_RULES)


def _save_rules(rules):
    os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)


def get_all_rules():
    """Return the full current rule set (used by the admin UI table)."""
    return _load_rules()


def upsert_rule(model_name, formula, min_frames=None, max_frames=None,
                 allowed_durations=None, min_duration=None, max_duration=None,
                 fps=24):
    """Add or update a rule for one model. Called from the admin panel."""
    if not model_name or not model_name.strip():
        return {"success": False, "message": "❌ Model name required."}
    if formula not in VALID_FORMULAS:
        return {"success": False, "message": f"❌ Formula must be one of: {VALID_FORMULAS}"}

    rules = _load_rules()
    rule = {"formula": formula, "fps": fps}

    if formula in ("8n+1", "4n+1", "multiple_of_8", "multiple_of_16"):
        rule["min_frames"] = int(min_frames) if min_frames else 1
        rule["max_frames"] = int(max_frames) if max_frames else 9999
    elif formula == "fixed_durations":
        if not allowed_durations:
            return {"success": False, "message": "❌ Provide at least one allowed duration."}
        rule["allowed_durations"] = sorted(set(int(d) for d in allowed_durations))
    elif formula == "any":
        rule["min_duration"] = int(min_duration) if min_duration else 1
        rule["max_duration"] = int(max_duration) if max_duration else 60

    rules[model_name.strip()] = rule
    _save_rules(rules)
    return {"success": True, "message": f"✅ Rule saved for '{model_name}'."}


def delete_rule(model_name):
    rules = _load_rules()
    if model_name in rules:
        del rules[model_name]
        _save_rules(rules)
        return {"success": True, "message": f"✅ Rule deleted for '{model_name}'."}
    return {"success": False, "message": f"❌ No rule found for '{model_name}'."}


# ------------------------------------------------------------
# Snapping logic
# ------------------------------------------------------------
def _snap_frames(n, formula, min_frames, max_frames):
    n = max(min_frames, min(int(n), max_frames))
    if formula == "8n+1":
        k = max(0, round((n - 1) / 8))
        snapped = 8 * k + 1
    elif formula == "4n+1":
        k = max(0, round((n - 1) / 4))
        snapped = 4 * k + 1
    elif formula == "multiple_of_8":
        snapped = max(8, round(n / 8) * 8)
    elif formula == "multiple_of_16":
        snapped = max(16, round(n / 16) * 16)
    else:
        snapped = n
    return max(min_frames, min(snapped, max_frames))


def get_valid_frame_count(model_name, requested_frames):
    """
    Snap `requested_frames` to the nearest valid count for `model_name`.
    If no rule exists for this model, returns the requested count unchanged
    (fail-open, so an unconfigured model doesn't silently break things —
    it just behaves exactly like before this system existed).
    """
    rules = _load_rules()
    rule = rules.get(model_name)
    if not rule:
        return int(requested_frames)

    formula = rule.get("formula", "any")
    if formula in ("8n+1", "4n+1", "multiple_of_8", "multiple_of_16"):
        min_frames = rule.get("min_frames", 1)
        max_frames = rule.get("max_frames", 99999)
        return _snap_frames(requested_frames, formula, min_frames, max_frames)

    return int(requested_frames)


def get_valid_duration(model_name, requested_seconds):
    """
    For models that take a duration (seconds) directly instead of a raw
    frame count — e.g. WAN's fixed 5/10s list, or LTX's min/max range.
    """
    rules = _load_rules()
    rule = rules.get(model_name)
    if not rule:
        return requested_seconds

    formula = rule.get("formula", "any")
    if formula == "fixed_durations":
        allowed = rule.get("allowed_durations", [requested_seconds])
        return min(allowed, key=lambda x: abs(x - requested_seconds))
    if formula == "any":
        lo = rule.get("min_duration", 1)
        hi = rule.get("max_duration", 60)
        return max(lo, min(requested_seconds, hi))

    return requested_seconds


def get_frames_for_duration(model_name, duration_seconds, fps=None):
    """
    Drop-in replacement for the old per-file get_frames_for_duration().
    Computes raw frames (seconds * fps) then snaps to this model's valid
    formula. This is the function feature files call before sending
    num_frames to Agnes/etc.
    """
    rules = _load_rules()
    rule = rules.get(model_name, {})
    fps = fps or rule.get("fps", 24)
    raw_frames = int(round(duration_seconds * fps))
    return get_valid_frame_count(model_name, raw_frames)


if __name__ == "__main__":
    print("Current rules:")
    for model, rule in get_all_rules().items():
        print(f"  {model}: {rule}")

    print("\nTest: agnes-video-v2.0, requested 241 frames ->",
          get_valid_frame_count("agnes-video-v2.0", 241))
    print("Test: agnes-video-v2.0, 10s @ 24fps ->",
          get_frames_for_duration("agnes-video-v2.0", 10))
    print("Test: wan-2.6-r2v, requested 7s duration ->",
          get_valid_duration("wan-2.6-r2v", 7))
    print("Test: unknown-model, requested 100 frames (should pass through) ->",
          get_valid_frame_count("unknown-model", 100))