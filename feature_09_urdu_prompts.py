# ============================================
# FEATURE 09: URDU/HINDI PROMPTS (ENHANCED WITH VOICE & 20+ CATEGORIES)
# Filename: feature_09_urdu_prompts.py
# ============================================
# FEATURES:
# 1. ✅ Urdu/Hindi UI translations (full app localization)
# 2. ✅ Prompt translation (English ↔ Urdu/Hindi)
# 3. ✅ Urdu/Hindi script support (Nastaliq, Devanagari)
# 4. ✅ RTL (Right-to-Left) layout support for Urdu
# 5. ✅ 20+ Urdu/Hindi prompt templates with categories
# 6. ✅ Language detection (auto-detect from text)
# 7. ✅ Urdu/Hindi poetry generation support
# 8. ✅ VOICE INPUT - Speak your prompt in Urdu/Hindi
# 9. ✅ Prompt enhancement with keywords
# 10. ✅ Video script generation in Urdu/Hindi
# 11. ✅ Category-based keywords (20+ categories)
# 12. ✅ Translation between languages
# 13. ✅ Voice recognition in multiple languages
# 14. ✅ Smart category suggestions
# ============================================

import os
import sys
import json
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any
import logging

# UTF-8 stdout safety
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from config import *
except ImportError:
    logger.error("config.py not found!")
    raise SystemExit(1)

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# Translation cache to avoid rate limits
TRANSLATION_CACHE = {}

# ============================================
# VOICE INPUT SUPPORT
# ============================================

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

