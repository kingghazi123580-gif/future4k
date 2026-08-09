# ============================================
# FEATURE 07: ADD VOICEOVER (TTS) - ENHANCED WITH VOICE OPTIONS
# Filename: feature_07_add_voiceover.py
# ============================================
# FEATURES:
# 1. ✅ Text-to-Speech with multiple languages (Urdu, Hindi, English, etc.)
# 2. ✅ Multiple TTS engines: gTTS (online), pyttsx3 (offline)
# 3. ✅ Auto-detect language from text
# 4. ✅ Voice speed control (0.5x - 2.0x)
# 5. ✅ Voice pitch control (0.5x - 2.0x)
# 6. ✅ Gender selection (male/female/robot/child) - pyttsx3 only
# 7. ✅ FAMOUS VOICES: Morgan Freeman, David Attenborough, Siri, Alexa, etc.
# 8. ✅ VOICE INPUT: Speak your prompt instead of typing
# 9. ✅ Multiple output formats (MP3, WAV, M4A)
# 10. ✅ Add voiceover to existing video (ANY SIZE - no limit)
# 11. ✅ Keep or replace original video audio
# 12. ✅ Watermark support
# 13. ✅ Progress tracking
# 14. ✅ Batch voiceover generation
# ============================================

import os
import sys
import json
import subprocess
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
import requests

# UTF-8 stdout safety
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from config import *
except ImportError:
    print("[ERROR] config.py not found!")
    raise SystemExit(1)

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# Get PATHS with fallbacks
if 'PATHS' not in dir():
    PATHS = {
        'temp': 'temp',
        'videos': 'videos',
        'audio': 'audio'
    }
else:
    if 'audio' not in PATHS:
        PATHS['audio'] = 'audio'

# Get WATERMARK with fallbacks
if 'WATERMARK' not in dir():
    WATERMARK = {
        'text': 'Filmaa',
        'color': '#FFFFFF',
        'font_size': 24,
        'opacity': 0.7,
        'position': 'bottom-right',
        'free_tier': True
    }

# ============================================
# VOICE INPUT SUPPORT
# ============================================

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

def speech_to_text(language="en-US", timeout=5, phrase_time_limit=30):
    """
    Convert speech to text using microphone.
    
    Parameters:
    - language (str): Language code (en-US, ur-PK, hi-IN)
    - timeout (int): Max seconds to wait for speech
    - phrase_time_limit (int): Max seconds for phrase
    
    Returns:
    - dict: {"success": bool, "text": str, "message": str}
    """
    if not SPEECH_RECOGNITION_AVAILABLE:
        return {
            "success": False, 
            "text": "", 
            "message": "Speech recognition not installed. Install with: pip install SpeechRecognition pyaudio"
        }
    
    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("🎤 Listening... Speak your voiceover text clearly.")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            
        print("🔄 Processing speech...")
        text = recognizer.recognize_google(audio, language=language)
        
        return {
            "success": True,
            "text": text,
            "message": f"Speech recognized: {text}"
        }
    except sr.WaitTimeoutError:
        return {"success": False, "text": "", "message": "No speech detected. Please try again."}
    except sr.UnknownValueError:
        return {"success": False, "text": "", "message": "Could not understand audio. Please speak clearly."}
    except sr.RequestError as e:
        return {"success": False, "text": "", "message": f"Speech recognition service error: {e}"}
    except Exception as e:
        return {"success": False, "text": "", "message": f"Error: {e}"}


# ============================================
# VOICE PRESETS (Famous Voices)
# ============================================

VOICE_PRESETS = {
    "morgan_freeman": {
        "name": "Morgan Freeman",
        "description": "Deep, calm, authoritative voice",
        "icon": "🎬",
        "gender": "male",
        "pitch": 0.85,
        "speed": 0.9,
        "voice_type": "narrator"
    },
    "david_attenborough": {
        "name": "David Attenborough",
        "description": "Warm, British, nature documentary style",
        "icon": "🌍",
        "gender": "male",
        "pitch": 1.0,
        "speed": 0.85,
        "voice_type": "narrator"
    },
    "siri": {
        "name": "Siri (Apple)",
        "description": "Clear, neutral, digital assistant voice",
        "icon": "📱",
        "gender": "female",
        "pitch": 1.05,
        "speed": 1.0,
        "voice_type": "digital"
    },
    "alexa": {
        "name": "Alexa (Amazon)",
        "description": "Warm, friendly, digital assistant voice",
        "icon": "🔊",
        "gender": "female",
        "pitch": 1.0,
        "speed": 0.95,
        "voice_type": "digital"
    },
    "google_assistant": {
        "name": "Google Assistant",
        "description": "Neutral, clear, professional voice",
        "icon": "🔵",
        "gender": "female",
        "pitch": 1.02,
        "speed": 1.0,
        "voice_type": "digital"
    },
    "robot": {
        "name": "Robot Voice",
        "description": "Metallic, futuristic, robotic voice",
        "icon": "🤖",
        "gender": "neutral",
        "pitch": 1.2,
        "speed": 0.8,
        "voice_type": "robotic"
    },
    "child_female": {
        "name": "Child (Girl)",
        "description": "High-pitched, young, energetic voice",
        "icon": "👧",
        "gender": "female",
        "pitch": 1.4,
        "speed": 1.1,
        "voice_type": "child"
    },
    "child_male": {
        "name": "Child (Boy)",
        "description": "High-pitched, playful, young voice",
        "icon": "👦",
        "gender": "male",
        "pitch": 1.35,
        "speed": 1.1,
        "voice_type": "child"
    },
    "female_professional": {
        "name": "Female Professional",
        "description": "Clear, confident, business voice",
        "icon": "💼",
        "gender": "female",
        "pitch": 1.0,
        "speed": 1.0,
        "voice_type": "professional"
    },
    "male_professional": {
        "name": "Male Professional",
        "description": "Deep, confident, business voice",
        "icon": "💼",
        "gender": "male",
        "pitch": 0.95,
        "speed": 1.0,
        "voice_type": "professional"
    },
    "female_warm": {
        "name": "Female Warm",
        "description": "Warm, friendly, comforting voice",
        "icon": "🤗",
        "gender": "female",
        "pitch": 1.05,
        "speed": 0.9,
        "voice_type": "warm"
    },
    "male_warm": {
        "name": "Male Warm",
        "description": "Warm, friendly, reassuring voice",
        "icon": "🤗",
        "gender": "male",
        "pitch": 0.95,
        "speed": 0.9,
        "voice_type": "warm"
    },
    "female_energetic": {
        "name": "Female Energetic",
        "description": "Energetic, enthusiastic, upbeat voice",
        "icon": "⚡",
        "gender": "female",
        "pitch": 1.1,
        "speed": 1.2,
        "voice_type": "energetic"
    },
    "male_energetic": {
        "name": "Male Energetic",
        "description": "Energetic, enthusiastic, upbeat voice",
        "icon": "⚡",
        "gender": "male",
        "pitch": 1.05,
        "speed": 1.2,
        "voice_type": "energetic"
    },
    "female_soft": {
        "name": "Female Soft",
        "description": "Soft, gentle, soothing voice",
        "icon": "🌙",
        "gender": "female",
        "pitch": 1.1,
        "speed": 0.8,
        "voice_type": "soft"
    },
    "male_soft": {
        "name": "Male Soft",
        "description": "Soft, gentle, soothing voice",
        "icon": "🌙",
        "gender": "male",
        "pitch": 1.0,
        "speed": 0.8,
        "voice_type": "soft"
    }
}

