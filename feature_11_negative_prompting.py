
# ============================================
# FEATURE 11: NEGATIVE PROMPTING (ULTIMATE - VOICE + 25+ CATEGORIES)
# Filename: feature_11_negative_prompting.py
# ============================================
# FEATURES:
# 1. ✅ Negative prompt input with validation
# 2. ✅ 30+ pre-built negative prompt templates
# 3. ✅ Automatic common artifact suppression [citation:8][citation:10][citation:11]
# 4. ✅ Weighted negative prompting (text:weight syntax) [citation:3]
# 5. ✅ 25+ Category-based negative prompts
# 6. ✅ Multi-language support (Urdu/Hindi/English)
# 7. ✅ VOICE INPUT - Speak your negative prompts
# 8. ✅ Smart negative prompt optimization
# 9. ✅ Save/load custom negative prompts
# 10. ✅ Usage tracking for effective prompts
# 11. ✅ Validation with suggestions
# 12. ✅ Format for different models (Agnes, WAN) [citation:2][citation:3][citation:8]
# 13. ✅ Negative prompt guidelines and best practices [citation:7]
# 14. ✅ Category-specific negative prompts for 25+ categories
# ============================================

import os
import sys
import json
import re
import random
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Set, Any
from collections import defaultdict
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
            print("🎤 Listening... Speak your negative prompts clearly.")
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
# STORAGE SETUP
# ============================================

NEGATIVE_DIR = os.path.join(os.path.dirname(__file__), "negative_prompts")
CUSTOM_NEGATIVES_FILE = os.path.join(NEGATIVE_DIR, "custom_negatives.json")
USAGE_STATS_FILE = os.path.join(NEGATIVE_DIR, "neg_usage_stats.json")
TEMPLATE_USAGE_FILE = os.path.join(NEGATIVE_DIR, "template_usage.json")

os.makedirs(NEGATIVE_DIR, exist_ok=True)

# Cache for performance
_NEGATIVE_CACHE = {}
_USAGE_STATS_CACHE = None


# ============================================
# COMPLETE NEGATIVE PROMPT LIBRARY (ENHANCED)
# ============================================

# Common visual artifacts to avoid [citation:8][citation:10][citation:11]
COMMON_NEGATIVES = {
    "en": [
        "blurry", "low quality", "watermark", "text overlay",
        "distorted", "deformed", "extra limbs", "bad anatomy",
        "jitter", "bad hands", "blur", "distortion",
        "static image", "worst quality", "JPEG artifacts",
        "ugly", "disfigured", "mutated", "poorly drawn",
        "cropped", "cut off", "out of frame",
        "duplicate", "repetitive", "boring", "flat",
        "overexposed", "underexposed", "grainy", "noisy",
        "pixelated", "compressed", "artifacts", "halo",
        "ghosting", "smudged", "unclear", "muddy",
        "washed out", "oversaturated", "hazy", "foggy"
    ],
    "ur": [
        "دھندلا", "کم معیار", "واٹر مارک", "متن کا اوورلے",
        "بگڑا ہوا", "خراب", "اضافی اعضاء", "خراب اناٹومی",
        "لرزتا ہوا", "خراب ہاتھ", "دھندلاپن", "مسخ شدہ",
        "جامد تصویر", "انتہائی خراب معیار", "JPEG آرٹفیکٹس",
        "بدصورت", "مسخ شدہ چہرہ", "تباہ شدہ", "بری طرح سے کھینچا گیا",
        "کٹا ہوا", "فریم سے باہر",
        "نقل شدہ", "تکراری", "بیزار کن", "پھیکا",
        "زیادہ روشن", "کم روشن", "دانے دار", "شور والا"
    ],
    "hi": [
        "धुंधला", "निम्न गुणवत्ता", "वॉटरमार्क", "टेक्स्ट ओवरले",
        "विकृत", "विकलांग", "अतिरिक्त अंग", "खराब एनाटॉमी",
        "हिलता हुआ", "खराब हाथ", "धुंधलापन", "विकृत",
        "स्थिर छवि", "बहुत खराब गुणवत्ता", "JPEG कलाकृतियाँ",
        "बदसूरत", "विकृत चेहरा", "विकृत", "खराब तरीके से खींचा गया",
        "कटा हुआ", "फ्रेम से बाहर",
        "नकल", "दोहराव", "उबाऊ", "बेजान",
        "अत्यधिक उजागर", "कम उजागर", "दानेदार", "शोर"
    ]
}

