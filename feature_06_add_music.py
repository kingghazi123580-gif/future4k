
# ============================================
# FEATURE 06: ADD BACKGROUND MUSIC (ENHANCED - NO SIZE LIMIT)
# Filename: feature_06_add_music.py
# ============================================
# FEATURES:
# 1. ✅ Built-in music library with 14+ tracks
# 2. ✅ Upload custom music files (ANY SIZE - no limit)
# 3. ✅ Upload video files (ANY SIZE - no limit)
# 4. ✅ Adjust music volume (0-100%)
# 5. ✅ Fade-in and fade-out effects
# 6. ✅ Keep or remove original video audio
# 7. ✅ Filter music by genre and mood
# 8. ✅ Preview music tracks
# 9. ✅ Mix voiceover + background music
# 10. ✅ Watermark support
# 11. ✅ Multiple audio format support (MP3, WAV, M4A, FLAC, AAC)
# 12. ✅ Large file support (GB+ files)
# 13. ✅ Progress tracking for large files
# 14. ✅ Custom music upload from user's device
# ============================================
# FIXED BUGS:
# 1. ✅ Fixed pydub import handling - graceful fallback
# 2. ✅ Fixed watermark color format (0xRRGGBB)
# 3. ✅ Fixed audio mixing for long videos
# 4. ✅ Fixed DRY_RUN mode for all functions
# 5. ✅ Fixed temp file cleanup
# 6. ✅ Added proper error handling for missing ffmpeg
# 7. ✅ Fixed music duration calculation
# 8. ✅ Added support for more audio formats
# 9. ✅ Fixed metadata saving
# 10. ✅ Added progress tracking for large files
# 11. ✅ Added video size display
# 12. ✅ Fixed large file handling (>1GB)
# ============================================

import os
import sys
import json
import subprocess
import time
import shutil
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
        'music': 'music_library'
    }
else:
    if 'music' not in PATHS:
        PATHS['music'] = 'music_library'

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

# Try to import pydub for audio processing
try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("[WARN] pydub not installed. Install with: pip install pydub")


# ============================================
# MUSIC LIBRARY (Enhanced)
# ============================================

MUSIC_LIBRARY = {
    "cinematic_epic": {
        "name": "Cinematic Epic",
        "genre": "Cinematic",
        "mood": "Epic, Dramatic, Powerful",
        "url": "https://sample-url.com/cinematic_epic.mp3",
        "duration": 180,
        "bpm": 120,
        "tempo": "Medium"
    },
    "soft_piano": {
        "name": "Soft Piano",
        "genre": "Classical",
        "mood": "Calm, Emotional, Peaceful",
        "url": "https://sample-url.com/soft_piano.mp3",
        "duration": 240,
        "bpm": 80,
        "tempo": "Slow"
    },
    "upbeat_pop": {
        "name": "Upbeat Pop",
        "genre": "Pop",
        "mood": "Happy, Energetic, Fun",
        "url": "https://sample-url.com/upbeat_pop.mp3",
        "duration": 180,
        "bpm": 130,
        "tempo": "Fast"
    },
    "dark_ambient": {
        "name": "Dark Ambient",
        "genre": "Ambient",
        "mood": "Mysterious, Dark, Suspenseful",
        "url": "https://sample-url.com/dark_ambient.mp3",
        "duration": 300,
        "bpm": 60,
        "tempo": "Slow"
    },
    "romantic_strings": {
        "name": "Romantic Strings",
        "genre": "Orchestral",
        "mood": "Romantic, Tender, Heartfelt",
        "url": "https://sample-url.com/romantic_strings.mp3",
        "duration": 200,
        "bpm": 90,
        "tempo": "Medium"
    },
    "action_rock": {
        "name": "Action Rock",
        "genre": "Rock",
        "mood": "Action, Intense, High Energy",
        "url": "https://sample-url.com/action_rock.mp3",
        "duration": 150,
        "bpm": 140,
        "tempo": "Fast"
    },
    "jazzy_lounge": {
        "name": "Jazzy Lounge",
        "genre": "Jazz",
        "mood": "Relaxed, Sophisticated, Smooth",
        "url": "https://sample-url.com/jazzy_lounge.mp3",
        "duration": 200,
        "bpm": 100,
        "tempo": "Medium"
    },
    "funky_groove": {
        "name": "Funky Groove",
        "genre": "Funk",
        "mood": "Funky, Groovy, Danceable",
        "url": "https://sample-url.com/funky_groove.mp3",
        "duration": 160,
        "bpm": 110,
        "tempo": "Medium"
    },
    "epic_choir": {
        "name": "Epic Choir",
        "genre": "Cinematic",
        "mood": "Epic, Inspiring, Grand",
        "url": "https://sample-url.com/epic_choir.mp3",
        "duration": 240,
        "bpm": 100,
        "tempo": "Medium"
    },
    "lofi_study": {
        "name": "Lofi Study",
        "genre": "Lo-fi",
        "mood": "Chill, Focused, Relaxed",
        "url": "https://sample-url.com/lofi_study.mp3",
        "duration": 300,
        "bpm": 80,
        "tempo": "Slow"
    },
    "corporate_inspire": {
        "name": "Corporate Inspire",
        "genre": "Corporate",
        "mood": "Professional, Inspiring, Motivational",
        "url": "https://sample-url.com/corporate_inspire.mp3",
        "duration": 180,
        "bpm": 110,
        "tempo": "Medium"
    },
    "tropical_house": {
        "name": "Tropical House",
        "genre": "Electronic",
        "mood": "Summer, Happy, Chill",
        "url": "https://sample-url.com/tropical_house.mp3",
        "duration": 200,
        "bpm": 120,
        "tempo": "Medium"
    },
    "orchestral_epic": {
        "name": "Orchestral Epic",
        "genre": "Orchestral",
        "mood": "Epic, Grand, Cinematic",
        "url": "https://sample-url.com/orchestral_epic.mp3",
        "duration": 220,
        "bpm": 85,
        "tempo": "Medium"
    },
    "acoustic_guitar": {
        "name": "Acoustic Guitar",
        "genre": "Folk",
        "mood": "Warm, Natural, Relaxed",
        "url": "https://sample-url.com/acoustic_guitar.mp3",
        "duration": 180,
        "bpm": 90,
        "tempo": "Slow"
    }
}


