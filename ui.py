# ============================================================
# FUTURE 4K — MAIN UI (REWRITTEN & DEBUGGED)
# Tagline: YOUR VISION . OUR AI .
# Features 01-26 (Complete Integration)
# ============================================================

import os
import sys
import io
import queue
import tempfile
import base64
import traceback
from datetime import datetime
from pathlib import Path

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import numpy as np

# Fix encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# CONFIGURATION & IMPORTS
# ============================================================

try:
    import config
    from config import RESOLUTIONS, MIN_CLIP_LENGTH, PATHS, MAX_CLIP_LENGTH
except ImportError as e:
    st.error(f"❌ config.py not found! Error: {e}")
    st.stop()

# Feature imports with error handling
FEATURE_IMPORTS = {
    'feat01': ('feature_01_text_to_video', 'Feature 01: Text-to-Video'),
    'feat02': ('feature_02_image_to_video', 'Feature 02: Image-to-Video'),
    'feat03': ('feature_03_clip_generation', 'Feature 03: Clip Generation'),
    'feat04': ('feature_04_extend_video', 'Feature 04: Extend Video'),
    'feat05': ('feature_05_timeline_editor', 'Feature 05: Timeline Editor'),
    'feat06': ('feature_06_add_music', 'Feature 06: Add Music'),
    'feat07': ('feature_07_add_voiceover', 'Feature 07: Voiceover'),
    'feat08': ('feature_08_watermark', 'Feature 08: Watermark'),
    'feat09': ('feature_09_urdu_prompts', 'Feature 09: Urdu Prompts'),
    'feat10': ('feature_10_prompt_templates', 'Feature 10: Prompt Templates'),
    'feat11': ('feature_11_negative_prompting', 'Feature 11: Negative Prompting'),
    'feat12': ('feature_12_video_library', 'Feature 12: Video Library'),
    'feat13': ('feature_13_folder_organization', 'Feature 13: Folder Organization'),
    'feat14': ('feature_14_favorites_collections', 'Feature 14: Favorites'),
    'feat17': ('feature_17_pay_per_video', 'Feature 17: Pay-Per-Video'),
    'feat18': ('feature_18_launch_discount', 'Feature 18: Launch Discount'),
    'feat19': ('feature_19_feedback', 'Feature 19: Feedback'),
    'feat20': ('feature_20_id_embedding', 'Feature 20: ID Embedding'),
    'feat21': ('feature_21_camera_motion', 'Feature 21: Camera Motion'),
    'feat22': ('feature_22_frame_to_frame', 'Feature 22: Frame-to-Frame'),
    'feat23': ('feature_23_stitching', 'Feature 23: Stitching'),
    'feat24': ('feature_24_admin_pricing', 'Feature 24: Admin Pricing'),
    'feature_25_scene_planner': ('feature_25_scene_planner', 'Feature 25: Scene Planner'),
    'feature_26_demo_videos': ('feature_26_demo_videos', 'Feature 26: Demo Videos'),
    'job_queue': ('job_queue', 'Job Queue'),
}

loaded_features = {}
failed_features = []

for attr_name, (module_name, display_name) in FEATURE_IMPORTS.items():
    try:
        module = __import__(module_name, fromlist=[''])
        loaded_features[attr_name] = module
        
        # Initialize databases where needed
        if hasattr(module, 'init_db'):
            try:
                module.init_db()
            except Exception as e:
                st.warning(f"⚠️ {display_name} DB init failed: {e}")
                
    except ImportError as e:
        failed_features.append((display_name, str(e)))
        st.warning(f"⚠️ {display_name} import failed: {e}")
    except Exception as e:
        failed_features.append((display_name, str(e)))
        st.error(f"❌ {display_name} error: {e}")

# Import auth and admin
try:
    import auth_gate
    import admin_panel
except ImportError as e:
    st.error(f"❌ Auth/Admin import failed: {e}")
    st.stop()

# ============================================================
# CONSTANTS & PATHS
# ============================================================

LOGO_PATH = "logo.png"
LOGO_AVAILABLE = os.path.exists(LOGO_PATH)
DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# ============================================================
# VOICE IMPORTS
# ============================================================

VOICE_AVAILABLE = False
try:
    import speech_recognition as sr
    import wave
    VOICE_AVAILABLE = True
except ImportError:
    pass

LANGUAGE_MAP = {
    "English (US)": "en-US",
    "Urdu (Pakistan)": "ur",
    "Hindi (India)": "hi-IN",
}

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="FUTURE 4K",
    page_icon=LOGO_PATH if LOGO_AVAILABLE else "🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# AUTH GATE
# ============================================================

try:
    if not auth_gate.render_gate():
        st.stop()
except Exception as e:
    st.error(f"Authentication error: {e}")
    st.stop()

# ============================================================
# CUSTOM CSS (COMPACT & OPTIMIZED)
# ============================================================