# 25+ Category-based negative prompts (ENHANCED)
CATEGORY_NEGATIVES = {
    "drama": {
        "en": "overacting, unrealistic emotions, poor acting, melodramatic, forced expressions, wooden dialogue, unnatural pauses, stiff performance, boring, predictable",
        "ur": "زیادہ اداکاری، غیر حقیقی جذبات، خراب اداکاری، جذباتی، جبری تاثرات، بے جان مکالمہ، سست اداکاری، اکتا دینے والا",
        "hi": "अत्यधिक अभिनय, अवास्तविक भावनाएं, खराब अभिनय, भावुक, जबरदस्ती भाव, बेजान संवाद, सुस्त अभिनय, उबाऊ"
    },
    "action": {
        "en": "slow motion, boring, no action, static camera, weak impact, unrealistic stunts, bad choreography, stiff movements, no energy, fake explosions",
        "ur": "سست رفتار، بورنگ، کوئی ایکشن نہیں، جامد کیمرہ، کمزور اثر، غیر حقیقی اسٹنٹس، خراب کوریوگرافی، سخت حرکات، جعلی دھماکے",
        "hi": "धीमी गति, उबाऊ, कोई एक्शन नहीं, स्थिर कैमरा, कमजोर प्रभाव, अवास्तविक स्टंट, खराब कोरियोग्राफी, सुस्त गतिविधियां, नकली विस्फोट"
    },
    "romance": {
        "en": "awkward, unromantic, cold, distant, forced chemistry, wooden acting, no chemistry, stiff, uncomfortable, cringy, cheesy dialogue",
        "ur": "بے تکی، غیر رومانوی، سرد، دور، جبری کیمسٹری، بے جان اداکاری، بے ربط، بے تکی، عجیب، پرانی گفتگو",
        "hi": "अजीब, अरोमांटिक, ठंडा, दूर, जबरदस्ती रसायन, बेजान अभिनय, असंबद्ध, अजीब, असहज, पुराना संवाद"
    },
    "poetry": {
        "en": "prosaic, unpoetic, literal, flat imagery, no metaphor, cliché, uninspired, ordinary, mundane, dull, boring rhymes",
        "ur": "غیر شاعرانہ، سادہ، بلا استعارہ، پھیکا منظر، کلچے، بے رنگ، معمولی، بے کیف، بے روح",
        "hi": "अकाव्यात्मक, साधारण, शाब्दिक, बेजान कल्पना, कोई रूपक नहीं, क्लिच, अप्रेरित, सामान्य, बेजान"
    },
    "nature": {
        "en": "polluted, unnatural, fake, artificial, over-saturated, plastic, synthetic, unrealistic colors, toxic, industrial",
        "ur": "آلودہ، غیر فطری، جعلی، مصنوعی، زیادہ سیر شدہ، پلاسٹک، نقلی، غیر حقیقی رنگ، زہریلا",
        "hi": "प्रदूषित, अप्राकृतिक, नकली, कृत्रिम, अत्यधिक संतृप्त, प्लास्टिक, नकली, अवास्तविक रंग, विषाक्त"
    },
    "city": {
        "en": "empty, unrealistic, fake, cartoonish, no people, sterile, artificial, abandoned, desolate, lifeless, soulless",
        "ur": "خالی، غیر حقیقی، جعلی، کارٹون جیسا، کوئی لوگ نہیں، بے جان، مصنوعی، ویران، سنسان، بے روح",
        "hi": "खाली, अवास्तविक, नकली, कार्टून जैसा, कोई लोग नहीं, बेजान, कृत्रिम, उजाड़, सुनसान, बेजान"
    },
    "fantasy": {
        "en": "uncreative, boring, generic, cliché, uninspired, derivative, predictable, conventional, mundane, childish",
        "ur": "غیر تخلیقی، بورنگ، معمولی، کلچے، بے رنگ، معمولی، پیشین گوئی، روایتی، بچکانہ",
        "hi": "अरचनात्मक, उबाऊ, सामान्य, क्लिच, अप्रेरित, व्युत्पन्न, अनुमानित, पारंपरिक, बचकाना"
    },
    "horror": {
        "en": "not scary, funny, ridiculous, cheap effects, laughable, campy, not frightening, silly, cartoonish, predictable jump scares",
        "ur": "ڈراؤنا نہیں، مضحکہ خیز، سستے اثرات، قابلِ ہنسی، مضحکہ خیز، ڈراؤنا نہیں، بچکانہ، جعلی",
        "hi": "डरावना नहीं, हास्यास्पद, सस्ते प्रभाव, हास्यजनक, डरावना नहीं, बचकाना, नकली"
    },
    "comedy": {
        "en": "not funny, forced humor, awkward, cringy, offensive, mean-spirited, tasteless, boring, predictable jokes",
        "ur": "مضحکہ خیز نہیں، جبری مزاح، بے تکی، بیہودہ، جارحانہ، بے ذائقہ، بورنگ، پرانے لطیفے",
        "hi": "हास्यास्पद नहीं, जबरदस्ती हास्य, अजीब, आक्रामक, अरुचिकर, बोरिंग, पुराने चुटकुले"
    },
    "thriller": {
        "en": "not suspenseful, predictable, boring, slow, no tension, anti-climactic, flat, dull, obvious twists",
        "ur": "سسپنس نہیں، قابلِ پیشن گوئی، بورنگ، سست، کوئی تناؤ نہیں، بے کیف، پھیکا، بے دلچسپی",
        "hi": "सस्पेंस नहीं, अनुमानित, उबाऊ, धीमा, कोई तनाव नहीं, नीरस, बेजान, उबाऊ"
    },
    "scifi": {
        "en": "unrealistic, cheap effects, bad cgi, cliché, derivative, boring, slow, no tension, childish, silly gadgets",
        "ur": "غیر حقیقی، سستے اثرات، خراب سی جی آئی، کلچے، معمولی، بورنگ، سست، بچکانہ",
        "hi": "अवास्तविक, सस्ते प्रभाव, खराब सीजीआई, क्लिच, व्युत्पन्न, उबाऊ, धीमा, बचकाना"
    },
    "adventure": {
        "en": "boring, slow, no excitement, predictable, flat, uninspired, derivative, dull, lifeless",
        "ur": "بورنگ، سست، کوئی جوش نہیں، قابلِ پیشن گوئی، پھیکا، بے رنگ، معمولی، بے جان",
        "hi": "उबाऊ, धीमा, कोई उत्साह नहीं, अनुमानित, नीरस, अप्रेरित, सामान्य, बेजान"
    },
    "mystery": {
        "en": "predictable, no tension, boring, slow, obvious clues, flat, dull, no suspense, anticlimactic",
        "ur": "قابلِ پیشن گوئی، کوئی تناؤ نہیں، بورنگ، سست، واضح اشارے، پھیکا، بے سسپنس",
        "hi": "अनुमानित, कोई तनाव नहीं, उबाऊ, धीमा, स्पष्ट संकेत, नीरस, कोई रहस्य नहीं"
    },
    "historical": {
        "en": "inaccurate, fake, modern elements, anachronistic, cartoonish, unrealistic, cheap costumes",
        "ur": "غلط، جعلی، جدید عناصر، تاریخی طور پر غلط، کارٹون جیسا، غیر حقیقی، سستے ملبوسات",
        "hi": "गलत, नकली, आधुनिक तत्व, ऐतिहासिक रूप से गलत, कार्टून जैसा, अवास्तविक"
    },
    "romantic_comedy": {
        "en": "not funny, not romantic, forced, awkward, cringy, boring, predictable, no chemistry",
        "ur": "مضحکہ خیز نہیں، رومانوی نہیں، جبری، بے تکی، عجیب، بورنگ، قابلِ پیشن گوئی",
        "hi": "हास्य नहीं, रोमांटिक नहीं, जबरदस्ती, अजीब, उबाऊ, अनुमानित"
    },
    "musical": {
        "en": "off-key, boring songs, bad singing, fake, unnatural, forced, no rhythm, amateur",
        "ur": "بے سُرے، بورنگ گانے، خراب گائیکی، جعلی، غیر فطری، جبری، بے تال، شوقیہ",
        "hi": "बेसुरा, उबाऊ गाने, खराब गायकी, नकली, अप्राकृतिक, जबरदस्ती"
    },
    "sports": {
        "en": "boring, no action, slow, predictable, flat, no excitement, amateur, low energy",
        "ur": "بورنگ، کوئی ایکشن نہیں، سست، قابلِ پیشن گوئی، پھیکا، کوئی جوش نہیں، شوقیہ",
        "hi": "उबाऊ, कोई एक्शन नहीं, धीमा, अनुमानित, नीरस, कोई उत्साह नहीं"
    },
    "food": {
        "en": "unappetizing, fake, plastic, artificial, boring, dull, unappealing, cartoonish",
        "ur": "بھوک نہ لانے والا، جعلی، پلاسٹک، مصنوعی، بورنگ، پھیکا، ناگوار",
        "hi": "अरुचिकर, नकली, प्लास्टिक, कृत्रिम, उबाऊ, नीरस, अप्रिय"
    },
    "travel": {
        "en": "boring, slow, no excitement, fake, artificial, cheap, uninteresting, flat",
        "ur": "بورنگ، سست، کوئی جوش نہیں، جعلی، مصنوعی، سستا، غیر دلچسپ",
        "hi": "उबाऊ, धीमा, कोई उत्साह नहीं, नकली, कृत्रिम, सस्ता, अरुचिकर"
    },
    "wedding": {
        "en": "cheap, tacky, fake, artificial, boring, no emotion, forced, plastic",
        "ur": "سستا، بھدا، جعلی، مصنوعی، بورنگ، کوئی جذبات نہیں، جبری، پلاسٹک",
        "hi": "सस्ता, भद्दा, नकली, कृत्रिम, उबाऊ, कोई भावना नहीं"
    },
    "party": {
        "en": "boring, dead, no energy, forced, fake, artificial, empty, dull",
        "ur": "بورنگ، مردہ، کوئی توانائی نہیں، جبری، جعلی، مصنوعی، خالی، پھیکا",
        "hi": "उबाऊ, मुर्दा, कोई ऊर्जा नहीं, जबरदस्ती, नकली, कृत्रिम, खाली"
    },
    "spiritual": {
        "en": "fake, insincere, forced, artificial, empty, shallow, hollow, commercial",
        "ur": "جعلی، غیر مخلص، جبری، مصنوعی، خالی، سطحی، بھدا، تجارتی",
        "hi": "नकली, ईमानदार नहीं, जबरदस्ती, कृत्रिम, खाली, सतही, व्यावसायिक"
    },
    "cartoon": {
        "en": "bad animation, flat, lifeless, cheap, amateur, ugly, unnatural, stiff",
        "ur": "خراب اینیمیشن، پھیکا، بے جان، سستا، شوقیہ، بدصورت، غیر فطری، سخت",
        "hi": "खराब एनिमेशन, नीरस, बेजान, सस्ता, शौकिया, बदसूरत, अप्राकृतिक"
    },
    "fashion": {
        "en": "tacky, cheap, ugly, outdated, boring, no style, unfashionable, plain",
        "ur": "بھدا، سستا، بدصورت، پرانا، بورنگ، بے سٹائل، غیر فیشن ایبل",
        "hi": "भद्दा, सस्ता, बदसूरत, पुराना, उबाऊ, बिना स्टाइल, साधारण"
    },
    "crime": {
        "en": "unrealistic, boring, slow, predictable, flat, no tension, amateur, cheap",
        "ur": "غیر حقیقی، بورنگ، سست، قابلِ پیشن گوئی، پھیکا، کوئی تناؤ نہیں، شوقیہ",
        "hi": "अवास्तविक, उबाऊ, धीमा, अनुमानित, नीरस, कोई तनाव नहीं"
    },
    "war": {
        "en": "unrealistic, boring, slow, no tension, fake, cheap effects, flat, no emotion",
        "ur": "غیر حقیقی، بورنگ، سست، کوئی تناؤ نہیں، جعلی، سستے اثرات، پھیکا",
        "hi": "अवास्तविक, उबाऊ, धीमा, कोई तनाव नहीं, नकली, सस्ते प्रभाव"
    },
    "western": {
        "en": "boring, slow, flat, unrealistic, fake, cheap, dull, no action",
        "ur": "بورنگ، سست، پھیکا، غیر حقیقی، جعلی، سستا، کوئی ایکشن نہیں",
        "hi": "उबाऊ, धीमा, नीरस, अवास्तविक, नकली, सस्ता, कोई एक्शन नहीं"
    },
    "noir": {
        "en": "boring, slow, flat, unrealistic, fake, cheap, no mystery, dull",
        "ur": "بورنگ، سست، پھیکا، غیر حقیقی، جعلی، سستا، کوئی راز نہیں",
        "hi": "उबाऊ, धीमा, नीरस, अवास्तविक, नकली, सस्ता, कोई रहस्य नहीं"
    },
    "superhero": {
        "en": "unrealistic, boring, generic, cliché, derivative, predictable, flat, no excitement",
        "ur": "غیر حقیقی، بورنگ، معمولی، کلچے، معمولی، پیشین گوئی، پھیکا، کوئی جوش نہیں",
        "hi": "अवास्तविक, उबाऊ, सामान्य, क्लिच, व्युत्पन्न, अनुमानित, नीरस"
    }
}