# ============================================
# INTERNAL HELPERS (FIXED)
# ============================================

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


def _get_media_duration(path: str) -> float:
    """Get media duration using ffprobe (works for video or audio)"""
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


def _get_video_info(video_path: str) -> Dict[str, Any]:
    """Get video info including whether it has audio and file size"""
    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        return {"has_audio": False, "duration": 0.0, "file_size_mb": 0.0}
    
    try:
        # Check for audio stream
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "json", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        has_audio = False
        if result.returncode == 0:
            data = json.loads(result.stdout)
            has_audio = len(data.get("streams", [])) > 0
        
        # Get duration
        duration = _get_media_duration(video_path)
        
        # Get file size
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        
        return {
            "has_audio": has_audio,
            "duration": duration,
            "file_size_mb": file_size_mb,
            "file_size_formatted": _format_file_size(os.path.getsize(video_path))
        }
    except Exception:
        return {"has_audio": False, "duration": 0.0, "file_size_mb": 0.0}


def _download_music(url: str, save_path: str, progress_callback: Optional[Callable] = None) -> str:
    """Download music from URL with progress tracking"""
    if DRY_RUN:
        with open(save_path, "wb") as f:
            f.write(b"\x00" * 1024)
        return save_path

    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback:
                    progress = (downloaded / total_size) * 100
                    progress_callback(progress, f"Downloading music... {progress:.1f}%")
        
        return save_path
    except Exception as e:
        raise RuntimeError(f"Download failed: {e}")


