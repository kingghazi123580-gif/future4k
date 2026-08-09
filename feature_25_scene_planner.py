# ============================================================
# FEATURE 25 — SCENE PLANNER (AI-powered long-form scene breakdown)
# Filename: feature_25_scene_planner.py
# ============================================================
# What this does:
# - Takes ONE "master prompt" + a target total duration and breaks it
#   into N short chunk-scenes (~chunk_duration seconds each), each one
#   naturally continuing from the one before it — so a 3-5 minute video
#   can be generated as a sequence of short clips and stitched together.
#
# - The AI model used to do this breakdown is PLUGGABLE. Nothing is
#   hardcoded to one company. The admin picks a provider (Mistral,
#   OpenAI, Anthropic, or ANY custom OpenAI-compatible endpoint) and
#   sets the API key/model from the Admin Panel — see
#   render_admin_settings() below, wired into admin_panel.py.
#
#   ADDING A NEW PROVIDER LATER (no other file needs to change):
#     1. Add a new class below inheriting from AIProvider
#        (copy MistralProvider as a template).
#     2. Implement its complete() method for that provider's API shape.
#     3. Add one line to the PROVIDERS dict at the bottom of this file.
#     4. It shows up automatically in the Admin Panel dropdown.
#
# - All admin-level knobs (which provider/model, API key, default chunk
#   length, long-form cost multiplier, ETA-per-chunk assumption) live in
#   a small local SQLite table, never hardcoded — see get_settings() /
#   save_settings() / render_admin_settings().
#
# NOTE: This module does the *planning* + a synchronous *best-effort*
# long-form generation loop (generate_long_form_with_character). The
# full background job-queue described in the FUTURE 4K advanced-features
# plan (a worker process that survives the user closing their tab) is a
# separate, later build step and is NOT implemented here. Until that
# exists, "Generate Full Video" in the UI runs inside the current
# Streamlit request, so the browser tab must stay open while it runs.
# ============================================================

import os
import abc
import json
import math
import time
import sqlite3

import requests

try:
    import config
    DB_PATH = getattr(config, "SCENE_PLANNER_DB_PATH", os.path.join("data", "scene_planner.db"))
except ImportError:
    DB_PATH = os.path.join("data", "scene_planner.db")

MAX_CHUNKS = 150  # safety cap so one request can't accidentally trigger hundreds of paid API calls


# ============================================================
# DATABASE — admin-configurable settings (single row)
# ============================================================