# Weighted negative prompt examples
WEIGHTED_EXAMPLES = {
    "en": [
        "(blurry:-1.5)", "(low quality:-2.0)", "(watermark:-1.0)",
        "(deformed:-1.5)", "(extra limbs:-2.0)", "(bad anatomy:-1.5)",
        "(jitter:-1.8)", "(distorted:-1.5)", "(static:-2.0)",
        "(overexposed:-1.3)", "(underexposed:-1.3)", "(grainy:-1.5)",
        "(pixelated:-1.8)", "(compressed:-1.5)", "(washed out:-1.5)"
    ],
    "ur": [
        "(دھندلا:-1.5)", "(کم معیار:-2.0)", "(واٹر مارک:-1.0)",
        "(بگڑا ہوا:-1.5)", "(اضافی اعضاء:-2.0)", "(خراب اناٹومی:-1.5)",
        "(لرزتا ہوا:-1.8)", "(مسخ شدہ:-1.5)", "(جامد:-2.0)"
    ],
    "hi": [
        "(धुंधला:-1.5)", "(निम्न गुणवत्ता:-2.0)", "(वॉटरमार्क:-1.0)",
        "(विकृत:-1.5)", "(अतिरिक्त अंग:-2.0)", "(खराब एनाटॉमी:-1.5)",
        "(हिलता हुआ:-1.8)", "(विकृत:-1.5)", "(स्थिर:-2.0)"
    ]
}