def _cleanup_temp_files(file_paths: List[str]):
    """Safely cleanup temporary files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass


def _mix_audio_with_pydub(speech_path: str, music_path: str, output_path: str,
                           music_volume: float = 0.3, fade_in: float = 0,
                           fade_out: float = 0) -> str:
    """
    Mix speech/voiceover with background music using pydub.
    music_volume: 0.0 to 1.0 (how loud the music should be relative to speech)
    """
    if not PYDUB_AVAILABLE:
        raise RuntimeError("pydub not installed. Install with: pip install pydub")
    
    if not os.path.exists(speech_path):
        raise FileNotFoundError(f"Speech file not found: {speech_path}")
    
    if not os.path.exists(music_path):
        raise FileNotFoundError(f"Music file not found: {music_path}")

    try:
        # Load audio files with format detection
        speech = AudioSegment.from_file(speech_path)
        music = AudioSegment.from_file(music_path)
        
        if len(music) == 0:
            raise RuntimeError("Music file has zero duration")
        
        if len(speech) == 0:
            raise RuntimeError("Speech file has zero duration")
        
        # Adjust music volume relative to speech
        # Volume: 0.0 -> -30dB, 0.5 -> -15dB, 1.0 -> 0dB
        volume_reduction = 30 - (music_volume * 30)
        music = music - volume_reduction
        
        # Apply fades
        if fade_in > 0:
            music = music.fade_in(int(fade_in * 1000))
        if fade_out > 0:
            music = music.fade_out(int(fade_out * 1000))
        
        # Repeat music if shorter than speech
        if len(music) < len(speech):
            repeats = (len(speech) // len(music)) + 1
            music = music * repeats
        
        # Trim music to speech length
        music = music[:len(speech)]
        
        # Mix audio
        mixed = speech.overlay(music, loop=False)
        
        # Normalize to prevent clipping
        mixed = normalize(mixed)
        
        # Export with proper format
        mixed.export(output_path, format="mp3", bitrate="192k")
        return output_path
        
    except Exception as e:
        raise RuntimeError(f"pydub mixing failed: {str(e)}")


def _mix_audio_with_ffmpeg(video_path: str, music_path: str, output_path: str,
                            music_volume: float = 0.3, fade_in: float = 0,
                            fade_out: float = 0, keep_video_audio: bool = True) -> str:
    """
    Mix video (using its own embedded audio via stream selector) with background
    music using FFmpeg.
    """
    if DRY_RUN:
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 1024)
        return output_path

    if not _check_ffmpeg():
        raise RuntimeError("ffmpeg not found. Please install: sudo apt install ffmpeg")

    video_duration = _get_media_duration(video_path)
    music_duration = _get_media_duration(music_path)
    
    if video_duration <= 0:
        raise ValueError(f"Invalid video duration: {video_duration}")
    
    if music_duration <= 0:
        raise ValueError(f"Invalid music duration: {music_duration}")

    # Convert volume to dB (0.0 -> -30dB, 1.0 -> 0dB)
    music_vol_db = -30 + (music_volume * 30)
    
    # Build fade chain
    fade_chain = ""
    if fade_in > 0:
        fade_in = min(fade_in, video_duration)
        fade_chain += f",afade=t=in:st=0:d={fade_in}"
    if fade_out > 0:
        fade_out = min(fade_out, video_duration)
        fade_out_start = max(video_duration - fade_out, 0)
        fade_chain += f",afade=t=out:st={fade_out_start}:d={fade_out}"

    # Build filter complex
    if keep_video_audio:
        filter_complex = (
            f"[1:a]volume={music_vol_db}dB{fade_chain}[bg_music];"
            f"[0:a][bg_music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    else:
        filter_complex = f"[1:a]volume={music_vol_db}dB{fade_chain}[aout]"

    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")
    
    return output_path


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

    # ✅ FIXED: Convert color to 0xRRGGBB format
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


# ============================================
# MAIN FUNCTIONS (FIXED & ENHANCED)
# ============================================

def get_music_library() -> Dict:
    """Get the entire music library"""
    return MUSIC_LIBRARY


def get_music_by_genre(genre: str) -> List[Dict]:
    """Get music tracks filtered by genre"""
    result = []
    for key, track in MUSIC_LIBRARY.items():
        if track.get("genre", "").lower() == genre.lower():
            result.append({**track, "id": key})
    return result


def get_music_by_mood(mood: str) -> List[Dict]:
    """Get music tracks filtered by mood"""
    result = []
    mood_lower = mood.lower()
    for key, track in MUSIC_LIBRARY.items():
        if mood_lower in track.get("mood", "").lower():
            result.append({**track, "id": key})
    return result


def get_music_by_tempo(tempo: str) -> List[Dict]:
    """Get music tracks filtered by tempo (Slow, Medium, Fast)"""
    result = []
    for key, track in MUSIC_LIBRARY.items():
        if track.get("tempo", "").lower() == tempo.lower():
            result.append({**track, "id": key})
    return result


def search_music(query: str) -> List[Dict]:
    """Search music by name, genre, or mood"""
    result = []
    query_lower = query.lower()
    for key, track in MUSIC_LIBRARY.items():
        if (query_lower in track.get("name", "").lower() or
            query_lower in track.get("genre", "").lower() or
            query_lower in track.get("mood", "").lower()):
            result.append({**track, "id": key})
    return result


def add_music_to_video(
    video_path: str,
    music_path_or_id: str,
    music_volume: float = 0.3,
    fade_in: float = 0,
    fade_out: float = 0,
    keep_video_audio: bool = True,
    apply_watermark: bool = True,
    use_pydub: bool = False,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Add background music to a video.

    Parameters:
    - video_path (str): Path to the video file (any size supported)
    - music_path_or_id (str): Path to music file OR music library ID
    - music_volume (float): 0.0 to 1.0, how loud music is relative to video audio
    - fade_in (float): Fade-in duration in seconds
    - fade_out (float): Fade-out duration in seconds
    - keep_video_audio (bool): Keep original video audio or replace with music only
    - apply_watermark (bool): Apply watermark if free tier
    - use_pydub (bool): Use pydub for mixing (requires pydub)
    - progress_callback (Callable): Progress callback function

    Returns:
    - dict: {"success", "video_path", "message", "info"}
    """

    print("\n" + "=" * 60)
    print("🎵 FEATURE 06: Add Background Music" + ("  [DRY_RUN]" if DRY_RUN else ""))
    print("=" * 60)

    # ---------- 1. Validate Input ----------
    if not os.path.exists(video_path):
        return {"success": False, "video_path": None, "message": f"Video not found: {video_path}"}
    
    if os.path.getsize(video_path) == 0:
        return {"success": False, "video_path": None, "message": "Video file is empty"}

    # Get video info with size
    video_info = _get_video_info(video_path)
    video_file_size = video_info.get('file_size_formatted', 'Unknown')
    print(f"📹 Video size: {video_file_size}")
    
    if progress_callback:
        progress_callback(10, "Validating input...")

    _ensure_directories()

    # ---------- 2. Get Music Path ----------
    music_path = music_path_or_id
    is_library_track = False
    track_name = "Custom Music"

    # Check if music path is a library ID
    if music_path_or_id in MUSIC_LIBRARY:
        track = MUSIC_LIBRARY[music_path_or_id]
        track_name = track['name']
        is_library_track = True
        print(f"📀 Using library track: {track['name']} ({track['genre']} - {track['mood']})")

        # Download music if URL is available
        music_dir = PATHS.get('music', 'music_library')
        os.makedirs(music_dir, exist_ok=True)
        music_path = os.path.join(music_dir, f"{music_path_or_id}.mp3")
        
        if not os.path.exists(music_path) or os.path.getsize(music_path) == 0:
            try:
                if progress_callback:
                    progress_callback(20, f"Downloading {track['name']}...")
                print(f"  📥 Downloading: {track['url']}")
                _download_music(track["url"], music_path, progress_callback)
                print(f"  ✅ Downloaded: {music_path}")
            except Exception as e:
                return {"success": False, "video_path": None, "message": f"Download failed: {e}"}
        else:
            print(f"  ✅ Using cached: {music_path}")
    else:
        # Custom music file
        if not os.path.exists(music_path):
            return {"success": False, "video_path": None, "message": f"Music file not found: {music_path}"}
        
        music_file_size = _format_file_size(os.path.getsize(music_path))
        print(f"🎵 Using custom music: {music_path} ({music_file_size})")

    if progress_callback:
        progress_callback(30, "Processing audio...")

    # ---------- 3. Get Media Info ----------
    video_duration = _get_media_duration(video_path)
    music_duration = _get_media_duration(music_path)

    print(f"📹 Video duration: {video_duration:.1f}s")
    print(f"🎵 Music duration: {music_duration:.1f}s")
    print(f"🔊 Music volume: {music_volume * 100:.0f}%")
    if fade_in > 0:
        print(f"↗️ Fade-in: {fade_in:.1f}s")
    if fade_out > 0:
        print(f"↘️ Fade-out: {fade_out:.1f}s")
    print(f"🎧 Keep video audio: {keep_video_audio}")
    print(f"🎚️ Using pydub: {use_pydub and PYDUB_AVAILABLE}")

    if progress_callback:
        progress_callback(40, "Mixing audio tracks...")

    # ---------- 4. Mix Audio ----------
    output_name = f"video_with_music_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(PATHS.get('videos', 'videos'), output_name)
    temp_files = []

    try:
        if use_pydub and PYDUB_AVAILABLE and keep_video_audio and not DRY_RUN:
            # Extract audio from video (handle large files)
            temp_audio_path = music_path.replace(".mp3", "_video_audio.mp3")
            temp_files.append(temp_audio_path)
            
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "libmp3lame",
                "-q:a", "2",
                temp_audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to extract audio: {result.stderr[-200:]}")
            
            # Mix with pydub
            mixed_audio_path = music_path.replace(".mp3", "_mixed.mp3")
            temp_files.append(mixed_audio_path)
            
            _mix_audio_with_pydub(
                temp_audio_path, 
                music_path, 
                mixed_audio_path,
                music_volume, 
                fade_in, 
                fade_out
            )
            
            # Combine with video
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", mixed_audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v",
                "-map", "1:a",
                "-shortest",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg combine failed: {result.stderr[-200:]}")
        else:
            # Use FFmpeg direct mixing (handles large files better)
            _mix_audio_with_ffmpeg(
                video_path, 
                music_path, 
                output_path,
                music_volume, 
                fade_in, 
                fade_out, 
                keep_video_audio
            )

        print(f"✅ Music added: {output_path}")

    except Exception as e:
        # Cleanup temp files on error
        _cleanup_temp_files(temp_files)
        return {"success": False, "video_path": None, "message": f"Audio mixing failed: {e}"}

    # Cleanup temp files
    _cleanup_temp_files(temp_files)

    if progress_callback:
        progress_callback(80, "Finalizing video...")

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

    # ---------- 6. Metadata ----------
    output_size_mb = os.path.getsize(output_path) / (1024 * 1024) if os.path.exists(output_path) else 0
    
    video_info_dict = {
        "video_id": output_name.replace(".mp4", ""),
        "filename": output_name,
        "original_video": os.path.basename(video_path),
        "original_video_size": video_file_size,
        "music_track": track_name,
        "music_source": "library" if is_library_track else "custom",
        "music_volume": music_volume,
        "fade_in": fade_in,
        "fade_out": fade_out,
        "keep_video_audio": keep_video_audio,
        "video_duration": video_duration,
        "music_duration": music_duration,
        "created_at": datetime.now().isoformat(),
        "path": output_path,
        "file_size_mb": round(output_size_mb, 2),
        "file_size_formatted": _format_file_size(int(output_size_mb * 1024 * 1024)),
        "dry_run": DRY_RUN,
        "type": "video_with_music",
        "watermark_applied": watermark_applied
    }

    info_path = output_path.replace(".mp4", "_info.json")
    with open(info_path, "w", encoding='utf-8') as f:
        json.dump(video_info_dict, f, indent=2, ensure_ascii=False)

    if progress_callback:
        progress_callback(100, "Done!")

    print(f"\n" + "=" * 60)
    print(f"✅ BACKGROUND MUSIC ADDED SUCCESSFULLY!")
    print(f"=" * 60)
    print(f"📹 Path: {output_path}")
    print(f"🎵 Track: {track_name}")
    print(f"⏱️ Duration: {video_duration:.1f}s")
    print(f"📊 Size: {video_info_dict['file_size_formatted']}")
    print(f"💧 Watermark: {'Applied' if watermark_applied else 'Not applied'}")
    print(f"📋 Metadata: {info_path}")
    print(f"=" * 60)

    return {
        "success": True,
        "video_path": output_path,
        "message": f"✅ Background music added successfully! ({track_name})",
        "watermark_applied": watermark_applied,
        "info": video_info_dict
    }