def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scene_planner_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            provider TEXT NOT NULL DEFAULT 'mistral',
            api_key TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            base_url TEXT NOT NULL DEFAULT '',
            default_chunk_duration INTEGER NOT NULL DEFAULT 8,
            cost_multiplier REAL NOT NULL DEFAULT 1.25,
            avg_processing_seconds_per_chunk INTEGER NOT NULL DEFAULT 40,
            updated_at REAL
        )
    """)
    conn.commit()
    return conn


def init_db():
    """Call once at app startup (same pattern as feature_24_admin_pricing.init_db())."""
    _get_conn().close()


def get_settings() -> dict:
    conn = _get_conn()
    row = conn.execute(
        "SELECT provider, api_key, model, base_url, default_chunk_duration, "
        "cost_multiplier, avg_processing_seconds_per_chunk "
        "FROM scene_planner_settings WHERE id = 1"
    ).fetchone()
    conn.close()
    if not row:
        return {
            "provider": "mistral", "api_key": "", "model": "", "base_url": "",
            "default_chunk_duration": 8, "cost_multiplier": 1.25,
            "avg_processing_seconds_per_chunk": 40,
        }
    return {
        "provider": row[0], "api_key": row[1], "model": row[2], "base_url": row[3],
        "default_chunk_duration": row[4], "cost_multiplier": row[5],
        "avg_processing_seconds_per_chunk": row[6],
    }


def save_settings(provider, api_key, model, base_url, default_chunk_duration,
                   cost_multiplier, avg_processing_seconds_per_chunk) -> None:
    conn = _get_conn()
    conn.execute("""
        INSERT INTO scene_planner_settings
            (id, provider, api_key, model, base_url, default_chunk_duration,
             cost_multiplier, avg_processing_seconds_per_chunk, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            provider=excluded.provider,
            api_key=excluded.api_key,
            model=excluded.model,
            base_url=excluded.base_url,
            default_chunk_duration=excluded.default_chunk_duration,
            cost_multiplier=excluded.cost_multiplier,
            avg_processing_seconds_per_chunk=excluded.avg_processing_seconds_per_chunk,
            updated_at=excluded.updated_at
    """, (provider, api_key, model, base_url, int(default_chunk_duration),
          float(cost_multiplier), int(avg_processing_seconds_per_chunk), time.time()))
    conn.commit()
    conn.close()


# ============================================================
# PLUGGABLE AI PROVIDERS
# ============================================================

class AIProvider(abc.ABC):
    name = "base"
    display_name = "Base Provider"
    default_model = ""

    @abc.abstractmethod
    def complete(self, system_prompt: str, user_prompt: str, api_key: str,
                 model: str, base_url: str = None) -> str:
        """Return the raw text completion for the given prompts."""
        raise NotImplementedError


class MistralProvider(AIProvider):
    name = "mistral"
    display_name = "Mistral AI"
    default_model = "mistral-large-latest"

    def complete(self, system_prompt, user_prompt, api_key, model, base_url=None):
        url = (base_url or "https://api.mistral.ai/v1").rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            raise RuntimeError(f"Mistral API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class OpenAIProvider(AIProvider):
    name = "openai"
    display_name = "OpenAI"
    default_model = "gpt-4o-mini"

    def complete(self, system_prompt, user_prompt, api_key, model, base_url=None):
        url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class AnthropicProvider(AIProvider):
    name = "anthropic"
    display_name = "Anthropic (Claude)"
    default_model = "claude-sonnet-4-5"

    def complete(self, system_prompt, user_prompt, api_key, model, base_url=None):
        url = (base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.default_model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return "".join(block.get("text", "") for block in data.get("content", []))


class CustomOpenAICompatibleProvider(AIProvider):
    """For any self-hosted or other API that follows the OpenAI
    chat-completions request/response shape (many do — vLLM, LM Studio,
    OpenRouter, etc). Admin sets the Base URL in the panel."""
    name = "custom"
    display_name = "Custom (OpenAI-compatible endpoint)"
    default_model = ""

    def complete(self, system_prompt, user_prompt, api_key, model, base_url=None):
        if not base_url:
            raise RuntimeError("Custom provider needs a Base URL set in the Admin Panel.")
        url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model or "default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            raise RuntimeError(f"Custom provider error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


PROVIDERS = {
    "mistral": MistralProvider(),
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "custom": CustomOpenAICompatibleProvider(),
}


# ============================================================
# SCENE PLANNING
# ============================================================

def _parse_scene_json(text: str) -> list:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            data = json.loads(text[start:end + 1])
        else:
            raise
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of scene strings")
    return [str(s).strip() for s in data if str(s).strip()]


def _inject_continuity(scenes: list) -> list:
    """Belt-and-suspenders local continuity tail, in case the AI's own
    continuity (which we also asked for in the system prompt) is weak.
    Uses the last ~14 words of the PREVIOUS raw scene, not the tagged
    version, so the tail doesn't compound in length over many scenes."""
    out = []
    prev_raw = None
    for raw in scenes:
        if prev_raw:
            tail_words = " ".join(prev_raw.split()[-14:])
            out.append(f"[Pehle: {tail_words}] {raw}")
        else:
            out.append(raw)
        prev_raw = raw
    return out


def plan_scenes(master_prompt: str, total_duration: int, chunk_duration: int = None) -> dict:
    """Breaks master_prompt into ~chunk_duration-second scenes covering
    total_duration seconds, using whichever AI provider the admin has
    configured. Returns {"success": False, "message": ...} on any
    failure (unconfigured, network/auth error, bad AI output)."""
    settings = get_settings()
    chunk_duration = int(chunk_duration or settings["default_chunk_duration"])
    if chunk_duration < 3:
        chunk_duration = 3

    if not settings.get("api_key"):
        return {
            "success": False,
            "message": "❌ Scene Planner abhi configure nahi hai. Admin ko Admin Panel → "
                       "🧠 Scene Planner (AI) tab mein provider + API key set karni hogi.",
        }
    if total_duration <= 0:
        return {"success": False, "message": "❌ Total duration 0 se zyada honi chahiye."}

    num_chunks = math.ceil(total_duration / chunk_duration)
    if num_chunks < 1:
        num_chunks = 1
    if num_chunks > MAX_CHUNKS:
        return {
            "success": False,
            "message": f"❌ Yeh duration {MAX_CHUNKS} chunks se zyada bana rahi hai "
                       f"(cost/time control ke liye limit hai). Duration kam karo ya "
                       f"chunk length barhao.",
        }

    provider = PROVIDERS.get(settings["provider"])
    if provider is None:
        return {"success": False, "message": f"❌ Unknown AI provider configured: {settings['provider']}"}

    system_prompt = (
        f"You are a film director breaking a story into short video-generation scenes.\n"
        f"Break the MASTER PROMPT below into exactly {num_chunks} short scenes, each covering "
        f"about {chunk_duration} seconds of screen time.\n\n"
        f"Rules:\n"
        f"- Keep character(s) and setting consistent across all scenes.\n"
        f"- Each scene must naturally continue from the previous one — clear beginning, "
        f"middle, and end across the whole set.\n"
        f"- Describe ONLY visual action (no dialogue — this feeds a text-to-video model).\n"
        f"- Return ONLY a JSON array of {num_chunks} strings, nothing else — no markdown, "
        f"no explanation, no numbering.\n\n"
        f'MASTER PROMPT: "{master_prompt}"'
    )

    try:
        raw = provider.complete(
            system_prompt=system_prompt,
            user_prompt=f"Generate the {num_chunks} scenes now, as a JSON array.",
            api_key=settings["api_key"],
            model=settings["model"] or provider.default_model,
            base_url=settings.get("base_url") or None,
        )
    except Exception as e:
        return {"success": False, "message": f"❌ AI provider error: {e}"}

    try:
        scenes = _parse_scene_json(raw)
    except Exception:
        return {"success": False, "message": "❌ AI ne valid scene list nahi di. Dobara try karo.", "raw": raw}

    if not scenes:
        return {"success": False, "message": "❌ AI ne khaali scene list wapas ki. Dobara try karo."}

    # AI sometimes drifts by a scene or two — trim/pad to the requested count.
    if len(scenes) > num_chunks:
        scenes = scenes[:num_chunks]
    elif len(scenes) < num_chunks:
        while len(scenes) < num_chunks:
            scenes.append(scenes[-1])

    return {
        "success": True,
        "scenes": _inject_continuity(scenes),
        "raw_scenes": scenes,
        "num_chunks": num_chunks,
        "chunk_duration": chunk_duration,
        "total_duration": num_chunks * chunk_duration,
    }


def estimate_cost_and_time(total_duration: int, resolution: str = "1080p",
                            quality: str = "standard", chunk_duration: int = None) -> dict:
    """Per section 3.4 of the integration plan: long-form videos need a
    cost multiplier reflecting the extra chunk/character-consistency
    overhead, and an ETA the user can be shown before confirming."""
    settings = get_settings()
    chunk_duration = int(chunk_duration or settings["default_chunk_duration"])
    num_chunks = max(1, math.ceil(total_duration / chunk_duration))

    per_chunk_cost = 0.0
    try:
        import feature_17_pay_per_video as feat17
        estimate = feat17.estimate_price(chunk_duration, resolution, quality, None)
        per_chunk_cost = float(estimate.get("final_price", 0))
    except Exception:
        per_chunk_cost = 0.0

    total_cost = per_chunk_cost * num_chunks * settings["cost_multiplier"]
    total_minutes = round((num_chunks * settings["avg_processing_seconds_per_chunk"]) / 60, 1)

    return {
        "num_chunks": num_chunks,
        "chunk_duration": chunk_duration,
        "estimated_cost": round(total_cost, 2),
        "estimated_minutes": total_minutes,
    }


# ============================================================
# LONG-FORM ORCHESTRATOR (synchronous, best-effort — see NOTE at top)
# ============================================================

def _extract_last_frame(video_path: str, out_dir: str = None):
    """Grabs the last frame of a clip via ffmpeg, for future last-frame
    continuity once the video-gen engine's continuation-frame parameter
    is confirmed (see integration plan, Open Items). Currently extracted
    but not yet wired into the generation call — see comment below."""
    import subprocess
    out_dir = out_dir or os.path.dirname(video_path) or "."
    out_path = os.path.join(out_dir, f"lastframe_{os.path.basename(video_path)}.jpg")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-sseof", "-1", "-i", video_path, "-update", "1", "-q:v", "2", out_path],
            capture_output=True, timeout=30,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        pass
    return None


def generate_long_form_with_character(scenes: list, reference_paths: list = None,
                                       resolution: str = "1080p", chunk_duration: int = 8,
                                       progress_callback=None) -> dict:
    """Generates each scene in order and stitches them into one video.

    If 2+ reference_paths are given, every chunk goes through Feature 20
    (character-consistent generation) with the SAME reference images
    resent each time (APIs are stateless — see integration plan §3.2).
    Otherwise falls back to plain Feature 1 text-to-video per chunk.

    NOTE: last-frame continuity (integration plan §3.3) is extracted via
    _extract_last_frame() but NOT yet passed into feat20's call — that
    requires confirming feat20's generation function accepts a
    continuation-frame parameter first (flagged as an Open Item in the
    plan). Wiring it in later is a one-line change once verified.
    """
    import feature_23_stitching as feat23

    if not scenes:
        return {"success": False, "message": "❌ No scenes to generate."}

    use_character = bool(reference_paths and len(reference_paths) >= 2)
    if use_character:
        import feature_20_id_embedding as feat20
    else:
        import feature_01_text_to_video as feat01

    chunk_paths = []
    for i, scene_prompt in enumerate(scenes):
        if progress_callback:
            progress_callback(i, len(scenes), scene_prompt)

        if use_character:
            result = feat20.generate_with_character_wan(
                prompt=scene_prompt,
                reference_paths=reference_paths,
                resolution=resolution,
                duration=chunk_duration,
                apply_watermark=True,
            )
        else:
            result = feat01.generate_video(
                prompt=scene_prompt,
                resolution=resolution,
                duration=chunk_duration,
                apply_watermark=True,
                quality="standard",
                use_voice=False,
            )

        if not result.get("success"):
            return {
                "success": False,
                "message": f"❌ Scene {i + 1}/{len(scenes)} failed: {result.get('message')}",
                "completed_chunks": chunk_paths,
            }

        chunk_paths.append(result["video_path"])
        _extract_last_frame(result["video_path"])  # reserved for future continuity wiring

    if progress_callback:
        progress_callback(len(scenes), len(scenes), "Stitching...")

    stitched = feat23.stitch_clips(
        video_paths=chunk_paths,
        transition="fade",
        transition_duration=0.6,
        output_resolution="1920x1080",
        output_fps=30,
    )
    if not stitched.get("success"):
        stitched["completed_chunks"] = chunk_paths
    return stitched


# ============================================================
# ADMIN SETTINGS UI (called from admin_panel.py)
# ============================================================

def render_admin_settings():
    import streamlit as st

    st.markdown("### 🧠 Scene Planner — AI Provider Settings")
    st.caption(
        "Controls which AI model breaks a long master-prompt into short, continuous "
        "scene-prompts, and the cost/time assumptions used for long-form video estimates."
    )

    settings = get_settings()
    provider_keys = list(PROVIDERS.keys())
    current_idx = provider_keys.index(settings["provider"]) if settings["provider"] in provider_keys else 0

    provider_choice = st.selectbox(
        "AI Provider", provider_keys, index=current_idx,
        format_func=lambda k: PROVIDERS[k].display_name, key="sp_admin_provider",
    )
    default_model = PROVIDERS[provider_choice].default_model

    model = st.text_input("Model name", value=settings["model"] or default_model, key="sp_admin_model")
    api_key = st.text_input("API Key", value=settings["api_key"] or "", type="password", key="sp_admin_apikey")
    base_url = st.text_input(
        "Custom API Base URL (optional — leave blank for provider default)",
        value=settings["base_url"] or "", key="sp_admin_baseurl",
        help="Only needed for self-hosted endpoints or the 'Custom' provider.",
    )

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        chunk_duration = st.number_input(
            "Default chunk length (seconds)", min_value=3, max_value=20,
            value=int(settings["default_chunk_duration"]), key="sp_admin_chunkdur",
        )
    with c2:
        cost_multiplier = st.number_input(
            "Long-form cost multiplier", min_value=1.0, max_value=5.0,
            value=float(settings["cost_multiplier"]), step=0.05, key="sp_admin_costmult",
            help="Applied on top of the normal per-second price to cover the extra "
                 "character-consistency + stitching overhead of long-form videos.",
        )
    avg_seconds = st.number_input(
        "Estimated processing time per chunk (seconds) — used for the ETA shown to users",
        min_value=5, max_value=600, value=int(settings["avg_processing_seconds_per_chunk"]),
        key="sp_admin_avgsec",
    )

    if st.button("💾 Save Scene Planner Settings", key="sp_admin_save", type="primary", use_container_width=True):
        save_settings(provider_choice, api_key, model, base_url, chunk_duration, cost_multiplier, avg_seconds)
        st.success("✅ Saved.")
        st.rerun()

    st.divider()
    if settings["api_key"]:
        st.success(f"✅ Configured — using **{PROVIDERS.get(settings['provider'], PROVIDERS['mistral']).display_name}** "
                   f"({settings['model'] or default_model})")
    else:
        st.warning("⚠️ No API key set yet — the Scene Planner tool will show an error to users until this is configured.")

    with st.expander("➕ How to add a new AI provider later"):
        st.markdown("""
1. Open `feature_25_scene_planner.py`
2. Add a new class inheriting from `AIProvider` (copy `MistralProvider` as a template)
3. Implement its `complete()` method for that provider's request/response shape
4. Add it to the `PROVIDERS` dict near the bottom of the file
5. It appears automatically in this dropdown — no other file needs to change.
        """)