# Complete negative prompt templates (ENHANCED)
NEGATIVE_TEMPLATES = {
    "en": [
        {
            "id": "neg_clean",
            "name": "Clean & Clear",
            "description": "Remove common artifacts and quality issues",
            "prompt": "blurry, low quality, watermark, text overlay, distorted, deformed, pixelated, grainy, artifacts",
            "category": "general"
        },
        {
            "id": "neg_human",
            "name": "Human Focus",
            "description": "Fix human anatomy and face issues",
            "prompt": "bad anatomy, extra limbs, bad hands, bad face, disfigured, ugly, mutated, poorly drawn, stiff, unnatural, mannequin, plastic, wax",
            "category": "human"
        },
        {
            "id": "neg_cinematic",
            "name": "Cinematic Quality",
            "description": "Remove amateur and low-quality elements",
            "prompt": "static image, worst quality, JPEG artifacts, amateur, flat lighting, dull colors, overexposed, underexposed, washed out, oversaturated",
            "category": "quality"
        },
        {
            "id": "neg_motion",
            "name": "Smooth Motion",
            "description": "Fix motion artifacts and jitter",
            "prompt": "jitter, blur, distortion, stutter, freezing, unnatural movement, choppy, jerky, laggy, shaky, unstable",
            "category": "motion"
        },
        {
            "id": "neg_professional",
            "name": "Professional Quality",
            "description": "Remove all amateur elements",
            "prompt": "amateur, low quality, poor composition, bad lighting, washed out, oversaturated, noise, artifacts, compression, cheap, unprofessional",
            "category": "quality"
        },
        {
            "id": "neg_style",
            "name": "Clean Style",
            "description": "Remove style contamination",
            "prompt": "cartoon, anime, painting, illustration, 3D render, CGI, artificial, digital art, filter, comic, sketch, drawing",
            "category": "style"
        },
        {
            "id": "neg_people",
            "name": "People Quality",
            "description": "Fix people-related issues",
            "prompt": "bad anatomy, extra limbs, bad hands, missing fingers, deformed face, unnatural pose, stiff, plastic, wax, mannequin, doll, puppet",
            "category": "human"
        },
        {
            "id": "neg_smooth",
            "name": "Smooth Motion",
            "description": "Ensure smooth, fluid motion",
            "prompt": "jitter, stutter, freezing, choppy, jerky, laggy, unnatural movement, robotic, mechanical, stiff, abrupt",
            "category": "motion"
        },
        {
            "id": "neg_clear",
            "name": "Crystal Clear",
            "description": "Crisp, clear image quality",
            "prompt": "blurry, out of focus, soft, hazy, foggy, smudged, unclear, muddy, pixelated, grainy, noisy, artifacts",
            "category": "quality"
        },
        {
            "id": "neg_natural",
            "name": "Natural Look",
            "description": "Natural, realistic appearance",
            "prompt": "artificial, fake, plastic, synthetic, unnatural, overprocessed, filtered, staged, posed, unnatural colors, oversaturated",
            "category": "style"
        }
    ],
    "ur": [
        {
            "id": "neg_clean",
            "name": "صاف اور شفاف",
            "description": "عام خامیوں کو ہٹائیں",
            "prompt": "دھندلا, کم معیار, واٹر مارک, متن کا اوورلے, بگڑا ہوا, پکسلز, دانے دار, نمونے",
            "category": "general"
        },
        {
            "id": "neg_human",
            "name": "انسانی توجہ",
            "description": "انسانی جسمانی مسائل درست کریں",
            "prompt": "خراب اناٹومی, اضافی اعضاء, خراب ہاتھ, خراب چہرہ, بگڑا ہوا, بدصورت, مسخ شدہ, جمود",
            "category": "human"
        },
        {
            "id": "neg_cinematic",
            "name": "سنیما معیار",
            "description": "غیر پیشہ ورانہ عناصر ہٹائیں",
            "prompt": "جامد تصویر, انتہائی خراب معیار, شوقیہ, پھیکا, دھندلا, زیادہ روشن, کم روشن",
            "category": "quality"
        },
        {
            "id": "neg_motion",
            "name": "ہموار حرکت",
            "description": "حرکت کی خامیاں درست کریں",
            "prompt": "لرزش, دھندلاپن, مسخ, رکاوٹ, غیر فطری حرکت, جھٹکے, جمود",
            "category": "motion"
        }
    ],
    "hi": [
        {
            "id": "neg_clean",
            "name": "साफ और स्पष्ट",
            "description": "सामान्य खामियों को हटाएं",
            "prompt": "धुंधला, निम्न गुणवत्ता, वॉटरमार्क, टेक्स्ट ओवरले, विकृत, पिक्सलेटेड, दानेदार, नमूने",
            "category": "general"
        },
        {
            "id": "neg_human",
            "name": "मानव केंद्रित",
            "description": "मानव शारीरिक समस्याओं को ठीक करें",
            "prompt": "खराब एनाटॉमी, अतिरिक्त अंग, खराब हाथ, खराब चेहरा, विकृत, बदसूरत, विकृत, जमाव",
            "category": "human"
        },
        {
            "id": "neg_cinematic",
            "name": "सिनेमैटिक गुणवत्ता",
            "description": "गैर-पेशेवर तत्वों को हटाएं",
            "prompt": "स्थिर छवि, बहुत खराब गुणवत्ता, शौकिया, बेजान, धुंधला, अत्यधिक उजागर, कम उजागर",
            "category": "quality"
        },
        {
            "id": "neg_motion",
            "name": "स्मूथ मोशन",
            "description": "गति संबंधी खामियों को ठीक करें",
            "prompt": "झटके, धुंधलापन, विकृति, रुकावट, अप्राकृतिक गति, झटके, जमाव",
            "category": "motion"
        }
    ]
}


# ============================================
# CORE FUNCTIONS (FIXED)
# ============================================

def get_all_categories() -> List[str]:
    """Get all available categories"""
    return list(CATEGORY_NEGATIVES.keys())


def get_category_names(language: str = "en") -> Dict[str, str]:
    """Get category names in specific language"""
    names = {
        "en": {
            "drama": "Drama", "action": "Action", "romance": "Romance",
            "poetry": "Poetry", "nature": "Nature", "city": "City",
            "fantasy": "Fantasy", "horror": "Horror", "comedy": "Comedy",
            "thriller": "Thriller", "scifi": "Sci-Fi", "adventure": "Adventure",
            "mystery": "Mystery", "historical": "Historical", "romantic_comedy": "Romantic Comedy",
            "musical": "Musical", "sports": "Sports", "food": "Food",
            "travel": "Travel", "wedding": "Wedding", "party": "Party",
            "spiritual": "Spiritual", "cartoon": "Cartoon", "fashion": "Fashion",
            "crime": "Crime", "war": "War", "western": "Western",
            "noir": "Noir", "superhero": "Superhero"
        },
        "ur": {
            "drama": "ڈرامہ", "action": "ایکشن", "romance": "رومانس",
            "poetry": "شاعری", "nature": "فطرت", "city": "شہر",
            "fantasy": "خیالی", "horror": "خوفناک", "comedy": "مزاحیہ",
            "thriller": "سنسنی خیز", "scifi": "سائنس فکشن", "adventure": "ایڈونچر",
            "mystery": "پراسرار", "historical": "تاریخی", "romantic_comedy": "رومانوی کامیڈی",
            "musical": "موسیقی", "sports": "کھیل", "food": "کھانا",
            "travel": "سفر", "wedding": "شادی", "party": "پارٹی",
            "spiritual": "روحانی", "cartoon": "کارٹون", "fashion": "فیشن",
            "crime": "جرائم", "war": "جنگ", "western": "ویسٹرن",
            "noir": "نوار", "superhero": "سپر ہیرو"
        },
        "hi": {
            "drama": "नाटक", "action": "एक्शन", "romance": "रोमांस",
            "poetry": "कविता", "nature": "प्रकृति", "city": "शहर",
            "fantasy": "काल्पनिक", "horror": "भयानक", "comedy": "हास्य",
            "thriller": "थ्रिलर", "scifi": "साइंस फिक्शन", "adventure": "एडवेंचर",
            "mystery": "रहस्यमय", "historical": "ऐतिहासिक", "romantic_comedy": "रोमांटिक कॉमेडी",
            "musical": "संगीत", "sports": "खेल", "food": "खाना",
            "travel": "यात्रा", "wedding": "शादी", "party": "पार्टी",
            "spiritual": "आध्यात्मिक", "cartoon": "कार्टून", "fashion": "फैशन",
            "crime": "अपराध", "war": "युद्ध", "western": "वेस्टर्न",
            "noir": "नॉयर", "superhero": "सुपर हीरो"
        }
    }
    return names.get(language, names["en"])


def get_common_negatives(language: str = "en") -> List[str]:
    """Get common negative prompts for a language"""
    return COMMON_NEGATIVES.get(language, COMMON_NEGATIVES["en"])


def get_category_negative(category: str, language: str = "en") -> str:
    """Get category-specific negative prompt"""
    cat_data = CATEGORY_NEGATIVES.get(category, {})
    return cat_data.get(language, cat_data.get("en", ""))


def get_weighted_examples(language: str = "en") -> List[str]:
    """Get weighted negative prompt examples"""
    return WEIGHTED_EXAMPLES.get(language, WEIGHTED_EXAMPLES["en"])


def get_negative_templates(language: str = "en") -> List[Dict]:
    """Get pre-built negative prompt templates"""
    return NEGATIVE_TEMPLATES.get(language, NEGATIVE_TEMPLATES["en"])


def get_negative_template_by_id(template_id: str, language: str = "en") -> Optional[Dict]:
    """Get a negative template by ID"""
    templates = get_negative_templates(language)
    for t in templates:
        if t.get("id") == template_id:
            return t
    return None


