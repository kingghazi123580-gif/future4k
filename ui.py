# ============================================================
# FUTURE 4K — MAIN UI (MERGED: Wallet Pricing + Auth Gate)
# Tagline: YOUR VISION . OUR AI .
# Features 01-25 (Free/Pro tier removed)
# MIC/AUDIO FEATURES FULLY REMOVED
# ============================================================

import streamlit as st
st.set_page_config(page_title="Future4K", layout="centered")

# ============================================
# SESSION STATE INITIALIZATION
# ============================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if "wallet_balance" not in st.session_state:
    st.session_state.wallet_balance = 0.0

if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

if "theme" not in st.session_state:
    st.session_state.theme = "Light"

if "language" not in st.session_state:
    st.session_state.language = "English"
import os
import sys
import io as _io
import tempfile as _tempfile
import streamlit as st

SMTP_SERVER=""
SMTP_PORT=""
SENDER_EMAIL=""
SENDER_APP_PASSWORD=""
JAZZCASH_NUMBER=""
JAZZCASH_ACCOUNT_TITLE="FUTURE 4K"
EASYPAISA_NUMBER=""
EASYPAISA_ACCOUNT_TITLE="FUTURE 4K"
SADAPAY_NUMBER=""
SADAPAY_ACCOUNT_TITLE="FUTURE 4K"
NAYAPAY_NUMBER=""
NAYAPAY_ACCOUNT_TITLE="FUTURE 4K"
MAX_SINGLE_TOPUP_PKR="50000"
MIN_SINGLE_TOPUP_PKR="100"

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import config
    from config import RESOLUTIONS, MIN_CLIP_LENGTH, PATHS, MAX_CLIP_LENGTH
except ImportError:
    print("[ERROR] config.py not found!")
    raise SystemExit(1)

# Feature imports (01-25)
import feature_01_text_to_video as feat01
import feature_02_image_to_video as feat02
import feature_03_clip_generation as feat03
import feature_04_extend_video as feat04
import feature_05_timeline_editor as feat05
import feature_06_add_music as feat06
import feature_07_add_voiceover as feat07
import feature_08_watermark as feat08
import feature_09_urdu_prompts as feat09
import feature_10_prompt_templates as feat10
import feature_11_negative_prompting as feat11
import feature_12_video_library as feat12
import feature_13_folder_organization as feat13
import feature_14_favorites_collections as feat14
import feature_17_pay_per_video as feat17
import feature_18_launch_discount as feat18
import feature_19_feedback as feat19
import feature_20_id_embedding as feat20
import feature_21_camera_motion as feat21
import feature_22_frame_to_frame as feat22
import feature_23_stitching as feat23
import feature_24_admin_pricing as feat24
feat24.init_db()
import feature_25_scene_planner
feature_25_scene_planner.init_db()
import job_queue
job_queue.init_db()
import feature_26_demo_videos
feature_26_demo_videos.init_db()

import auth_gate
import admin_panel
import manual_payments
import sidebar_settings

# ============================================================
# LOGO PATH
# ============================================================
LOGO_PATH = "logo.png"
_LOGO_AVAILABLE = os.path.exists(LOGO_PATH)

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FUTURE 4K",
    page_icon=LOGO_PATH if _LOGO_AVAILABLE else "🎬",
    layout="wide",
)
DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# ============================================================
# AUTH GATE
# ============================================================
if not auth_gate.render_gate():
    st.stop()

