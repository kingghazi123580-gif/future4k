# ============================================
# VOICE INPUT HELPER — Browser-based recording
# Supports: Urdu (ur), Hindi (hi-IN), English (en-US)
# Uses: streamlit-webrtc + SpeechRecognition
# No PyAudio needed — works in cloud deployment
# ============================================

import io
import os
import tempfile
import numpy as np
import speech_recognition as sr
from pydub import AudioSegment

# Always True since we use browser recording
SPEECH_RECOGNITION_AVAILABLE = True

# Language code mapping for Google Speech Recognition
LANGUAGE_MAP = {
    "English (US)": "en-US",
    "Urdu (Pakistan)": "ur",
    "Hindi (India)": "hi-IN",
}

LANGUAGE_DISPLAY = list(LANGUAGE_MAP.keys())


def get_google_lang_code(display_name):
    """
    Convert display name to Google Speech Recognition language code.
    
    Args:
        display_name: e.g., "English (US)", "Urdu (Pakistan)", "Hindi (India)"
    
    Returns:
        Google language code: e.g., "en-US", "ur", "hi-IN"
    """
    return LANGUAGE_MAP.get(display_name, "en-US")


def audio_frames_to_wav_bytes(audio_frames):
    """
    Convert audio frames from streamlit-webrtc to WAV bytes.
    
    Args:
        audio_frames: List of av.AudioFrame objects from webrtc
    
    Returns:
        BytesIO: WAV audio as bytes buffer, or None if no frames
    """
    if not audio_frames:
        return None
    
    try:
        # Concatenate all audio frames into one numpy array
        all_audio = np.concatenate([f.to_ndarray() for f in audio_frames], axis=1)
        
        # Convert float audio (-1.0 to 1.0) to int16 (-32768 to 32767)
        audio_int16 = (all_audio * 32767).astype(np.int16)
        
        # Get sample rate from first frame
        sample_rate = audio_frames[0].sample_rate
        
        # Determine channels
        if all_audio.shape[0] == 1:
            channels = 1
        else:
            channels = all_audio.shape[0]
        
        # Create AudioSegment from raw bytes
        audio_segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,  # 16-bit audio = 2 bytes per sample
            channels=channels
        )
        
        # Export to WAV format in memory
        wav_io = io.BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)  # Reset buffer position to start
        
        return wav_io
    
    except Exception as e:
        print(f"[ERROR] audio_frames_to_wav_bytes: {e}")
        return None


def speech_to_text(audio_bytes, language_display="English (US)"):
    """
    Convert recorded audio bytes to text using Google Speech Recognition.
    
    Args:
        audio_bytes: BytesIO object containing WAV audio
        language_display: Display name like "English (US)", "Urdu (Pakistan)", "Hindi (India)"
    
    Returns:
        dict: {"success": bool, "text": str, "message": str}
    """
    if audio_bytes is None:
        return {
            "success": False,
            "text": "",
            "message": "No audio recorded. Please speak and try again."
        }
    
    google_lang = get_google_lang_code(language_display)
    
    try:
        # Reset buffer position to beginning
        audio_bytes.seek(0)
        
        # Create recognizer
        recognizer = sr.Recognizer()
        
        # Save audio bytes to temporary WAV file
        # (SpeechRecognition needs a file path, not bytes)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(audio_bytes.read())
            tmp_path = tmp.name
        
        try:
            # Open the audio file
            with sr.AudioFile(tmp_path) as source:
                # Adjust for ambient noise (helps with recognition)
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.record(source)
            
            # Recognize speech using Google's free API
            text = recognizer.recognize_google(audio, language=google_lang)
            
            return {
                "success": True,
                "text": text,
                "message": f"Recognized ({language_display}): {text}"
            }
        
        finally:
            # Always clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except sr.UnknownValueError:
        return {
            "success": False,
            "text": "",
            "message": f"Could not understand audio in {language_display}. Please speak clearly and try again."
        }
    
    except sr.RequestError as e:
        return {
            "success": False,
            "text": "",
            "message": f"Speech recognition service error. Check your internet connection. Error: {e}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "message": f"Error processing audio: {e}"
        }


# ============================================
# TEST FUNCTION
# ============================================
def test():
    """Test that all functions work correctly."""
    print("=" * 50)
    print("🧪 Voice Input Helper — Test")
    print("=" * 50)
    
    print(f"\n✅ Speech Recognition Available: {SPEECH_RECOGNITION_AVAILABLE}")
    
    print("\n📋 Supported Languages:")
    for display, code in LANGUAGE_MAP.items():
        print(f"  • {display} → Google code: {code}")
    
    # Test get_google_lang_code
    assert get_google_lang_code("Urdu (Pakistan)") == "ur"
    assert get_google_lang_code("Hindi (India)") == "hi-IN"
    assert get_google_lang_code("English (US)") == "en-US"
    assert get_google_lang_code("Unknown") == "en-US"
    print("\n✅ get_google_lang_code() — All tests passed")
    
    # Test with None audio
    result = speech_to_text(None, "English (US)")
    assert result["success"] is False
    print("✅ speech_to_text(None) — Returns error correctly")
    
    # Test audio_frames_to_wav_bytes with empty list
    result = audio_frames_to_wav_bytes([])
    assert result is None
    print("✅ audio_frames_to_wav_bytes([]) — Returns None correctly")
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    test()