def build_negative_prompt(
    user_negatives: List[str],
    auto_include: bool = True,
    category: str = None,
    language: str = "en",
    use_weighted: bool = False,
    weight_value: float = -1.5,
    max_terms: int = 20
) -> str:
    """
    Build a complete negative prompt from user inputs and auto-includes.
    
    Parameters:
    - user_negatives (List[str]): User-specified things to avoid
    - auto_include (bool): Add common artifacts automatically [citation:8]
    - category (str): Category for additional negatives
    - language (str): 'en', 'ur', 'hi'
    - use_weighted (bool): Use weighted syntax (text:weight)
    - weight_value (float): Default weight for weighted syntax
    - max_terms (int): Maximum number of terms to include
    
    Returns:
    - str: Complete negative prompt
    """
    
    if not user_negatives:
        user_negatives = []
    
    negatives = []
    
    # Add user negatives (clean and normalize)
    if user_negatives:
        for item in user_negatives:
            cleaned = item.strip().lower()
            if cleaned:
                if use_weighted:
                    negatives.append(f"({cleaned}:{weight_value})")
                else:
                    negatives.append(cleaned)
    
    # Add common artifacts [citation:8][citation:10][citation:11]
    if auto_include:
        common = get_common_negatives(language)
        common_to_add = common[:8]
        if use_weighted:
            for item in common_to_add:
                exists = any(item.lower() in n.lower() for n in negatives)
                if not exists:
                    negatives.append(f"({item}:{weight_value})")
        else:
            for item in common_to_add:
                exists = any(item.lower() in n.lower() for n in negatives)
                if not exists:
                    negatives.append(item)
    
    # Add category-specific negatives
    if category:
        cat_neg = get_category_negative(category, language)
        if cat_neg:
            cat_items = [item.strip() for item in cat_neg.split(",") if item.strip()]
            if use_weighted:
                for item in cat_items:
                    if item:
                        exists = any(item.lower() in n.lower() for n in negatives)
                        if not exists:
                            negatives.append(f"({item}:{weight_value})")
            else:
                for item in cat_items:
                    if item:
                        exists = any(item.lower() in n.lower() for n in negatives)
                        if not exists:
                            negatives.append(item)
    
    # Remove duplicates (case-insensitive) - FIXED
    seen: Set[str] = set()
    unique_negatives = []
    for n in negatives:
        # For weighted, compare the text part
        if use_weighted and '(' in n and ':' in n:
            match = re.match(r'\(\s*([^:]+)\s*:', n)
            key = match.group(1).strip().lower() if match else n.lower()
        else:
            key = n.lower()
        
        if key not in seen:
            seen.add(key)
            unique_negatives.append(n)
    
    # Limit number of terms
    if len(unique_negatives) > max_terms:
        unique_negatives = unique_negatives[:max_terms]
    
    return ", ".join(unique_negatives)


def parse_weighted_negative(negative_text: str) -> List[Tuple[str, float]]:
    """
    Parse weighted negative prompt syntax.
    Format: (text:weight) where weight can be negative or positive.
    Example: "(blurry:-1.5), (watermark:-2.0)" [citation:3]
    
    Returns:
    - List of (text, weight) tuples
    """
    if not negative_text or not negative_text.strip():
        return []
    
    pattern = r'\(\s*([^:]+?)\s*:\s*([-+]?\d*\.?\d+)\s*\)'
    matches = re.findall(pattern, negative_text)
    
    if matches:
        return [(text.strip(), float(weight)) for text, weight in matches]
    
    items = [item.strip() for item in negative_text.split(",") if item.strip()]
    return [(item, -1.0) for item in items]


def enhance_negative_prompt(
    negative_text: str,
    language: str = "en",
    add_common: bool = True,
    category: str = None,
    max_terms: int = 20
) -> str:
    """
    Enhance a negative prompt by adding common artifacts and category-specific negatives.
    """
    if not negative_text or not negative_text.strip():
        return build_negative_prompt(
            user_negatives=[],
            auto_include=add_common,
            category=category,
            language=language,
            max_terms=max_terms
        )
    
    parsed = parse_weighted_negative(negative_text)
    user_negatives = [text for text, _ in parsed]
    
    use_weighted = any(weight != -1.0 for _, weight in parsed)
    weight_value = -1.5
    
    if parsed and all(w == -1.0 for _, w in parsed):
        use_weighted = False
    
    enhanced = build_negative_prompt(
        user_negatives=user_negatives,
        auto_include=add_common,
        category=category,
        language=language,
        use_weighted=use_weighted,
        weight_value=weight_value,
        max_terms=max_terms
    )
    
    return enhanced


def optimize_negative_prompt(negative_text: str, language: str = "en") -> str:
    """
    Optimize a negative prompt by removing redundancy and duplicates.
    """
    if not negative_text or not negative_text.strip():
        return ""
    
    items = [item.strip() for item in negative_text.split(",") if item.strip()]
    
    seen: Set[str] = set()
    unique_items = []
    for item in items:
        key = item.lower()
        if '(' in key and ':' in key:
            match = re.match(r'\(\s*([^:]+)\s*:', key)
            if match:
                key = match.group(1).strip()
        
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    
    optimized = []
    for item in unique_items:
        is_redundant = False
        for other in unique_items:
            if other != item:
                item_clean = re.sub(r'\(\s*([^:]+)\s*:.*?\)', r'\1', item).strip().lower()
                other_clean = re.sub(r'\(\s*([^:]+)\s*:.*?\)', r'\1', other).strip().lower()
                if item_clean and other_clean and item_clean in other_clean:
                    is_redundant = True
                    break
        if not is_redundant:
            optimized.append(item)
    
    return ", ".join(optimized)


def format_negative_for_agnes(negative_prompt: str) -> str:
    """
    Format negative prompt for Agnes API.
    Agnes API expects negative_prompt as a string parameter. [citation:2]
    """
    if not negative_prompt or not negative_prompt.strip():
        return ""
    
    cleaned = ", ".join([n.strip() for n in negative_prompt.split(",") if n.strip()])
    
    return cleaned


def format_negative_for_wan(negative_prompt: str, use_nag: bool = True) -> str:
    """
    Format negative prompt for WAN models.
    WAN models work better with NAG (Negative-Aware Guidance). [citation:3]
    """
    if not negative_prompt or not negative_prompt.strip():
        return ""
    
    if use_nag:
        common = get_common_negatives("en")
        existing = [n.strip() for n in negative_prompt.split(",") if n.strip()]
        all_negatives = existing + common[:5]
        seen = set()
        unique = []
        for n in all_negatives:
            if '(' in n and ':' in n:
                match = re.match(r'\(\s*([^:]+)\s*:', n)
                key = match.group(1).strip().lower() if match else n.lower()
            else:
                key = n.lower()
            
            if key not in seen:
                seen.add(key)
                unique.append(n)
        return ", ".join(unique[:15])
    
    return negative_prompt


def format_negative_for_model(negative_prompt: str, model_type: str = "agnes") -> str:
    """
    Format negative prompt for different model types.
    
    Supported model_types:
    - "agnes": Standard Agnes format [citation:2]
    - "wan": WAN format with NAG [citation:3][citation:8]
    - "default": Generic format
    """
    if not negative_prompt or not negative_prompt.strip():
        return ""
    
    if model_type == "agnes":
        return format_negative_for_agnes(negative_prompt)
    elif model_type == "wan":
        return format_negative_for_wan(negative_prompt, use_nag=True)
    else:
        return ", ".join([n.strip() for n in negative_prompt.split(",") if n.strip()])