# ============================================================
# CSS (Mic-related styles removed)
# ============================================================
st.markdown("""
<style>
    :root { 
        --bg: #F4F5F7; 
        --surface: #FFFFFF; 
        --ink: #14181F; 
        --ink-muted: #626B76;
        --accent: #0FA968; 
        --accent-dark: #0B7F4F; 
        --accent-light: #E8F5E9;
        --accent-hover: #1DBF7A; 
        --navy: #101A30; 
        --line: #E4E7EB; 
        --card-border: #0FA968;
        --card-bg: #FFFFFF;
        --text-color: #14181F;
    }
    .stApp { background-color: var(--bg); }
    html, body, p, span, div { font-family: 'Inter', sans-serif; color: var(--text-color); }
    h1, h2, h3 { font-family: 'Sora', sans-serif; color: var(--text-color); }
    section[data-testid="stSidebar"] { background-color: var(--navy); }
    section[data-testid="stSidebar"] * { color: #C4CCDA !important; }
    section[data-testid="stSidebar"] h1, h2, h3 { color: #FFFFFF !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px; border: 2px solid var(--card-border) !important;
        background-color: var(--card-bg) !important; padding: 16px;
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 6px 20px rgba(15, 169, 104, 0.15); border-color: var(--accent-dark) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] * { color: var(--text-color) !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] .fm-card-title { color: var(--text-color) !important; font-weight: 700; }
    div[data-testid="stVerticalBlockBorderWrapper"] .fm-card-desc { color: var(--ink-muted) !important; }
    .stButton>button {
        background-color: var(--accent) !important; color: #FFFFFF !important; border: none !important;
        border-radius: 8px !important; padding: 0.5rem 1.1rem !important; font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        background-color: var(--accent-dark) !important; transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(15, 169, 104, 0.3);
    }
    .stButton>button[kind="primary"] { background-color: var(--accent) !important; color: #FFFFFF !important; }
    .stButton>button[kind="primary"]:hover { background-color: var(--accent-dark) !important; }
    .stButton>button[kind="secondary"] {
        background-color: transparent !important; color: var(--accent) !important; border: 1.5px solid var(--accent) !important;
    }
    .stButton>button[kind="secondary"]:hover {
        background-color: var(--accent-light) !important; border-color: var(--accent-dark) !important; color: var(--accent-dark) !important;
    }
    .fm-icon-chip {
        display: inline-flex; align-items: center; justify-content: center;
        width: 38px; height: 38px; border-radius: 9px;
        background: rgba(15, 169, 104, 0.12) !important;
        font-size: 1.2rem; margin-bottom: 0.5rem; color: var(--accent-dark) !important;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        background: var(--accent) !important; border-color: var(--accent) !important; color: #FFFFFF !important;
    }
    div[data-testid="stRadio"] label:has(input:checked) p { color: #FFFFFF !important; }
    div[data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--line);
        border-radius: 10px; padding: 0.6rem; transition: border-color 0.15s ease;
    }
    div[data-testid="stMetric"]:hover { border-color: var(--accent); }
    div[data-testid="stMetric"] * { color: var(--text-color) !important; }
    .stProgress > div > div > div { background: var(--accent) !important; }
    .fm-section-title .lbl { color: var(--text-color); font-weight: 700; }
    .fm-section-title .sub { color: var(--ink-muted); }
    .stTextInput>div>div>input {
        color: var(--text-color) !important; background-color: #FFFFFF !important;
        border: 1px solid var(--line) !important; border-radius: 8px !important;
    }
    .stTextArea>div>div>textarea {
        color: var(--text-color) !important; background-color: #FFFFFF !important;
        border: 1px solid var(--line) !important; border-radius: 8px !important;
    }
    .stTextInput>div>div>input:focus {
        border-color: var(--accent) !important; box-shadow: 0 0 0 2px rgba(15, 169, 104, 0.2) !important;
    }
    .stTextArea>div>div>textarea:focus {
        border-color: var(--accent) !important; box-shadow: 0 0 0 2px rgba(15, 169, 104, 0.2) !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important; border: 1px solid var(--line) !important; border-radius: 8px !important;
    }
    div[data-baseweb="select"] * { color: var(--text-color) !important; background-color: transparent !important; }
    div[data-baseweb="select"] svg { fill: var(--text-color) !important; }
    div[data-testid="stWidgetLabel"] p, div[data-testid="stWidgetLabel"] label,
    .stSelectbox label, .stSlider label, .stNumberInput label, .stRadio label, .stCheckbox label {
        color: var(--text-color) !important;
    }
    div[data-testid="stNumberInput"] input { color: var(--text-color) !important; background-color: #FFFFFF !important; }
    div[data-testid="stSlider"] * { color: var(--text-color) !important; }
    div[data-testid="stRadio"] label p, div[data-testid="stCheckbox"] label p { color: var(--text-color) !important; }
    .stTabs [data-baseweb="tab"] { color: var(--text-color) !important; }
    .stTabs [data-baseweb="tab"] p { color: var(--text-color) !important; }
    .stTabs [aria-selected="true"] { color: var(--accent-dark) !important; font-weight: 700; }
    .stTabs [aria-selected="true"] p { color: var(--accent-dark) !important; }
    a { color: var(--accent) !important; }
    a:hover { color: var(--accent-dark) !important; }
    .fm-crumb { font-size:0.78rem; color: var(--accent-dark); text-transform:uppercase; letter-spacing:0.06em; }
    .fm-detail-title { font-weight:800; font-size:1.5rem; margin: 0.15rem 0 1rem 0; color: var(--text-color) !important; }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text-color) !important; }
    .stSubheader { color: var(--text-color) !important; }
    .stCaption { color: var(--ink-muted) !important; }
    hr { border-color: var(--line) !important; }
    div[data-baseweb="popover"] { background-color: #FFFFFF !important; }
    ul[data-baseweb="menu"] { background-color: #FFFFFF !important; }
    ul[data-baseweb="menu"] li, li[role="option"] { background-color: #FFFFFF !important; color: var(--text-color) !important; }
    ul[data-baseweb="menu"] li:hover, li[role="option"]:hover {
        background-color: var(--accent-light) !important; color: var(--accent-dark) !important;
    }
    li[aria-selected="true"] { background-color: var(--accent-light) !important; color: var(--accent-dark) !important; }
    div[data-testid="stCodeBlock"] { background-color: #FFFFFF !important; border: 1px solid var(--line) !important; border-radius: 8px !important; }
    div[data-testid="stCodeBlock"] pre { background-color: #FFFFFF !important; }
    div[data-testid="stCodeBlock"] pre code, div[data-testid="stCodeBlock"] code, div[data-testid="stCodeBlock"] span {
        background-color: #FFFFFF !important; color: var(--text-color) !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================

sidebar_settings.render_sidebar_and_settings()

if DRY_RUN:
    with st.sidebar:
        st.info("🔶 DRY_RUN mode")

# Push API key — now admin-controlled (Admin Panel → 🔑 API Settings),
# no longer a per-user sidebar field. Env var AGNES_API_KEY still wins
# if set, for safe ops/deploy overrides (see admin_panel.get_agnes_api_key()).
agnes_key = admin_panel.get_agnes_api_key()
for feat in [feat01, feat02, feat03, feat04, feat05, feat06, feat07,
             feat08, feat09, feat10, feat11, feat12, feat13, feat14,
             feat17, feat18, feat19, feat20, feat21, feat22, feat23, feat24]:
    if hasattr(feat, 'AGNES_API_KEY'):
        feat.AGNES_API_KEY = agnes_key or config.AGNES_API_KEY

# ============================================================
# LIVE PRICE CALCULATOR + WALLET CHARGE HELPER
# ============================================================

def render_live_price(duration_seconds, resolution, quality, key_prefix):
    user_id = st.session_state.get("current_user_id", "")
    estimate = feat17.estimate_price(duration_seconds, resolution, quality, user_id or None)
    if not estimate.get("success", True) and "final_price" not in estimate:
        st.caption("💰 Price unavailable")
        return estimate
    price = estimate.get("final_price", 0)
    discount = estimate.get("discount_percent", 0)
    if discount:
        st.markdown(
            f"💰 **Estimated Price: ${price:.2f}** "
            f"<span style='color:#0FA968;'>({discount:.0f}% discount applied)</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"💰 **Estimated Price: ${price:.2f}**")
    return estimate


def charge_wallet_or_block(duration_seconds, resolution, quality, tool_name, video_id=""):
    user_id = st.session_state.get("current_user_id", "")
    if not user_id:
        return False, {"success": False, "message": "❌ Please enter a User ID in the sidebar first."}
    result = feat17.charge_for_video(
        user_id=user_id,
        duration_seconds=duration_seconds,
        resolution=resolution,
        quality=quality,
        video_id=video_id,
        tool_name=tool_name,
    )
    return result.get("success", False), result

# ============================================================
# FEATURE RENDERERS (01-25)
# ============================================================

def render_feat_00():
    st.subheader("📝 Text-to-Video")
    st.write("Urdu, Hindi ya English mein prompt likho — Agnes AI video banaye ga.")
    prompt = st.text_area("📝 Prompt", key="t2v_prompt_field", height=150, placeholder="Misaal: ایک خوبصورت لڑکی باغ میں پھول چُن رہی ہے")
    st.markdown('<div class="fm-section-title"><span class="ico">⚙️</span><span class="lbl">Configuration</span></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        resolution = st.selectbox("Resolution", options=list(feat01.RESOLUTION_CONFIGS.keys()), index=2, format_func=lambda x: feat01.RESOLUTION_CONFIGS[x]["label"], key="t2v_res")
    with col2:
        quality = st.selectbox("Quality", options=list(feat01.QUALITY_PRESETS.keys()), index=0, format_func=lambda x: f"{feat01.QUALITY_PRESETS[x]['label']} — {feat01.QUALITY_PRESETS[x]['description']}", key="t2v_quality")
    with col3:
        dur_min = st.number_input("Minutes", 0, 120, 0, key="t2v_min")
        dur_sec = st.number_input("Seconds", 0, 59, 10, key="t2v_sec")
    duration = int(dur_min) * 60 + int(dur_sec)
    st.caption(f"⏱️ Total: **{duration}s** | 📐 **{feat01.RESOLUTION_CONFIGS[resolution]['label']}** | 🎯 **{feat01.QUALITY_PRESETS[quality]['label']}**")

    camera_motion = st.selectbox(
        "🎥 Camera Motion (optional)",
        ["None"] + list(feat21.CAMERA_MOTIONS.keys()),
        key="t2v_camera_motion",
        help="Cinematic camera move — dolly, pan, tilt, zoom, orbit, crane.",
    )

    ref_files = None
    with st.expander("🆔 Character Consistent Rakhna Hai? (optional)"):
        st.caption("2-5 reference images upload karo — AI isi character ko is video mein consistent rakhega.")
        ref_files = st.file_uploader(
            "Reference Images (2-5)", type=["jpg", "jpeg", "png"],
            accept_multiple_files=True, key="t2v_char_refs",
        )

    render_live_price(duration, resolution, quality, "t2v")
    with st.expander("⚙️ Advanced Options"):
        negative_prompt = st.text_input("🚫 Negative Prompt", key="t2v_negative_field", placeholder="e.g., blurry, low quality")
        apply_watermark = st.checkbox("Watermark (free tier)", True, key="t2v_watermark")
    st.divider()
    if st.button("🎬 Generate Video", type="primary", key="t2v_generate", use_container_width=True):
        if auth_gate.guest_locked("video generation"):
            pass
        elif not prompt or len(prompt.strip()) < 3:
            st.error("❌ Pehle koi prompt likho ya voice input use karo.")
        elif duration < 2:
            st.error("❌ Duration kam az kam 2 seconds honi chahiye.")
        elif ref_files and 0 < len(ref_files) < 2:
            st.error("❌ Character consistency ke liye kam az kam 2 reference images chahiye (ya field khaali chhoro).")
        else:
            ok, charge = charge_wallet_or_block(duration, resolution, quality, "text_to_video")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
            else:
                st.success(f"💳 {charge.get('message')}")
                use_character = bool(ref_files and len(ref_files) >= 2)

                # Routing: character-consistent > camera-motion > plain T2V
                if use_character:
                    char_res = resolution if resolution in ("720p", "1080p") else "1080p"
                    ref_paths = []
                    for i, file in enumerate(ref_files[:5]):
                        path = os.path.join(PATHS.get("temp", "temp"), f"t2v_ref_{i}_{file.name}")
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, "wb") as f:
                            f.write(file.getbuffer())
                        ref_paths.append(path)
                    with st.spinner("🎬 Generating character-consistent video..."):
                        result = feat20.generate_with_character_wan(
                            prompt=prompt, reference_paths=ref_paths, resolution=char_res,
                            duration=duration, apply_watermark=apply_watermark,
                        )
                    for p in ref_paths:
                        if os.path.exists(p):
                            os.remove(p)
                elif camera_motion != "None":
                    cam_res = resolution if resolution in ("2k", "4k") else "2k"
                    with st.spinner(f"🎬 Generating video with {camera_motion}..."):
                        result = feat21.generate_with_camera_motion(
                            prompt=prompt, camera_motion=camera_motion, resolution=cam_res,
                            duration=duration, apply_watermark=apply_watermark,
                        )
                else:
                    with st.spinner(f"🎬 Generating {feat01.QUALITY_PRESETS[quality]['label']} quality video..."):
                        result = feat01.generate_video(prompt=prompt, resolution=resolution, duration=duration, negative_prompt=negative_prompt or None, apply_watermark=apply_watermark, quality=quality, use_voice=False)

                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    vp = result["video_path"]
                    if os.path.exists(vp) and os.path.getsize(vp) > 100:
                        st.video(vp)
                        with open(vp, "rb") as f:
                            st.download_button("📥 Download Video", f, os.path.basename(vp), "video/mp4")
                    else:
                        st.info(f"ℹ️ DRY_RUN — {vp}")
                else:
                    st.error(f"❌ {result['message']}")

def render_feat_01():
    st.subheader("🖼️ Image-to-Video")
    st.write("Ek ya zyada images upload karo aur bata do unhein kaisay animate karna hai.")

    story_mode = st.checkbox(
        "📖 Story Mode — sab images ek hi combined video banayein (alag-alag scenes, ek prompt har image ke liye)",
        value=False, key="img2vid_story_mode",
        help="OFF: har image apni ALAG video banayegi (jaisa pehle tha). "
             "ON: har image apna scene banati hai, phir sab scenes hard-cut se jud kar EK final video banti hai.",
    )

    uploaded_images = st.file_uploader("Image(s) upload karein", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True, key="img2vid_uploader")
    if uploaded_images:
        st.caption(f"📸 {len(uploaded_images)} image(s)")
    st.divider()

    scene_prompts = []
    if story_mode and uploaded_images:
        st.markdown('<div class="fm-section-title"><span class="lbl">📝 Har Image Ke Liye Scene Prompt</span></div>', unsafe_allow_html=True)
        for idx, img in enumerate(uploaded_images, start=1):
            scene_prompt = st.text_area(
                f"Scene {idx}: {img.name}",
                key=f"story_scene_prompt_{idx}",
                placeholder=f"Misaal: Scene {idx} mein kya ho raha hai...",
                height=80,
            )
            scene_prompts.append(scene_prompt)
        st.divider()
    else:
        img_prompt = st.text_area("📝 Motion Prompt", key="img2vid_prompt_field", placeholder="Misaal: Halki hawa mein baadal aahista aahista chal rahe hain", height=120)
        st.divider()

    c1, c2 = st.columns(2)
    with c1:
        img_resolution = st.selectbox("Resolution", options=list(feat02.RESOLUTION_CONFIGS.keys()), index=2, format_func=lambda x: feat02.RESOLUTION_CONFIGS[x]["label"], key="img2vid_res")
    with c2:
        img_aspect = st.selectbox("Aspect Ratio", ["16:9", "9:16", "1:1", "4:3", "3:4"], key="img2vid_aspect")
    img_camera_motion = st.selectbox(
        "🎥 Camera Motion (optional)",
        ["None"] + list(feat21.CAMERA_MOTIONS.keys()),
        key="img2vid_camera_motion",
        help="Cinematic camera move — dolly, pan, tilt, zoom, orbit, crane.",
    )
    dc1, dc2 = st.columns(2)
    with dc1:
        img_dur_min = st.number_input("Minutes", 0, 120, 0, key="img2vid_min")
    with dc2:
        img_dur_sec = st.number_input("Seconds", 0, 59, 5, key="img2vid_sec")
    img_duration = int(img_dur_min) * 60 + int(img_dur_sec)
    st.caption(f"⏱️ **{img_duration}s** per image" if not story_mode else f"⏱️ **{img_duration}s** per scene")

    _price_dur = img_duration * (len(uploaded_images) if (story_mode and uploaded_images) else 1)
    render_live_price(_price_dur, img_resolution, "standard", "img2vid")

    with st.expander("⚙️ Advanced Options"):
        if not story_mode:
            img_neg = st.text_input("🚫 Negative Prompt", key="img2vid_negative_field", placeholder="e.g., blurry")
            img_seed = st.number_input("Seed (0=random)", 0, 999999, 0, key="img2vid_seed")
            img_seed = img_seed if img_seed > 0 else None
        else:
            img_neg = None
            img_seed = None
        img_wm = st.checkbox("Watermark (free tier)", True, key="img2vid_watermark")
    st.divider()

    button_label = "📖 Generate Story Video" if story_mode else "🎬 Generate Video(s)"
    if st.button(button_label, type="primary", key="img2vid_generate", use_container_width=True):
        if auth_gate.guest_locked("video generation"):
            pass
        elif not uploaded_images:
            st.error("❌ Pehle kam az kam ek image upload karo.")
        elif story_mode and len(uploaded_images) < 2:
            st.error("❌ Story Mode ke liye kam az kam 2 images chahiye.")
        elif story_mode and any(not p or len(p.strip()) < 3 for p in scene_prompts):
            st.error("❌ Har image ke liye kam az kam ek chhota scene prompt likho.")
        elif not story_mode and (not img_prompt or len(img_prompt.strip()) < 3):
            st.error("❌ Motion prompt likho ya voice use karo.")
        elif img_duration < MIN_CLIP_LENGTH:
            st.error(f"❌ Duration kam az kam {MIN_CLIP_LENGTH}s honi chahiye.")
        else:
            if story_mode:
                ok, charge = charge_wallet_or_block(_price_dur, img_resolution, "standard", "image_story_video")
                if not ok:
                    st.error(f"❌ {charge.get('message')}")
                else:
                    st.success(f"💳 {charge.get('message')}")
                    temp_paths = []
                    scenes = []
                    for idx, (img, s_prompt) in enumerate(zip(uploaded_images, scene_prompts), start=1):
                        temp_path = os.path.join(PATHS.get("temp", "temp"), f"story_upload_{os.getpid()}_{idx}_{img.name}")
                        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                        with open(temp_path, "wb") as f:
                            f.write(img.getbuffer())
                        temp_paths.append(temp_path)
                        final_scene_prompt = s_prompt
                        if img_camera_motion != "None":
                            final_scene_prompt = f"{s_prompt}. Camera motion: {img_camera_motion}."
                        scenes.append({"image_path": temp_path, "prompt": final_scene_prompt, "duration": img_duration})

                    with st.spinner(f"📖 Generating story video ({len(scenes)} scenes)..."):
                        result = feat02.generate_story_from_images(
                            scenes=scenes,
                            resolution=img_resolution,
                            apply_watermark=img_wm,
                            aspect_ratio=img_aspect,
                        )

                    for p in temp_paths:
                        if os.path.exists(p):
                            os.remove(p)

                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        vp = result["video_path"]
                        if os.path.exists(vp) and os.path.getsize(vp) > 100:
                            st.video(vp)
                            with open(vp, "rb") as f:
                                st.download_button("📥 Download Story Video", f, os.path.basename(vp), "video/mp4")
                    else:
                        st.error(f"❌ {result['message']}")
            else:
                for idx, img in enumerate(uploaded_images, start=1):
                    st.markdown(f"---\n**🖼️ Image {idx}/{len(uploaded_images)}: {img.name}**")
                    ok, charge = charge_wallet_or_block(img_duration, img_resolution, "standard", "image_to_video", video_id=f"img_{idx}")
                    if not ok:
                        st.error(f"❌ {charge.get('message')}")
                        continue
                    st.success(f"💳 {charge.get('message')}")
                    temp_path = os.path.join(PATHS.get("temp", "temp"), f"upload_{os.getpid()}_{idx}_{img.name}")
                    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                    with open(temp_path, "wb") as f:
                        f.write(img.getbuffer())
                    with st.spinner(f"Generating video for image {idx}..."):
                        final_prompt = img_prompt
                        if img_camera_motion != "None":
                            final_prompt = f"{img_prompt}. Camera motion: {img_camera_motion}."
                        result = feat02.generate_video_from_image(image_path=temp_path, prompt=final_prompt, resolution=img_resolution, duration=img_duration, negative_prompt=img_neg or None, apply_watermark=img_wm, seed=img_seed, aspect_ratio=img_aspect, use_voice=False)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        vp = result["video_path"]
                        if os.path.exists(vp) and os.path.getsize(vp) > 100:
                            st.video(vp)
                    else:
                        st.error(f"❌ {result['message']}")

def render_feat_02():
    st.subheader("✂️ 30-Second Clip")
    st.write("Reels, Shorts ya TikTok ke liye ready-made chhoti video banao.")
    clip_prompt = st.text_area("📝 Prompt", key="clip_prompt_field", placeholder="Misaal: Lahore ki gali mein cricket khelte bachay", height=100)
    c1, c2, c3 = st.columns(3)
    with c1:
        clip_res = st.selectbox("Resolution", options=list(feat03.RESOLUTION_CONFIGS.keys()), index=2, format_func=lambda x: feat03.RESOLUTION_CONFIGS[x]["label"], key="clip_res")
    with c2:
        clip_dur = st.slider("Duration (s)", MIN_CLIP_LENGTH, 30, 15, key="clip_dur")
    with c3:
        platform = st.selectbox("Platform", ["Instagram Reels", "YouTube Shorts", "TikTok", "Square (1:1)", "Landscape (16:9)"], key="clip_platform")
    render_live_price(clip_dur, clip_res, "standard", "clip")
    with st.expander("⚙️ Advanced Options"):
        clip_neg = st.text_input("🚫 Negative Prompt", key="clip_negative_field", placeholder="e.g., blurry")
        clip_wm = st.checkbox("Watermark (free tier)", True, key="clip_watermark")
    st.divider()
    if st.button("🎬 Generate Clip", type="primary", key="clip_generate", use_container_width=True):
        if auth_gate.guest_locked("clip generation"):
            pass
        elif not clip_prompt or len(clip_prompt.strip()) < 3:
            st.error("❌ Prompt likho.")
        else:
            ok, charge = charge_wallet_or_block(clip_dur, clip_res, "standard", "clip_generation")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
            else:
                st.success(f"💳 {charge.get('message')}")
                with st.spinner(f"🎬 Generating clip..."):
                    result = feat03.generate_short_clip(prompt=clip_prompt, duration=clip_dur, negative_prompt=clip_neg or None, apply_watermark=clip_wm, resolution=clip_res, platform=platform, use_voice=False)
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    vp = result["video_path"]
                    if os.path.exists(vp) and os.path.getsize(vp) > 100:
                        st.video(vp)
                else:
                    st.error(f"❌ {result['message']}")

def render_feat_03():
    st.subheader("📏 Extend Video")
    st.write("Ek maujooda video upload karo aur bata do aagay kya hona chahiye.")
    uploaded_video = st.file_uploader("Video upload karein", type=["mp4", "mov", "m4v"], key="extend_uploader")
    extend_prompt = st.text_area("Extension Prompt", placeholder="Misaal: Camera aahista peechay jata hai", height=100, key="extend_prompt")
    col1, col2 = st.columns(2)
    with col1:
        extend_seconds = st.slider("Extension Duration (seconds)", 5, 30, 10, key="extend_seconds")
    with col2:
        keep_original = st.checkbox("Original video ko safe rakho", True, key="extend_keep")
    render_live_price(extend_seconds, "720p", "standard", "extend")
    extend_apply_watermark = st.checkbox("Watermark add karein (free tier)", True, key="extend_watermark")
    if st.button("🎬 Extend Video", type="primary", key="extend_generate"):
        if auth_gate.guest_locked("video extension"):
            pass
        elif uploaded_video is None:
            st.error("❌ Pehle ek video upload karo.")
        elif not extend_prompt or len(extend_prompt.strip()) < 3:
            st.error("❌ Pehle koi extension prompt likho.")
        else:
            ok, charge = charge_wallet_or_block(extend_seconds, "720p", "standard", "extend_video")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
            else:
                st.success(f"💳 {charge.get('message')}")
                video_ext = os.path.splitext(uploaded_video.name)[1] or ".mp4"
                temp_video_path = os.path.join(PATHS.get("temp", "temp"), f"extend_upload_{os.getpid()}{video_ext}")
                os.makedirs(os.path.dirname(temp_video_path), exist_ok=True)
                with open(temp_video_path, "wb") as f:
                    f.write(uploaded_video.getbuffer())
                with st.spinner("🎬 Video extend ho raha hai..."):
                    extend_result = feat04.extend_video(temp_video_path, extend_prompt, extend_seconds, extend_apply_watermark, keep_original)
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)
                if extend_result["success"]:
                    st.success(f"✅ {extend_result['message']}")
                    vp = extend_result["video_path"]
                    if os.path.exists(vp) and os.path.getsize(vp) > 100:
                        st.video(vp)
                else:
                    st.error(f"❌ {extend_result['message']}")

def render_feat_04():
    st.subheader("⏳ Timeline Editor")
    st.write("Clips ko arrange, trim aur edit karein.")
    if "timeline_project" not in st.session_state:
        st.session_state.timeline_project = None
    if st.button("📁 New Project", key="tle_new"):
        st.session_state.timeline_project = feat05.create_project("My Project")
        st.success("✅ Project created")
    if st.session_state.timeline_project:
        project = st.session_state.timeline_project
        info = feat05.get_timeline_info(project)
        st.markdown(f"Project: {info['name']} | Clips: {info['clip_count']} | Duration: {info['total_duration']:.1f}s")
        uploaded_clips = st.file_uploader("Add Videos", type=["mp4"], accept_multiple_files=True, key="tle_upload")
        if uploaded_clips:
            for file in uploaded_clips:
                temp_path = os.path.join(PATHS.get("temp", "temp"), file.name)
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(file.getbuffer())
                feat05.add_clip_to_timeline(project, temp_path, file.name)
                st.info(f"✅ Added: {file.name}")
        for i, clip in enumerate(project.clips):
            cols = st.columns([2, 1, 1, 1])
            cols[0].text(f"#{i+1}: {clip.name} ({clip.get_trimmed_duration():.1f}s)")
            if cols[3].button("🗑️", key=f"tle_del_{i}"):
                feat05.remove_clip_from_timeline(project, clip.clip_id)
                st.rerun()
        if st.button("🎬 Render Timeline", key="tle_render"):
            if auth_gate.guest_locked("timeline rendering"):
                pass
            else:
                with st.spinner("Rendering..."):
                    output = feat05.render_timeline(project, resolution="720p")
                st.success(f"✅ Rendered: {output}")
                if os.path.exists(output) and os.path.getsize(output) > 100:
                    st.video(output)

def render_feat_05():
    st.subheader("🎵 Background Music")
    st.write("Video mein background music add karein.")
    video_file = st.file_uploader("Upload Video", type=["mp4", "mov", "avi", "webm"], key="f06_upload")
    library = feat06.get_music_library()
    track_names = [f"{k}: {v['name']} ({v['genre']})" for k, v in library.items()]
    selected = st.selectbox("Select Music", track_names, key="f06_lib")
    music_id = selected.split(":")[0] if selected else None
    volume = st.slider("Music Volume", 0.0, 1.0, 0.3, key="f06_vol")
    fade_in = st.slider("Fade In (s)", 0, 5, 2, key="f06_fade_in")
    fade_out = st.slider("Fade Out (s)", 0, 5, 2, key="f06_fade_out")
    apply_wm = st.checkbox("Add Watermark", True, key="f06_wm")
    if video_file and music_id and st.button("🎵 Add Music", key="f06_gen"):
        if auth_gate.guest_locked("adding music"):
            pass
        else:
            temp_video = os.path.join(PATHS.get("temp", "temp"), video_file.name)
            os.makedirs(os.path.dirname(temp_video), exist_ok=True)
            with open(temp_video, "wb") as f:
                f.write(video_file.getbuffer())
            with st.spinner("Adding music..."):
                result = feat06.add_music_to_video(temp_video, music_id, volume, fade_in, fade_out, apply_watermark=apply_wm)
            if result["success"]:
                st.success("✅ Music added!")
                vp = result["video_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
            else:
                st.error(f"❌ {result['message']}")

def render_feat_06():
    st.subheader("🎙️ Voiceover (TTS)")
    st.write("Text-to-speech voiceover add karein.")
    video_file = st.file_uploader("Upload Video", type=["mp4"], key="f07_upload")
    text = st.text_area("Voiceover Text", value="السلام علیکم، میں فلماء ہوں۔", key="f07_text")
    language = st.selectbox("Language", ["ur", "hi", "en"], key="f07_lang")
    speed = st.slider("Speed", 0.5, 2.0, 1.0, key="f07_speed")
    gender = st.selectbox("Gender", ["female", "male"], key="f07_gender")
    apply_wm = st.checkbox("Add Watermark", True, key="f07_wm")
    if video_file and text and st.button("🎙️ Add Voiceover", key="f07_gen"):
        if auth_gate.guest_locked("adding voiceover"):
            pass
        else:
            temp_video = os.path.join(PATHS.get("temp", "temp"), video_file.name)
            os.makedirs(os.path.dirname(temp_video), exist_ok=True)
            with open(temp_video, "wb") as f:
                f.write(video_file.getbuffer())
            with st.spinner("Generating voiceover..."):
                result = feat07.add_voiceover_to_video(temp_video, text, language, "gtts", speed, gender, apply_watermark=apply_wm)
            if result["success"]:
                st.success("✅ Voiceover added!")
                vp = result["video_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
            else:
                st.error(f"❌ {result['message']}")

def render_feat_07():
    st.subheader("📌 Watermark")
    st.write("Video mein text ya image watermark add karein.")
    video_file = st.file_uploader("Upload Video", type=["mp4"], key="f08_upload")
    text = st.text_input("Watermark Text", "FUTURE 4K", key="f08_text")
    font_size = st.slider("Font Size", 10, 60, 24, key="f08_fs")
    opacity = st.slider("Opacity", 0.1, 1.0, 0.7, key="f08_op")
    position = st.selectbox("Position", ["bottom-right", "bottom-left", "top-right", "top-left", "center"], key="f08_pos")
    if video_file and st.button("📌 Add Watermark", key="f08_gen"):
        if auth_gate.guest_locked("adding a watermark"):
            pass
        else:
            temp_video = os.path.join(PATHS.get("temp", "temp"), video_file.name)
            os.makedirs(os.path.dirname(temp_video), exist_ok=True)
            with open(temp_video, "wb") as f:
                f.write(video_file.getbuffer())
            with st.spinner("Adding watermark..."):
                result = feat08.add_text_watermark_ffmpeg(temp_video, text, position, font_size, "#FFFFFF", opacity)
            if result["success"]:
                st.success("✅ Watermark added!")
                vp = result["video_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
            else:
                st.error(f"❌ {result['message']}")

def render_feat_08():
    st.subheader("🕌 Urdu/Hindi Prompts")
    st.write("Prompt ko enhance karein.")
    text_input = st.text_area("Enter Text", value="ایک بہادر سپاہی", key="f09_text")
    language = st.selectbox("Language", ["ur", "hi", "en"], key="f09_lang")
    category = st.selectbox("Category", ["drama", "action", "romance", "poetry", "nature", "city", "fantasy"], key="f09_cat")
    if st.button("✨ Enhance Prompt", key="f09_enhance"):
        if language == "ur":
            result = feat09.enhance_urdu_prompt_full(text_input, category)
        elif language == "hi":
            result = feat09.enhance_hindi_prompt_full(text_input, category)
        else:
            result = text_input
        st.success("✅ Enhanced Prompt:")
        st.code(result)

def render_feat_09():
    st.subheader("📋 Prompt Templates")
    st.write("100+ ready-made prompt templates across 35+ categories.")

    lang_display = st.selectbox("Language / زبان", ["Urdu", "Hindi", "English"], index=0, key="f10_lang_display")
    lang_map = {"Urdu": "ur", "Hindi": "hi", "English": "en"}
    lang = lang_map[lang_display]

    category_names = feat10.get_category_names(lang)
    categories = feat10.get_all_categories()
    counts = feat10.get_category_templates_count(lang)

    def _fmt_cat(c):
        if c == "All":
            return "🗂️ All Categories"
        info = feat10.get_category_info(c) or {}
        name = category_names.get(c, c)
        cnt = counts.get(c, 0)
        return f"{info.get('emoji', '📌')} {name} ({cnt})"

    category = st.selectbox("Category", ["All"] + categories, format_func=_fmt_cat, key="f10_cat")
    search_query = st.text_input("🔍 Search", placeholder="Search by name, template text, or tags...", key="f10_search")

    if search_query:
        cats_filter = None if category == "All" else [category]
        templates = feat10.search_templates(search_query, lang, cats_filter)
        st.caption(f"🔍 {len(templates)} matching templates")
    elif category == "All":
        templates = feat10.get_all_templates(lang)
    else:
        templates = feat10.get_templates_by_category(category, lang)
        st.caption(f"📊 {len(templates)} templates in this category")

    if not templates:
        st.info("ℹ️ Is language mein abhi templates nahi hain — 'Urdu' try karo, sabse zyada templates wahan hain.")
    else:
        for t in templates[:20]:
            with st.container(border=True):
                cat_info = feat10.get_category_info(t.get("category")) or {}
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{cat_info.get('emoji', '📌')} {t['name']}**")
                    st.caption(f"📂 {category_names.get(t.get('category'), t.get('category'))}")
                    st.code(t['template'], language="text")
                    if t.get('tags'):
                        st.caption("🏷️ " + ", ".join(t['tags']))
                    rating = feat10.get_template_rating(t['id'])
                    rc1, rc2, rc3 = st.columns([2, 2, 2])
                    with rc1:
                        if rating["total_ratings"] > 0:
                            st.caption(f"{rating['stars']} ({rating['average_rating']}/5, {rating['total_ratings']} ratings)")
                        else:
                            st.caption("☆☆☆☆☆ No ratings yet")
                    with rc2:
                        star_pick = st.select_slider("Rate", options=[1, 2, 3, 4, 5], value=5,
                                                      key=f"f10_starpick_{t['id']}", label_visibility="collapsed")
                    with rc3:
                        if st.button("⭐ Submit Rating", key=f"f10_rate_{t['id']}", use_container_width=True):
                            result = feat10.rate_template(t['id'], star_pick)
                            if result["success"]:
                                st.success("✅ Rating saved!")
                                st.rerun()
                            else:
                                st.error(result["message"])
                with col2:
                    usage = feat10.get_template_usage_stats(t['id'])
                    if usage["usage_count"] > 0:
                        st.caption(f"📊 Used {usage['usage_count']}x")
                    if st.button("📝 Use", key=f"f10_use_{t['id']}", use_container_width=True):
                        st.session_state["t2v_prompt_field"] = t['template']
                        feat10.track_template_usage(t['id'])
                        st.success("✅ Text-to-Video mein bhej diya!")

        if len(templates) > 20:
            st.info(f"ℹ️ {len(templates)} mein se 20 dikhaye ja rahe hain — specific templates ke liye search use karo.")

    with st.expander("🔥 Popular Templates (most used)"):
        popular = feat10.get_popular_templates(lang, 5)
        if popular:
            for p in popular:
                st.markdown(f"**{p.get('name')}** — used {p.get('usage_count')}x")
                st.code(p.get('template'), language="text")
        else:
            st.caption("Abhi koi usage data nahi hai — templates use karo, yahan dikhne lagenge.")

    with st.expander("✏️ Apna Custom Template Banao"):
        cc1, cc2 = st.columns(2)
        with cc1:
            custom_name = st.text_input("Template Name", placeholder="Mera Template", key="f10_custom_name")
            custom_category = st.selectbox("Category", categories, format_func=lambda c: _fmt_cat(c), key="f10_custom_cat")
        with cc2:
            custom_vars = st.text_input("Variables (comma separated)", placeholder="character, action, setting", key="f10_custom_vars")
            custom_tags = st.text_input("Tags (comma separated)", placeholder="custom, personal", key="f10_custom_tags")
        custom_text = st.text_area("Template Text", placeholder="e.g. Ek {character} {setting} mein {action} kar raha hai",
                                    height=100, key="f10_custom_text")
        if st.button("💾 Save Custom Template", key="f10_save_custom"):
            if not custom_name or not custom_text:
                st.error("❌ Naam aur template text dono chahiye.")
            else:
                vars_list = [v.strip() for v in custom_vars.split(",") if v.strip()]
                tags_list = [tg.strip() for tg in custom_tags.split(",") if tg.strip()]
                saved = feat10.save_custom_template(custom_name, custom_text, custom_category, lang, vars_list, tags_list)
                if saved:
                    st.success("✅ Custom template save ho gaya!")
                    st.rerun()
                else:
                    st.error("❌ Save nahi ho saka, dobara try karo.")

        custom_templates = feat10.get_custom_templates(lang)
        if custom_templates:
            st.markdown("**Tumhare Custom Templates:**")
            for ct in custom_templates:
                cc_col1, cc_col2 = st.columns([4, 1])
                with cc_col1:
                    st.markdown(f"**{ct.get('name')}**")
                    st.code(ct.get('template'), language="text")
                with cc_col2:
                    if st.button("🗑️ Delete", key=f"f10_del_custom_{ct['id']}", use_container_width=True):
                        if feat10.delete_custom_template(ct['id']):
                            st.success("✅ Deleted!")
                            st.rerun()

def render_feat_10():
    st.subheader("🚫 Negative Prompting")
    st.write("AI ko batao ke video mein kya NAHI hona chahiye.")
    negative_input = st.text_area("Negative Prompts (comma separated)", value="blurry, watermark, low quality", key="f11_text")
    category = st.selectbox("Category", ["drama", "action", "romance", "poetry", "nature", "city", "fantasy"], key="f11_cat")
    if st.button("🔨 Build Negative Prompt", key="f11_build"):
        negatives = [n.strip() for n in negative_input.split(",") if n.strip()]
        result = feat11.build_negative_prompt(negatives, True, category)
        st.success("✅ Generated Negative Prompt:")
        st.code(result)

def render_feat_11():
    st.subheader("📚 Video Library")
    st.write("All generated videos in one place.")
    videos = feat12.get_all_videos()
    st.info(f"Total videos: {len(videos)}")
    for v in videos[:10]:
        with st.expander(f"🎬 {v.get('filename', 'Unknown')}"):
            st.caption(f"Prompt: {v.get('prompt', 'N/A')}")
            st.caption(f"Duration: {v.get('duration', 0):.1f}s | Resolution: {v.get('resolution', 'N/A')}")

def render_feat_12():
    st.subheader("📁 Folder Organization")
    st.write("Videos ko folders mein organize karein.")
    folders = feat13.get_all_folders()
    for f in folders:
        with st.expander(f"📁 {f.get('name', 'Unknown')}"):
            st.caption(f"ID: {f.get('id')}")
            st.caption(f"Videos: {f.get('video_count', 0)}")
    folder_name = st.text_input("New Folder Name", key="f13_name")
    if st.button("📁 Create Folder", key="f13_create"):
        result = feat13.create_folder(folder_name)
        if result["success"]:
            st.success("✅ Folder created!")
            st.rerun()
        else:
            st.error(f"❌ {result['message']}")

def render_feat_13():
    st.subheader("⭐ Favorites & Collections")
    st.write("Favorite videos save karein aur collections banayein.")
    tab_fav, tab_col = st.tabs(["⭐ Favorites", "📁 Collections"])
    with tab_fav:
        favorites = feat14.get_all_favorites()
        st.info(f"⭐ {len(favorites)} favorites")
        for f in favorites[:5]:
            with st.expander(f"⭐ {f.get('video_title', 'Unknown')}"):
                st.caption(f"Added: {f.get('added_at', 'N/A')}")
    with tab_col:
        collections = feat14.get_all_collections()
        for c in collections:
            with st.expander(f"📁 {c.get('name', 'Unknown')}"):
                st.caption(f"Videos: {c.get('video_count', 0)}")

def render_feat_14():
    st.subheader("💰 Pay-Per-Video Wallet")
    st.write("Top up your USD wallet and pay only for what you generate")
    user_id = st.session_state.get("current_user_id", "")
    user_id = st.text_input("User ID", value=user_id or "test_ppv_user_001", key="f17_user")
    if user_id:
        st.session_state["current_user_id"] = user_id
        tab1, tab2, tab3, tab4 = st.tabs(["💳 Wallet", "📲 Manual Payments", "🧮 Price Calculator", "📊 Stats"])
        with tab1:
            balance = feat17.get_wallet_balance(user_id)
            st.metric("💰 Wallet Balance", f"${balance.get('balance', 0):.2f}")
            st.caption(f"Lifetime top-ups: ${balance.get('total_topped_up', 0):.2f} · Lifetime spend: ${balance.get('total_spent', 0):.2f}")
            st.info("Wallet top-up kernay kayliay 'Manual Payments ' tab use karo.")
            custom_amount = st.number_input("Custom amount (USD)", min_value=0.0, step=1.0, key="f17_custom_amount")
            if st.button("💳 Top Up Custom Amount", key="f17_custom_topup"):
                if auth_gate.guest_locked("topping up your wallet"):
                    pass
                else:
                    result = feat17.top_up_wallet(user_id, custom_amount, "card")
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])
        with tab2:
            st.write("Manual top-up requests (Admin verification required).")
            all_methods = manual_payments.get_all_payment_instructions()
            if not all_methods:
                st.warning("⚠️ Koi payment method abhi admin ne configure nahi ki. Admin Panel → Manual Payments setup karo.")
            else:
                method_names = [m["method"] for m in all_methods]
                selected_method = st.selectbox("Payment Method", method_names, key="manual_pay_method")
                selected_details = next((m for m in all_methods if m["method"] == selected_method), None)
                if selected_details:
                    extra_info = f" ({selected_details['extra']})" if selected_details.get("extra") else ""
                    st.markdown(
                        f"""
                        <div style="background:#E8F5E9; border-radius:10px; padding:1rem; text-align:center;">
                            <div style="font-size:0.9rem; color:#0B7F4F;">Send payment to</div>
                            <div style="font-size:1.6rem; font-weight:800; color:#14181F;">{selected_details['account_label']}</div>
                            <div style="font-size:1.1rem; color:#0FA968; font-weight:700;">{selected_method}: {selected_details['number']}{extra_info}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                st.caption("1️⃣ Apne payment app se upar diye number par payment bhejo. 2️⃣ Neeche amount + Transaction ID daal kar submit karo. 3️⃣ Admin confirm karega, phir wallet credit ho jayega.")
                jc_amount = st.number_input("Amount Sent (PKR)", min_value=0.0, step=50.0, key="jc_amount")
                jc_txn_id = st.text_input("Transaction ID", key="jc_txn_id", placeholder="e.g. JC20260808123456")
                if st.button("📤 Submit for Verification", key="jc_submit", use_container_width=True):
                    if auth_gate.guest_locked("submitting a manual payment"):
                        pass
                    else:
                        result = manual_payments.create_request(
                            user_id=user_id, amount=jc_amount, txn_id=jc_txn_id,
                            method=selected_method,
                            user_email=st.session_state.get("user_email", ""),
                        )
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])

                st.divider()
                st.markdown("**Your Pending Requests**")
                my_requests = manual_payments.get_user_requests(user_id, limit=10)
                if my_requests.get("success") and my_requests.get("requests"):
                    STATUS_ICON = {"pending": "🟡 Pending", "approved": "✅ Approved", "rejected": "🔴 Rejected"}
                    for r in my_requests["requests"]:
                        st.caption(f"{STATUS_ICON.get(r['status'], r['status'])} — Rs. {r['amount']:.0f} — Txn: {r['txn_id']} ({r.get('method', 'JazzCash')})"
                                   + (f" — {r['admin_note']}" if r.get('admin_note') and r['status'] == 'rejected' else ""))
                else:
                    st.caption("Abhi koi request nahi.")
        with tab3:
            st.write("See exactly what any video would cost before you generate it.")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                calc_dur = st.number_input("Duration (s)", min_value=1, value=10, key="f17_calc_dur")
            with cc2:
                res_options = list(feat24.get_resolution_multipliers().keys()) or ["720p"]
                calc_res = st.selectbox("Resolution", res_options, key="f17_calc_res")
            with cc3:
                qual_options = list(feat24.get_quality_multipliers().keys()) or ["standard"]
                calc_qual = st.selectbox("Quality", qual_options, key="f17_calc_qual")
            estimate = feat17.estimate_price(calc_dur, calc_res, calc_qual, user_id)
            st.metric("💰 Price", f"${estimate.get('final_price', 0):.2f}")
            with st.expander("Breakdown"):
                st.json(estimate)
        with tab4:
            stats = feat17.get_ppv_stats()
            st.json(stats)
            st.divider()
            st.markdown("**Your stats**")
            st.json(feat17.get_user_ppv_stats(user_id))