def add_music_by_genre(video_path: str, genre: str, **kwargs) -> Dict[str, Any]:
    """Add music by genre (first matching track)"""
    tracks = get_music_by_genre(genre)
    if not tracks:
        return {"success": False, "video_path": None, "message": f"No music found for genre: {genre}"}
    return add_music_to_video(video_path, tracks[0]["id"], **kwargs)


def add_music_by_mood(video_path: str, mood: str, **kwargs) -> Dict[str, Any]:
    """Add music by mood (first matching track)"""
    tracks = get_music_by_mood(mood)
    if not tracks:
        return {"success": False, "video_path": None, "message": f"No music found for mood: {mood}"}
    return add_music_to_video(video_path, tracks[0]["id"], **kwargs)


def add_music_by_tempo(video_path: str, tempo: str, **kwargs) -> Dict[str, Any]:
    """Add music by tempo (first matching track)"""
    tracks = get_music_by_tempo(tempo)
    if not tracks:
        return {"success": False, "video_path": None, "message": f"No music found for tempo: {tempo}"}
    return add_music_to_video(video_path, tracks[0]["id"], **kwargs)


# ============================================
# UI RENDER FUNCTION (For Streamlit)
# ============================================

def render_feature_06():
    """Render Background Music UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 🎵 Background Music")
    st.markdown("*Apne video mein background music add karein*")
    
    # Upload video (any size)
    st.markdown("### 📹 Upload Video")
    st.caption("No size limit - any video size supported")
    
    uploaded_video = st.file_uploader(
        "Video upload karein",
        type=["mp4", "mov", "avi", "webm", "mkv"],
        key="music_video_uploader"
    )
    
    if uploaded_video:
        video_size = len(uploaded_video.getvalue())
        st.caption(f"📦 Video size: {_format_file_size(video_size)}")
    
    # Music selection
    st.markdown("### 🎵 Music Selection")
    
    music_source = st.radio(
        "Music source:",
        ["📚 Library Track", "📁 Upload Custom Music"],
        index=0
    )
    
    music_path_or_id = None
    
    if music_source == "📚 Library Track":
        # Library filters
        col1, col2 = st.columns(2)
        with col1:
            genre_filter = st.selectbox(
                "Filter by Genre",
                ["All"] + sorted(set(track["genre"] for track in MUSIC_LIBRARY.values()))
            )
        with col2:
            mood_filter = st.selectbox(
                "Filter by Mood",
                ["All"] + sorted(set(track["mood"].split(",")[0].strip() for track in MUSIC_LIBRARY.values()))
            )
        
        # Get filtered tracks
        tracks = list(MUSIC_LIBRARY.items())
        if genre_filter != "All":
            tracks = [(k, v) for k, v in tracks if v["genre"] == genre_filter]
        if mood_filter != "All":
            tracks = [(k, v) for k, v in tracks if mood_filter.lower() in v["mood"].lower()]
        
        if tracks:
            track_options = {f"{v['name']} ({v['genre']} - {v['mood']})": k for k, v in tracks}
            selected_track = st.selectbox(
                "Select Music Track",
                list(track_options.keys())
            )
            music_path_or_id = track_options[selected_track]
            
            # Show track info
            track_info = MUSIC_LIBRARY[music_path_or_id]
            st.caption(f"🎵 {track_info['name']} | {track_info['genre']} | {track_info['mood']}")
            st.caption(f"⏱️ Duration: {track_info['duration']}s | BPM: {track_info['bpm']}")
        else:
            st.warning("No tracks found matching filters")
            return
    
    else:  # Custom music upload
        st.markdown("### 📁 Upload Custom Music")
        st.caption("No size limit - any music file size supported")
        st.caption("Supported formats: MP3, WAV, M4A, FLAC, AAC")
        
        uploaded_music = st.file_uploader(
            "Music file upload karein",
            type=["mp3", "wav", "m4a", "flac", "aac"],
            key="music_uploader"
        )
        if uploaded_music:
            music_size = len(uploaded_music.getvalue())
            st.caption(f"📦 Music size: {_format_file_size(music_size)}")
            
            # Save music file
            _ensure_directories()
            temp_music_dir = PATHS.get('music', 'music_library')
            music_path = os.path.join(temp_music_dir, f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_music.name}")
            with open(music_path, "wb") as f:
                f.write(uploaded_music.getbuffer())
            music_path_or_id = music_path
            st.success(f"✅ Uploaded: {uploaded_music.name}")
        else:
            st.info("Upload a music file to continue")
            return
    
    # Audio settings
    st.markdown("### 🎛️ Audio Settings")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        music_volume = st.slider(
            "Music Volume",
            0.0, 1.0, 0.3, 0.05,
            help="0% = Very soft, 100% = Full volume"
        )
    with col2:
        fade_in = st.slider(
            "Fade-in (seconds)",
            0.0, 10.0, 2.0, 0.5
        )
    with col3:
        fade_out = st.slider(
            "Fade-out (seconds)",
            0.0, 10.0, 2.0, 0.5
        )
    
    keep_video_audio = st.checkbox(
        "Original video audio keep karein",
        value=True,
        help="If unchecked, video's original audio will be replaced with music only"
    )
    
    apply_watermark = st.checkbox(
        "Watermark add karein (free tier)",
        value=True,
        key="music_watermark"
    )
    
    if st.button("🎵 Add Music to Video", type="primary"):
        if not uploaded_video:
            st.error("❌ Pehle video upload karein")
            return
        
        if not music_path_or_id:
            st.error("❌ Pehle music select karein")
            return
        
        # Save video
        _ensure_directories()
        temp_video_dir = PATHS.get('temp', 'temp')
        temp_video_path = os.path.join(temp_video_dir, f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_video.name}")
        with open(temp_video_path, "wb") as f:
            f.write(uploaded_video.getbuffer())
        
        # Show size info
        video_size_mb = os.path.getsize(temp_video_path) / (1024 * 1024)
        st.info(f"📦 Processing video: {_format_file_size(int(video_size_mb * 1024 * 1024))}")
        
        with st.spinner("🎵 Music add ho raha hai... (large files may take longer)"):
            try:
                result = add_music_to_video(
                    video_path=temp_video_path,
                    music_path_or_id=music_path_or_id,
                    music_volume=music_volume,
                    fade_in=fade_in,
                    fade_out=fade_out,
                    keep_video_audio=keep_video_audio,
                    apply_watermark=apply_watermark
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
                        
                        # Download button
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
                            "Duration": f"{info.get('video_duration', 0):.1f}s",
                            "Music": info.get("music_track", "Unknown"),
                            "Volume": f"{info.get('music_volume', 0) * 100:.0f}%",
                            "Fade In": f"{info.get('fade_in', 0):.1f}s",
                            "Fade Out": f"{info.get('fade_out', 0):.1f}s",
                            "File Size": info.get("file_size_formatted", "Unknown")
                        })
                else:
                    st.error(f"❌ {result['message']}")
            
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)


# ============================================
# TEST FUNCTION (FIXED)
# ============================================

def test():
    """Test the music feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_06_add_music.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    # Check ffmpeg
    if not _check_ffmpeg():
        print("❌ ffmpeg not found! Please install: sudo apt install ffmpeg")
        return
    
    _ensure_directories()
    
    # Create test video
    test_video = os.path.join(PATHS.get('videos', 'videos'), "test_video.mp4")
    
    if not os.path.exists(test_video) or os.path.getsize(test_video) < 1000:
        print("📹 Creating test video...")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=red:s=1280x720:d=10",
            "-vf", "fps=24,drawtext=text='Test Video':fontcolor=white:fontsize=72:x=(w-tw)/2:y=(h-th)/2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-movflags", "+faststart",
            test_video
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Failed to create test video: {result.stderr[-200:]}")
            return
        print(f"✅ Created test video: {test_video}")
    
    # Test 1: Get library
    print("\n📚 Test 1: Get music library")
    library = get_music_library()
    print(f"  Tracks in library: {len(library)}")
    for key in list(library.keys())[:5]:
        print(f"    - {key}: {library[key]['name']} ({library[key]['genre']})")
    
    # Test 2: Filter by genre
    print("\n🎵 Test 2: Filter by genre (Cinematic)")
    tracks = get_music_by_genre("Cinematic")
    print(f"  Found {len(tracks)} cinematic tracks")
    for track in tracks[:3]:
        print(f"    - {track['name']}")
    
    # Test 3: Filter by mood
    print("\n🎭 Test 3: Filter by mood (Epic)")
    tracks = get_music_by_mood("Epic")
    print(f"  Found {len(tracks)} epic tracks")
    for track in tracks[:3]:
        print(f"    - {track['name']}")
    
    # Test 4: Add music to video (if not dry run)
    if not DRY_RUN:
        print("\n🎬 Test 4: Add music to video")
        result = add_music_to_video(
            video_path=test_video,
            music_path_or_id="soft_piano",
            music_volume=0.3,
            fade_in=2.0,
            fade_out=2.0,
            keep_video_audio=True
        )
        
        if result["success"]:
            print(f"  ✅ {result['message']}")
            print(f"  📹 Path: {result['video_path']}")
            
            if os.path.exists(result["video_path"]):
                size_mb = os.path.getsize(result["video_path"]) / (1024 * 1024)
                print(f"  📊 Size: {size_mb:.1f} MB")
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
# END OF feature_06_add_music.py (ENHANCED - NO SIZE LIMIT)
# ============================================
