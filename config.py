# ============================================
# FILMAA — CENTRAL CONFIG
# Filename: config.py
# ============================================
# What this file does (English summary):
# Single source of truth for every feature module.
# - Agnes AI connection settings (key, base URL, model, polling)
# - Filesystem paths used by all features (videos/, temp/, etc.)
# - Shared limits (prompt length, clip length)
# - Watermark settings for the free tier
# - Resolution + frame-rate helper functions
# - Free/Pro tier limits (used by feature_15 / feature_16 later)
#
# Every other feature_XX_*.py file does `from config import *`
# so anything a new feature needs should be added HERE, not
# hardcoded inside the feature file.
# ============================================

import os

# ============================================
# AGNES AI — API CONNECTION
# ============================================
# NEVER hardcode the real key in this file. Set it as an
# environment variable before running the app:
#   export AGNES_API_KEY="your-real-key-here"
# NEVER hardcode the real key in this file. Set it as an
# environment variable before running the app:
#   export AGNES_API_KEY="your-real-key-here"
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")

# Confirmed against official Agnes AI docs (agnes-ai.com/doc/agnes-video-v20):
# - Task creation lives under /v1  ->  {AGNES_AI_BASE_URL}/videos
# - Result polling is NOT under /v1, it's at the API root -> {AGNES_AI_ROOT_URL}/agnesapi?video_id=...
# Do not append "/v1" again in feature code — AGNES_AI_BASE_URL already includes it.
AGNES_AI_BASE_URL = os.environ.get("AGNES_AI_BASE_URL", "https://apihub.agnes-ai.com/v1")
AGNES_AI_ROOT_URL = os.environ.get("AGNES_AI_ROOT_URL", "https://apihub.agnes-ai.com")
AGNES_AI_MODEL = "agnes-video-v2.0"

# Polling behavior while waiting for a clip to render
AGNES_POLL_INTERVAL_SECONDS = 5
AGNES_MAX_POLL_ATTEMPTS = 120  # 5s * 120 = 10 minutes max wait per clip

# Agnes AI official docs (github.com/AgnesAI-Labs/AgnesAI-Models) list the
# free/default plan's video quota as ~20 actual RPM. A 429 on light usage is
# more likely a burst (e.g. duplicate submissions) than the sustained RPM cap,
# so we use short exponential backoff rather than a long fixed wait.
AGNES_429_BASE_BACKOFF_SECONDS = 3
AGNES_429_MAX_BACKOFF_SECONDS = 30
AGNES_429_MAX_RETRIES = 5

# Small courtesy delay between successive clip requests in a multi-clip video.
AGNES_CLIP_SPACING_SECONDS = 4

# ============================================
# CLIP LENGTH LIMITS
# ============================================
# Agnes can only render up to this many seconds in a single call.
# Longer requests get split into multiple clips and stitched with ffmpeg.
MAX_CLIP_LENGTH = 18   # seconds
MIN_CLIP_LENGTH = 2    # seconds

# ============================================
# SHARED LIMITS (used across many features)
# ============================================
SHARED = {
    "max_prompt_length": None,  # None = no artificial limit (Agnes itself will reject if truly too long)
    "default_resolution": "720p",
    "default_frame_rate": 24,
}

# ============================================
# API RETRY BEHAVIOR
# ============================================
API = {
    "retry_count": 3,
    "retry_delay": 5,  # seconds between retries
}

# ============================================
# FILESYSTEM PATHS
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PATHS = {
    "videos": os.path.join(BASE_DIR, "videos"),
    "temp": os.path.join(BASE_DIR, "temp"),
    "thumbnails": os.path.join(BASE_DIR, "thumbnails"),
    "audio": os.path.join(BASE_DIR, "audio"),
    "showcase_media": os.path.join(BASE_DIR, "showcase_media"),
    "templates": os.path.join(BASE_DIR, "templates"),
    "logs": os.path.join(BASE_DIR, "logs"),
}

# Make sure every path above actually exists on disk
for _p in PATHS.values():
    os.makedirs(_p, exist_ok=True)

# ============================================
# WATERMARK (Free tier)
# ============================================
WATERMARK = {
    "text": "Filmaa.com",
    "color": "white",
    "opacity": 0.6,
    "font_size": 24,
    "position": "bottom-right",   # bottom-right | bottom-left | top-right | top-left
    "free_tier": True,            # only burned in for free-tier users
}

# ============================================
# RESOLUTION PRESETS
# ============================================
RESOLUTIONS = {
    "480p": {"width": 854, "height": 480},
    "720p": {"width": 1280, "height": 720},
    "1080p": {"width": 1920, "height": 1080},
}


def get_agnes_resolution(resolution: str) -> dict:
    """Map a resolution label (e.g. '720p') to Agnes width/height."""
    if resolution not in RESOLUTIONS:
        raise ValueError(
            f"Unknown resolution '{resolution}'. Choose from: {list(RESOLUTIONS.keys())}"
        )
    return RESOLUTIONS[resolution]


def get_frames_for_duration(seconds: float, frame_rate: int = 24) -> int:
    """
    How many frames Agnes needs to render `seconds` at `frame_rate` fps.

    Agnes requires num_frames to be of the form (8 * n + 1) — e.g. 1, 9, 17,
    ..., 233, 241. We round the raw frame count to the nearest valid value
    so the actual rendered duration stays as close as possible to what was
    requested.
    """
    raw_frames = seconds * frame_rate
    n = round((raw_frames - 1) / 8)
    n = max(n, 0)  # never go below n=0 (1 frame)
    return 8 * n + 1


# ============================================
# TIER LIMITS (used later by feature_15 / feature_16)
# ============================================
TIERS = {
    "free": {
        "videos_per_month": 5,
        "max_resolution": "480p",
        "max_duration_seconds": 30,
        "watermark": True,
    },
    "pro_monthly": {
        "videos_per_month": None,  # unlimited
        "max_resolution": "1080p",
        "max_duration_seconds": 7200,
        "watermark": False,
        "price_usd": 30,
    },
    "pro_yearly": {
        "videos_per_month": None,
        "max_resolution": "1080p",
        "max_duration_seconds": 7200,
        "watermark": False,
        "price_usd": 300,
    },
    "pay_per_video": {
        "price_usd": 5,
        "max_resolution": "720p",
        "max_duration_seconds": 3600,
        "watermark": False,
    },
}

# ============================================
# END OF config.py
# ============================================