def validate_negative_prompt(negative_prompt: str) -> Dict[str, Any]:
    """
    Validate a negative prompt for common issues.
    
    Returns:
    - dict: {"valid", "issues", "suggestions", "warnings"}
    """
    issues = []
    suggestions = []
    warnings = []
    
    if not negative_prompt or not negative_prompt.strip():
        return {
            "valid": True,
            "issues": [],
            "suggestions": [],
            "warnings": ["Negative prompt is empty"],
            "word_count": 0,
            "term_count": 0
        }
    
    positive_words = [
        "beautiful", "good", "nice", "great", "excellent", "perfect",
        "awesome", "amazing", "wonderful", "fantastic", "gorgeous",
        "stunning", "brilliant", "magnificent", "splendid", "terrific",
        "خوبصورت", "اچھا", "عالی", "بہترین", "شاندار", "دلکش",
        "अच्छा", "सुंदर", "उत्कृष्ट", "शानदार", "बढ़िया", "खूबसूरत"
    ]
    
    prompt_lower = negative_prompt.lower()
    for word in positive_words:
        if word.lower() in prompt_lower:
            issues.append(f"Contains positive word: '{word}'")
            suggestions.append(f"Remove '{word}' from negative prompt (use direct negative terms instead)")
    
    if re.search(r'\bno\b|\bnot\b', prompt_lower):
        issues.append("Contains 'no' or 'not'")
        suggestions.append("Use direct terms instead of 'no X'. Example: use 'blurry' not 'no blurry'")
    
    word_count = len(negative_prompt.split())
    if word_count > 50:
        warnings.append(f"Very long negative prompt ({word_count} words)")
        suggestions.append("Consider using only 10-20 specific terms for best results")
    
    items = [item.strip().lower() for item in negative_prompt.split(",") if item.strip()]
    if len(items) != len(set(items)):
        warnings.append("Contains duplicate terms")
        suggestions.append("Remove duplicate terms for cleaner prompt")
    
    if word_count < 3 and negative_prompt.strip():
        warnings.append("Very short negative prompt (less than 3 words)")
        suggestions.append("Consider adding more specific terms to guide the model better")
    
    weighted_matches = re.findall(r'\([^:]+:\d+\.?\d*\)', negative_prompt)
    for match in weighted_matches:
        if not re.match(r'\(\s*[^:]+\s*:\s*-?\d+\.?\d*\s*\)', match):
            issues.append(f"Invalid weighted syntax: '{match}'")
            suggestions.append(f"Use format: (text:weight) e.g., (blurry:-1.5)")
    
    if '(' in negative_prompt and ')' not in negative_prompt:
        issues.append("Unclosed parentheses in weighted syntax")
        suggestions.append("Make sure all '(' have matching ')'")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions,
        "warnings": warnings,
        "word_count": word_count,
        "term_count": len(items) if items else 0
    }


def get_negative_prompt_guidelines(language: str = "en") -> Dict[str, Any]:
    """Get guidelines for writing effective negative prompts [citation:7]"""
    
    guidelines = {
        "en": {
            "title": "How to write effective negative prompts",
            "tips": [
                "Be specific about what you don't want [citation:7]",
                "Use contrasts - describe what you want, then specify the opposite for what you don't [citation:7]",
                "Include context - explaining why something shouldn't be present can help [citation:7]",
                "Avoid ambiguity - make sure your prompt can't be misinterpreted [citation:7]",
                "Use direct terms instead of 'no X' (use 'blurry' instead of 'no blurry') [citation:5]",
                "Common artifacts: blurry, low quality, watermark, text, distorted [citation:8][citation:10]",
                "Use 10-20 specific terms for best results",
                "Weighted syntax can emphasize important negatives: (text:-1.5) [citation:3]",
                "Keep it negative - don't include positive terms",
                "Be specific - generic terms are less effective"
            ],
            "common_mistakes": [
                "Using positive words in negative prompts",
                "Using 'no' or 'not' instead of direct terms [citation:5]",
                "Being too vague or general",
                "Using contradictory terms",
                "Using too many terms (50+)",
                "Including what you want instead of what you don't want"
            ]
        },
        "ur": {
            "title": "مؤثر منفی پروانہ کیسے لکھیں",
            "tips": [
                "مخصوص بنیں کہ آپ کیا نہیں چاہتے [citation:7]",
                "متضاد استعمال کریں [citation:7]",
                "سیاق و سباق شامل کریں [citation:7]",
                "ابہام سے بچیں [citation:7]",
                "براہ راست اصطلاحات استعمال کریں [citation:5]",
                "وزن شدہ نحو استعمال کریں: (text:weight) [citation:3]",
                "منفی رکھیں - مثبت اصطلاحات شامل نہ کریں",
                "مخصوص بنیں - عمومی اصطلاحات کم اثر رکھتی ہیں"
            ],
            "common_mistakes": [
                "مثبت الفاظ کا استعمال",
                "'نہیں' یا 'مت' کا استعمال",
                "بہت مبہم ہونا",
                "متضاد اصطلاحات",
                "بہت زیادہ اصطلاحات (50+)",
                "جو چاہتے ہیں اسے شامل کرنا بجائے جو نہیں چاہتے"
            ]
        },
        "hi": {
            "title": "प्रभावी नेगेटिव प्रॉम्प्ट कैसे लिखें",
            "tips": [
                "विशिष्ट बनें कि आप क्या नहीं चाहते [citation:7]",
                "विरोधाभास का उपयोग करें [citation:7]",
                "संदर्भ शामिल करें [citation:7]",
                "अस्पष्टता से बचें [citation:7]",
                "सीधे शब्दों का उपयोग करें [citation:5]",
                "भारित वाक्यविन्यास का उपयोग करें: (text:weight) [citation:3]",
                "नकारात्मक रखें - सकारात्मक शब्द शामिल न करें",
                "विशिष्ट बनें - सामान्य शब्द कम प्रभावी होते हैं"
            ],
            "common_mistakes": [
                "सकारात्मक शब्दों का उपयोग",
                "'नहीं' या 'न' का उपयोग",
                "बहुत अस्पष्ट होना",
                "विरोधाभासी शब्द",
                "बहुत अधिक शब्द (50+)",
                "जो चाहते हैं उसे शामिल करना बजाय जो नहीं चाहते"
            ]
        }
    }
    
    return guidelines.get(language, guidelines["en"])


# ============================================
# CUSTOM NEGATIVE PROMPT STORAGE (FIXED)
# ============================================