# ============================================
# LANGUAGE CONFIGURATION (ENHANCED)
# ============================================

LANGUAGE_CODES = {
    "ur": {"code": "ur", "name": "Urdu", "gtts_code": "ur", "pyttsx3_voice": "Urdu"},
    "hi": {"code": "hi", "name": "Hindi", "gtts_code": "hi", "pyttsx3_voice": "Hindi"},
    "en": {"code": "en", "name": "English", "gtts_code": "en", "pyttsx3_voice": "English"},
    "ar": {"code": "ar", "name": "Arabic", "gtts_code": "ar", "pyttsx3_voice": "Arabic"},
    "fr": {"code": "fr", "name": "French", "gtts_code": "fr", "pyttsx3_voice": "French"},
    "es": {"code": "es", "name": "Spanish", "gtts_code": "es", "pyttsx3_voice": "Spanish"},
    "de": {"code": "de", "name": "German", "gtts_code": "de", "pyttsx3_voice": "German"},
    "zh": {"code": "zh", "name": "Chinese", "gtts_code": "zh-CN", "pyttsx3_voice": "Chinese"},
    "ja": {"code": "ja", "name": "Japanese", "gtts_code": "ja", "pyttsx3_voice": "Japanese"},
    "ko": {"code": "ko", "name": "Korean", "gtts_code": "ko", "pyttsx3_voice": "Korean"},
    "ru": {"code": "ru", "name": "Russian", "gtts_code": "ru", "pyttsx3_voice": "Russian"},
    "pt": {"code": "pt", "name": "Portuguese", "gtts_code": "pt", "pyttsx3_voice": "Portuguese"},
    "it": {"code": "it", "name": "Italian", "gtts_code": "it", "pyttsx3_voice": "Italian"},
    "nl": {"code": "nl", "name": "Dutch", "gtts_code": "nl", "pyttsx3_voice": "Dutch"},
    "tr": {"code": "tr", "name": "Turkish", "gtts_code": "tr", "pyttsx3_voice": "Turkish"},
    "fa": {"code": "fa", "name": "Persian", "gtts_code": "fa", "pyttsx3_voice": "Persian"},
}


def detect_language(text: str) -> str:
    """Detect language of the text. Returns 'ur', 'hi', or 'en' (default)."""
    urdu_chars = set('اآبپتٹثجچحخدڈذرزژسشصضطظعغفقکگلمنہھوؤےئ')
    if any(c in urdu_chars for c in text):
        return "ur"
    
    hindi_chars = set('अआइईउऊऋएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह')
    if any(c in hindi_chars for c in text):
        return "hi"
    
    arabic_chars = set('ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهو')
    if any(c in arabic_chars for c in text):
        return "ar"
    
    return "en"


def detect_language_with_confidence(text: str) -> Tuple[str, float]:
    """Detect language with confidence score"""
    urdu_chars = set('اآبپتٹثجچحخدڈذرزژسشصضطظعغفقکگلمنہھوؤےئ')
    hindi_chars = set('अआइईउऊऋएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह')
    arabic_chars = set('ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهو')
    
    total_chars = len(text.strip())
    if total_chars == 0:
        return "en", 0.0
    
    urdu_count = sum(1 for c in text if c in urdu_chars)
    hindi_count = sum(1 for c in text if c in hindi_chars)
    arabic_count = sum(1 for c in text if c in arabic_chars)
    
    if urdu_count > total_chars * 0.3:
        return "ur", urdu_count / total_chars
    elif hindi_count > total_chars * 0.3:
        return "hi", hindi_count / total_chars
    elif arabic_count > total_chars * 0.3:
        return "ar", arabic_count / total_chars
    else:
        return "en", 1.0 - (urdu_count + hindi_count + arabic_count) / total_chars