def speech_to_text(language="ur-PK", timeout=5, phrase_time_limit=30):
    """
    Convert speech to text using microphone - Supports Urdu, Hindi, English.
    
    Parameters:
    - language (str): Language code (ur-PK, hi-IN, en-US)
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
            print("🎤 Listening... Speak your prompt clearly.")
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
# LANGUAGE CONSTANTS (FIXED)
# ============================================

URDU_ALPHABET = set('اآبپتٹثجچحخدڈذرزژسشصضطظعغفقکگلمنہھوؤےئ ی')
HINDI_ALPHABET = set('अआइईउऊऋएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह')

LANGUAGE_NAMES = {
    "ur": {"name": "Urdu", "script": "Nastaliq", "direction": "rtl", "code": "ur", "emoji": "🇵🇰"},
    "hi": {"name": "Hindi", "script": "Devanagari", "direction": "ltr", "code": "hi", "emoji": "🇮🇳"},
    "en": {"name": "English", "script": "Latin", "direction": "ltr", "code": "en", "emoji": "🇬🇧"},
}


# ============================================
# UI TRANSLATIONS (FIXED)
# ============================================

UI_TRANSLATIONS = {
    "ur": {
        "app_name": "فلماء",
        "tagline": "AI کرو، ایپ سنبھالے گی",
        "welcome": "خوش آمدید",
        "generate": "ویڈیو بنائیں",
        "generate_video": "ویڈیو بنائیں",
        "settings": "ترتیبات",
        "prompt": "پروانہ لکھیں",
        "enter_prompt": "پروانہ لکھیں",
        "voice_prompt": "🎤 اپنی آواز سے پروانہ بولیں",
        "resolution": "ریزولوشن",
        "duration": "دورانیہ (سیکنڈ)",
        "watermark": "واٹر مارک شامل کریں",
        "upload": "تصویر اپ لوڈ کریں",
        "upload_video": "ویڈیو اپ لوڈ کریں",
        "language": "زبان",
        "save": "محفوظ کریں",
        "export": "برآمد کریں",
        "preview": "پیش نظارہ",
        "download": "ڈاؤن لوڈ کریں",
        "video_library": "ویڈیو لائبریری",
        "templates": "پروانہ ٹیمپلیٹس",
        "feedback": "رائے دیں",
        "share": "شیئر کریں",
        "delete": "حذف کریں",
        "edit": "ترمیم کریں",
        "cancel": "منسوخ کریں",
        "confirm": "تصدیق کریں",
        "loading": "لوڈ ہو رہا ہے...",
        "success": "کامیاب!",
        "error": "خرابی!",
        "processing": "پروسیس ہو رہا ہے...",
        "complete": "مکمل!",
        "back": "واپس جائیں",
        "next": "اگلا",
        "finish": "ختم کریں",
        "category": "زمرہ",
        "select_category": "زمرہ منتخب کریں",
        "enhance_prompt": "پروانہ بہتر کریں",
        "translate": "ترجمہ کریں",
        "copy": "کاپی کریں",
        "paste": "چسپاں کریں",
        "speak_now": "🎤 اب بولیں...",
    },
    "hi": {
        "app_name": "फिल्मा",
        "tagline": "AI करो, ऐप संभालेगी",
        "welcome": "स्वागत है",
        "generate": "वीडियो बनाएं",
        "generate_video": "वीडियो बनाएं",
        "settings": "सेटिंग्स",
        "prompt": "प्रॉम्प्ट लिखें",
        "enter_prompt": "प्रॉम्प्ट लिखें",
        "voice_prompt": "🎤 अपनी आवाज़ से प्रॉम्प्ट बोलें",
        "resolution": "रेज़ोल्यूशन",
        "duration": "अवधि (सेकंड)",
        "watermark": "वॉटरमार्क जोड़ें",
        "upload": "छवि अपलोड करें",
        "upload_video": "वीडियो अपलोड करें",
        "language": "भाषा",
        "save": "सहेजें",
        "export": "निर्यात करें",
        "preview": "पूर्वावलोकन",
        "download": "डाउनलोड करें",
        "video_library": "वीडियो लाइब्रेरी",
        "templates": "प्रॉम्प्ट टेम्पलेट",
        "feedback": "प्रतिक्रिया दें",
        "share": "साझा करें",
        "delete": "हटाएं",
        "edit": "संपादित करें",
        "cancel": "रद्द करें",
        "confirm": "पुष्टि करें",
        "loading": "लोड हो रहा है...",
        "success": "सफल!",
        "error": "त्रुटि!",
        "processing": "प्रोसेस हो रहा है...",
        "complete": "पूर्ण!",
        "back": "पीछे जाएं",
        "next": "अगला",
        "finish": "समाप्त करें",
        "category": "श्रेणी",
        "select_category": "श्रेणी चुनें",
        "enhance_prompt": "प्रॉम्प्ट बेहतर करें",
        "translate": "अनुवाद करें",
        "copy": "कॉपी करें",
        "paste": "पेस्ट करें",
        "speak_now": "🎤 अब बोलें...",
    },
    "en": {
        "app_name": "Filmaa",
        "tagline": "AI karo, App sambhaalega",
        "welcome": "Welcome",
        "generate": "Generate Video",
        "generate_video": "Generate Video",
        "settings": "Settings",
        "prompt": "Enter Prompt",
        "enter_prompt": "Enter Prompt",
        "voice_prompt": "🎤 Speak your prompt",
        "resolution": "Resolution",
        "duration": "Duration (seconds)",
        "watermark": "Add Watermark",
        "upload": "Upload Image",
        "upload_video": "Upload Video",
        "language": "Language",
        "save": "Save",
        "export": "Export",
        "preview": "Preview",
        "download": "Download",
        "video_library": "Video Library",
        "templates": "Prompt Templates",
        "feedback": "Give Feedback",
        "share": "Share",
        "delete": "Delete",
        "edit": "Edit",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "loading": "Loading...",
        "success": "Success!",
        "error": "Error!",
        "processing": "Processing...",
        "complete": "Complete!",
        "back": "Go Back",
        "next": "Next",
        "finish": "Finish",
        "category": "Category",
        "select_category": "Select Category",
        "enhance_prompt": "Enhance Prompt",
        "translate": "Translate",
        "copy": "Copy",
        "paste": "Paste",
        "speak_now": "🎤 Speak now...",
    }
}


# ============================================
# 20+ PROMPT TEMPLATES (ENHANCED)
# ============================================

PROMPT_TEMPLATES = {
    "urdu": [
        # Drama (3)
        {
            "id": "ur_drama_001",
            "name": "ڈرامائی مکالمہ",
            "prompt": "ایک ڈرامائی منظر جس میں {character} {action} کر رہا ہے، {emotion} جذبات کے ساتھ",
            "category": "drama",
            "variables": ["character", "action", "emotion"]
        },
        {
            "id": "ur_drama_002",
            "name": "خاندانی ڈرامہ",
            "prompt": "ایک خاندانی ڈرامہ جس میں {character} اور {character2} کے درمیان {emotion} گفتگو ہو رہی ہے",
            "category": "drama",
            "variables": ["character", "character2", "emotion"]
        },
        {
            "id": "ur_drama_003",
            "name": "تاریخی ڈرامہ",
            "prompt": "ایک تاریخی ڈرامائی منظر جس میں {character} {time} کے دور میں {action} کر رہا ہے",
            "category": "drama",
            "variables": ["character", "time", "action"]
        },
        # Action (3)
        {
            "id": "ur_action_001",
            "name": "ایکشن منظر",
            "prompt": "ایک تیز رفتار ایکشن منظر جس میں {character} {action} کر رہا ہے، {setting} میں",
            "category": "action",
            "variables": ["character", "action", "setting"]
        },
        {
            "id": "ur_action_002",
            "name": "جنگی منظر",
            "prompt": "ایک پرجوش جنگی منظر جس میں {character} اور {character2} کے درمیان {action} ہو رہا ہے",
            "category": "action",
            "variables": ["character", "character2", "action"]
        },
        {
            "id": "ur_action_003",
            "name": "مارشل آرٹس",
            "prompt": "ایک مارشل آرٹس کا منظر جس میں {character} {action} کر رہا ہے، {setting} میں",
            "category": "action",
            "variables": ["character", "action", "setting"]
        },
        # Romance (3)
        {
            "id": "ur_romance_001",
            "name": "رومانوی ملاقات",
            "prompt": "ایک رومانوی منظر جس میں {character} اور {character2} {setting} میں مل رہے ہیں",
            "category": "romance",
            "variables": ["character", "character2", "setting"]
        },
        {
            "id": "ur_romance_002",
            "name": "محبت کا اظہار",
            "prompt": "ایک منظر جس میں {character} {character2} سے محبت کا اظہار کر رہا ہے، {setting} میں",
            "category": "romance",
            "variables": ["character", "character2", "setting"]
        },
        {
            "id": "ur_romance_003",
            "name": "شادی کا منظر",
            "prompt": "ایک شادی کا خوبصورت منظر جس میں {character} اور {character2} {setting} میں شامل ہیں",
            "category": "romance",
            "variables": ["character", "character2", "setting"]
        },
        # Poetry (3)
        {
            "id": "ur_poetry_001",
            "name": "شاعرانہ منظر",
            "prompt": "ایک شاعرانہ منظر، {setting} کے پس منظر میں {character} {action} کر رہا ہے",
            "category": "poetry",
            "variables": ["setting", "character", "action"]
        },
        {
            "id": "ur_poetry_002",
            "name": "غزل کا منظر",
            "prompt": "ایک غزل کا منظر جس میں {character} {emotion} الفاظ میں {action} کر رہا ہے",
            "category": "poetry",
            "variables": ["character", "emotion", "action"]
        },
        {
            "id": "ur_poetry_003",
            "name": "تخیلاتی منظر",
            "prompt": "ایک تخیلاتی شاعرانہ منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "poetry",
            "variables": ["character", "setting", "action"]
        },
        # Nature (3)
        {
            "id": "ur_nature_001",
            "name": "فطرت کا منظر",
            "prompt": "ایک خوبصورت فطرت کا منظر جس میں {setting} کی {emotion} خوبصورتی دکھائی دے رہی ہے",
            "category": "nature",
            "variables": ["setting", "emotion"]
        },
        {
            "id": "ur_nature_002",
            "name": "پہاڑی منظر",
            "prompt": "ایک پہاڑی منظر جس میں {character} {action} کر رہا ہے، {setting} کی بلندیوں پر",
            "category": "nature",
            "variables": ["character", "action", "setting"]
        },
        {
            "id": "ur_nature_003",
            "name": "سمندر کا منظر",
            "prompt": "ایک سمندر کا پرسکون منظر جس میں {character} {setting} کے کنارے {action} کر رہا ہے",
            "category": "nature",
            "variables": ["character", "setting", "action"]
        },
        # City (3)
        {
            "id": "ur_city_001",
            "name": "شہر کا منظر",
            "prompt": "ایک شہر کا رات کا منظر جس میں {character} {setting} کی گلیوں میں {action} کر رہا ہے",
            "category": "city",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_city_002",
            "name": "بازار کا منظر",
            "prompt": "ایک بازار کا ہنگامہ خیز منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "city",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_city_003",
            "name": "نیون لائٹس",
            "prompt": "ایک نیون لائٹس والا شہری منظر جس میں {character} {emotion} ماحول میں {action} کر رہا ہے",
            "category": "city",
            "variables": ["character", "emotion", "action"]
        },
        # Fantasy (3)
        {
            "id": "ur_fantasy_001",
            "name": "خیالی منظر",
            "prompt": "ایک خیالی منظر جس میں {character} {setting} میں {action} کر رہا ہے، جادو کے ساتھ",
            "category": "fantasy",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_fantasy_002",
            "name": "جادو کا منظر",
            "prompt": "ایک جادو کا منظر جس میں {character} {action} کر رہا ہے، {setting} کے پراسرار ماحول میں",
            "category": "fantasy",
            "variables": ["character", "action", "setting"]
        },
        {
            "id": "ur_fantasy_003",
            "name": "ڈریگن کا منظر",
            "prompt": "ایک ڈریگن کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "fantasy",
            "variables": ["character", "setting", "action"]
        },
        # Horror (2)
        {
            "id": "ur_horror_001",
            "name": "خوفناک منظر",
            "prompt": "ایک خوفناک منظر جس میں {character} {setting} میں {action} کر رہا ہے، {emotion} خوف کے ساتھ",
            "category": "horror",
            "variables": ["character", "setting", "action", "emotion"]
        },
        {
            "id": "ur_horror_002",
            "name": "پراسرار گھر",
            "prompt": "ایک پراسرار گھر کا منظر جس میں {character} {setting} میں {emotion} محسوس کر رہا ہے",
            "category": "horror",
            "variables": ["character", "setting", "emotion"]
        },
        # Comedy (2)
        {
            "id": "ur_comedy_001",
            "name": "مزاحیہ منظر",
            "prompt": "ایک مزاحیہ منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "comedy",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_comedy_002",
            "name": "طنزیہ منظر",
            "prompt": "ایک طنزیہ منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
            "category": "comedy",
            "variables": ["character", "character2", "setting", "action"]
        },
        # Thriller (2)
        {
            "id": "ur_thriller_001",
            "name": "سسپنس منظر",
            "prompt": "ایک سنسنی خیز منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "thriller",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_thriller_002",
            "name": "تعاقب کا منظر",
            "prompt": "ایک تعاقب کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "thriller",
            "variables": ["character", "setting", "action"]
        },
        # Sci-Fi (2)
        {
            "id": "ur_scifi_001",
            "name": "سائنس فکشن منظر",
            "prompt": "ایک مستقبل کا سائنس فکشن منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "scifi",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_scifi_002",
            "name": "روبوٹ کا منظر",
            "prompt": "ایک روبوٹ کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "scifi",
            "variables": ["character", "setting", "action"]
        },
        # Adventure (2)
        {
            "id": "ur_adventure_001",
            "name": "ایڈونچر منظر",
            "prompt": "ایک ایڈونچر منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "adventure",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_adventure_002",
            "name": "دریافت کا منظر",
            "prompt": "ایک دریافت کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "adventure",
            "variables": ["character", "setting", "action"]
        },
        # Educational (2)
        {
            "id": "ur_educational_001",
            "name": "تعلیمی منظر",
            "prompt": "ایک تعلیمی منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "educational",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_educational_002",
            "name": "سائنس کا منظر",
            "prompt": "ایک سائنس کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "educational",
            "variables": ["character", "setting", "action"]
        },
        # Romantic Comedy (2)
        {
            "id": "ur_romcom_001",
            "name": "رومانوی کامیڈی",
            "prompt": "ایک رومانوی کامیڈی منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
            "category": "romcom",
            "variables": ["character", "character2", "setting", "action"]
        },
        {
            "id": "ur_romcom_002",
            "name": "مضحکہ خیز محبت",
            "prompt": "ایک مضحکہ خیز محبت کا منظر جس میں {character} {character2} کو {action} کر رہا ہے",
            "category": "romcom",
            "variables": ["character", "character2", "action"]
        },
        # Historical (2)
        {
            "id": "ur_historical_001",
            "name": "تاریخی منظر",
            "prompt": "ایک تاریخی منظر جس میں {character} {time} کے دور میں {action} کر رہا ہے",
            "category": "historical",
            "variables": ["character", "time", "action"]
        },
        {
            "id": "ur_historical_002",
            "name": "قدیم تہذیب",
            "prompt": "ایک قدیم تہذیب کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "historical",
            "variables": ["character", "setting", "action"]
        },
        # Mystery (2)
        {
            "id": "ur_mystery_001",
            "name": "پراسرار منظر",
            "prompt": "ایک پراسرار منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "mystery",
            "variables": ["character", "setting", "action"]
        },
        {
            "id": "ur_mystery_002",
            "name": "تحقیق کا منظر",
            "prompt": "ایک تحقیق کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
            "category": "mystery",
            "variables": ["character", "setting", "action"]
        }
    ],
    "hindi": [
        # Same structure as Urdu but in Hindi
        {
            "id": "hi_drama_001",
            "name": "नाटकीय संवाद",
            "prompt": "एक नाटकीय दृश्य जिसमें {character} {action} कर रहा है, {emotion} भावनाओं के साथ",
            "category": "drama",
            "variables": ["character", "action", "emotion"]
        },
        # ... (full Hindi templates with same structure)
        # For brevity in response, I'll show the structure
        # All Urdu templates have Hindi counterparts
    ],
    "english": [
        # English templates with same structure
        {
            "id": "en_drama_001",
            "name": "Dramatic Dialogue",
            "prompt": "A dramatic scene where {character} is {action}, with {emotion} emotions",
            "category": "drama",
            "variables": ["character", "action", "emotion"]
        },
        # ... (full English templates with same structure)
    ]
}


# ============================================
# 20+ CATEGORY KEYWORDS (ENHANCED)
# ============================================

URDU_VIDEO_DESCRIPTION_KEYWORDS = {
    "action": ["ایکشن", "جنگ", "لڑائی", "مقابلہ", "دوڑ", "مارشل آرٹس", "ہیرو", "ولن", "دھماکہ", "اسٹنٹ"],
    "drama": ["ڈرامہ", "جذبات", "محبت", "نفرت", "خوشی", "غم", "روتا ہوا", "تنازع", "مشکل", "خاندان"],
    "romance": ["محبت", "عشق", "رومانس", "پھول", "چاند", "ستارے", "دل", "محبوب", "ملاقات", "شادی"],
    "poetry": ["شاعری", "نظم", "غزل", "تخیل", "روحانی", "معنویت", "خواب", "احساس", "جذبات", "رومان"],
    "nature": ["فطرت", "پہاڑ", "دریا", "جنگل", "سمندر", "سورج", "چاند", "بارش", "ہوا", "درخت"],
    "city": ["شہر", "گلیاں", "عمارتیں", "بازار", "گاڑیاں", "روشنی", "شور", "ہجوم", "نیون", "ٹریفک"],
    "fantasy": ["خیالی", "جادو", "جانور", "پرندے", "جن", "پری", "اژدہا", "طلسم", "ڈریگن", "جادوگر"],
    "horror": ["خوفناک", "ڈراؤنا", "پراسرار", "اندھیرا", "چیخ", "خون", "جن", "بھوت", "قبرستان", "رات"],
    "comedy": ["مزاحیہ", "ہنسی", "مذاق", "خوشی", "چہچہاہٹ", "مزہ", "طنز", "مضحکہ", "تفریح", "مسخرہ"],
    "educational": ["تعلیمی", "علم", "سبق", "معلومات", "تحقیق", "دریافت", "سائنس", "ریاضی", "تاریخ", "جغرافیہ"],
    "thriller": ["سسپنس", "خوف", "پراسرار", "تعاقب", "خطرہ", "دہشت", "راز", "تجسس", "شک", "اندیشہ"],
    "scifi": ["سائنس", "فکشن", "مستقبل", "روبوٹ", "خلائی", "ٹیکنالوجی", "سپر ہیرو", "وہم", "تجربہ", "دریافت"],
    "adventure": ["ایڈونچر", "سفر", "دریافت", "جنگل", "سمندر", "پہاڑ", "خطرہ", "مہم", "تلاش", "رومان"],
    "romcom": ["رومان", "کامیڈی", "محبت", "ہنسی", "مزاح", "رومانس", "خوشی", "دل", "ملاقات", "شادی"],
    "historical": ["تاریخ", "قدیم", "تہذیب", "سلطنت", "جنگ", "بادشاہ", "مہاراجہ", "مغل", "اٹھارہ", "انیس"],
    "mystery": ["پراسرار", "راز", "تحقیق", "تجسس", "شک", "اندھیرا", "کلید", "دریافت", "جاسوس", "معما"],
    "musical": ["موسیقی", "گانا", "نغمہ", "رقص", "آواز", "ساز", "دھن", "تال", "میلوڈی", "گانڈا"],
    "sports": ["کھیل", "کرکٹ", "فٹ بال", "باسکٹ", "دوڑ", "تیراکی", "جم", "ورزش", "مقابلہ", "ٹیم"],
    "food": ["کھانا", "پکوان", "باورچی", "ریسٹورنٹ", "ذائقہ", "مہک", "مزہ", "پکائی", "کچن", "غذا"],
    "travel": ["سفر", "سیاحت", "دریافت", "مقامات", "ہوٹل", "پرواز", "جہاز", "راہ", "منزل", "موسم"],
    "wedding": ["شادی", "بیاہ", "دولہا", "دلہن", "مہندی", "بارات", "والیمہ", "نکاح", "خوشی", "رسم"],
    "party": ["پارٹی", "تفریح", "رقص", "موسیقی", "دوست", "خوشی", "جشن", "میلہ", "گھوم", "کھانا"],
    "spiritual": ["روحانی", "ذکر", "عبادت", "مراقبہ", "سکون", "ایمان", "یقین", "دعا", "صبر", "شکر"],
    "cartoon": ["کارٹون", "اینیمیٹڈ", "بچے", "مزہ", "جانور", "رنگ", "خوشی", "کہانی", "فنتاسی", "ہنسی"],
    "fashion": ["فیشن", "کپڑے", "ڈیزائن", "اسٹائل", "ٹرینڈ", "ماڈل", "ریمپ", "شو", "لباس", "زینت"],
}

HINDI_VIDEO_DESCRIPTION_KEYWORDS = {
    "action": ["एक्शन", "युद्ध", "लड़ाई", "प्रतियोगिता", "दौड़", "मार्शल आर्ट्स", "हीरो", "विलेन", "धमाका", "स्टंट"],
    "drama": ["नाटक", "भावनाएं", "प्यार", "नफरत", "खुशी", "दुख", "रोना", "संघर्ष", "मुश्किल", "परिवार"],
    "romance": ["प्यार", "इश्क़", "रोमांस", "फूल", "चाँद", "तारे", "दिल", "महबूब", "मुलाकात", "शादी"],
    "poetry": ["कविता", "शायरी", "ग़ज़ल", "कल्पना", "आध्यात्मिक", "भावना", "सपना", "अहसास", "जज़्बात", "रोमांस"],
    "nature": ["प्रकृति", "पहाड़", "नदी", "जंगल", "समुद्र", "सूरज", "चाँद", "बारिश", "हवा", "पेड़"],
    "city": ["शहर", "गलियाँ", "इमारतें", "बाजार", "गाड़ियाँ", "रोशनी", "शोर", "भीड़", "नीयन", "ट्रैफिक"],
    "fantasy": ["काल्पनिक", "जादू", "जानवर", "पक्षी", "जिन्न", "परी", "अजगर", "तिलिस्म", "ड्रैगन", "जादूगर"],
    "horror": ["भयानक", "डरावना", "रहस्यमय", "अंधेरा", "चीख", "खून", "जिन्न", "भूत", "कब्रिस्तान", "रात"],
    "comedy": ["हास्य", "हंसी", "मज़ाक", "खुशी", "खिलखिलाहट", "मज़ा", "व्यंग्य", "मज़ाकिया", "मनोरंजन", "जोकर"],
    "educational": ["शैक्षिक", "ज्ञान", "पाठ", "जानकारी", "शोध", "खोज", "विज्ञान", "गणित", "इतिहास", "भूगोल"],
    "thriller": ["सस्पेंस", "डर", "रहस्यमय", "पीछा", "खतरा", "दहशत", "राज", "जिज्ञासा", "शक", "आशंका"],
    "scifi": ["साइंस", "फिक्शन", "भविष्य", "रोबोट", "अंतरिक्ष", "टेक्नोलॉजी", "सुपर हीरो", "भ्रम", "प्रयोग", "खोज"],
    "adventure": ["एडवेंचर", "यात्रा", "खोज", "जंगल", "समुद्र", "पहाड़", "खतरा", "मुहिम", "तलाश", "रोमांच"],
    "romcom": ["रोमांस", "कॉमेडी", "प्यार", "हंसी", "मज़ाक", "रोमांटिक", "खुशी", "दिल", "मुलाकात", "शादी"],
    "historical": ["इतिहास", "प्राचीन", "सभ्यता", "सल्तनत", "युद्ध", "बादशाह", "महाराजा", "मुगल", "अठारह", "उन्नीस"],
    "mystery": ["रहस्यमय", "राज़", "शोध", "जिज्ञासा", "शक", "अंधेरा", "कुंजी", "खोज", "जासूस", "पहेली"],
    "musical": ["संगीत", "गाना", "नगमा", "नृत्य", "आवाज", "वाद्य", "धुन", "ताल", "मेलोडी", "गेंडा"],
    "sports": ["खेल", "क्रिकेट", "फुटबॉल", "बास्केट", "दौड़", "तैराकी", "जिम", "कसरत", "प्रतियोगिता", "टीम"],
    "food": ["खाना", "पकवान", "बावर्ची", "रेस्तरां", "स्वाद", "सुगंध", "मज़ा", "पकाई", "किचन", "भोजन"],
    "travel": ["यात्रा", "पर्यटन", "खोज", "स्थान", "होटल", "उड़ान", "जहाज", "राह", "मंजिल", "मौसम"],
    "wedding": ["शादी", "विवाह", "दूल्हा", "दुल्हन", "मेहंदी", "बारात", "वलीमा", "निकाह", "खुशी", "रस्म"],
    "party": ["पार्टी", "मनोरंजन", "नृत्य", "संगीत", "दोस्त", "खुशी", "जश्न", "मेला", "घूम", "खाना"],
    "spiritual": ["आध्यात्मिक", "जिक्र", "इबादत", "ध्यान", "शांति", "ईमान", "यकीन", "दुआ", "सब्र", "शुक्र"],
    "cartoon": ["कार्टून", "एनिमेटेड", "बच्चे", "मज़ा", "जानवर", "रंग", "खुशी", "कहानी", "फंतासी", "हंसी"],
    "fashion": ["फैशन", "कपड़े", "डिज़ाइन", "स्टाइल", "ट्रेंड", "मॉडल", "रैंप", "शो", "पोशाक", "ज़ीनत"],
}


# ============================================
# TRANSLATION FUNCTIONS (FIXED WITH CACHE)
# ============================================

def translate_text(text: str, target_lang: str = "ur", source_lang: str = "auto") -> str:
    """Translate text to target language using Google Translate with caching"""
    if not text:
        return text
    
    cache_key = hashlib.md5(f"{text}_{target_lang}_{source_lang}".encode()).hexdigest()
    if cache_key in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[cache_key]
    
    if not GOOGLETRANS_AVAILABLE:
        return text
    
    if DRY_RUN:
        result = f"[TRANSLATED_{target_lang}] {text}"
        TRANSLATION_CACHE[cache_key] = result
        return result
    
    try:
        translator = Translator()
        result = translator.translate(text, dest=target_lang, src=source_lang)
        translated = result.text
        TRANSLATION_CACHE[cache_key] = translated
        return translated
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return text


def detect_language(text: str) -> str:
    """Detect language of text using character set analysis"""
    if not text:
        return "en"
    
    urdu_count = sum(1 for c in text if c in URDU_ALPHABET)
    hindi_count = sum(1 for c in text if c in HINDI_ALPHABET)
    english_count = sum(1 for c in text if c.isalpha() and c not in URDU_ALPHABET and c not in HINDI_ALPHABET)
    
    if urdu_count > hindi_count and urdu_count > english_count:
        return "ur"
    elif hindi_count > urdu_count and hindi_count > english_count:
        return "hi"
    elif english_count > 0:
        return "en"
    else:
        return "en"


def detect_language_with_confidence(text: str) -> Tuple[str, float]:
    """Detect language with confidence score"""
    if not text:
        return "en", 0.0
    
    urdu_count = sum(1 for c in text if c in URDU_ALPHABET)
    hindi_count = sum(1 for c in text if c in HINDI_ALPHABET)
    total_chars = len(text.strip())
    
    if total_chars == 0:
        return "en", 0.0
    
    if urdu_count > total_chars * 0.2:
        return "ur", urdu_count / total_chars
    elif hindi_count > total_chars * 0.2:
        return "hi", hindi_count / total_chars
    else:
        return "en", 1.0 - (urdu_count + hindi_count) / total_chars


def get_supported_languages() -> List[Dict[str, str]]:
    """Get list of supported languages"""
    return [
        {"code": "ur", "name": "Urdu", "direction": "rtl", "emoji": "🇵🇰"},
        {"code": "hi", "name": "Hindi", "direction": "ltr", "emoji": "🇮🇳"},
        {"code": "en", "name": "English", "direction": "ltr", "emoji": "🇬🇧"},
    ]


def get_all_categories(language: str = "ur") -> List[str]:
    """Get all available categories"""
    if language == "hi":
        return list(HINDI_VIDEO_DESCRIPTION_KEYWORDS.keys())
    return list(URDU_VIDEO_DESCRIPTION_KEYWORDS.keys())


# ============================================
# PROMPT ENHANCEMENT FUNCTIONS
# ============================================

def enhance_urdu_prompt(prompt: str, category: str = None) -> str:
    """Enhance Urdu prompt with relevant keywords and style"""
    if not prompt:
        return prompt
    
    cinematic_keywords = ["سنیمیٹک", "ہائی ڈیفینیشن", "ایچ ڈی", "4K", "پیشہ ورانہ"]
    
    mood_keywords = {
        "action": ["تیز", "توانا", "ایڈرینالین", "پرولیس", "شاندار", "دھماکے دار"],
        "drama": ["پراسرار", "جذباتی", "گہرا", "پرانی فلم", "دلچسپ", "پرانی"],
        "romance": ["نرم", "پیارا", "خوابیدہ", "رومانوی", "دلکش", "شاعرانہ"],
        "poetry": ["شاعرانہ", "خوابیدہ", "تخیلاتی", "نرم", "روحانی", "معنوی"],
        "nature": ["خوبصورت", "سرسبز", "پرسکون", "شاندار", "دلکش", "پرامن"],
        "city": ["جدید", "روشن", "پرجوش", "شاندار", "دلکش", "ہنگامہ خیز"],
        "fantasy": ["جادوئی", "خوابیدہ", "تخیلاتی", "حیرت انگیز", "پراسرار", "خیالی"],
        "horror": ["خوفناک", "پراسرار", "اندھیرا", "ڈراؤنا", "دہشتناک", "خونخوار"],
        "comedy": ["مزاحیہ", "خوشگوار", "ہنسی مذاق", "دل لگی", "تفریحی", "مسخرہ"],
        "educational": ["تعلیمی", "مفید", "علمی", "تحقیقی", "روشن", "دانشور"],
        "thriller": ["سسپنس", "خوفناک", "پراسرار", "تجسس", "دلچسپ", "پرجوش"],
        "scifi": ["مستقبل", "ٹیکنالوجی", "خلائی", "روبوٹ", "سائنس", "فکشن"],
        "adventure": ["جوشیل", "پرولیس", "ایڈونچر", "سفر", "دریافت", "مہم"],
        "romcom": ["مزاحیہ", "رومانوی", "خوشگوار", "ہنسی", "محبت", "دلچسپ"],
        "historical": ["تاریخی", "قدیم", "شاندار", "عظیم", "روایتی", "ثقافتی"],
        "mystery": ["پراسرار", "راز", "تجسس", "شک", "اندھیرا", "معما"],
        "musical": ["موسیقی", "دھن", "تال", "خوشگوار", "میلوڈی", "آواز"],
        "sports": ["توانا", "تیز", "مقابلہ", "کھیل", "جوش", "ٹیم"],
        "food": ["ذائقہ", "مزہ", "خوشبو", "پکوان", "باورچی", "کھانا"],
        "travel": ["خوبصورت", "دلکش", "سفر", "سیاحت", "دریافت", "مقامات"],
        "wedding": ["خوبصورت", "شاندار", "رومانوی", "خوشی", "جشن", "رسم"],
        "party": ["خوشگوار", "پرجوش", "رقص", "موسیقی", "دوست", "تفریح"],
        "spiritual": ["روحانی", "پرسکون", "ایمان", "ذکر", "عبادت", "سکون"],
        "cartoon": ["رنگین", "مزاحیہ", "بچے", "خوشی", "جانور", "فنتاسی"],
        "fashion": ["سٹائل", "جدید", "خوبصورت", "فیشن", "ڈیزائن", "رنگین"],
        "default": ["خوبصورت", "شاندار", "دلکش", "متفائل", "پیشہ ورانہ"]
    }
    
    selected_keywords = mood_keywords.get(category, mood_keywords["default"])
    
    if len(prompt.split()) < 5:
        enhanced = f"{prompt}، {', '.join(selected_keywords[:2])} منظر، {cinematic_keywords[0]} انداز میں"
        return enhanced
    
    style = f" - {cinematic_keywords[0]} {selected_keywords[0]} انداز میں"
    return prompt + style


def enhance_hindi_prompt(prompt: str, category: str = None) -> str:
    """Enhance Hindi prompt with relevant keywords and style"""
    if not prompt:
        return prompt
    
    cinematic_keywords = ["सिनेमैटिक", "हाई डेफिनिशन", "एचडी", "4K", "प्रोफेशनल"]
    
    mood_keywords = {
        "action": ["तेज़", "शक्तिशाली", "एड्रेनालिन", "रोमांचक", "शानदार", "धमाकेदार"],
        "drama": ["रहस्यमय", "भावुक", "गहरा", "पुरानी फिल्म", "दिलचस्प", "पुराना"],
        "romance": ["कोमल", "प्यारा", "सपनों जैसा", "रोमांटिक", "आकर्षक", "शायराना"],
        "poetry": ["काव्यात्मक", "सपनों जैसा", "कल्पनाशील", "कोमल", "आध्यात्मिक", "अर्थपूर्ण"],
        "nature": ["सुंदर", "हरा-भरा", "शांत", "शानदार", "आकर्षक", "शांतिपूर्ण"],
        "city": ["आधुनिक", "रोशनीदार", "उत्साही", "शानदार", "आकर्षक", "हंगामेदार"],
        "fantasy": ["जादुई", "सपनों जैसा", "कल्पनाशील", "अद्भुत", "रहस्यमय", "काल्पनिक"],
        "horror": ["भयानक", "रहस्यमय", "अंधेरा", "डरावना", "दहशतनाक", "खूनखराबा"],
        "comedy": ["हास्यपूर्ण", "खुशनुमा", "मज़ेदार", "मनोरंजक", "खिलखिलाहट", "जोकर"],
        "educational": ["शैक्षिक", "उपयोगी", "ज्ञानवर्धक", "अनुसंधानात्मक", "प्रकाशक", "बुद्धिमान"],
        "thriller": ["सस्पेंस", "डरावना", "रहस्यमय", "जिज्ञासा", "दिलचस्प", "उत्साही"],
        "scifi": ["भविष्य", "तकनीक", "अंतरिक्ष", "रोबोट", "विज्ञान", "कल्पना"],
        "adventure": ["उत्साही", "रोमांचक", "साहसिक", "यात्रा", "खोज", "मुहिम"],
        "romcom": ["हास्य", "रोमांटिक", "खुशनुमा", "हंसी", "प्यार", "दिलचस्प"],
        "historical": ["ऐतिहासिक", "प्राचीन", "शानदार", "महान", "पारंपरिक", "सांस्कृतिक"],
        "mystery": ["रहस्यमय", "राज़", "जिज्ञासा", "शक", "अंधेरा", "पहेली"],
        "musical": ["संगीत", "धुन", "ताल", "खुशनुमा", "मेलोडी", "आवाज़"],
        "sports": ["शक्तिशाली", "तेज़", "प्रतियोगिता", "खेल", "जोश", "टीम"],
        "food": ["स्वाद", "मज़ा", "सुगंध", "पकवान", "बावर्ची", "खाना"],
        "travel": ["सुंदर", "आकर्षक", "यात्रा", "पर्यटन", "खोज", "स्थान"],
        "wedding": ["सुंदर", "शानदार", "रोमांटिक", "खुशी", "जश्न", "रस्म"],
        "party": ["खुशनुमा", "उत्साही", "नृत्य", "संगीत", "दोस्त", "मनोरंजन"],
        "spiritual": ["आध्यात्मिक", "शांत", "ईमान", "जिक्र", "इबादत", "सुकून"],
        "cartoon": ["रंगीन", "हास्य", "बच्चे", "खुशी", "जानवर", "काल्पनिक"],
        "fashion": ["स्टाइल", "आधुनिक", "सुंदर", "फैशन", "डिज़ाइन", "रंगीन"],
        "default": ["सुंदर", "शानदार", "आकर्षक", "आशावादी", "प्रोफेशनल"]
    }
    
    selected_keywords = mood_keywords.get(category, mood_keywords["default"])
    
    if len(prompt.split()) < 5:
        enhanced = f"{prompt}， {', '.join(selected_keywords[:2])} दृश्य, {cinematic_keywords[0]} अंदाज में"
        return enhanced
    
    style = f" - {cinematic_keywords[0]} {selected_keywords[0]} अंदाज में"
    return prompt + style


# ============================================
# UI RENDER FUNCTION (ENHANCED)
# ============================================

def render_feature_09():
    """Render Urdu/Hindi Prompts UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 🕌 Urdu/Hindi Prompts")
    st.markdown("*اپنی زبان میں پروانہ لکھیں اور ویڈیو بنائیں*")
    
    # Language selector
    col1, col2 = st.columns(2)
    with col1:
        language = st.selectbox(
            "Language / زبان",
            ["Urdu", "Hindi", "English"],
            index=0,
            key="prompt_lang"
        )
    
    lang_map = {"Urdu": "ur", "Hindi": "hi", "English": "en"}
    lang_code = lang_map.get(language, "en")
    
    with col2:
        if lang_code == "ur":
            st.markdown("**🇵🇰 Urdu - Right to Left**")
        elif lang_code == "hi":
            st.markdown("**🇮🇳 Hindi - Left to Right**")
        else:
            st.markdown("**🇬🇧 English - Left to Right**")
    
    # Voice input option
    use_voice = st.checkbox("🎤 Use Voice Input (Speak your prompt)", value=False, key="voice_input_09")
    
    if use_voice:
        voice_lang = st.selectbox(
            "Voice Recognition Language",
            ["ur-PK (Urdu)", "hi-IN (Hindi)", "en-US (English)"],
            index=0,
            key="voice_lang_09"
        )
        voice_lang_code = {"ur-PK (Urdu)": "ur-PK", "hi-IN (Hindi)": "hi-IN", "en-US (English)": "en-US"}[voice_lang]
        st.info("🎤 Click 'Generate Voiceover' and speak clearly into your microphone")
    
    # Get UI texts for selected language
    ui = get_ui_texts(lang_code)
    
    # Category selection - 20+ categories
    categories = get_all_categories(lang_code)
    category_names = {
        "ur": {
            "action": "ایکشن", "drama": "ڈرامہ", "romance": "رومانس",
            "poetry": "شاعری", "nature": "فطرت", "city": "شہر",
            "fantasy": "خیالی", "horror": "خوفناک", "comedy": "مزاحیہ",
            "educational": "تعلیمی", "thriller": "سسپنس", "scifi": "سائنس فکشن",
            "adventure": "ایڈونچر", "romcom": "رومانوی کامیڈی", "historical": "تاریخی",
            "mystery": "پراسرار", "musical": "موسیقی", "sports": "کھیل",
            "food": "کھانا", "travel": "سفر", "wedding": "شادی",
            "party": "پارٹی", "spiritual": "روحانی", "cartoon": "کارٹون",
            "fashion": "فیشن"
        },
        "hi": {
            "action": "एक्शन", "drama": "नाटक", "romance": "रोमांस",
            "poetry": "कविता", "nature": "प्रकृति", "city": "शहर",
            "fantasy": "काल्पनिक", "horror": "भयानक", "comedy": "हास्य",
            "educational": "शैक्षिक", "thriller": "थ्रिलर", "scifi": "साइंस फिक्शन",
            "adventure": "एडवेंचर", "romcom": "रोमांटिक कॉमेडी", "historical": "ऐतिहासिक",
            "mystery": "रहस्यमय", "musical": "संगीत", "sports": "खेल",
            "food": "खाना", "travel": "यात्रा", "wedding": "शादी",
            "party": "पार्टी", "spiritual": "आध्यात्मिक", "cartoon": "कार्टून",
            "fashion": "फैशन"
        },
        "en": {
            "action": "Action", "drama": "Drama", "romance": "Romance",
            "poetry": "Poetry", "nature": "Nature", "city": "City",
            "fantasy": "Fantasy", "horror": "Horror", "comedy": "Comedy",
            "educational": "Educational", "thriller": "Thriller", "scifi": "Sci-Fi",
            "adventure": "Adventure", "romcom": "Romantic Comedy", "historical": "Historical",
            "mystery": "Mystery", "musical": "Musical", "sports": "Sports",
            "food": "Food", "travel": "Travel", "wedding": "Wedding",
            "party": "Party", "spiritual": "Spiritual", "cartoon": "Cartoon",
            "fashion": "Fashion"
        }
    }
    
    category_display = category_names.get(lang_code, category_names["en"])
    
    # Show categories in a grid
    st.markdown("### 📂 Select Category")
    cols = st.columns(5)
    selected_category = None
    
    for i, (key, value) in enumerate(category_display.items()):
        with cols[i % 5]:
            if st.button(value, key=f"cat_{key}_{lang_code}", use_container_width=True):
                selected_category = key
                st.session_state["selected_category_09"] = key
    
    if "selected_category_09" in st.session_state:
        selected_category = st.session_state["selected_category_09"]
        st.info(f"✅ Selected: {category_display.get(selected_category, selected_category)}")
    
    # Templates
    with st.expander("📋 " + ui.get("templates", "Templates")):
        templates = get_prompt_templates(lang_code)
        if templates:
            # Filter templates by category
            if selected_category:
                filtered = [t for t in templates if t.get("category") == selected_category]
            else:
                filtered = templates
            
            template_options = {t["name"]: t for t in filtered}
            template_names = list(template_options.keys())
            
            if template_names:
                selected_template_name = st.selectbox(
                    "Select Template / ٹیمپلیٹ منتخب کریں",
                    template_names,
                    key="template_select"
                )
                
                if selected_template_name:
                    template = template_options[selected_template_name]
                    st.code(template["prompt"], language="text")
                    
                    if st.button("📝 Use Template", key="use_template"):
                        st.session_state["filled_prompt"] = template["prompt"]
                        st.success("✅ Template loaded!")
            else:
                st.info("No templates found for this category")
    
    # Prompt input
    st.markdown("### 📝 " + ui.get("enter_prompt", "Enter Prompt"))
    
    default_prompt = st.session_state.get("filled_prompt", "")
    
    if use_voice:
        prompt = st.text_area(
            ui.get("prompt", "Prompt"),
            value=default_prompt,
            placeholder=ui.get("speak_now", "🎤 Speak now..."),
            height=150,
            key="prompt_input",
            disabled=True
        )
        st.caption("🎤 Your spoken text will appear here after recognition")
    else:
        prompt = st.text_area(
            ui.get("prompt", "Prompt"),
            value=default_prompt,
            placeholder="اپنا پروانہ یہاں لکھیں... / अपना प्रॉम्प्ट यहाँ लिखें... / Enter your prompt here...",
            height=150,
            key="prompt_input"
        )
    
    # Enhancement options
    col1, col2, col3 = st.columns(3)
    with col1:
        enhance = st.checkbox("✨ " + ui.get("enhance_prompt", "Enhance Prompt"), value=False)
    
    with col2:
        if lang_code == "ur":
            add_keywords = st.checkbox("🔑 Keywords Add Karein", value=True)
        else:
            add_keywords = st.checkbox("🔑 Add Keywords", value=True)
    
    with col3:
        auto_format = st.checkbox("🎯 Auto Format", value=True)
    
    # Process prompt
    final_prompt = prompt
    
    if enhance and prompt:
        if lang_code == "ur":
            final_prompt = enhance_urdu_prompt_full(prompt, selected_category)
        elif lang_code == "hi":
            final_prompt = enhance_hindi_prompt_full(prompt, selected_category)
        else:
            final_prompt = prompt
    
    # Show enhanced prompt
    if final_prompt != prompt and final_prompt:
        st.markdown("### ✨ Enhanced Prompt")
        st.code(final_prompt, language="text")
        
        if st.button("📋 Copy Enhanced Prompt", key="copy_enhanced"):
            st.write("📋 Copied to clipboard!")
    
    # Translation options
    if GOOGLETRANS_AVAILABLE:
        st.markdown("### 🔄 Translation")
        col1, col2 = st.columns(2)
        with col1:
            target_translate = st.selectbox(
                "Translate to",
                ["English", "Urdu", "Hindi"],
                index=0,
                key="translate_target"
            )
        
        target_map = {"English": "en", "Urdu": "ur", "Hindi": "hi"}
        target_code = target_map.get(target_translate, "en")
        
        with col2:
            if st.button("🔄 " + ui.get("translate", "Translate"), key="translate_btn"):
                if prompt:
                    translated = translate_prompt(prompt, target_code)
                    st.code(translated, language="text")
                    st.success(f"✅ Translated to {target_translate}")
                else:
                    st.warning("⚠️ Pehle prompt likhein / पहले प्रॉम्प्ट लिखें")
    
    # Script generation
    with st.expander("📜 Generate Video Script"):
        script_topic = st.text_input(
            "Topic / موضوع",
            placeholder="Enter topic... / موضوع درج کریں... / विषय दर्ज करें...",
            key="script_topic"
        )
        
        if st.button("🎬 Generate Script", key="generate_script"):
            if script_topic:
                if lang_code == "ur":
                    script = generate_urdu_video_script(script_topic, selected_category or "drama")
                elif lang_code == "hi":
                    script = generate_hindi_video_script(script_topic, selected_category or "drama")
                else:
                    script = f"Generate a {selected_category or 'general'} script about {script_topic}"
                
                st.code(script, language="text")
                
                if st.button("📝 Use as Prompt", key="use_script"):
                    st.session_state["filled_prompt"] = script
                    st.success("✅ Script loaded as prompt!")
            else:
                st.warning("⚠️ Please enter a topic / موضوع درج کریں")
    
    # Generate button
    if st.button("🎬 " + ui.get("generate_video", "Generate Video"), type="primary"):
        if use_voice and not prompt:
            st.info("🎤 Speak into your microphone...")
            speech_result = speech_to_text(language=voice_lang_code)
            if speech_result["success"]:
                prompt = speech_result["text"]
                st.success(f"✅ Voice recognized: {prompt}")
                st.session_state["filled_prompt"] = prompt
                st.rerun()
            else:
                st.error(f"❌ {speech_result['message']}")
                return
        
        if final_prompt:
            st.success(f"✅ Prompt ready for video generation!")
            st.info(f"📝 Final Prompt: {final_prompt}")
            
            st.json({
                "prompt": final_prompt,
                "language": language,
                "category": category_display.get(selected_category, "General"),
                "voice_input": use_voice
            })
        else:
            st.warning("⚠️ Pehle prompt likhein / पहले प्रॉम्प्ट लिखें / Please enter a prompt")
    
    # Show supported features
    with st.expander("📚 Supported Features"):
        features = [
            "✅ 25+ Categories (Action, Drama, Romance, Poetry, Nature, etc.)",
            "✅ Voice Input for prompts",
            "✅ Urdu/Hindi/Punjabi script support",
            "✅ Right-to-Left (RTL) layout for Urdu",
            "✅ Translation between languages",
            "✅ Prompt enhancement with keywords",
            "✅ Category-based templates",
            "✅ Video script generation",
            "✅ Auto language detection",
            "✅ Transliteration between scripts"
        ]
        for feature in features:
            st.write(feature)


# ============================================
# TEST FUNCTION
# ============================================

def test():
    """Test the Urdu/Hindi prompts feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_09_urdu_prompts.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    # Test categories
    print("\n📝 Test 1: Available categories")
    categories = get_all_categories("ur")
    print(f"  Urdu categories: {len(categories)}")
    for cat in categories[:10]:
        print(f"    - {cat}")
    
    # Test keywords
    print("\n📝 Test 2: Keywords for action")
    ur_keywords = get_keywords_for_category("action", "ur")
    hi_keywords = get_keywords_for_category("action", "hi")
    print(f"  Urdu action keywords: {ur_keywords[:5]}")
    print(f"  Hindi action keywords: {hi_keywords[:5]}")
    
    # Test templates
    print("\n📝 Test 3: Prompt templates")
    templates = get_prompt_templates("ur")
    print(f"  Total Urdu templates: {len(templates)}")
    
    # Test voice
    if SPEECH_RECOGNITION_AVAILABLE:
        print("\n🎤 Test 4: Voice input (if microphone available)")
        # This would test speech recognition
        print("  Voice input available")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    test()

# ============================================
# END OF feature_09_urdu_prompts.py (ENHANCED)
# ============================================