def _load_custom_negatives() -> List[Dict]:
    """Load custom negatives from file"""
    if os.path.exists(CUSTOM_NEGATIVES_FILE):
        try:
            with open(CUSTOM_NEGATIVES_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load custom negatives: {e}")
    return []


def _save_custom_negatives(custom_negatives: List[Dict]) -> bool:
    """Save custom negatives to file"""
    try:
        with open(CUSTOM_NEGATIVES_FILE, "w", encoding='utf-8') as f:
            json.dump(custom_negatives, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save custom negatives: {e}")
        return False


def save_custom_negative(
    name: str,
    prompt: str,
    category: str = None,
    language: str = "en",
    tags: List[str] = None
) -> Dict:
    """Save a custom negative prompt"""
    
    if not name or not prompt:
        raise ValueError("Name and prompt are required")
    
    custom_negatives = _load_custom_negatives()
    
    new_negative = {
        "id": f"custom_neg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(name.encode()).hexdigest()[:6]}",
        "name": name,
        "prompt": prompt,
        "category": category,
        "language": language,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
        "usage_count": 0,
        "last_used": None
    }
    
    for i, existing in enumerate(custom_negatives):
        if existing.get("name") == name and existing.get("language") == language:
            custom_negatives[i] = new_negative
            _save_custom_negatives(custom_negatives)
            return new_negative
    
    custom_negatives.append(new_negative)
    _save_custom_negatives(custom_negatives)
    
    return new_negative


def get_custom_negatives(language: str = None) -> List[Dict]:
    """Get custom negatives, optionally filtered by language"""
    custom_negatives = _load_custom_negatives()
    
    if language:
        return [c for c in custom_negatives if c.get("language") == language]
    
    return custom_negatives


def delete_custom_negative(negative_id: str) -> bool:
    """Delete a custom negative prompt"""
    custom_negatives = _load_custom_negatives()
    original_count = len(custom_negatives)
    custom_negatives = [c for c in custom_negatives if c.get("id") != negative_id]
    
    if len(custom_negatives) < original_count:
        return _save_custom_negatives(custom_negatives)
    
    return False


# ============================================
# USAGE TRACKING (FIXED)
# ============================================

def _load_usage_stats() -> Dict:
    """Load usage statistics from file"""
    global _USAGE_STATS_CACHE
    
    if _USAGE_STATS_CACHE is not None:
        return _USAGE_STATS_CACHE
    
    if os.path.exists(USAGE_STATS_FILE):
        try:
            with open(USAGE_STATS_FILE, "r", encoding='utf-8') as f:
                _USAGE_STATS_CACHE = json.load(f)
                return _USAGE_STATS_CACHE
        except Exception as e:
            logger.warning(f"Failed to load usage stats: {e}")
    
    _USAGE_STATS_CACHE = {"usage_count": {}, "last_used": {}}
    return _USAGE_STATS_CACHE


def _save_usage_stats(stats: Dict) -> None:
    """Save usage statistics to file"""
    try:
        with open(USAGE_STATS_FILE, "w", encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save usage stats: {e}")


def track_negative_usage(negative_prompt: str, language: str = "en") -> None:
    """Track usage of a negative prompt"""
    if not negative_prompt or not negative_prompt.strip():
        return
    
    stats = _load_usage_stats()
    
    prompt_key = hashlib.md5(negative_prompt.encode()).hexdigest()
    
    stats["usage_count"][prompt_key] = stats["usage_count"].get(prompt_key, 0) + 1
    
    if "prompts" not in stats:
        stats["prompts"] = {}
    stats["prompts"][prompt_key] = {
        "text": negative_prompt,
        "language": language,
        "last_used": datetime.now().isoformat()
    }
    
    _save_usage_stats(stats)


def get_popular_negatives(limit: int = 5) -> List[Dict]:
    """Get most used negative prompts"""
    stats = _load_usage_stats()
    usage_counts = stats.get("usage_count", {})
    prompts = stats.get("prompts", {})
    
    results = []
    for key, count in usage_counts.items():
        if key in prompts:
            results.append({
                "prompt": prompts[key].get("text", ""),
                "language": prompts[key].get("language", "en"),
                "usage_count": count,
                "last_used": prompts[key].get("last_used")
            })
    
    results.sort(key=lambda x: x.get("usage_count", 0), reverse=True)
    
    return results[:limit]


# ============================================
# UI RENDER FUNCTION (ENHANCED WITH VOICE)
# ============================================

def render_feature_11():
    """Render Negative Prompting UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 🚫 Negative Prompting")
    st.markdown("*Apne video mein kya nahi hona chahiye, yeh batayein*")
    
    # Language selector
    language = st.selectbox(
        "Language / زبان",
        ["English", "Urdu", "Hindi"],
        index=0,
        key="neg_lang"
    )
    
    lang_map = {"English": "en", "Urdu": "ur", "Hindi": "hi"}
    lang_code = lang_map.get(language, "en")
    
    # Voice input option
    use_voice = st.checkbox("🎤 Use Voice Input (Speak your negative prompts)", value=False, key="neg_voice_input")
    
    if use_voice:
        voice_lang = st.selectbox(
            "Voice Recognition Language",
            ["en-US (English)", "ur-PK (Urdu)", "hi-IN (Hindi)"],
            index=0,
            key="neg_voice_lang"
        )
        voice_lang_code = {"en-US (English)": "en-US", "ur-PK (Urdu)": "ur-PK", "hi-IN (Hindi)": "hi-IN"}[voice_lang]
        st.info("🎤 Click 'Build Negative Prompt' and speak clearly into your microphone")
    
    # Guidelines
    with st.expander("📖 Guidelines for Effective Negative Prompts"):
        guidelines = get_negative_prompt_guidelines(lang_code)
        st.markdown(f"### {guidelines.get('title', 'Guidelines')}")
        
        st.markdown("**Tips:**")
        for tip in guidelines.get("tips", []):
            st.markdown(f"• {tip}")
        
        st.markdown("**Common Mistakes to Avoid:**")
        for mistake in guidelines.get("common_mistakes", []):
            st.markdown(f"• {mistake}")
    
    # Templates
    with st.expander("📋 Pre-built Templates"):
        templates = get_negative_templates(lang_code)
        for t in templates:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{t.get('name')}**")
                st.caption(t.get('description', ''))
                st.code(t.get('prompt', ''), language="text")
            with col2:
                if st.button(f"📝 Use", key=f"neg_use_{t.get('id')}"):
                    st.session_state["neg_prompt_input"] = t.get('prompt')
                    st.success("✅ Template loaded!")
            st.divider()
    
    # Category selection - 25+ categories
    categories = get_all_categories()
    category_names = get_category_names(lang_code)
    
    st.markdown("### 📂 Category-Based Negatives")
    category_options = ["None"] + [category_names.get(c, c) for c in categories]
    
    selected_category_display = st.selectbox(
        "Category / زمرہ",
        category_options,
        key="neg_category"
    )
    
    if selected_category_display != "None":
        category_key = None
        for key, value in category_names.items():
            if value == selected_category_display:
                category_key = key
                break
    else:
        category_key = None
    
    # Show category info
    if category_key:
        cat_neg = get_category_negative(category_key, lang_code)
        if cat_neg:
            st.caption(f"📝 Category negative: {cat_neg[:100]}...")
    
    # Negative prompt input
    st.markdown("### 📝 Negative Prompt")
    st.caption("Jin cheezo ko video mein nahi dekhna chahte, unhein likhein")
    
    default_prompt = st.session_state.get("neg_prompt_input", "")
    
    if use_voice:
        neg_prompt = st.text_area(
            "Negative Prompt",
            value=default_prompt,
            placeholder="🎤 Speak your negative prompts...",
            height=120,
            key="neg_prompt_input",
            disabled=True
        )
        st.caption("🎤 Your spoken text will appear here after recognition")
    else:
        neg_prompt = st.text_area(
            "Negative Prompt",
            value=default_prompt,
            placeholder="e.g., blurry, low quality, watermark, distorted, bad anatomy\nExample: (blurry:-1.5), (low quality:-2.0)",
            height=120,
            key="neg_prompt_input"
        )
    
    # Options
    col1, col2, col3 = st.columns(3)
    with col1:
        auto_include = st.checkbox("🔧 Auto-include common artifacts", value=True)
        if auto_include:
            st.caption("Adds: blurry, low quality, watermark, etc.")
    
    with col2:
        use_weighted = st.checkbox("⚖️ Use weighted syntax", value=False)
        if use_weighted:
            weight_value = st.slider("Default weight", -3.0, -0.5, -1.5, 0.1)
    
    with col3:
        max_terms = st.slider("Max terms", 5, 30, 20, 5)
    
    # Validation and enhancement
    if neg_prompt:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Validate Prompt", key="validate_neg"):
                validation = validate_negative_prompt(neg_prompt)
                
                if validation["valid"]:
                    st.success("✅ Prompt looks good!")
                else:
                    st.warning("⚠️ Issues found:")
                    for issue in validation["issues"]:
                        st.write(f"• {issue}")
                
                if validation["suggestions"]:
                    st.info("💡 Suggestions:")
                    for suggestion in validation["suggestions"]:
                        st.write(f"• {suggestion}")
                
                if validation["warnings"]:
                    st.info("⚠️ Warnings:")
                    for warning in validation["warnings"]:
                        st.write(f"• {warning}")
        
        with col2:
            if st.button("✨ Enhance Prompt", key="enhance_neg"):
                enhanced = enhance_negative_prompt(
                    negative_text=neg_prompt,
                    language=lang_code,
                    add_common=auto_include,
                    category=category_key,
                    max_terms=max_terms
                )
                st.session_state["neg_prompt_input"] = enhanced
                st.success("✅ Prompt enhanced!")
                st.rerun()
        
        # Optimize
        if st.button("🔄 Optimize (Remove Duplicates)", key="optimize_neg"):
            optimized = optimize_negative_prompt(neg_prompt, lang_code)
            st.session_state["neg_prompt_input"] = optimized
            st.success("✅ Prompt optimized!")
            st.rerun()
    
    # Format for different models
    if neg_prompt:
        st.markdown("### 🎯 Format for Models")
        
        col1, col2 = st.columns(2)
        with col1:
            model_type = st.selectbox(
                "Model Type",
                ["agnes", "wan", "default"],
                index=0,
                key="neg_model"
            )
        
        with col2:
            if st.button("📋 Format Prompt", key="format_neg"):
                formatted = format_negative_for_model(neg_prompt, model_type)
                st.code(formatted, language="text")
                
                if use_weighted or '(' in neg_prompt:
                    parsed = parse_weighted_negative(neg_prompt)
                    if parsed:
                        st.caption("Parsed weighted terms:")
                        for text, weight in parsed:
                            st.write(f"• {text}: {weight}")
    
    # Voice input button
    if use_voice:
        if st.button("🎤 Speak Negative Prompts", key="speak_neg"):
            st.info("🎤 Listening... Speak your negative prompts clearly.")
            speech_result = speech_to_text(language=voice_lang_code)
            if speech_result["success"]:
                current_prompt = st.session_state.get("neg_prompt_input", "")
                if current_prompt:
                    new_prompt = f"{current_prompt}, {speech_result['text']}"
                else:
                    new_prompt = speech_result['text']
                st.session_state["neg_prompt_input"] = new_prompt
                st.success(f"✅ Voice recognized: {speech_result['text']}")
                st.rerun()
            else:
                st.error(f"❌ {speech_result['message']}")
    
    # Save custom
    st.markdown("---")
    st.markdown("### 💾 Save Custom Negative Prompt")
    
    col1, col2 = st.columns(2)
    with col1:
        custom_name = st.text_input("Name", placeholder="My Custom Negative", key="neg_custom_name")
        custom_category = st.selectbox(
            "Category (optional)",
            ["None"] + categories,
            key="neg_custom_cat"
        )
    with col2:
        custom_tags = st.text_input("Tags (comma separated)", placeholder="quality, human, general", key="neg_custom_tags")
        custom_lang = st.selectbox(
            "Language",
            ["en", "ur", "hi"],
            index=0,
            key="neg_custom_lang"
        )
    
    if st.button("💾 Save Custom Negative", key="save_custom_neg"):
        if not custom_name or not neg_prompt:
            st.error("❌ Name and prompt are required")
        else:
            try:
                tags_list = [t.strip() for t in custom_tags.split(",") if t.strip()]
                cat = custom_category if custom_category != "None" else None
                
                result = save_custom_negative(
                    name=custom_name,
                    prompt=neg_prompt,
                    category=cat,
                    language=custom_lang,
                    tags=tags_list
                )
                st.success(f"✅ Saved: {result.get('name')}")
            except Exception as e:
                st.error(f"❌ Failed to save: {e}")
    
    # Show custom negatives
    custom_negatives = get_custom_negatives(lang_code)
    if custom_negatives:
        st.markdown("### 📂 Custom Negatives")
        for c in custom_negatives[:5]:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{c.get('name')}**")
                st.code(c.get('prompt', '')[:100] + "...", language="text")
            with col2:
                if st.button(f"🗑️ Delete", key=f"del_neg_{c.get('id')}"):
                    if delete_custom_negative(c.get('id')):
                        st.success("✅ Deleted!")
                        st.rerun()
            st.divider()
    
    # Popular negatives
    st.markdown("---")
    st.markdown("### 🔥 Popular Negative Prompts")
    popular = get_popular_negatives(5)
    if popular:
        for p in popular:
            st.markdown(f"**Used {p.get('usage_count', 0)} times**")
            st.code(p.get('prompt', ''), language="text")
            st.divider()
    else:
        st.info("ℹ️ No usage data yet. Start using negative prompts to see popular ones here!")
    
    # Common artifacts
    with st.expander("🔧 Common Artifacts (Auto-included)"):
        common = get_common_negatives(lang_code)
        cols = st.columns(4)
        for i, item in enumerate(common):
            cols[i % 4].write(f"• {item}")


# ============================================
# TEST FUNCTION (FIXED)
# ============================================

def test():
    """Test the negative prompting feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_11_negative_prompting.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    # Test 1: Get common negatives
    print("\n📝 Test 1: Common negatives")
    common = get_common_negatives("en")
    print(f"  Common negatives: {len(common)}")
    print(f"  First 5: {common[:5]}")
    
    # Test 2: Categories
    print("\n📝 Test 2: Categories")
    categories = get_all_categories()
    print(f"  Total categories: {len(categories)}")
    print(f"  First 5: {categories[:5]}")
    
    # Test 3: Category negatives
    print("\n📝 Test 3: Category negatives")
    for category in ["drama", "action", "romance", "scifi"]:
        neg = get_category_negative(category, "en")
        print(f"  {category}: {neg[:50]}...")
    
    # Test 4: Build negative prompt
    print("\n📝 Test 4: Build negative prompt")
    result = build_negative_prompt(
        user_negatives=["blurry", "low quality"],
        auto_include=True,
        category="drama",
        language="en",
        use_weighted=True,
        max_terms=10
    )
    print(f"  Built prompt: {result}")
    
    # Test 5: Voice input
    if SPEECH_RECOGNITION_AVAILABLE:
        print("\n🎤 Test 5: Voice input (if microphone available)")
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
# END OF feature_11_negative_prompting.py (ULTIMATE)
# ============================================