# ============================================
# INTERNAL HELPERS (FIXED)
# ============================================

def _format_file_size(size_bytes: int) -> str:
    """Format file size to human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _ensure_directories():
    """Ensure required directories exist"""
    for dir_name in PATHS.values():
        os.makedirs(dir_name, exist_ok=True)


def _get_media_duration(path: str) -> float:
    """Get media duration using ffprobe"""
    if not os.path.exists(path):
        return 0.0
    
    if os.path.getsize(path) == 0:
        return 0.0
    
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            try:
                duration = float(result.stdout.strip())
                return max(0, duration)
            except ValueError:
                pass
    except Exception:
        pass
    return 0.0


def _get_audio_codec_for_format(format: str) -> str:
    """Get appropriate audio codec for format"""
    format = format.lower().lstrip(".")
    codecs = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "m4a": "aac",
        "aac": "aac",
        "flac": "flac",
        "ogg": "libvorbis"
    }
    return codecs.get(format, "aac")


def _cleanup_temp_files(file_paths: List[str]):
    """Safely cleanup temporary files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass


def _apply_watermark(video_path: str) -> Tuple[str, bool]:
    """Apply watermark using ffmpeg - FIXED"""
    if not _check_ffmpeg():
        return video_path, False

    tmp_path = video_path.replace(".mp4", "_wm.mp4")

    pos_map = {
        "bottom-right": "x=w-tw-20:y=h-th-20",
        "bottom-left": "x=20:y=h-th-20",
        "top-right": "x=w-tw-20:y=20",
        "top-left": "x=20:y=20",
    }
    position = pos_map.get(WATERMARK.get("position", "bottom-right"), pos_map["bottom-right"])

    color = WATERMARK.get("color", "#FFFFFF").lstrip("#")
    color = f"0x{color}"

    text = str(WATERMARK.get("text", "Filmaa")).replace("'", "\\'").replace(":", "\\:")

    drawtext = (
        f"drawtext=text='{text}':"
        f"fontcolor={color}@{WATERMARK.get('opacity', 0.7)}:"
        f"fontsize={WATERMARK.get('font_size', 24)}:"
        f"{position}"
    )

    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", drawtext, "-codec:a", "copy", tmp_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[warn] Watermark failed: {result.stderr[-200:]}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return video_path, False

    os.replace(tmp_path, video_path)
    return video_path, True


def _mix_audio_with_video(video_path: str, audio_path: str, output_path: str,
                           keep_video_audio: bool = False) -> str:
    """Mix audio with video using FFmpeg - FIXED"""
    if DRY_RUN:
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 1024)
        return output_path

    if not _check_ffmpeg():
        raise RuntimeError("ffmpeg not found. Please install: sudo apt install ffmpeg")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    if keep_video_audio:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v",
            "-map", "1:a",
            "-shortest",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")
    
    return output_path


def _apply_audio_effects(audio_path: str, output_path: str,
                          speed: float = 1.0, pitch: float = 1.0,
                          volume: float = 1.0, target_format: str = "mp3") -> str:
    """Apply audio effects using FFmpeg"""
    if DRY_RUN:
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 1024)
        return output_path

    if not _check_ffmpeg():
        raise RuntimeError("ffmpeg not found. Please install: sudo apt install ffmpeg")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    filters = []

    if speed != 1.0:
        speed = max(0.5, min(2.0, speed))
        if speed <= 2.0:
            filters.append(f"atempo={speed}")
        else:
            parts = []
            remaining = speed
            while remaining > 2.0:
                parts.append("atempo=2.0")
                remaining /= 2.0
            if remaining > 1.0:
                parts.append(f"atempo={remaining}")
            filters.extend(parts)

    if pitch != 1.0:
        pitch = max(0.5, min(2.0, pitch))
        filters.append(f"asetrate=44100*{pitch},aresample=44100")

    if volume != 1.0:
        volume = max(0.0, min(2.0, volume))
        filters.append(f"volume={volume}")

    if not filters:
        shutil.copy2(audio_path, output_path)
        return output_path

    filter_str = ",".join(filters)
    codec = _get_audio_codec_for_format(target_format)

    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-af", filter_str,
        "-c:a", codec,
        "-b:a", "192k",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg effects failed: {result.stderr[-500:]}")
    
    return output_path


# ============================================
# MAIN TTS FUNCTIONS (ENHANCED)
# ============================================