def render_feat_15():
    st.subheader("🎯 Launch Discount")
    st.write("First 200 early adopters will get 40% discount")
    status = feat18.get_discount_status()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎟️ Total", status.get("total_slots", 200))
    col2.metric("✅ Used", status.get("used_slots", 0))
    col3.metric("📊 Left", status.get("remaining_slots", 0))
    col4.metric("🎯 Discount", f"{status.get('discount_percent', 20)}%")
    fill_pct = status.get("fill_percentage", 0)
    st.progress(fill_pct / 100)
    st.caption(f"🔥 {fill_pct:.1f}% filled - {status.get('remaining_slots', 0)} slots left")
    discount_user_id = st.text_input("User ID", key="discount_user_id_18")
    discount_code = st.text_input("Referral Code (optional)", key="discount_code_18")
    if st.button("Apply Discount", key="apply_discount_btn_18"):
        if discount_user_id:
            result = feat18.apply_discount(discount_user_id, discount_code or None)
            if result["success"]:
                st.success(f"✅ {result['message']}")
                st.json(result.get("discount", {}))
            else:
                st.error(f"❌ {result['message']}")
        else:
            st.warning("Please enter a user ID")

def render_feat_16():
    st.subheader("💬 Feedback System")
    st.write("Apni raaye dein, feature request karein, ya bug report karein")
    fb_tab1, fb_tab2, fb_tab3, fb_tab4, fb_tab5 = st.tabs([
        "📝 Submit", "🚀 Feature Request", "🐛 Bug Report", "📊 Analytics", "📋 Surveys"
    ])
    with fb_tab1:
        st.markdown("### 📝 Submit Feedback")
        fb_user_id = st.text_input("User ID", value="test_user_001", key="fb_user_id_19")
        fb_rating = st.slider("Rating", 1, 5, 4, key="fb_rating_19")
        fb_comment = st.text_area("Comment", height=100, key="fb_comment_19")
        fb_category = st.selectbox("Category", ["general", "video", "feature", "ux", "performance", "bug", "other"], key="fb_category_19")
        if st.button("Submit Feedback", key="fb_submit_btn_19"):
            if not fb_comment:
                st.error("Please provide a comment")
            else:
                result = feat19.submit_feedback(user_id=fb_user_id, rating=fb_rating, comment=fb_comment, category=fb_category, is_anonymous=False)
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                else:
                    st.error(f"❌ {result['message']}")
    with fb_tab2:
        st.markdown("### 🚀 Feature Request")
        fr_title = st.text_input("Title", key="fr_title_19")
        fr_description = st.text_area("Description", height=100, key="fr_description_19")
        if st.button("Submit Request", key="fr_submit_btn_19"):
            if fr_title and fr_description:
                result = feat19.submit_feature_request(user_id="test_user_001", title=fr_title, description=fr_description, priority="medium", category="feature")
                if result["success"]:
                    st.success(f"✅ {result['message']}")
            else:
                st.error("Title and description required")
    with fb_tab3:
        st.markdown("### 🐛 Bug Report")
        bug_title = st.text_input("Title", key="bug_title_19")
        bug_description = st.text_area("Description", height=100, key="bug_description_19")
        bug_severity = st.selectbox("Severity", ["critical", "high", "medium", "low"], key="bug_severity_19")
        if st.button("Submit Bug", key="bug_submit_btn_19"):
            if bug_title and bug_description:
                result = feat19.submit_bug_report(user_id="test_user_001", title=bug_title, description=bug_description, severity=bug_severity, steps_to_reproduce=[])
                if result["success"]:
                    st.success(f"✅ {result['message']}")
            else:
                st.error("Title and description required")
    with fb_tab4:
        st.markdown("### 📊 Analytics")
        if st.button("Refresh", key="fb_refresh_19"):
            analytics = feat19.get_feedback_analytics()
            st.json(analytics)
    with fb_tab5:
        st.markdown("### 📋 Surveys")
        surveys = feat19.get_all_surveys(active_only=True)
        for survey in surveys.get("surveys", []):
            with st.expander(f"📝 {survey.get('title')}"):
                st.caption(f"Responses: {survey.get('response_count', 0)}")