def load_css():
    """Load custom CSS with theme variables."""
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
            --navy: #101A30;
            --line: #E4E7EB;
            --card-border: #0FA968;
            --shadow: 0 6px 20px rgba(15, 169, 104, 0.15);
        }
        
        /* Global styles */
        .stApp { background: var(--bg); }
        html, body, p, span, div { 
            font-family: 'Inter', -apple-system, sans-serif; 
            color: var(--ink); 
        }
        h1, h2, h3 { 
            font-family: 'Sora', -apple-system, sans-serif; 
            color: var(--ink); 
        }
        
        /* Sidebar */
        section[data-testid="stSidebar"] { 
            background: var(--navy); 
        }
        section[data-testid="stSidebar"] * { 
            color: #C4CCDA !important; 
        }
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3 { 
            color: #FFFFFF !important; 
        }
        
        /* Cards */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            border: 2px solid var(--card-border) !important;
            background: var(--surface) !important;
            padding: 20px;
            transition: all 0.2s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: var(--shadow);
            border-color: var(--accent-dark) !important;
        }
        
        /* Buttons */
        .stButton > button {
            background: var(--accent) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1.2rem !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover {
            background: var(--accent-dark) !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(15, 169, 104, 0.3);
        }
        .stButton > button[kind="secondary"] {
            background: transparent !important;
            color: var(--accent) !important;
            border: 1.5px solid var(--accent) !important;
        }
        .stButton > button[kind="secondary"]:hover {
            background: var(--accent-light) !important;
            color: var(--accent-dark) !important;
        }
        
        /* Input fields */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background: #FFFFFF !important;
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
            color: var(--ink) !important;
        }
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 2px rgba(15, 169, 104, 0.2) !important;
        }
        
        /* Select boxes */
        div[data-baseweb="select"] > div {
            background: #FFFFFF !important;
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
        }
        
        /* Progress bars */
        .stProgress > div > div > div { 
            background: var(--accent) !important; 
        }
        
        /* Metrics */
        div[data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 0.8rem;
        }
        
        /* Links */
        a { color: var(--accent) !important; }
        a:hover { color: var(--accent-dark) !important; }
        
        /* Tabs */
        .stTabs [aria-selected="true"] { 
            color: var(--accent-dark) !important; 
            font-weight: 700; 
        }
        
        /* Custom classes */
        .fm-icon-chip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: rgba(15, 169, 104, 0.12) !important;
            font-size: 1.3rem;
            margin-bottom: 0.5rem;
        }
        .fm-card-title {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }
        .fm-card-desc {
            font-size: 0.85rem;
            color: var(--ink-muted);
            margin-bottom: 0.75rem;
        }
        .fm-crumb {
            font-size: 0.78rem;
            color: var(--accent-dark);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .fm-detail-title {
            font-weight: 800;
            font-size: 1.6rem;
            margin: 0.15rem 0 1rem 0;
        }
        .voice-status-box {
            padding: 0.8rem 1rem;
            border-radius: 10px;
            margin: 0.5rem 0;
            border: 2px dashed var(--accent);
            background: rgba(15, 169, 104, 0.05);
            text-align: center;
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4 { 
            color: var(--ink) !important; 
        }
        .stCaption { 
            color: var(--ink-muted) !important; 
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

def init_session_state():
    """Initialize all session state variables with defaults."""
    defaults = {
        'agnes_api_key': os.environ.get('AGNES_API_KEY', ''),
        'app_language': 'English',
        'current_user_id': os.environ.get('DEFAULT_USER_ID', 'test_user_001'),
        'active_nav': '🏠 Home',
        'active_tool': None,
        't2v_voice_prompt': '',
        'img2vid_voice_prompt': '',
        'clip_voice_prompt': '',
        'timeline_project': None,
        'sp_planned_scenes': None,
        'sp_plan_meta': None,
        'user_email': os.environ.get('DEFAULT_USER_EMAIL', ''),
        'audio_queues': {},
        'recorder_states': {},
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_voice_queue(key_prefix):
    """Get or create a voice audio queue for a feature."""
    qkey = f"{key_prefix}_audio_queue"
    if qkey not in st.session_state.audio_queues:
        st.session_state.audio_queues[qkey] = queue.Queue()
    return st.session_state.audio_queues[qkey]

def audio_frames_to_wav_bytes(audio_frames):
    """Convert audio frames to WAV bytes."""
    if not audio_frames or not VOICE_AVAILABLE:
        return None
    try:
        all_audio = np.concatenate([f.to_ndarray() for f in audio_frames], axis=1)
        if np.issubdtype(all_audio.dtype, np.floating):
            audio_int16 = (np.clip(all_audio, -1.0, 1.0) * 32767).astype(np.int16)
        else:
            audio_int16 = all_audio.astype(np.int16)
        
        sample_rate = audio_frames[0].sample_rate
        channels = all_audio.shape[0] if all_audio.ndim == 2 else 1
        interleaved = audio_int16.T.copy() if channels > 1 else audio_int16.reshape(-1)
        
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(interleaved.tobytes())
        wav_io.seek(0)
        return wav_io
    except Exception as e:
        st.error(f"Audio conversion error: {e}")
        return None

def speech_to_text(audio_bytes, language_display="English (US)"):
    """Convert speech to text using Google Speech Recognition."""
    if audio_bytes is None:
        return {"success": False, "text": "", "message": "No audio recorded."}
    if not VOICE_AVAILABLE:
        return {"success": False, "text": "", "message": "Voice recognition not available. Install SpeechRecognition."}
    
    google_lang = LANGUAGE_MAP.get(language_display, "en-US")
    tmp_path = None
    
    try:
        audio_bytes.seek(0)
        recognizer = sr.Recognizer()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(audio_bytes.read())
            tmp_path = tmp.name
        
        with sr.AudioFile(tmp_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio, language=google_lang)
        return {"success": True, "text": text, "message": f"Recognized: {text}"}
        
    except sr.UnknownValueError:
        return {"success": False, "text": "", "message": "Could not understand audio. Please speak clearly."}
    except sr.RequestError as e:
        return {"success": False, "text": "", "message": f"Speech service error: {e}"}
    except Exception as e:
        return {"success": False, "text": "", "message": f"Error: {e}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

def render_live_price(duration_seconds, resolution, quality, key_prefix=""):
    """Display live price estimate with any applicable discounts."""
    if 'feat17' not in loaded_features:
        st.caption("💰 Price calculation unavailable")
        return {}
    
    user_id = st.session_state.get("current_user_id", "")
    try:
        estimate = loaded_features['feat17'].estimate_price(
            duration_seconds, resolution, quality, user_id or None
        )
    except Exception as e:
        st.caption(f"💰 Price calculation error: {e}")
        return {}
    
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
    """Charge user wallet or block if insufficient funds."""
    if 'feat17' not in loaded_features:
        return False, {"success": False, "message": "Payment system unavailable"}
    
    user_id = st.session_state.get("current_user_id", "")
    if not user_id:
        return False, {"success": False, "message": "❌ Please enter a User ID in the sidebar first."}
    
    try:
        result = loaded_features['feat17'].charge_for_video(
            user_id=user_id,
            duration_seconds=duration_seconds,
            resolution=resolution,
            quality=quality,
            video_id=video_id,
            tool_name=tool_name,
        )
        return result.get("success", False), result
    except Exception as e:
        return False, {"success": False, "message": f"Payment error: {e}"}

def save_uploaded_file(uploaded_file, prefix="upload"):
    """Save uploaded file to temp directory and return path."""
    temp_dir = PATHS.get("temp", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, f"{prefix}_{os.getpid()}_{uploaded_file.name}")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path

def display_video_result(result):
    """Display video result with download button."""
    if not result.get("success"):
        st.error(f"❌ {result.get('message', 'Unknown error')}")
        return
    
    st.success(f"✅ {result.get('message', 'Done!')}")
    video_path = result.get("video_path", "")
    
    if video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 100:
        st.video(video_path)
        with open(video_path, "rb") as f:
            st.download_button(
                "📥 Download Video",
                f,
                os.path.basename(video_path),
                "video/mp4",
                key=f"dl_{os.path.basename(video_path)}"
            )
    elif DRY_RUN:
        st.info(f"ℹ️ DRY_RUN — would create: {video_path}")

def compact_prompt_field(key_prefix, session_key, label, placeholder="", height=150, is_negative=False):
    """Render a prompt field with optional voice input."""
    open_key = f"{key_prefix}_recorder_open"
    if open_key not in st.session_state.recorder_states:
        st.session_state.recorder_states[open_key] = False
    
    st.markdown(f'<div class="fm-section-title"><span class="lbl">{label}</span></div>', unsafe_allow_html=True)
    
    with st.container():
        col1, col2 = st.columns([20, 1])
        
        with col1:
            if is_negative:
                value = st.text_input(
                    label,
                    value=st.session_state.get(session_key, ""),
                    placeholder=placeholder,
                    key=f"{key_prefix}_field",
                    label_visibility="collapsed"
                )
            else:
                value = st.text_area(
                    label,
                    value=st.session_state.get(session_key, ""),
                    placeholder=placeholder,
                    height=height,
                    key=f"{key_prefix}_field",
                    label_visibility="collapsed"
                )
        
        with col2:
            mic_icon = "🔴" if st.session_state.recorder_states[open_key] else "🎙️"
            if st.button(mic_icon, key=f"{key_prefix}_mic_btn", help="Voice input"):
                st.session_state.recorder_states[open_key] = not st.session_state.recorder_states[open_key]
                st.rerun()
    
    if st.session_state.recorder_states[open_key]:
        with st.container(border=True):
            voice_recorder_component(key_prefix, session_key)
    
    return value

def voice_recorder_component(key_prefix, session_key):
    """Voice recorder component using WebRTC."""
    if not VOICE_AVAILABLE:
        st.warning("⚠️ Voice input not available. Install: pip install SpeechRecognition pyaudio")
        return
    
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
    
    RTC_CONFIG = RTCConfiguration({
        "iceServers": [
            {"urls": ["stun:stun.l.google.com:19302"]},
        ]
    })
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        voice_lang = st.selectbox(
            "Voice Language",
            list(LANGUAGE_MAP.keys()),
            index=0,
            key=f"{key_prefix}_voice_lang"
        )
    
    audio_queue = get_voice_queue(key_prefix)
    
    def audio_frame_callback(frame):
        audio_queue.put(frame)
        return frame
    
    with col2:
        webrtc_ctx = webrtc_streamer(
            key=f"{key_prefix}_voice_recorder",
            mode=WebRtcMode.SENDONLY,
            audio_receiver_size=1024,
            rtc_configuration=RTC_CONFIG,
            media_stream_constraints={"audio": True, "video": False},
            audio_frame_callback=audio_frame_callback,
        )
        
        if webrtc_ctx.state.playing:
            st.markdown(
                '<div class="voice-status-box">🔴 <b>Recording...</b> Click "Transcribe" below</div>',
                unsafe_allow_html=True
            )
    
    if st.button("📝 Transcribe", key=f"{key_prefix}_transcribe", use_container_width=True):
        frames = []
        while not audio_queue.empty():
            try:
                frames.append(audio_queue.get_nowait())
            except queue.Empty:
                break
        
        if not frames:
            st.warning("⚠️ No audio captured yet. Speak and try again.")
            return
        
        with st.spinner("🔄 Processing speech..."):
            wav_bytes = audio_frames_to_wav_bytes(frames)
            if wav_bytes:
                result = speech_to_text(wav_bytes, voice_lang)
                if result["success"]:
                    st.session_state[session_key] = result["text"]
                    st.session_state.recorder_states[f"{key_prefix}_recorder_open"] = False
                    st.success(f"✅ Recognized: **{result['text']}**")
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():
    """Render the sidebar with branding, settings, and wallet info."""
    with st.sidebar:
        # Logo & Branding
        if LOGO_AVAILABLE:
            st.image(LOGO_PATH, width=140)
        else:
            st.markdown(
                '<div style="font-family:Sora,sans-serif; font-weight:800; font-size:1.5rem; color:#FFFFFF;">'
                '🎬 FUTURE 4K</div>',
                unsafe_allow_html=True
            )
        
        st.caption("YOUR VISION . OUR AI .")
        st.divider()
        
        # Auth controls
        try:
            auth_gate.render_logout_control()
        except Exception as e:
            st.error(f"Auth error: {e}")
        
        st.divider()
        
        # API Key
        api_key = st.text_input(
            "🔑 Agnes AI API Key",
            value=st.session_state.agnes_api_key,
            type="password",
            key="sidebar_api_key",
            help="Your Agnes AI API key for video generation"
        )
        st.session_state.agnes_api_key = api_key
        
        if api_key:
            st.success("✅ API Key set")
        elif not DRY_RUN:
            st.warning("⚠️ No API key - DRY_RUN mode only")
        
        # Language
        app_language = st.selectbox(
            "🌐 Language",
            ["English", "Urdu", "Hindi"],
            index=["English", "Urdu", "Hindi"].index(st.session_state.app_language),
            key="app_language_select"
        )
        st.session_state.app_language = app_language
        
        st.divider()
        
        # User ID & Wallet
        user_id = st.text_input(
            "👤 User ID",
            value=st.session_state.current_user_id,
            key="sidebar_user_id",
            help="Used for wallet charging and billing"
        )
        st.session_state.current_user_id = user_id
        
        # Show wallet balance
        if 'feat17' in loaded_features and user_id:
            try:
                wallet = loaded_features['feat17'].get_wallet_balance(user_id)
                st.metric(
                    "💰 Wallet Balance",
                    f"${wallet.get('balance', 0):.2f}"
                )
            except Exception as e:
                st.caption(f"Wallet error: {e}")
        
        # Status indicators
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if DRY_RUN:
                st.info("🔶 DRY_RUN")
            else:
                st.success("🟢 LIVE")
        
        with col2:
            if VOICE_AVAILABLE:
                st.success("🎤 Voice")
            else:
                st.warning("🔇 No Voice")
        
        # Feature status
        if failed_features:
            st.divider()
            with st.expander("⚠️ Failed Features"):
                for name, error in failed_features:
                    st.caption(f"• {name}: {error}")
        
        st.divider()
        st.caption("FUTURE 4K · v2.0 · 26 Modules")

render_sidebar()

# ============================================================
# API KEY DISTRIBUTION
# ============================================================

api_key = st.session_state.agnes_api_key or config.AGNES_API_KEY

for module in loaded_features.values():
    if hasattr(module, 'AGNES_API_KEY'):
        module.AGNES_API_KEY = api_key

# ============================================================
# FEATURE RENDERERS
# ============================================================

def render_text_to_video():
    """Feature 01: Text-to-Video Generation"""
    st.subheader("📝 Text-to-Video")
    st.write("Urdu, Hindi ya English mein prompt likho — AI video banaye ga.")
    
    # Prompt input with voice
    prompt = compact_prompt_field(
        "t2v_prompt", "t2v_voice_prompt",
        "📝 Prompt",
        placeholder="Misaal: ایک خوبصورت لڑکی باغ میں پھول چُن رہی ہے",
        height=150
    )
    
    # Configuration
    st.markdown("### ⚙️ Configuration")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'feat01' in loaded_features:
            resolutions = list(loaded_features['feat01'].RESOLUTION_CONFIGS.keys())
            resolution = st.selectbox(
                "Resolution",
                options=resolutions,
                index=min(2, len(resolutions)-1),
                format_func=lambda x: loaded_features['feat01'].RESOLUTION_CONFIGS[x]["label"],
                key="t2v_res"
            )
        else:
            resolution = st.selectbox("Resolution", ["480p", "720p", "1080p"], key="t2v_res")
    
    with col2:
        if 'feat01' in loaded_features:
            qualities = list(loaded_features['feat01'].QUALITY_PRESETS.keys())
            quality = st.selectbox(
                "Quality",
                options=qualities,
                index=0,
                format_func=lambda x: loaded_features['feat01'].QUALITY_PRESETS[x]['label'],
                key="t2v_quality"
            )
        else:
            quality = "standard"
            st.selectbox("Quality", ["standard"], key="t2v_quality")
    
    with col3:
        dur_min = st.number_input("Minutes", 0, 120, 0, key="t2v_min")
        dur_sec = st.number_input("Seconds", 0, 59, 10, key="t2v_sec")
    
    duration = int(dur_min) * 60 + int(dur_sec)
    st.caption(f"⏱️ Total: **{duration}s**")
    
    # Camera motion option
    camera_motion = "None"
    if 'feat21' in loaded_features:
        camera_motion = st.selectbox(
            "🎥 Camera Motion (optional)",
            ["None"] + list(loaded_features['feat21'].CAMERA_MOTIONS.keys()),
            key="t2v_camera_motion"
        )
    
    # Character consistency
    ref_files = None
    if 'feat20' in loaded_features:
        with st.expander("🆔 Character Consistency (optional)"):
            st.caption("2-5 reference images for consistent character")
            ref_files = st.file_uploader(
                "Reference Images (2-5)",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key="t2v_char_refs"
            )
    
    # Live price
    render_live_price(duration, resolution, quality, "t2v")
    
    # Advanced options
    with st.expander("⚙️ Advanced Options"):
        negative_prompt = compact_prompt_field(
            "t2v_negative", "t2v_voice_negative",
            "🚫 Negative Prompt",
            placeholder="e.g., blurry, low quality",
            is_negative=True
        )
        apply_watermark = st.checkbox("Watermark", True, key="t2v_watermark")
    
    st.divider()
    
    # Generate button
    if st.button("🎬 Generate Video", type="primary", key="t2v_generate", use_container_width=True):
        if not prompt or len(prompt.strip()) < 3:
            st.error("❌ Please enter a prompt (at least 3 characters).")
        elif duration < 2:
            st.error("❌ Duration must be at least 2 seconds.")
        elif ref_files and len(ref_files) < 2:
            st.error("❌ Character consistency requires at least 2 reference images.")
        else:
            ok, charge = charge_wallet_or_block(duration, resolution, quality, "text_to_video")
            if not ok:
                st.error(f"❌ {charge.get('message')}")
                return
            
            st.success(f"💳 {charge.get('message')}")
            
            # Route to appropriate generator
            use_character = bool(ref_files and len(ref_files) >= 2 and 'feat20' in loaded_features)
            use_camera = camera_motion != "None" and 'feat21' in loaded_features
            
            try:
                if use_character:
                    # Character-consistent generation
                    char_res = resolution if resolution in ("720p", "1080p") else "1080p"
                    ref_paths = []
                    for i, file in enumerate(ref_files[:5]):
                        path = save_uploaded_file(file, f"t2v_ref_{i}")
                        ref_paths.append(path)
                    
                    with st.spinner("🎬 Generating character-consistent video..."):
                        result = loaded_features['feat20'].generate_with_character_wan(
                            prompt=prompt,
                            reference_paths=ref_paths,
                            resolution=char_res,
                            duration=duration,
                            apply_watermark=apply_watermark,
                        )
                    
                    # Cleanup
                    for p in ref_paths:
                        if os.path.exists(p):
                            os.remove(p)
                    
                elif use_camera:
                    # Camera motion generation
                    cam_res = resolution if resolution in ("2k", "4k") else "2k"
                    with st.spinner(f"🎬 Generating with {camera_motion} camera motion..."):
                        result = loaded_features['feat21'].generate_with_camera_motion(
                            prompt=prompt,
                            camera_motion=camera_motion,
                            resolution=cam_res,
                            duration=duration,
                            apply_watermark=apply_watermark,
                        )
                else:
                    # Standard generation
                    with st.spinner(f"🎬 Generating {quality} quality video..."):
                        result = loaded_features['feat01'].generate_video(
                            prompt=prompt,
                            resolution=resolution,
                            duration=duration,
                            negative_prompt=negative_prompt or None,
                            apply_watermark=apply_watermark,
                            quality=quality,
                            use_voice=False
                        )
                
                display_video_result(result)
                
            except Exception as e:
                st.error(f"❌ Generation failed: {e}")
                st.code(traceback.format_exc())

def render_image_to_video():
    """Feature 02: Image-to-Video"""
    st.subheader("🖼️ Image-to-Video")
    st.write("Images upload karo aur unhein animate karo.")
    
    # Story mode
    story_mode = st.checkbox(
        "📖 Story Mode — multiple images into one video",
        value=False,
        key="img2vid_story_mode"
    )
    
    uploaded_images = st.file_uploader(
        "Image(s)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="img2vid_uploader"
    )
    
    if uploaded_images:
        st.caption(f"📸 {len(uploaded_images)} image(s)")
    
    # Scene prompts for story mode
    scene_prompts = []
    if story_mode and uploaded_images:
        st.markdown("### 📝 Scene Prompts")
        for idx, img in enumerate(uploaded_images, start=1):
            prompt = st.text_area(
                f"Scene {idx}: {img.name}",
                key=f"story_scene_prompt_{idx}",
                placeholder=f"What happens in scene {idx}...",
                height=80
            )
            scene_prompts.append(prompt)
    elif not story_mode:
        prompt = compact_prompt_field(
            "img2vid_prompt", "img2vid_voice_prompt",
            "📝 Motion Prompt",
            placeholder="Misaal: Halki hawa mein baadal chal rahe hain",
            height=120
        )
    
    st.divider()
    
    # Configuration
    c1, c2 = st.columns(2)
    with c1:
        if 'feat02' in loaded_features:
            resolutions = list(loaded_features['feat02'].RESOLUTION_CONFIGS.keys())
            img_resolution = st.selectbox(
                "Resolution",
                options=resolutions,
                index=min(2, len(resolutions)-1),
                format_func=lambda x: loaded_features['feat02'].RESOLUTION_CONFIGS[x]["label"],
                key="img2vid_res"
            )
        else:
            img_resolution = "720p"
            st.selectbox("Resolution", ["720p"], key="img2vid_res")
    
    with c2:
        aspect_ratio = st.selectbox(
            "Aspect Ratio",
            ["16:9", "9:16", "1:1", "4:3", "3:4"],
            key="img2vid_aspect"
        )
    
    # Camera motion
    img_camera_motion = "None"
    if 'feat21' in loaded_features:
        img_camera_motion = st.selectbox(
            "🎥 Camera Motion (optional)",
            ["None"] + list(loaded_features['feat21'].CAMERA_MOTIONS.keys()),
            key="img2vid_camera_motion"
        )
    
    # Duration
    dc1, dc2 = st.columns(2)
    with dc1:
        img_dur_min = st.number_input("Minutes", 0, 120, 0, key="img2vid_min")
    with dc2:
        img_dur_sec = st.number_input("Seconds", 0, 59, 5, key="img2vid_sec")
    
    img_duration = int(img_dur_min) * 60 + int(img_dur_sec)
    
    if story_mode:
        st.caption(f"⏱️ **{img_duration}s** per scene")
    else:
        st.caption(f"⏱️ **{img_duration}s** per image")
    
    # Price
    price_dur = img_duration * (len(uploaded_images) if (story_mode and uploaded_images) else 1)
    render_live_price(price_dur, img_resolution, "standard", "img2vid")
    
    # Advanced
    with st.expander("⚙️ Advanced Options"):
        if not story_mode:
            img_neg = compact_prompt_field(
                "img2vid_negative", "img2vid_voice_negative",
                "🚫 Negative Prompt",
                placeholder="e.g., blurry",
                is_negative=True
            )
            img_seed = st.number_input("Seed (0=random)", 0, 999999, 0, key="img2vid_seed")
            img_seed = img_seed if img_seed > 0 else None
        else:
            img_neg = None
            img_seed = None
        
        img_wm = st.checkbox("Watermark", True, key="img2vid_watermark")
    
    st.divider()
    
    # Generate
    button_label = "📖 Generate Story Video" if story_mode else "🎬 Generate Video(s)"
    if st.button(button_label, type="primary", key="img2vid_generate", use_container_width=True):
        if not uploaded_images:
            st.error("❌ Please upload at least one image.")
            return
        
        if story_mode and len(uploaded_images) < 2:
            st.error("❌ Story Mode requires at least 2 images.")
            return
        
        if story_mode and any(not p or len(p.strip()) < 3 for p in scene_prompts):
            st.error("❌ Each scene needs a prompt (at least 3 characters).")
            return
        
        if not story_mode and (not prompt or len(prompt.strip()) < 3):
            st.error("❌ Please enter a motion prompt.")
            return
        
        if img_duration < MIN_CLIP_LENGTH:
            st.error(f"❌ Duration must be at least {MIN_CLIP_LENGTH}s.")
            return
        
        ok, charge = charge_wallet_or_block(price_dur, img_resolution, "standard", "image_to_video")
        if not ok:
            st.error(f"❌ {charge.get('message')}")
            return
        
        st.success(f"💳 {charge.get('message')}")
        
        try:
            if story_mode and 'feat02' in loaded_features:
                # Story mode
                temp_paths = []
                scenes = []
                for idx, (img, s_prompt) in enumerate(zip(uploaded_images, scene_prompts), start=1):
                    temp_path = save_uploaded_file(img, f"story_{idx}")
                    temp_paths.append(temp_path)
                    scenes.append({
                        "image_path": temp_path,
                        "prompt": s_prompt,
                        "duration": img_duration
                    })
                
                with st.spinner(f"📖 Generating story video ({len(scenes)} scenes)..."):
                    result = loaded_features['feat02'].generate_story_from_images(
                        scenes=scenes,
                        resolution=img_resolution,
                        apply_watermark=img_wm,
                        aspect_ratio=aspect_ratio
                    )
                
                # Cleanup
                for p in temp_paths:
                    if os.path.exists(p):
                        os.remove(p)
                
                display_video_result(result)
                
            else:
                # Individual image processing
                for idx, img in enumerate(uploaded_images, start=1):
                    st.markdown(f"---\n**🖼️ Image {idx}/{len(uploaded_images)}: {img.name}**")
                    
                    ok, charge = charge_wallet_or_block(
                        img_duration, img_resolution, "standard",
                        "image_to_video", video_id=f"img_{idx}"
                    )
                    if not ok:
                        st.error(f"❌ {charge.get('message')}")
                        continue
                    
                    temp_path = save_uploaded_file(img, f"img2vid_{idx}")
                    
                    final_prompt = prompt
                    if img_camera_motion != "None":
                        final_prompt = f"{prompt}. Camera motion: {img_camera_motion}."
                    
                    with st.spinner(f"Generating video for image {idx}..."):
                        if 'feat02' in loaded_features:
                            result = loaded_features['feat02'].generate_video_from_image(
                                image_path=temp_path,
                                prompt=final_prompt,
                                resolution=img_resolution,
                                duration=img_duration,
                                negative_prompt=img_neg or None,
                                apply_watermark=img_wm,
                                seed=img_seed,
                                aspect_ratio=aspect_ratio,
                                use_voice=False
                            )
                        else:
                            result = {"success": False, "message": "Feature not loaded"}
                    
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    display_video_result(result)
                    
        except Exception as e:
            st.error(f"❌ Generation failed: {e}")
            st.code(traceback.format_exc())

# ... (Continue with remaining feature renderers following the same pattern)

# ============================================================
# FEATURE INDEX MAPPING
# ============================================================

FEATURE_NAMES = [
    '📝 Text-to-Video',      # 0
    '🖼️ Image-to-Video',     # 1
    '✂️ 30-Second Clip',     # 2
    '📏 Extend Video',       # 3
    '⏳ Timeline Editor',    # 4
    '🎵 Background Music',   # 5
    '🎙️ Voiceover',         # 6
    '📌 Watermark',          # 7
    '🕌 Urdu/Hindi Prompts', # 8
    '📋 Prompt Templates',   # 9
    '🚫 Negative Prompting', # 10
    '📚 Video Library',      # 11
    '📁 Folder Organization',# 12
    '⭐ Favorites',          # 13
    '💰 Pay-Per-Video',      # 14
    '🎯 Launch Discount',    # 15
    '💬 Feedback',           # 16
    '🆔 Character Consistency', # 17
    '🎥 Camera Motion',      # 18
    '🖼️ Frame-to-Frame',    # 19
    '🔗 Stitching',          # 20
    '🔐 Admin Panel',        # 21
    '🧠 Scene Planner',      # 22
    '📋 My Jobs',            # 23
]

FEATURE_ICONS = ['📝', '🖼️', '✂️', '📏', '⏳', '🎵', '🎙️', '📌', 
                 '🕌', '📋', '🚫', '📚', '📁', '⭐', '💰', '🎯', 
                 '💬', '🆔', '🎥', '🖼️', '🔗', '🔐', '🧠', '📋']

FEATURE_DESCRIPTIONS = {
    0: 'AI se direct video banao. Voice + 4K support.',
    1: 'Images ko animate karo. Story Mode + custom sizes.',
    2: 'Reels/Shorts ke liye clips. Platform presets.',
    3: 'Existing video ko extend karo.',
    4: 'Clips arrange aur render karo.',
    5: 'Background music add karo.',
    6: 'TTS voiceover generate karo.',
    7: 'Text/image watermark lagao.',
    8: 'Urdu/Hindi prompts enhance karo.',
    9: 'Ready-made templates use karo.',
    10: 'Batao video mein kya nahi chahiye.',
    17: '3-5 images se consistent character.',
    18: 'Cinematic camera controls.',
    19: 'Start/end frame ke beech generate.',
    20: 'Multiple clips seamless stitch karo.',
    22: 'Master prompt se lambi video plan karo.',
}

FEATURE_RENDERERS = [
    render_text_to_video,      # 0
    render_image_to_video,     # 1
    # ... add all 24 renderers
]

# ============================================================
# NAVIGATION
# ============================================================

NAV_OPTIONS = ["🏠 Home", "🔥 Trending", "🛠️ Tools", "📁 Assets", "👤 Profile"]

def open_tool(idx):
    """Navigate to a specific tool."""
    st.session_state.active_nav = "🛠️ Tools"
    st.session_state.active_tool = idx
    st.rerun()

def render_tool_card(idx, key_prefix):
    """Render a tool card in grid view."""
    with st.container(border=True):
        st.markdown(f'<div class="fm-icon-chip">{FEATURE_ICONS[idx]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="fm-card-title">{FEATURE_NAMES[idx]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="fm-card-desc">{FEATURE_DESCRIPTIONS.get(idx, "")}</div>', unsafe_allow_html=True)
        st.button(
            "Open →",
            key=f"{key_prefix}_{idx}",
            on_click=open_tool,
            args=(idx,),
            type="primary",
            use_container_width=True
        )

def render_tool_detail(idx):
    """Render a tool's detail view."""
    st.button(
        "← Back to Tools",
        key=f"back_{idx}",
        on_click=lambda: st.session_state.update(active_tool=None)
    )
    st.markdown('<div class="fm-crumb">Tools</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="fm-detail-title">{FEATURE_ICONS[idx]} {FEATURE_NAMES[idx]}</div>', unsafe_allow_html=True)
    
    # Call the feature renderer
    if idx < len(FEATURE_RENDERERS):
        FEATURE_RENDERERS[idx]()
    else:
        st.warning("Feature renderer not available.")

# ============================================================
# MAIN APP
# ============================================================

def main():
    """Main application entry point."""
    
    # Header with logo
    if LOGO_AVAILABLE:
        logo_b64 = base64.b64encode(open(LOGO_PATH, "rb").read()).decode()
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:1rem;">
                <img src="data:image/png;base64,{logo_b64}" style="height:56px; width:auto;" />
                <div>
                    <div style="font-family:Sora,sans-serif; font-weight:800; font-size:2rem; line-height:1.1;">
                        FUTURE 4K
                    </div>
                    <div style="font-size:0.85rem; color:#626B76; letter-spacing:0.03em;">
                        YOUR VISION . OUR AI .
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("# 🎬 FUTURE 4K")
        st.caption("YOUR VISION . OUR AI .")
    
    # Navigation
    nav = st.radio(
        "Navigate",
        NAV_OPTIONS,
        key="active_nav",
        label_visibility="collapsed",
        horizontal=True
    )
    
    st.divider()
    
    # Route to appropriate page
    if nav == "🏠 Home":
        render_home_page()
    elif nav == "🔥 Trending":
        render_trending_page()
    elif nav == "🛠️ Tools":
        render_tools_page()
    elif nav == "📁 Assets":
        render_assets_page()
    elif nav == "👤 Profile":
        render_profile_page()
    
    st.divider()
    st.caption("FUTURE 4K — YOUR VISION . OUR AI .")

def render_home_page():
    """Render the home/dashboard page."""
    # Stats
    try:
        videos = loaded_features.get('feat12', None)
        favorites = loaded_features.get('feat14', None)
        
        video_count = len(videos.get_all_videos()) if videos and hasattr(videos, 'get_all_videos') else 0
        fav_count = len(favorites.get_all_favorites()) if favorites and hasattr(favorites, 'get_all_favorites') else 0
    except:
        video_count = 0
        fav_count = 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🎬 Total Videos", video_count)
    c2.metric("⏱️ Session", datetime.now().strftime("%H:%M"))
    c3.metric("⭐ Favorites", fav_count)
    
    # Quick Actions
    st.markdown("### 🚀 Quick Actions")
    qa_cols = st.columns(4)
    for pos, idx in enumerate([0, 1, 2, 3]):
        with qa_cols[pos]:
            render_tool_card(idx, "home_qa")
    
    # Recent Videos
    st.markdown("### 📹 Recent Videos")
    if video_count > 0 and loaded_features.get('feat12'):
        try:
            videos_list = loaded_features['feat12'].get_all_videos()
            for v in videos_list[:5]:
                st.markdown(f"🎬 **{v.get('filename', 'Unknown')}** · ⏱️ {v.get('duration', 0):.0f}s")
        except:
            st.caption("Could not load videos.")
    else:
        st.caption("No videos yet — generate one from Quick Actions above.")
    
    st.info("💡 Try Urdu/Hindi prompts for better cultural context.")

def render_trending_page():
    """Render trending/prompt templates page."""
    st.markdown("### 📋 Browse Prompt Templates")
    
    c1, c2 = st.columns(2)
    with c1:
        lang_display = st.selectbox("Language", ["Urdu", "Hindi", "English"], key="trend_lang")
        lang_map = {"Urdu": "ur", "Hindi": "hi", "English": "en"}
        lang = lang_map[lang_display]
    
    with c2:
        if 'feat10' in loaded_features:
            categories = loaded_features['feat10'].get_all_categories()
            category = st.selectbox("Category", categories, key="trend_cat")
        else:
            category = "All"
            st.selectbox("Category", ["All"], key="trend_cat")
    
    if 'feat10' in loaded_features:
        templates = loaded_features['feat10'].get_templates_by_category(category, lang)
        st.caption(f"Found {len(templates)} templates")
        
        for tpl in templates[:8]:
            with st.expander(f"📋 {tpl['name']}"):
                st.code(tpl['template'], language="text")
                if st.button("📝 Use in Text-to-Video", key=f"trend_use_{tpl['id']}"):
                    st.session_state.t2v_voice_prompt = tpl['template']
                    try:
                        loaded_features['feat10'].track_template_usage(tpl['id'])
                    except:
                        pass
                    st.success("✅ Sent to Text-to-Video!")
    else:
        st.info("Prompt templates feature not available.")
    
    # Demo Videos
    st.divider()
    st.markdown("### 🎬 Demo Videos")
    
    if 'feature_26_demo_videos' in loaded_features:
        with st.expander("📤 Upload Your Demo Video"):
            demo_file = st.file_uploader(
                "Video (mp4/mov/webm/m4v)",
                type=["mp4", "mov", "webm", "m4v"],
                key="demo_upload"
            )
            demo_caption = st.text_input("Caption (optional)", key="demo_caption")
            
            if st.button("📤 Submit for Review", key="demo_submit", use_container_width=True):
                try:
                    auth_gate.guest_locked("uploading demo")
                except:
                    pass
                
                result = loaded_features['feature_26_demo_videos'].submit_demo_video(
                    user_id=st.session_state.current_user_id,
                    user_email=st.session_state.get('user_email', ''),
                    uploaded_file=demo_file,
                    caption=demo_caption,
                )
                
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
        
        approved = loaded_features['feature_26_demo_videos'].get_approved_videos()
        if approved:
            for v in approved:
                with st.container(border=True):
                    st.markdown(f"**{v['filename']}**")
                    if v.get('caption'):
                        st.caption(v['caption'])
                    if os.path.exists(v['filepath']):
                        st.video(v['filepath'])
        else:
            st.caption("No verified demos yet — be the first!")

def render_tools_page():
    """Render tools page with grid or detail view."""
    if st.session_state.active_tool is not None:
        render_tool_detail(st.session_state.active_tool)
    else:
        TOOLS_GROUPS = [
            ('Create', [0, 1, 2, 3], '🎬'),
            ('Enhance', [4, 5, 6, 7], '🛠️'),
            ('Prompt Tools', [8, 9, 10], '✨'),
            ('Advanced', [17, 18, 19, 20, 22], '⚡'),
        ]
        
        for group_name, indices, icon in TOOLS_GROUPS:
            st.markdown(f"### {icon} {group_name}")
            cols = st.columns(4)
            for pos, idx in enumerate(indices):
                with cols[pos % 4]:
                    render_tool_card(idx, "tools_grid")
            st.divider()

def render_assets_page():
    """Render assets/library page."""
    tabs = st.tabs(["📚 Library", "📁 Folders", "⭐ Favorites"])
    
    with tabs[0]:
        if 'feat12' in loaded_features:
            st.subheader("📚 Video Library")
            videos = loaded_features['feat12'].get_all_videos()
            st.info(f"Total videos: {len(videos)}")
            for v in videos[:10]:
                with st.expander(f"🎬 {v.get('filename', 'Unknown')}"):
                    st.caption(f"Prompt: {v.get('prompt', 'N/A')}")
                    st.caption(f"Duration: {v.get('duration', 0):.1f}s")
        else:
            st.warning("Library feature not available.")
    
    with tabs[1]:
        if 'feat13' in loaded_features:
            st.subheader("📁 Folder Organization")
            folders = loaded_features['feat13'].get_all_folders()
            for f in folders:
                with st.expander(f"📁 {f.get('name', 'Unknown')}"):
                    st.caption(f"Videos: {f.get('video_count', 0)}")
        else:
            st.warning("Folder feature not available.")
    
    with tabs[2]:
        if 'feat14' in loaded_features:
            st.subheader("⭐ Favorites & Collections")
            favorites = loaded_features['feat14'].get_all_favorites()
            st.info(f"⭐ {len(favorites)} favorites")
        else:
            st.warning("Favorites feature not available.")

def render_profile_page():
    """Render profile/settings page."""
    tabs = st.tabs(["💰 Wallet", "🎯 Discounts", "💬 Feedback", "📋 My Jobs", "🔐 Admin"])
    
    with tabs[0]:
        if 'feat17' in loaded_features:
            st.subheader("💰 Pay-Per-Video Wallet")
            user_id = st.session_state.current_user_id
            
            if user_id:
                balance = loaded_features['feat17'].get_wallet_balance(user_id)
                st.metric("💰 Balance", f"${balance.get('balance', 0):.2f}")
                
                # Top up buttons
                st.markdown("**Top Up Wallet**")
                cols = st.columns(4)
                for i, amount in enumerate([5, 10, 25, 50]):
                    if cols[i].button(f"${amount}", key=f"topup_{amount}"):
                        result = loaded_features['feat17'].top_up_wallet(user_id, amount, "card")
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])
        else:
            st.warning("Wallet feature not available.")
    
    with tabs[1]:
        if 'feat18' in loaded_features:
            st.subheader("🎯 Launch Discount")
            status = loaded_features['feat18'].get_discount_status()
            cols = st.columns(4)
            cols[0].metric("Total Slots", status.get("total_slots", 200))
            cols[1].metric("Used", status.get("used_slots", 0))
            cols[2].metric("Remaining", status.get("remaining_slots", 0))
            cols[3].metric("Discount", f"{status.get('discount_percent', 20)}%")
            
            st.progress(status.get("fill_percentage", 0) / 100)
        else:
            st.warning("Discount feature not available.")
    
    with tabs[2]:
        if 'feat19' in loaded_features:
            st.subheader("💬 Feedback")
            comment = st.text_area("Your feedback", height=100, key="feedback_comment")
            rating = st.slider("Rating", 1, 5, 4, key="feedback_rating")
            
            if st.button("Submit Feedback", key="feedback_submit"):
                result = loaded_features['feat19'].submit_feedback(
                    user_id=st.session_state.current_user_id,
                    rating=rating,
                    comment=comment,
                    category="general"
                )
                if result["success"]:
                    st.success("✅ Thank you for your feedback!")
                else:
                    st.error(result["message"])
        else:
            st.warning("Feedback feature not available.")
    
    with tabs[3]:
        st.subheader("📋 My Jobs")
        if 'job_queue' in loaded_features:
            user_id = st.session_state.current_user_id
            jobs = loaded_features['job_queue'].get_user_jobs(user_id, limit=20)
            
            if not jobs:
                st.info("No jobs yet. Use Scene Planner to queue long-form videos.")
            else:
                for job in jobs:
                    with st.container(border=True):
                        status_map = {
                            "queued": "🟡 Queued",
                            "processing": "🔵 Processing",
                            "done": "✅ Done",
                            "failed": "❌ Failed"
                        }
                        status = status_map.get(job['status'], job['status'])
                        st.markdown(f"**Job #{job['id']}** — {status}")
                        
                        if job['status'] == 'processing':
                            if job.get('progress_total'):
                                pct = job['progress_current'] / job['progress_total']
                                st.progress(min(pct, 1.0))
                        
                        if job['status'] == 'done' and job.get('result_path'):
                            if os.path.exists(job['result_path']):
                                st.video(job['result_path'])
        else:
            st.warning("Job queue not available.")
    
    with tabs[4]:
        if 'feat24' in loaded_features:
            loaded_features['feat24'].render_admin_page()
        if 'admin_panel' in dir():
            admin_panel.render_admin_page()

# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    main()