def generate_voiceover(
    text: str,
    language: str = None,
    engine: str = "gtts",
    speed: float = 1.0,
    pitch: float = 1.0,
    gender: str = "female",
    voice_preset: str = None,
    format: str = "mp3",
    output_path: str = None,
    use_voice_input: bool = False,
    voice_language: str = "en-US",
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Generate voiceover from text.

    Parameters:
    - text (str): Text to convert to speech
    - language (str): 'ur', 'hi', 'en' (auto-detected if None)
    - engine (str): 'gtts' (online), 'pyttsx3' (offline)
    - speed (float): 0.5 to 2.0
    - pitch (float): 0.5 to 2.0 (1.0 = no change)
    - gender (str): 'male' or 'female' (only for some engines)
    - voice_preset (str): One of VOICE_PRESETS keys
    - format (str): 'mp3', 'wav', 'm4a'
    - output_path (str): Where to save the audio file
    - use_voice_input (bool): If True, get text from microphone
    - voice_language (str): Language for voice recognition
    - progress_callback (Callable): Progress callback function

    Returns:
    - dict: {"success", "audio_path", "duration", "message", "info"}
    """

    print("\n" + "=" * 60)
    print("🎙️ FEATURE 07: Voiceover (TTS)" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 60)

    # ---------- Handle Voice Input ----------
    if use_voice_input:
        print("🎤 Voice input enabled...")
        speech_result = speech_to_text(language=voice_language)
        if not speech_result["success"]:
            return {
                "success": False,
                "audio_path": None,
                "duration": 0,
                "message": f"Voice input failed: {speech_result['message']}"
            }
        text = speech_result["text"]
        print(f"📝 Voice recognized: {text}")

    # ---------- 1. Validate Input ----------
    if not text or len(text.strip()) < 2:
        return {
            "success": False, 
            "audio_path": None, 
            "duration": 0,
            "message": "Text is too short. Please write at least 2 words."
        }

    text = text.strip()
    print(f"📝 Text: {text[:100]}..." if len(text) > 100 else f"📝 Text: {text}")

    if progress_callback:
        progress_callback(10, "Validating input...")

    # ---------- 2. Apply Voice Preset ----------
    preset_speed = speed
    preset_pitch = pitch
    
    if voice_preset and voice_preset in VOICE_PRESETS:
        preset = VOICE_PRESETS[voice_preset]
        print(f"🎤 Voice preset: {preset['icon']} {preset['name']}")
        print(f"  Description: {preset['description']}")
        # Apply preset values (user can still override)
        if speed == 1.0:  # Only if user didn't change
            preset_speed = preset.get('speed', speed)
        if pitch == 1.0:  # Only if user didn't change
            preset_pitch = preset.get('pitch', pitch)
        # Update gender from preset
        if preset.get('gender') and gender == "female":  # Default gender
            gender = preset.get('gender')

    # ---------- 3. Detect Language ----------
    if language is None:
        language, confidence = detect_language_with_confidence(text)
        print(f"🔍 Auto-detected language: {language} (confidence: {confidence:.0%})")
    else:
        language = language.lower()
        print(f"🔍 Selected language: {language}")

    lang_info = LANGUAGE_CODES.get(language, LANGUAGE_CODES["en"])
    print(f"🌐 Language: {lang_info['name']} ({lang_info['code']})")

    if progress_callback:
        progress_callback(20, f"Using {lang_info['name']} language...")

    # ---------- 4. Select Engine ----------
    if engine == "gtts" and not GTTS_AVAILABLE:
        engine = "pyttsx3"
        print("ℹ️ gTTS not available, switching to pyttsx3")

    if engine == "pyttsx3" and not PYTTSX3_AVAILABLE:
        engine = "gtts"
        print("ℹ️ pyttsx3 not available, switching to gTTS")

    if engine == "gtts" and not GTTS_AVAILABLE:
        return {
            "success": False, 
            "audio_path": None, 
            "duration": 0,
            "message": "No TTS engine available. Install gTTS or pyttsx3."
        }

    print(f"⚙️ Engine: {engine}")
    print(f"⚡ Speed: {preset_speed}  🎵 Pitch: {preset_pitch}")
    print(f"👤 Gender: {gender}")
    if voice_preset:
        print(f"🎤 Voice preset: {VOICE_PRESETS[voice_preset]['name']}")

    if progress_callback:
        progress_callback(30, f"Generating with {engine}...")

    # ---------- 5. Generate Speech ----------
    if output_path is None:
        audio_dir = PATHS.get('audio', 'audio')
        _ensure_directories()
        output_path = os.path.join(audio_dir, f"voiceover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}")

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    duration = 5.0
    temp_files = []

    if DRY_RUN:
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 1024)
        print(f"🔶 [DRY_RUN] Voiceover simulation: {output_path}")
        duration = 5.0
    else:
        try:
            if engine == "gtts":
                gtts_lang = lang_info["gtts_code"]
                tts = gTTS(text=text, lang=gtts_lang, slow=False)
                temp_mp3 = output_path.replace(f".{format}", "_temp.mp3")
                temp_files.append(temp_mp3)
                tts.save(temp_mp3)
                
                if format != "mp3" and PYDUB_AVAILABLE:
                    audio = AudioSegment.from_mp3(temp_mp3)
                    audio.export(output_path, format=format)
                    duration = _get_media_duration(output_path)
                elif format != "mp3":
                    cmd = ["ffmpeg", "-y", "-i", temp_mp3, output_path]
                    subprocess.run(cmd, capture_output=True, check=True)
                    duration = _get_media_duration(output_path)
                else:
                    os.rename(temp_mp3, output_path)
                    duration = _get_media_duration(output_path)
                
                print(f"✅ Voiceover generated using gTTS")

            elif engine == "pyttsx3":
                engine_tts = pyttsx3.init()
                
                voices = engine_tts.getProperty('voices')
                if voices:
                    # Try to find matching voice based on gender and preset
                    if voice_preset and voice_preset in VOICE_PRESETS:
                        # Try to find voice matching preset name
                        preset_name = VOICE_PRESETS[voice_preset]['name'].lower()
                        for voice in voices:
                            voice_name = voice.name.lower()
                            if preset_name in voice_name:
                                engine_tts.setProperty('voice', voice.id)
                                break
                    
                    # Fallback to gender-based selection
                    if gender == "female":
                        for voice in voices:
                            voice_name = voice.name.lower()
                            if any(f in voice_name for f in ['zira', 'female', 'hazel', 'susan']):
                                engine_tts.setProperty('voice', voice.id)
                                break
                    elif gender == "male":
                        for voice in voices:
                            voice_name = voice.name.lower()
                            if any(m in voice_name for m in ['david', 'male', 'mark', 'george']):
                                engine_tts.setProperty('voice', voice.id)
                                break
                
                temp_wav = output_path.replace(f".{format}", "_temp.wav")
                temp_files.append(temp_wav)
                engine_tts.save_to_file(text, temp_wav)
                engine_tts.runAndWait()
                
                if PYDUB_AVAILABLE:
                    audio = AudioSegment.from_wav(temp_wav)
                    audio.export(output_path, format=format)
                    duration = _get_media_duration(output_path)
                else:
                    cmd = ["ffmpeg", "-y", "-i", temp_wav, output_path]
                    subprocess.run(cmd, capture_output=True, check=True)
                    duration = _get_media_duration(output_path)
                
                print(f"✅ Voiceover generated using pyttsx3")

            else:
                return {
                    "success": False, 
                    "audio_path": None, 
                    "duration": 0,
                    "message": f"Unknown engine: {engine}"
                }

        except Exception as e:
            _cleanup_temp_files(temp_files)
            return {
                "success": False, 
                "audio_path": None, 
                "duration": 0,
                "message": f"Voiceover generation failed: {str(e)}"
            }

    _cleanup_temp_files(temp_files)

    if progress_callback:
        progress_callback(60, "Applying audio effects...")

    # ---------- 6. Apply Effects (speed / pitch) ----------
    if (preset_speed != 1.0 or preset_pitch != 1.0) and not DRY_RUN and os.path.exists(output_path):
        try:
            effects_path = output_path.replace(f".{format}", f"_effected.{format}")
            _apply_audio_effects(
                output_path, 
                effects_path, 
                speed=preset_speed, 
                pitch=preset_pitch,
                target_format=format
            )
            os.replace(effects_path, output_path)
            duration = _get_media_duration(output_path)
            print(f"✅ Effects applied: speed={preset_speed}, pitch={preset_pitch}")
        except Exception as e:
            print(f"⚠️ Effects failed: {e}")

    if progress_callback:
        progress_callback(80, "Saving metadata...")

    # ---------- 7. Save Metadata ----------
    audio_info = {
        "audio_id": os.path.basename(output_path).replace(f".{format}", ""),
        "filename": os.path.basename(output_path),
        "text": text,
        "language": lang_info,
        "engine": engine,
        "speed": preset_speed,
        "pitch": preset_pitch,
        "gender": gender,
        "voice_preset": voice_preset,
        "voice_preset_name": VOICE_PRESETS[voice_preset]['name'] if voice_preset else None,
        "voice_input": use_voice_input,
        "format": format,
        "duration": duration,
        "created_at": datetime.now().isoformat(),
        "path": output_path,
        "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 2) if os.path.exists(output_path) else 0,
        "dry_run": DRY_RUN,
        "type": "voiceover"
    }

    info_path = output_path.replace(f".{format}", "_info.json")
    with open(info_path, "w", encoding='utf-8') as f:
        json.dump(audio_info, f, indent=2, ensure_ascii=False)

    if progress_callback:
        progress_callback(100, "Done!")

    print(f"\n" + "=" * 60)
    print(f"✅ VOICEOVER GENERATED SUCCESSFULLY!")
    print(f"=" * 60)
    print(f"🎙️ Path: {output_path}")
    print(f"⏱️ Duration: {duration:.1f}s")
    print(f"📊 Size: {audio_info['file_size_mb']} MB")
    if voice_preset:
        print(f"🎤 Voice: {VOICE_PRESETS[voice_preset]['name']}")
    print(f"📋 Metadata: {info_path}")
    print(f"=" * 60)

    return {
        "success": True,
        "audio_path": output_path,
        "duration": duration,
        "message": f"✅ Voiceover generated successfully! ({duration:.1f}s)",
        "info": audio_info
    }


def add_voiceover_to_video(
    video_path: str,
    text: str,
    language: str = None,
    engine: str = "gtts",
    speed: float = 1.0,
    pitch: float = 1.0,
    gender: str = "female",
    voice_preset: str = None,
    keep_video_audio: bool = False,
    apply_watermark: bool = True,
    use_voice_input: bool = False,
    voice_language: str = "en-US",
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Generate voiceover and add it to a video (any size supported).

    Returns:
    - dict: {"success", "video_path", "audio_path", "message", "info"}
    """

    print("\n" + "=" * 60)
    print("🎬 FEATURE 07: Add Voiceover to Video" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 60)

    # ---------- 1. Validate Input ----------
    if not os.path.exists(video_path):
        return {
            "success": False, 
            "video_path": None, 
            "audio_path": None,
            "message": f"Video not found: {video_path}"
        }
    
    if os.path.getsize(video_path) == 0:
        return {
            "success": False, 
            "video_path": None, 
            "audio_path": None,
            "message": "Video file is empty"
        }

    # Show video size
    video_size = _format_file_size(os.path.getsize(video_path))
    print(f"📹 Video size: {video_size}")

    if not text or len(text.strip()) < 2:
        return {
            "success": False, 
            "video_path": None, 
            "audio_path": None,
            "message": "Text is too short. Please write at least 2 words."
        }

    if progress_callback:
        progress_callback(10, "Validating input...")

    _ensure_directories()

    if not _check_ffmpeg():
        return {
            "success": False, 
            "video_path": None, 
            "audio_path": None,
            "message": "ffmpeg not found. Please install: sudo apt install ffmpeg"
        }

    # ---------- 2. Generate Voiceover ----------
    if progress_callback:
        progress_callback(20, "Generating voiceover...")

    audio_dir = PATHS.get('audio', 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, f"voiceover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")

    voiceover_result = generate_voiceover(
        text=text,
        language=language,
        engine=engine,
        speed=speed,
        pitch=pitch,
        gender=gender,
        voice_preset=voice_preset,
        format="mp3",
        output_path=audio_path,
        use_voice_input=use_voice_input,
        voice_language=voice_language,
        progress_callback=lambda p, m: progress_callback(20 + p * 0.5, m) if progress_callback else None
    )

    if not voiceover_result["success"]:
        return {
            "success": False, 
            "video_path": None, 
            "audio_path": None,
            "message": f"Voiceover generation failed: {voiceover_result['message']}"
        }

    audio_path = voiceover_result["audio_path"]
    audio_duration = voiceover_result["duration"]
    print(f"🎙️ Voiceover duration: {audio_duration:.1f}s")

    if progress_callback:
        progress_callback(70, "Mixing audio with video...")

    # ---------- 3. Get Video Info ----------
    video_duration = _get_media_duration(video_path)
    print(f"📹 Video duration: {video_duration:.1f}s")

    # ---------- 4. Mix Voiceover with Video ----------
    output_name = f"video_with_voiceover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(PATHS.get('videos', 'videos'), output_name)

    try:
        _mix_audio_with_video(video_path, audio_path, output_path, keep_video_audio)
        print(f"✅ Voiceover mixed with video")
    except Exception as e:
        return {
            "success": False, 
            "video_path": None, 
            "audio_path": audio_path,
            "message": f"Audio mixing failed: {str(e)}"
        }

    if progress_callback:
        progress_callback(85, "Adding watermark...")

    # ---------- 5. Watermark ----------
    watermark_applied = False
    if apply_watermark and WATERMARK.get("free_tier", True) and not DRY_RUN:
        try:
            print(f"💧 Adding watermark: {WATERMARK.get('text', 'Filmaa')}")
            _, watermark_applied = _apply_watermark(output_path)
            if watermark_applied:
                print("  ✅ Watermark applied")
            else:
                print("  ⚠️ Watermark failed to apply")
        except Exception as e:
            print(f"  [warn] Watermark error: {e}")

    if progress_callback:
        progress_callback(95, "Saving metadata...")

    # ---------- 6. Save Metadata ----------
    output_size = _format_file_size(os.path.getsize(output_path)) if os.path.exists(output_path) else "0 B"
    
    video_info = {
        "video_id": output_name.replace(".mp4", ""),
        "filename": output_name,
        "original_video": os.path.basename(video_path),
        "original_video_size": video_size,
        "audio_file": os.path.basename(audio_path),
        "text": text[:200] + "..." if len(text) > 200 else text,
        "language": language or detect_language(text),
        "engine": engine,
        "speed": speed,
        "pitch": pitch,
        "gender": gender,
        "voice_preset": voice_preset,
        "voice_preset_name": VOICE_PRESETS[voice_preset]['name'] if voice_preset else None,
        "voice_input": use_voice_input,
        "video_duration": video_duration,
        "audio_duration": audio_duration,
        "keep_video_audio": keep_video_audio,
        "created_at": datetime.now().isoformat(),
        "path": output_path,
        "file_size": output_size,
        "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 2) if os.path.exists(output_path) else 0,
        "dry_run": DRY_RUN,
        "type": "video_with_voiceover",
        "watermark_applied": watermark_applied
    }

    info_path = output_path.replace(".mp4", "_info.json")
    with open(info_path, "w", encoding='utf-8') as f:
        json.dump(video_info, f, indent=2, ensure_ascii=False)

    if progress_callback:
        progress_callback(100, "Done!")

    print(f"\n" + "=" * 60)
    print(f"✅ VOICEOVER ADDED TO VIDEO SUCCESSFULLY!")
    print(f"=" * 60)
    print(f"📹 Path: {output_path}")
    print(f"🎙️ Voiceover: {audio_duration:.1f}s")
    print(f"⏱️ Total duration: {video_duration:.1f}s")
    print(f"📊 Size: {output_size}")
    if voice_preset:
        print(f"🎤 Voice: {VOICE_PRESETS[voice_preset]['name']}")
    print(f"💧 Watermark: {'Applied' if watermark_applied else 'Not applied'}")
    print(f"📋 Metadata: {info_path}")
    print(f"=" * 60)

    return {
        "success": True,
        "video_path": output_path,
        "audio_path": audio_path,
        "message": f"✅ Voiceover added to video successfully! ({audio_duration:.1f}s voiceover)",
        "watermark_applied": watermark_applied,
        "info": video_info
    }


# ============================================
# SHORTCUT FUNCTIONS
# ============================================

def generate_urdu_voiceover(text: str, **kwargs) -> Dict[str, Any]:
    """Generate Urdu voiceover"""
    return generate_voiceover(text, language="ur", **kwargs)


def generate_hindi_voiceover(text: str, **kwargs) -> Dict[str, Any]:
    """Generate Hindi voiceover"""
    return generate_voiceover(text, language="hi", **kwargs)


def generate_english_voiceover(text: str, **kwargs) -> Dict[str, Any]:
    """Generate English voiceover"""
    return generate_voiceover(text, language="en", **kwargs)


def generate_arabic_voiceover(text: str, **kwargs) -> Dict[str, Any]:
    """Generate Arabic voiceover"""
    return generate_voiceover(text, language="ar", **kwargs)


def list_available_languages() -> List[Dict]:
    """List all supported languages"""
    return [{"code": k, "name": v["name"]} for k, v in LANGUAGE_CODES.items()]


def list_voice_presets() -> List[Dict]:
    """List all available voice presets"""
    return [{"id": k, **v} for k, v in VOICE_PRESETS.items()]


def batch_generate_voiceover(texts: List[str], **kwargs) -> List[Dict[str, Any]]:
    """Generate multiple voiceovers in batch"""
    results = []
    for i, text in enumerate(texts):
        print(f"\nProcessing {i+1}/{len(texts)}...")
        result = generate_voiceover(text, **kwargs)
        results.append(result)
    return results


# ============================================
# UI RENDER FUNCTION (For Streamlit)
# ============================================

def render_feature_07():
    """Render Voiceover UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 🎙️ Voiceover (TTS)")
    st.markdown("*Text ko speech mein convert karein aur video mein add karein*")
    
    # Voice input option
    col1, col2 = st.columns(2)
    with col1:
        use_voice_input = st.checkbox(
            "🎤 Use Voice Input (Speak your text)",
            value=False,
            key="voiceover_voice_input"
        )
        
        if use_voice_input:
            voice_lang = st.selectbox(
                "Voice Recognition Language",
                ["en-US", "ur-PK", "hi-IN", "ar-SA", "fr-FR", "es-ES", "de-DE"],
                key="voiceover_voice_lang"
            )
            st.info("🎤 Click 'Generate Voiceover' and speak clearly into your microphone")
    
    with col2:
        st.markdown("### 📝 Text Input")
        if use_voice_input:
            text = st.text_area(
                "Text will be auto-filled from voice",
                placeholder="Speak your text...",
                height=100,
                key="voiceover_text",
                disabled=True
            )
            st.caption("🎤 Your spoken text will appear here after recognition")
        else:
            text = st.text_area(
                "Text for voiceover",
                placeholder="Apna text yahan likhein...\nExample: السلام علیکم، میں فلماء ہوں۔\nExample: नमस्ते, मैं फिल्मा हूँ।\nExample: Hello, I am Filmaa.",
                height=150,
                key="voiceover_text"
            )
            
            text_length = len(text.strip())
            if text_length > 0:
                st.caption(f"📝 {text_length} characters")
                if text_length < 2:
                    st.warning("⚠️ Kam az kam 2 characters likhein")
    
    # Settings
    st.markdown("### ⚙️ Settings")
    
    col1, col2 = st.columns(2)
    with col1:
        # Language
        language = st.selectbox(
            "Language",
            ["Auto-detect"] + [f"{v['name']} ({k})" for k, v in LANGUAGE_CODES.items()],
            index=0,
            key="voiceover_lang"
        )
        
        if language == "Auto-detect":
            lang_code = None
        else:
            lang_code = language.split("(")[-1].rstrip(")")
        
        # Engine
        engine = st.selectbox(
            "TTS Engine",
            ["gtts (Online - Google)", "pyttsx3 (Offline)"],
            index=0,
            key="voiceover_engine"
        )
        engine = "gtts" if "gtts" in engine else "pyttsx3"
    
    with col2:
        # Voice Preset
        voice_presets = list_voice_presets()
        preset_options = ["None (Custom)"] + [f"{p['icon']} {p['name']} - {p['description']}" for p in voice_presets]
        selected_preset = st.selectbox(
            "Voice Preset",
            preset_options,
            index=0,
            key="voiceover_preset"
        )
        
        voice_preset = None
        if selected_preset != "None (Custom)":
            # Find the preset ID
            for p in voice_presets:
                if f"{p['icon']} {p['name']} - {p['description']}" == selected_preset:
                    voice_preset = p['id']
                    break
    
    # Advanced settings
    col1, col2, col3 = st.columns(3)
    with col1:
        gender = st.selectbox(
            "Gender",
            ["female", "male", "neutral"],
            index=0,
            key="voiceover_gender"
        )
    with col2:
        speed = st.slider(
            "Speed",
            0.5, 2.0, 1.0, 0.1,
            key="voiceover_speed"
        )
    with col3:
        pitch = st.slider(
            "Pitch",
            0.5, 2.0, 1.0, 0.1,
            key="voiceover_pitch"
        )
    
    # Output format
    format = st.selectbox(
        "Output Format",
        ["mp3", "wav", "m4a"],
        index=0,
        key="voiceover_format"
    )
    
    # Video integration
    st.markdown("---")
    st.markdown("### 🎬 Add to Video (Optional)")
    st.caption("No size limit - any video size supported")
    
    col1, col2 = st.columns(2)
    with col1:
        uploaded_video = st.file_uploader(
            "Video upload karein (optional)",
            type=["mp4", "mov", "avi", "webm", "mkv"],
            key="voiceover_video"
        )
        
        if uploaded_video:
            video_size = len(uploaded_video.getvalue())
            st.caption(f"📦 Video size: {_format_file_size(video_size)}")
        
        keep_audio = st.checkbox(
            "Original video audio keep karein",
            value=False,
            help="If checked, voiceover will mix with original audio"
        )
    
    with col2:
        apply_watermark = st.checkbox(
            "Watermark add karein (free tier)",
            value=True,
            key="voiceover_watermark"
        )
        
        if apply_watermark:
            st.caption(f"💧 Watermark: {WATERMARK.get('text', 'Filmaa')}")
    
    # Generate button
    if st.button("🎙️ Generate Voiceover", type="primary", key="voiceover_generate"):
        if not text or len(text.strip()) < 2:
            if not use_voice_input:
                st.error("❌ Pehle text likhein (kam az kam 2 characters)")
            else:
                st.info("🎤 Speak into your microphone...")
            return
        
        # Generate voiceover
        with st.spinner("🎙️ Voiceover generate ho raha hai..."):
            try:
                if use_voice_input:
                    st.info("🎤 Please speak clearly into your microphone...")
                
                if uploaded_video:
                    # Save uploaded video
                    _ensure_directories()
                    temp_video_dir = PATHS.get('temp', 'temp')
                    temp_video_path = os.path.join(temp_video_dir, f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_video.name}")
                    with open(temp_video_path, "wb") as f:
                        f.write(uploaded_video.getbuffer())
                    
                    # Add voiceover to video
                    result = add_voiceover_to_video(
                        video_path=temp_video_path,
                        text=text,
                        language=lang_code,
                        engine=engine,
                        speed=speed,
                        pitch=pitch,
                        gender=gender,
                        voice_preset=voice_preset,
                        keep_video_audio=keep_audio,
                        apply_watermark=apply_watermark,
                        use_voice_input=use_voice_input,
                        voice_language=voice_lang if use_voice_input else "en-US"
                    )
                    
                    # Cleanup temp video
                    if os.path.exists(temp_video_path):
                        os.remove(temp_video_path)
                    
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        
                        # Show video
                        video_path = result["video_path"]
                        if os.path.exists(video_path) and os.path.getsize(video_path) > 1000:
                            with open(video_path, "rb") as f:
                                video_data = f.read()
                            
                            st.video(video_data)
                            
                            st.download_button(
                                label="📥 Download Video",
                                data=video_data,
                                file_name=os.path.basename(video_path),
                                mime="video/mp4"
                            )
                        
                        # Show info
                        info = result.get("info", {})
                        if info:
                            st.json({
                                "Voiceover Duration": f"{info.get('audio_duration', 0):.1f}s",
                                "Video Duration": f"{info.get('video_duration', 0):.1f}s",
                                "Language": info.get("language", "Unknown"),
                                "Engine": info.get("engine", "Unknown"),
                                "Voice Preset": info.get("voice_preset_name", "Custom"),
                                "Watermark": "Applied" if info.get("watermark_applied") else "Not applied",
                                "File Size": info.get("file_size", "Unknown")
                            })
                    else:
                        st.error(f"❌ {result['message']}")
                else:
                    # Generate voiceover only
                    result = generate_voiceover(
                        text=text,
                        language=lang_code,
                        engine=engine,
                        speed=speed,
                        pitch=pitch,
                        gender=gender,
                        voice_preset=voice_preset,
                        format=format,
                        use_voice_input=use_voice_input,
                        voice_language=voice_lang if use_voice_input else "en-US"
                    )
                    
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        
                        audio_path = result["audio_path"]
                        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
                            with open(audio_path, "rb") as f:
                                audio_data = f.read()
                            
                            st.audio(audio_data, format=f"audio/{format}")
                            
                            st.download_button(
                                label=f"📥 Download Audio ({format.upper()})",
                                data=audio_data,
                                file_name=os.path.basename(audio_path),
                                mime=f"audio/{format}"
                            )
                        
                        # Show info
                        info = result.get("info", {})
                        if info:
                            st.json({
                                "Duration": f"{info.get('duration', 0):.1f}s",
                                "Language": info.get("language", {}).get("name", "Unknown"),
                                "Engine": info.get("engine", "Unknown"),
                                "Voice Preset": info.get("voice_preset_name", "Custom"),
                                "Voice Input": "Yes" if info.get("voice_input") else "No",
                                "Size": f"{info.get('file_size_mb', 0):.2f} MB"
                            })
                    else:
                        st.error(f"❌ {result['message']}")
            
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Show available languages and voice presets
    with st.expander("📚 Supported Languages"):
        languages = list_available_languages()
        cols = st.columns(4)
        for i, lang in enumerate(languages):
            cols[i % 4].write(f"• {lang['name']} ({lang['code']})")
    
    with st.expander("🎤 Voice Presets"):
        presets = list_voice_presets()
        cols = st.columns(3)
        for i, preset in enumerate(presets):
            with cols[i % 3]:
                st.markdown(f"**{preset['icon']} {preset['name']}**")
                st.caption(preset['description'])
                st.caption(f"Gender: {preset.get('gender', 'N/A')}")
                st.caption(f"Speed: {preset.get('speed', 1.0)}x | Pitch: {preset.get('pitch', 1.0)}x")
                st.divider()


# ============================================
# TEST FUNCTION (FIXED)
# ============================================

def test():
    """Test the voiceover feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_07_add_voiceover.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    # Check ffmpeg
    if not _check_ffmpeg():
        print("❌ ffmpeg not found! Please install: sudo apt install ffmpeg")
        return
    
    _ensure_directories()
    
    # Test 1: Language detection
    print("\n📝 Test 1: Language detection")
    test_texts = [
        ("السلام علیکم", "ur"),
        ("नमस्ते", "hi"),
        ("Hello", "en"),
        ("مرحبا", "ar"),
    ]
    for t, expected in test_texts:
        detected, confidence = detect_language_with_confidence(t)
        status = "✅" if detected == expected else "❌"
        print(f"  {status} '{t[:20]}' -> {detected} (expected: {expected}) confidence: {confidence:.0%}")
    
    # Test 2: Voice presets
    print("\n🎤 Test 2: Voice presets")
    presets = list_voice_presets()
    print(f"  Total presets: {len(presets)}")
    for p in presets[:5]:
        print(f"    - {p['icon']} {p['name']} ({p['gender']})")
    
    # Test 3: Generate voiceover
    if not DRY_RUN:
        print("\n🎙️ Test 3: Generate voiceover with Morgan Freeman preset")
        result = generate_voiceover(
            text="Hello, this is a test voiceover for Filmaa with Morgan Freeman voice.",
            language="en",
            engine="gtts",
            voice_preset="morgan_freeman",
            format="mp3"
        )
        
        if result["success"]:
            print(f"  ✅ {result['message']}")
            print(f"  📁 Path: {result['audio_path']}")
            print(f"  ⏱️ Duration: {result['duration']:.1f}s")
        else:
            print(f"  ❌ {result['message']}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    test()

# ============================================
# END OF feature_07_add_voiceover.py (ENHANCED)
# ============================================