# ============================================================
# NEW FEATURES 20-25
# ============================================================

def render_feat_17():
    st.subheader("🆔 Character Consistency (ID-Embedding)")
    st.write("3-5 reference images upload karo aur AI us character ko consistent rakhega across multiple scenes. WAN 2.6 R2V (recommended) ya LTX 2.3 support.")
    engine = st.radio("Engine", ["WAN 2.6 R2V (Recommended)", "LTX 2.3"], index=0, key="id_engine")
    col1, col2 = st.columns(2)
    with col1:
        ref_files = st.file_uploader("Reference Images (3-5)", type=["jpg", "jpeg", "png", "mp4"], accept_multiple_files=True, key="id_refs")
    with col2:
        id_prompt = st.text_area("Prompt", "character1 walks through the city", key="id_prompt", height=100)
        id_duration = st.selectbox("Duration", [5, 10], index=1, key="id_dur")
        id_res = st.selectbox("Resolution", ["720p", "1080p"], key="id_res")
    render_live_price(id_duration, id_res, "high", "idembed")
    if st.button("🎬 Generate Consistent Character", type="primary", key="id_gen"):
        if auth_gate.guest_locked("character-consistent video generation"):
            pass
        elif not ref_files or len(ref_files) < 2:
            st.error("❌ Please upload at least 2 reference files (3-5 recommended).")
        elif not id_prompt or len(id_prompt.strip()) < 3:
            st.error("❌ Please enter a prompt.")
        else:
            ok, charge = charge_wallet_or_block(id_duration, id_res, "high", "character_consistency")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
                return
            st.success(f"💳 {charge.get('message')}")
            ref_paths = []
            for i, file in enumerate(ref_files[:3]):
                path = os.path.join(PATHS.get("temp", "temp"), f"ref_{i}_{file.name}")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
                ref_paths.append(path)
            with st.spinner("🎬 Generating character-consistent video..."):
                if engine == "WAN 2.6 R2V (Recommended)":
                    result = feat20.generate_with_character_wan(prompt=id_prompt, reference_paths=ref_paths, resolution=id_res, duration=id_duration, apply_watermark=True)
                else:
                    result = feat20.generate_with_character_ltx(prompt=id_prompt, reference_image_path=ref_paths[0] if ref_paths else None, resolution="1920x1080", duration=id_duration, apply_watermark=True)
            for p in ref_paths:
                if os.path.exists(p):
                    os.remove(p)
            if result["success"]:
                st.success(f"✅ {result['message']}")
                vp = result["video_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
                    with open(vp, "rb") as f:
                        st.download_button("📥 Download", f, os.path.basename(vp), "video/mp4")
            else:
                st.error(f"❌ {result['message']}")

def render_feat_18():
    st.subheader("🎥 Camera Motion Control (2K/4K)")
    st.write("Cinematic camera commands — dolly, pan, tilt, zoom, orbit, crane.")
    col1, col2 = st.columns(2)
    with col1:
        cm_prompt = st.text_area("Scene Description", "A car driving through a desert at sunset", key="cm_prompt", height=100)
    with col2:
        cm_motion = st.selectbox("Camera Motion", list(feat21.CAMERA_MOTIONS.keys()), key="cm_motion")
        cm_res = st.selectbox("Resolution", ["2k", "4k"], key="cm_res")
        cm_dur = st.slider("Duration (s)", 5, 20, 8, key="cm_dur")
    render_live_price(cm_dur, cm_res, "high", "cammotion")
    if st.button("🎬 Generate with Camera Motion", type="primary", key="cm_gen"):
        if auth_gate.guest_locked("camera motion generation"):
            pass
        elif not cm_prompt or len(cm_prompt.strip()) < 3:
            st.error("❌ Please enter a scene description.")
        else:
            ok, charge = charge_wallet_or_block(cm_dur, cm_res, "high", "camera_motion")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
                return
            st.success(f"💳 {charge.get('message')}")
            with st.spinner(f"🎬 Generating {cm_res.upper()} video with {cm_motion}..."):
                result = feat21.generate_with_camera_motion(prompt=cm_prompt, camera_motion=cm_motion, resolution=cm_res, duration=cm_dur, apply_watermark=True)
            if result["success"]:
                st.success(f"✅ {result['message']}")
                vp = result["video_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
                    with open(vp, "rb") as f:
                        st.download_button("📥 Download", f, os.path.basename(vp), "video/mp4")
            else:
                st.error(f"❌ {result['message']}")

def render_feat_19():
    st.subheader("🖼️ Frame-to-Frame Control")
    st.write("Start frame aur end frame define karo — AI beech ki sequence generate karega.")
    col1, col2 = st.columns(2)
    with col1:
        start_frame = st.file_uploader("Start Frame", type=["jpg", "jpeg", "png"], key="ftf_start")
        end_frame = st.file_uploader("End Frame", type=["jpg", "jpeg", "png"], key="ftf_end")
    with col2:
        ftf_prompt = st.text_area("Motion Description", "Smooth transition, camera holds steady", key="ftf_prompt", height=100)
        ftf_model = st.selectbox("Model", ["ltx-2-3-pro", "ltx-2-3-fast"], key="ftf_model")
        ftf_dur = st.slider("Duration (s)", 3, 10, 5, key="ftf_dur")
    render_live_price(ftf_dur, "1080p", "standard", "ftf")
    if st.button("🎬 Generate Frame Interpolation", type="primary", key="ftf_gen"):
        if auth_gate.guest_locked("frame interpolation"):
            pass
        elif not start_frame or not end_frame:
            st.error("❌ Please upload both start and end frames.")
        elif not ftf_prompt or len(ftf_prompt.strip()) < 3:
            st.error("❌ Please enter a motion description.")
        else:
            ok, charge = charge_wallet_or_block(ftf_dur, "1080p", "standard", "frame_to_frame")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
                return
            st.success(f"💳 {charge.get('message')}")
            temp_start = os.path.join(PATHS.get("temp", "temp"), f"ftf_start_{start_frame.name}")
            temp_end = os.path.join(PATHS.get("temp", "temp"), f"ftf_end_{end_frame.name}")
            os.makedirs(os.path.dirname(temp_start), exist_ok=True)
            with open(temp_start, "wb") as f:
                f.write(start_frame.getbuffer())
            with open(temp_end, "wb") as f:
                f.write(end_frame.getbuffer())
            with st.spinner("🎬 Generating frame interpolation..."):
                result = feat22.generate_frame_interpolation(first_frame_path=temp_start, last_frame_path=temp_end, prompt=ftf_prompt, model=ftf_model, duration=ftf_dur, apply_watermark=True)
            if os.path.exists(temp_start):
                os.remove(temp_start)
            if os.path.exists(temp_end):
                os.remove(temp_end)
            if result["success"]:
                st.success(f"✅ {result['message']}")
                vp = result["video_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
                    with open(vp, "rb") as f:
                        st.download_button("📥 Download", f, os.path.basename(vp), "video/mp4")
            else:
                st.error(f"❌ {result['message']}")

def render_feat_20():
    st.subheader("🔗 Stitching — Seamless Multi-Clip Join")
    st.write("Multiple clips ko FFmpeg xfade transitions ke saath stitch karo.")
    uploaded_clips = st.file_uploader("Upload Clips (2+)", type=["mp4"], accept_multiple_files=True, key="stitch_clips")
    if uploaded_clips and len(uploaded_clips) >= 2:
        st.caption(f"📹 {len(uploaded_clips)} clips uploaded")
    col1, col2 = st.columns(2)
    with col1:
        transition = st.selectbox("Transition", list(feat23.VALID_TRANSITIONS), key="stitch_trans")
    with col2:
        trans_dur = st.slider("Transition Duration (s)", 0.1, 2.0, 1.0, 0.1, key="stitch_dur")
    _stitch_est_dur = (len(uploaded_clips) * 5) if uploaded_clips else 5
    render_live_price(_stitch_est_dur, "1080p", "standard", "stitch")
    if st.button("🔗 Stitch Clips", type="primary", key="stitch_gen"):
        if auth_gate.guest_locked("clip stitching"):
            pass
        elif not uploaded_clips or len(uploaded_clips) < 2:
            st.error("❌ Please upload at least 2 clips.")
        else:
            ok, charge = charge_wallet_or_block(_stitch_est_dur, "1080p", "standard", "stitching")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
                return
            st.success(f"💳 {charge.get('message')}")
            clip_paths = []
            for i, clip in enumerate(uploaded_clips):
                path = os.path.join(PATHS.get("temp", "temp"), f"stitch_{i}_{clip.name}")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(clip.getbuffer())
                clip_paths.append(path)
            with st.spinner("🔗 Stitching clips together..."):
                result = feat23.stitch_clips(video_paths=clip_paths, transition=transition, transition_duration=trans_dur, output_resolution="1920x1080", output_fps=30)
            for p in clip_paths:
                if os.path.exists(p):
                    os.remove(p)
            if result["success"]:
                st.success(f"✅ {result['message']}")
                vp = result["video_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
                    with open(vp, "rb") as f:
                        st.download_button("📥 Download", f, os.path.basename(vp), "video/mp4")
            else:
                st.error(f"❌ {result['message']}")

def render_feat_21():
    st.subheader("🔐 Admin Panel")
    admin_tabs = st.tabs(["💰 Pricing & Discounts", "👥 Users & Security"])
    with admin_tabs[0]:
        st.write("Password-protected admin panel. Manage the global dynamic pricing formula, flat prices, user overrides, and discounts.")
        feat24.render_admin_page()
    with admin_tabs[1]:
        st.write("Password-protected. View every registered user, the permanent OTP security log, and block/unblock any account with a reason on record.")
        admin_panel.render_admin_page()

def render_feat_22():
    st.subheader("🧠 Scene Planner — Long-Form Video Breakdown")
    st.write("Ek lambi video (jaisay 2-5 minute) ke liye ek hi 'master' prompt likho — AI usay chhotay, continuous scenes mein tod dega. Har scene generate ho kar aakhir mein aapas mein stitch ho jayega.")
    settings = feature_25_scene_planner.get_settings()
    if not settings.get("api_key"):
        st.warning("⚠️ Scene Planner abhi admin ne configure nahi ki. Admin Panel → 🧠 Scene Planner (AI) tab mein provider/API key set honi chahiye.")
    master_prompt = st.text_area("Master Story Prompt", height=120, key="sp_master_prompt", placeholder="Misaal: Ek larka jungle mein safar karta hai aur purana khazana dhoondta hai")
    c1, c2, c3 = st.columns(3)
    with c1:
        total_min = st.number_input("Total Duration (minutes)", 0, 30, 1, key="sp_total_min")
        total_sec = st.number_input("+ seconds", 0, 59, 0, key="sp_total_sec")
    with c2:
        chunk_duration = st.slider("Chunk Length (s)", 4, 15, int(settings["default_chunk_duration"]), key="sp_chunk_dur")
    with c3:
        sp_res = st.selectbox("Resolution", ["720p", "1080p"], index=1, key="sp_res")
    total_duration = int(total_min) * 60 + int(total_sec)
    st.markdown("**🆔 Character Consistency (optional)**")
    ref_files = st.file_uploader("Reference Images (2-5, optional — keeps the same character across every scene)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="sp_refs")
    sp_camera_motion = st.selectbox(
        "🎥 Camera Motion (used when no character references are uploaded)",
        ["None"] + list(feat21.CAMERA_MOTIONS.keys()),
        key="sp_camera_motion",
        help="Agar reference images nahi de rahe, ye camera motion har scene par apply hoga. 'None' rakha to plain generation use hogi.",
    )
    if st.button("📋 Plan Scenes", key="sp_plan_btn", use_container_width=True):
        if auth_gate.guest_locked("scene planning"):
            pass
        elif not master_prompt or len(master_prompt.strip()) < 5:
            st.error("❌ Pehle master prompt likho.")
        elif total_duration < chunk_duration:
            st.error(f"❌ Total duration kam az kam {chunk_duration}s honi chahiye.")
        else:
            with st.spinner("🧠 AI scenes plan kar raha hai..."):
                plan = feature_25_scene_planner.plan_scenes(master_prompt, total_duration, chunk_duration)
            if not plan["success"]:
                st.error(plan["message"])
            else:
                st.session_state["sp_planned_scenes"] = plan["scenes"]
                st.session_state["sp_plan_meta"] = plan
                st.success(f"✅ {plan['num_chunks']} scenes planned!")
                st.rerun()
    if st.session_state.get("sp_planned_scenes"):
        scenes = st.session_state["sp_planned_scenes"]
        st.divider()
        st.markdown(f"### 📝 Review & Edit — {len(scenes)} Scenes")
        st.caption("AI ne yeh scenes banaye hain — chaho to edit kar lo confirm karne se pehle.")
        edited_scenes = []
        for i, scene_text in enumerate(scenes):
            edited = st.text_area(f"Scene {i + 1}", value=scene_text, height=70, key=f"sp_scene_edit_{i}")
            edited_scenes.append(edited)
        st.session_state["sp_planned_scenes"] = edited_scenes
        cost_est = feature_25_scene_planner.estimate_cost_and_time(total_duration, sp_res, "standard", chunk_duration)
        st.divider()
        cc1, cc2 = st.columns(2)
        cc1.metric("💰 Estimated Cost", f"${cost_est.get('estimated_cost', 0):.2f}")
        cc2.metric("⏱️ Estimated Time", f"~{cost_est.get('estimated_minutes', 0)} min")
        st.caption("💡 Confirm karne ke baad yeh background mein queue ho jayega — tab band kar sakte ho, processing hamare server pe chalti rahegi. Progress 'My Jobs' (Profile tab) mein dikhega, aur ready hote hi email aayega.")
        if st.button("🎬 Confirm & Generate Full Video", type="primary", key="sp_generate_btn", use_container_width=True):
            if auth_gate.guest_locked("long-form video generation"):
                pass
            else:
                ok, charge = charge_wallet_or_block(total_duration, sp_res, "high", "scene_planner_longform")
                if not ok:
                    st.error(f"❌ {charge.get('message')}")
                else:
                    st.success(f"💳 {charge.get('message')}")
                    ref_paths = []
                    for i, file in enumerate(ref_files or []):
                        path = os.path.join(PATHS.get("temp", "temp"), f"sp_ref_{i}_{file.name}")
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, "wb") as f:
                            f.write(file.getbuffer())
                        ref_paths.append(path)
                    job_id = job_queue.create_job(
                        user_id=st.session_state.get("current_user_id", ""),
                        user_email=st.session_state.get("user_email", ""),
                        job_type="long_form_video",
                        payload={
                            "scenes": edited_scenes,
                            "reference_paths": ref_paths,
                            "camera_motion": sp_camera_motion,
                            "resolution": sp_res,
                            "chunk_duration": chunk_duration,
                        },
                        eta_minutes=cost_est.get("estimated_minutes", 0),
                    )
                    st.success(f"✅ Job #{job_id} queue mein daal diya gaya hai!\n\n⏱️ Estimated time: **~{cost_est.get('estimated_minutes', 0)} minutes**\n\n👀 Progress 'Profile → 📋 My Jobs' mein dekh sakte ho. Video ready hote hi email par notify ho jayega.")
                    st.session_state.pop("sp_planned_scenes", None)
                    st.session_state.pop("sp_plan_meta", None)

def render_feat_23():
    st.subheader("📋 My Jobs")
    st.write("Aapki background mein queue hui long-form videos ka status.")
    user_id = st.session_state.get("current_user_id", "")
    if not user_id:
        st.warning("⚠️ Sidebar mein User ID set karo jobs dekhne ke liye.")
        return
    if st.button("🔄 Refresh", key="myjobs_refresh"):
        st.rerun()
    jobs = job_queue.get_user_jobs(user_id, limit=20)
    if not jobs:
        st.info("Abhi koi job nahi — Scene Planner se ek long-form video queue karo, yahan dikhegi.")
        return
    STATUS_LABELS = {"queued": "🟡 Queued", "processing": "🔵 Processing", "done": "✅ Done", "failed": "❌ Failed", "cancelled": "⚪ Cancelled"}
    for job in jobs:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**Job #{job['id']}** — {STATUS_LABELS.get(job['status'], job['status'])}")
                if job["status"] == "processing" and job["progress_total"]:
                    pct = job["progress_current"] / max(job["progress_total"], 1)
                    st.progress(min(pct, 1.0))
                    st.caption(f"{job['progress_label']} ({job['progress_current']}/{job['progress_total']})")
                elif job["status"] == "queued":
                    st.caption(f"⏱️ Estimated time: ~{job.get('eta_minutes') or '?'} minutes")
                elif job["status"] == "failed":
                    st.caption(f"Error: {job.get('error_message', 'Unknown error')}")
            with c2:
                if job["status"] == "queued":
                    if st.button("🗑️ Cancel", key=f"myjobs_cancel_{job['id']}", use_container_width=True):
                        cancel_result = job_queue.cancel_job(job["id"])
                        if cancel_result.get("success"):
                            st.success(cancel_result.get("message", "Cancelled."))
                            st.rerun()
                        else:
                            st.error(cancel_result.get("message", "Could not cancel this job."))
            if job["status"] == "done" and job.get("result_path"):
                vp = job["result_path"]
                if os.path.exists(vp) and os.path.getsize(vp) > 100:
                    st.video(vp)
                    with open(vp, "rb") as f:
                        st.download_button("📥 Download", f, os.path.basename(vp), "video/mp4", key=f"myjobs_dl_{job['id']}")

# ============================================================
# NAVIGATION
# ============================================================

FEATURE_RENDERERS = [
    render_feat_00, render_feat_01, render_feat_02, render_feat_03,
    render_feat_04, render_feat_05, render_feat_06, render_feat_07,
    render_feat_08, render_feat_09, render_feat_10, render_feat_11,
    render_feat_12, render_feat_13, render_feat_14, render_feat_15,
    render_feat_16, render_feat_17, render_feat_18, render_feat_19,
    render_feat_20, render_feat_21, render_feat_22, render_feat_23
]

TOOLS_GROUPS = [
    ('Create', [0, 1, 2, 3], '🎬', 'Generate brand-new videos'),
    ('Enhance', [4, 5, 6, 7], '🛠️', 'Polish and finish your videos'),
    ('Prompt Tools', [8, 9, 10], '✨', 'Write better prompts'),
    ('Advanced', [17, 18, 19, 20, 22], '⚡', 'Pro-level controls, stitching & long-form AI planning'),
]

DESCRIPTIONS = {
    0: 'Prompt se seedha AI video banao. 4K support.',
    1: 'Images ko motion do. Custom size + Story Mode.',
    2: 'Reels/Shorts ke liye clip. Platform presets + 4K.',
    3: 'Apni maujudaa video ko extend karay.',
    4: 'Clips arrange aur render karo.',
    5: 'Background music add karo.',
    6: 'TTS voiceover generate karo.',
    7: 'Text / logo type watermark lagao.',
    8: 'Urdu/Hindi prompt enhance karo.',
    9: 'Ready-made templates wasool karay.',
    10: 'Batao video mein kya nahi chahiye.',
    17: '3-5 images se consistent character rakho.',
    18: 'Cinematic camera controls — 2K/4K.',
    19: 'Start aur end frame ke beech generate karo.',
    20: 'Multiple clips ko seamless stitch karo.',
    22: 'Ek master prompt se lambi (multi-minute) video plan + generate karo.',
}

NAMES = [
    '📝 Text-to-Video', '🖼️ Image-to-Video', '✂️ 30-Second Clip', '📏 Extend Video',
    '⏳ Timeline Editor', '🎵 Background Music', '🎙️ Voiceover', '📌 Watermark',
    '🕌 Urdu/Hindi Prompts', '📋 Prompt Templates', '🚫 Negative Prompting',
    '📚 Video Library', '📁 Folder Organization', '⭐ Favorites & Collections',
    '💰 Pay-Per-Video', '🎯 Launch Discount', '💬 Feedback System',
    '🆔 Character Consistency', '🎥 Camera Motion', '🖼️ Frame-to-Frame', '🔗 Stitching',
    '🧠 Scene Planner'
]

icons = ['📝', '🖼️', '✂️', '📏', '⏳', '🎵', '🎙️', '📌', '🕌', '📋', '🚫', '📚', '📁', '⭐', '💰', '🎯', '💬', '🆔', '🎥', '🖼️', '🔗', '🔐', '🧠', '📋']
titles = [
    'Text-to-Video', 'Image-to-Video', '30-Second Clip', 'Extend Video',
    'Timeline Editor', 'Background Music', 'Voiceover', 'Watermark',
    'Urdu/Hindi Prompts', 'Prompt Templates', 'Negative Prompting',
    'Video Library', 'Folder Organization', 'Favorites & Collections',
    'Pay-Per-Video', 'Launch Discount', 'Feedback System',
    'Character Consistency', 'Camera Motion', 'Frame-to-Frame', 'Stitching',
    'Admin Panel', 'Scene Planner', 'My Jobs'
]
QUICK_ACTION_IDX = [0, 1, 2, 3]

def open_tool(i):
    st.session_state["active_nav"] = "🛠️ Tools"
    st.session_state["active_tool"] = i

def render_tool_card(idx, key_prefix):
    with st.container(border=True):
        st.markdown(f'<div class="fm-icon-chip">{icons[idx]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="fm-card-title">{titles[idx]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="fm-card-desc">{DESCRIPTIONS.get(idx, "")}</div>', unsafe_allow_html=True)
        st.button("Open →", key=f"{key_prefix}_{idx}", on_click=open_tool, args=(idx,), type="primary", use_container_width=True)

def render_tool_detail(idx):
    st.button("← Back", key=f"back_{idx}", on_click=lambda: st.session_state.update(active_tool=None))
    st.markdown('<div class="fm-crumb">Tools</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="fm-detail-title">{icons[idx]} {titles[idx]}</div>', unsafe_allow_html=True)
    FEATURE_RENDERERS[idx]()

NAV_OPTIONS = ["🏠 Home", "🔥 Trending", "🛠️ Tools", "📁 Assets", "👤 Profile"]
if "active_nav" not in st.session_state:
    st.session_state["active_nav"] = "🏠 Home"
if "active_tool" not in st.session_state:
    st.session_state["active_tool"] = None

import base64 as _base64

def _get_base64_of_file(path):
    try:
        with open(path, "rb") as f:
            return _base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

_logo_b64 = _get_base64_of_file(LOGO_PATH) if _LOGO_AVAILABLE else None

if _logo_b64:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:0.2rem;">
            <img src="data:image/png;base64,{_logo_b64}" style="height:56px; width:auto;" />
            <div>
                <div style="font-family:Sora,sans-serif; font-weight:800; font-size:1.9rem; line-height:1.1; color:#14181F;">FUTURE 4K</div>
                <div style="font-size:0.85rem; color:#626B76; letter-spacing:0.03em;">YOUR VISION . OUR AI .</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown("## FUTURE 4K")
    st.caption("YOUR VISION . OUR AI .")

active_nav = st.radio("Navigate", NAV_OPTIONS, key="active_nav", label_visibility="collapsed", horizontal=True)
st.divider()

# HOME
if active_nav == "🏠 Home":
    videos, favorites = [], []
    try:
        videos = feat12.get_all_videos()
    except Exception:
        pass
    try:
        favorites = feat14.get_all_favorites()
    except Exception:
        pass
    total_duration = sum(v.get("duration", 0) for v in videos) if videos else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("🎬 Total Videos", len(videos))
    c2.metric("⏱️ Total Duration", f"{total_duration:.0f}s")
    c3.metric("⭐ Favorites", len(favorites))

    st.markdown('<div class="fm-section-title"><span class="ico">🚀</span><span class="lbl">Quick Actions</span></div>', unsafe_allow_html=True)
    qa_cols = st.columns(4)
    for pos, idx in enumerate(QUICK_ACTION_IDX):
        with qa_cols[pos]:
            render_tool_card(idx, "home_qa")

    st.markdown('<div class="fm-section-title"><span class="ico">📹</span><span class="lbl">Recent Videos</span></div>', unsafe_allow_html=True)
    if videos:
        for v in videos[:5]:
            st.markdown(f"🎬 **{v.get('filename', 'Unknown')}** · ⏱️ {v.get('duration', 0):.0f}s")
    else:
        st.caption("No videos yet — generate one from Quick Actions above.")
    st.info("💡 Try Urdu/Hindi prompts for better cultural context.")

# TRENDING
elif active_nav == "🔥 Trending":
    st.markdown('<div class="fm-section-title"><span class="ico">📋</span><span class="lbl">Browse Prompt Templates</span></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        trend_lang_display = st.selectbox("Language", ["Urdu", "Hindi", "English"], key="trend_lang_display")
        trend_lang_map = {"Urdu": "ur", "Hindi": "hi", "English": "en"}
        trend_lang = trend_lang_map[trend_lang_display]
    with c2:
        trend_category_names = feat10.get_category_names(trend_lang)
        trend_counts = feat10.get_category_templates_count(trend_lang)
        trend_categories = feat10.get_all_categories()
        def _fmt_trend_cat(c):
            info = feat10.get_category_info(c) or {}
            name = trend_category_names.get(c, c)
            cnt = trend_counts.get(c, 0)
            return f"{info.get('emoji', '📌')} {name} ({cnt})"
        trend_cat = st.selectbox("Category", trend_categories, format_func=_fmt_trend_cat, key="trend_cat")
    templates = feat10.get_templates_by_category(trend_cat, trend_lang)
    st.caption(f"Found {len(templates)} templates")
    if not templates:
        st.info("ℹ️ Is category/language combination mein abhi templates nahi hain — 'Urdu' try karo.")
    for tpl in templates[:8]:
        cat_info = feat10.get_category_info(tpl.get('category')) or {}
        with st.expander(f"{cat_info.get('emoji', '📋')} {tpl['name']}"):
            st.caption(tpl['template'])
            if st.button("📝 Use in Text-to-Video", key=f"trend_use_{tpl['id']}"):
                st.session_state["t2v_prompt_field"] = tpl['template']
                feat10.track_template_usage(tpl['id'])
                st.success("✅ Text-to-Video mein bhej diya!")

    st.divider()
    st.markdown('<div class="fm-section-title"><span class="ico">🎬</span><span class="lbl">Demo Videos</span></div>', unsafe_allow_html=True)
    st.caption("Apna demo video share karo — admin verify karne ke baad yahan sab ko dikhega.")
    with st.expander("📤 Apna Demo Video Upload Karo"):
        demo_file = st.file_uploader("Video (mp4/mov/webm/m4v)", type=["mp4", "mov", "webm", "m4v"], key="demo_upload_file")
        demo_caption = st.text_input("Caption (optional)", key="demo_upload_caption", placeholder="Ismein kya hai...")
        if st.button("📤 Submit for Review", key="demo_upload_submit", use_container_width=True):
            if auth_gate.guest_locked("uploading a demo video"):
                pass
            else:
                result = feature_26_demo_videos.submit_demo_video(
                    user_id=st.session_state.get("current_user_id", ""),
                    user_email=st.session_state.get("user_email", ""),
                    uploaded_file=demo_file,
                    caption=demo_caption,
                )
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
    approved_demos = feature_26_demo_videos.get_approved_videos()
    if not approved_demos:
        st.caption("Abhi koi verified demo video nahi — pehla upload karne wale banoo!")
    else:
        for v in approved_demos:
            with st.container(border=True):
                st.markdown(f"**{v['filename']}**" + (f" — {v['caption']}" if v['caption'] else ""))
                if os.path.exists(v['filepath']):
                    st.video(v['filepath'])

# TOOLS
elif active_nav == "🛠️ Tools":
    if st.session_state["active_tool"] is not None:
        render_tool_detail(st.session_state["active_tool"])
    else:
        for group_name, indices, group_icon, group_sub in TOOLS_GROUPS:
            st.markdown(f'<div class="fm-section-title"><span class="ico">{group_icon}</span><span class="lbl">{group_name}</span></div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for pos, idx in enumerate(indices):
                with cols[pos % 4]:
                    render_tool_card(idx, "tools_grid")

# ASSETS
elif active_nav == "📁 Assets":
    asset_tabs = st.tabs(["📚 Library", "📁 Folders", "⭐ Favorites & Collections"])
    with asset_tabs[0]:
        render_feat_11()
    with asset_tabs[1]:
        render_feat_12()
    with asset_tabs[2]:
        render_feat_13()

# PROFILE
elif active_nav == "👤 Profile":
    profile_tabs = st.tabs(["💰 Pay-Per-Video", "🎯 Launch Discount", "💬 Feedback", "📋 My Jobs", "🔐 Admin"])
    with profile_tabs[0]:
        render_feat_14()
    with profile_tabs[1]:
        render_feat_15()
    with profile_tabs[2]:
        render_feat_16()
    with profile_tabs[3]:
        render_feat_23()
    with profile_tabs[4]:
        render_feat_21()

st.divider()
st.caption("FUTURE 4K — YOUR VISION . OUR AI .")
