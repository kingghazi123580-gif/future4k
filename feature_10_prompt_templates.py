# ============================================
# FEATURE 10: PROMPT TEMPLATES (ULTIMATE - 100+ TEMPLATES, 25+ CATEGORIES)
# Filename: feature_10_prompt_templates.py
# ============================================
# FEATURES:
# 1. ✅ 100+ ready-made prompt templates across 25+ categories
# 2. ✅ Support for Urdu, Hindi, and English languages
# 3. ✅ Template categories: drama, action, romance, poetry, nature, city, fantasy, horror, comedy, thriller,
#    sci-fi, adventure, mystery, historical, romantic comedy, musical, sports, food, travel, wedding,
#    party, spiritual, cartoon, fashion, crime, war, western, noir, superhero, mythology, etc.
# 4. ✅ Template variables: {character}, {action}, {setting}, {emotion}, {time}, {object}
# 5. ✅ Search templates by category, language, keyword
# 6. ✅ Get random template with usage tracking
# 7. ✅ Save custom templates
# 8. ✅ Template rating system (1-5 stars)
# 9. ✅ Most used templates tracking
# 10. ✅ Template usage analytics
#
# CHANGE LOG (bug fix — previously undefined functions):
# The original UI function (render_feature_10) called seven functions that
# were referenced but never implemented anywhere in this file:
#   track_template_usage, save_custom_template, get_custom_templates,
#   delete_custom_template, get_template_rating, get_template_usage_stats,
#   get_popular_templates
# Calling render_feature_10() as-is would have crashed the moment the
# "Popular Templates" section (or any Use/Rate/Save button) ran. All seven
# are now implemented below using simple JSON files in TEMPLATES_DIR
# (custom_templates.json, usage_stats.json, ratings.json — the paths were
# already declared at the top of this file but never actually used).
# ============================================

import os
import sys
import json
import random
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any
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
# DIRECTORY SETUP
# ============================================

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
CUSTOM_TEMPLATES_FILE = os.path.join(TEMPLATES_DIR, "custom_templates.json")
USAGE_STATS_FILE = os.path.join(TEMPLATES_DIR, "usage_stats.json")
RATINGS_FILE = os.path.join(TEMPLATES_DIR, "ratings.json")

os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Cache for performance
_TEMPLATE_CACHE = {}
_CUSTOM_TEMPLATE_CACHE = None
_USAGE_STATS_CACHE = None
_RATINGS_CACHE = None

# ============================================
# CATEGORY DEFINITIONS
# ============================================

CATEGORIES = {
    "drama": {"name": "Drama", "emoji": "🎭", "description": "Emotional and intense storytelling"},
    "action": {"name": "Action", "emoji": "💥", "description": "Fast-paced, high-energy scenes"},
    "romance": {"name": "Romance", "emoji": "❤️", "description": "Love and relationship stories"},
    "poetry": {"name": "Poetry", "emoji": "📝", "description": "Artistic and poetic expressions"},
    "nature": {"name": "Nature", "emoji": "🌿", "description": "Scenic and natural landscapes"},
    "city": {"name": "City", "emoji": "🏙️", "description": "Urban and metropolitan scenes"},
    "fantasy": {"name": "Fantasy", "emoji": "🐉", "description": "Magical and mythical worlds"},
    "horror": {"name": "Horror", "emoji": "👻", "description": "Scary and terrifying scenes"},
    "comedy": {"name": "Comedy", "emoji": "😂", "description": "Funny and humorous moments"},
    "thriller": {"name": "Thriller", "emoji": "🔪", "description": "Suspenseful and gripping tales"},
    "scifi": {"name": "Sci-Fi", "emoji": "🚀", "description": "Futuristic and technological worlds"},
    "adventure": {"name": "Adventure", "emoji": "🗺️", "description": "Exciting journeys and quests"},
    "mystery": {"name": "Mystery", "emoji": "🔍", "description": "Puzzles and investigations"},
    "historical": {"name": "Historical", "emoji": "🏛️", "description": "Stories from the past"},
    "romantic_comedy": {"name": "Romantic Comedy", "emoji": "💕", "description": "Love and laughter combined"},
    "musical": {"name": "Musical", "emoji": "🎵", "description": "Songs and rhythmic stories"},
    "sports": {"name": "Sports", "emoji": "⚽", "description": "Athletic competitions and triumphs"},
    "food": {"name": "Food", "emoji": "🍜", "description": "Culinary and gastronomic experiences"},
    "travel": {"name": "Travel", "emoji": "✈️", "description": "Journeys and discoveries"},
    "wedding": {"name": "Wedding", "emoji": "💒", "description": "Celebrations of love"},
    "party": {"name": "Party", "emoji": "🎉", "description": "Festivities and celebrations"},
    "spiritual": {"name": "Spiritual", "emoji": "🕊️", "description": "Soulful and meditative stories"},
    "cartoon": {"name": "Cartoon", "emoji": "🎨", "description": "Animated and colorful worlds"},
    "fashion": {"name": "Fashion", "emoji": "👗", "description": "Style and design stories"},
    "crime": {"name": "Crime", "emoji": "🚔", "description": "Law, order, and criminal tales"},
    "war": {"name": "War", "emoji": "⚔️", "description": "Conflict and military stories"},
    "western": {"name": "Western", "emoji": "🤠", "description": "Cowboys and frontier tales"},
    "noir": {"name": "Noir", "emoji": "🕵️", "description": "Dark and mysterious atmosphere"},
    "superhero": {"name": "Superhero", "emoji": "🦸", "description": "Heroes with extraordinary abilities"},
    "mythology": {"name": "Mythology", "emoji": "🏛️", "description": "Gods, legends, and ancient tales"},
    "epic": {"name": "Epic", "emoji": "⚡", "description": "Grand and heroic narratives"},
    "steampunk": {"name": "Steampunk", "emoji": "⚙️", "description": "Victorian-era futuristic worlds"},
    "dystopian": {"name": "Dystopian", "emoji": "🌆", "description": "Dark and oppressive futures"},
    "post_apocalyptic": {"name": "Post-Apocalyptic", "emoji": "☢️", "description": "Worlds after catastrophe"},
    "coming_of_age": {"name": "Coming of Age", "emoji": "🌱", "description": "Growth and self-discovery stories"}
}

# ============================================
# URDU TEMPLATES (70+)
# ============================================

URDU_TEMPLATES = [
    # Drama (6)
    {
        "id": "ur_drama_001",
        "name": "ڈرامائی مکالمہ",
        "category": "drama",
        "template": "ایک ڈرامائی منظر جس میں {character} {action} کر رہا ہے، {emotion} جذبات کے ساتھ، {setting} کے پس منظر میں",
        "variables": ["character", "action", "emotion", "setting"],
        "language": "ur",
        "tags": ["dramatic", "dialogue", "emotional"]
    },
    {
        "id": "ur_drama_002",
        "name": "خاندانی ڈرامہ",
        "category": "drama",
        "template": "ایک خاندانی ڈرامہ جس میں {character} اور {character2} کے درمیان {emotion} گفتگو ہو رہی ہے، {setting} میں",
        "variables": ["character", "character2", "emotion", "setting"],
        "language": "ur",
        "tags": ["family", "emotional", "dialogue"]
    },
    {
        "id": "ur_drama_003",
        "name": "جذباتی منظر",
        "category": "drama",
        "template": "ایک جذباتی منظر جس میں {character} {emotion} کا اظہار کر رہا ہے، {setting} کے خوبصورت ماحول میں",
        "variables": ["character", "emotion", "setting"],
        "language": "ur",
        "tags": ["emotional", "expressive", "beautiful"]
    },
    {
        "id": "ur_drama_004",
        "name": "تاریخی ڈرامہ",
        "category": "drama",
        "template": "ایک تاریخی ڈرامائی منظر جس میں {character} {time} کے دور میں {action} کر رہا ہے",
        "variables": ["character", "time", "action"],
        "language": "ur",
        "tags": ["historical", "dramatic", "period"]
    },
    {
        "id": "ur_drama_005",
        "name": "سماجی ڈرامہ",
        "category": "drama",
        "template": "ایک سماجی ڈرامہ جس میں {character} معاشرے کے {emotion} مسائل کا سامنا کر رہا ہے",
        "variables": ["character", "emotion"],
        "language": "ur",
        "tags": ["social", "drama", "issues"]
    },
    {
        "id": "ur_drama_006",
        "name": "سیاسی ڈرامہ",
        "category": "drama",
        "template": "ایک سیاسی ڈرامہ جس میں {character} {setting} میں {action} کر رہا ہے، {emotion} جذبات کے ساتھ",
        "variables": ["character", "setting", "action", "emotion"],
        "language": "ur",
        "tags": ["political", "dramatic", "power"]
    },
    # Action (6)
    {
        "id": "ur_action_001",
        "name": "ایکشن منظر",
        "category": "action",
        "template": "ایک تیز رفتار ایکشن منظر جس میں {character} {action} کر رہا ہے، {setting} میں، {emotion} جذبے کے ساتھ",
        "variables": ["character", "action", "setting", "emotion"],
        "language": "ur",
        "tags": ["action", "fast", "energetic"]
    },
    {
        "id": "ur_action_002",
        "name": "کار چیز منظر",
        "category": "action",
        "template": "ایک دلکش کار چیز منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["car", "chase", "action"]
    },
    {
        "id": "ur_action_003",
        "name": "جنگی منظر",
        "category": "action",
        "template": "ایک پرجوش جنگی منظر جس میں {character} اور {character2} کے درمیان {action} ہو رہا ہے",
        "variables": ["character", "character2", "action"],
        "language": "ur",
        "tags": ["war", "battle", "intense"]
    },
    {
        "id": "ur_action_004",
        "name": "مارشل آرٹس",
        "category": "action",
        "template": "ایک مارشل آرٹس کا منظر جس میں {character} {action} کر رہا ہے، {setting} میں",
        "variables": ["character", "action", "setting"],
        "language": "ur",
        "tags": ["martial arts", "fight", "action"]
    },
    {
        "id": "ur_action_005",
        "name": "ایڈرینالین رش",
        "category": "action",
        "template": "ایک ایڈرینالین سے بھرپور منظر جس میں {character} {action} کر رہا ہے، {emotion} کے ساتھ",
        "variables": ["character", "action", "emotion"],
        "language": "ur",
        "tags": ["adrenaline", "thrill", "action"]
    },
    {
        "id": "ur_action_006",
        "name": "اسٹنٹ منظر",
        "category": "action",
        "template": "ایک خطرناک اسٹنٹ منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["stunt", "danger", "action"]
    },
    # Romance (6)
    {
        "id": "ur_romance_001",
        "name": "رومانوی ملاقات",
        "category": "romance",
        "template": "ایک رومانوی منظر جس میں {character} اور {character2} {setting} میں مل رہے ہیں، {emotion} ماحول میں",
        "variables": ["character", "character2", "setting", "emotion"],
        "language": "ur",
        "tags": ["romance", "meeting", "love"]
    },
    {
        "id": "ur_romance_002",
        "name": "محبت کا اظہار",
        "category": "romance",
        "template": "ایک منظر جس میں {character} {character2} سے محبت کا اظہار کر رہا ہے، {setting} کے {time} میں",
        "variables": ["character", "character2", "setting", "time"],
        "language": "ur",
        "tags": ["love", "confession", "romance"]
    },
    {
        "id": "ur_romance_003",
        "name": "شادی کا منظر",
        "category": "romance",
        "template": "ایک شادی کا خوبصورت منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
        "variables": ["character", "character2", "setting", "action"],
        "language": "ur",
        "tags": ["wedding", "romance", "beautiful"]
    },
    {
        "id": "ur_romance_004",
        "name": "عاشقانہ نظم",
        "category": "romance",
        "template": "ایک عاشقانہ منظر جس میں {character} {character2} کے لیے {emotion} نظم پڑھ رہا ہے",
        "variables": ["character", "character2", "emotion"],
        "language": "ur",
        "tags": ["poetry", "romance", "love"]
    },
    {
        "id": "ur_romance_005",
        "name": "دل ٹوٹنا",
        "category": "romance",
        "template": "ایک جذباتی منظر جس میں {character} کا دل {character2} کی وجہ سے {emotion} ہے",
        "variables": ["character", "character2", "emotion"],
        "language": "ur",
        "tags": ["heartbreak", "emotional", "romance"]
    },
    {
        "id": "ur_romance_006",
        "name": "پہلی نظر کی محبت",
        "category": "romance",
        "template": "ایک رومانوی منظر جس میں {character} کو {character2} سے پہلی نظر میں محبت ہو جاتی ہے، {setting} میں",
        "variables": ["character", "character2", "setting"],
        "language": "ur",
        "tags": ["love at first sight", "romance", "magical"]
    },
    # Poetry (5)
    {
        "id": "ur_poetry_001",
        "name": "شاعرانہ منظر",
        "category": "poetry",
        "template": "ایک شاعرانہ منظر، {setting} کے پس منظر میں {character} {action} کر رہا ہے",
        "variables": ["setting", "character", "action"],
        "language": "ur",
        "tags": ["poetic", "beautiful", "artistic"]
    },
    {
        "id": "ur_poetry_002",
        "name": "غزل کا منظر",
        "category": "poetry",
        "template": "ایک غزل کا منظر جس میں {character} {emotion} الفاظ میں {action} کر رہا ہے",
        "variables": ["character", "emotion", "action"],
        "language": "ur",
        "tags": ["ghazal", "poetic", "emotional"]
    },
    {
        "id": "ur_poetry_003",
        "name": "نظم کا منظر",
        "category": "poetry",
        "template": "ایک نظم کا منظر، {setting} میں {character} {emotion} کا اظہار کر رہا ہے",
        "variables": ["setting", "character", "emotion"],
        "language": "ur",
        "tags": ["poem", "expressive", "artistic"]
    },
    {
        "id": "ur_poetry_004",
        "name": "تخیلاتی منظر",
        "category": "poetry",
        "template": "ایک تخیلاتی شاعرانہ منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["imaginative", "poetic", "creative"]
    },
    {
        "id": "ur_poetry_005",
        "name": "موسیقی کا منظر",
        "category": "poetry",
        "template": "ایک موسیقی سے بھرپور شاعرانہ منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["music", "poetic", "melodic"]
    },
    # Nature (5)
    {
        "id": "ur_nature_001",
        "name": "فطرت کا منظر",
        "category": "nature",
        "template": "ایک خوبصورت فطرت کا منظر جس میں {setting} کی {emotion} خوبصورتی دکھائی دے رہی ہے",
        "variables": ["setting", "emotion"],
        "language": "ur",
        "tags": ["nature", "beautiful", "scenic"]
    },
    {
        "id": "ur_nature_002",
        "name": "پہاڑی منظر",
        "category": "nature",
        "template": "ایک پہاڑی منظر جس میں {character} {action} کر رہا ہے، {setting} کی بلندیوں پر",
        "variables": ["character", "action", "setting"],
        "language": "ur",
        "tags": ["mountains", "nature", "adventure"]
    },
    {
        "id": "ur_nature_003",
        "name": "سمندر کا منظر",
        "category": "nature",
        "template": "ایک سمندر کا پرسکون منظر جس میں {character} {setting} کے کنارے {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["ocean", "calm", "nature"]
    },
    {
        "id": "ur_nature_004",
        "name": "غروب آفتاب",
        "category": "nature",
        "template": "ایک غروب آفتاب کا منظر جس میں {setting} {emotion} رنگوں میں ڈوبا ہوا ہے",
        "variables": ["setting", "emotion"],
        "language": "ur",
        "tags": ["sunset", "beautiful", "nature"]
    },
    {
        "id": "ur_nature_005",
        "name": "بارش کا منظر",
        "category": "nature",
        "template": "ایک بارش کا منظر جس میں {character} {setting} میں {emotion} ماحول میں {action} کر رہا ہے",
        "variables": ["character", "setting", "emotion", "action"],
        "language": "ur",
        "tags": ["rain", "romantic", "nature"]
    },
    # City (5)
    {
        "id": "ur_city_001",
        "name": "شہر کا منظر",
        "category": "city",
        "template": "ایک شہر کا رات کا منظر جس میں {character} {setting} کی گلیوں میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["city", "night", "urban"]
    },
    {
        "id": "ur_city_002",
        "name": "بازار کا منظر",
        "category": "city",
        "template": "ایک بازار کا ہنگامہ خیز منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["market", "bustling", "city"]
    },
    {
        "id": "ur_city_003",
        "name": "نیون لائٹس",
        "category": "city",
        "template": "ایک نیون لائٹس والا شہری منظر جس میں {character} {emotion} ماحول میں {action} کر رہا ہے",
        "variables": ["character", "emotion", "action"],
        "language": "ur",
        "tags": ["neon lights", "city", "night"]
    },
    {
        "id": "ur_city_004",
        "name": "شہری زندگی",
        "category": "city",
        "template": "ایک شہری زندگی کا منظر جس میں {character} {setting} کی مصروفیت میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["urban life", "busy", "city"]
    },
    {
        "id": "ur_city_005",
        "name": "چھت کا منظر",
        "category": "city",
        "template": "ایک چھت کا منظر جس میں {character} {setting} کے شہر کو {emotion} نظروں سے دیکھ رہا ہے",
        "variables": ["character", "setting", "emotion"],
        "language": "ur",
        "tags": ["rooftop", "view", "city"]
    },
    # Fantasy (5)
    {
        "id": "ur_fantasy_001",
        "name": "خیالی منظر",
        "category": "fantasy",
        "template": "ایک خیالی منظر جس میں {character} {setting} میں {action} کر رہا ہے، {emotion} جادو کے ساتھ",
        "variables": ["character", "setting", "action", "emotion"],
        "language": "ur",
        "tags": ["fantasy", "magical", "imaginative"]
    },
    {
        "id": "ur_fantasy_002",
        "name": "جادو کا منظر",
        "category": "fantasy",
        "template": "ایک جادو کا منظر جس میں {character} {action} کر رہا ہے، {setting} کے پراسرار ماحول میں",
        "variables": ["character", "action", "setting"],
        "language": "ur",
        "tags": ["magic", "mysterious", "fantasy"]
    },
    {
        "id": "ur_fantasy_003",
        "name": "جنوں کا منظر",
        "category": "fantasy",
        "template": "ایک جنوں کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["jinn", "fantasy", "mystical"]
    },
    {
        "id": "ur_fantasy_004",
        "name": "پراسرار منظر",
        "category": "fantasy",
        "template": "ایک پراسرار منظر جس میں {character} {setting} کے {emotion} راز کو {action} کر رہا ہے",
        "variables": ["character", "setting", "emotion", "action"],
        "language": "ur",
        "tags": ["mysterious", "secret", "fantasy"]
    },
    {
        "id": "ur_fantasy_005",
        "name": "ڈریگن کا منظر",
        "category": "fantasy",
        "template": "ایک ڈریگن کا منظر جس میں {character} {setting} میں {action} کر رہا ہے، {emotion} کے ساتھ",
        "variables": ["character", "setting", "action", "emotion"],
        "language": "ur",
        "tags": ["dragon", "epic", "fantasy"]
    },
    # Horror (3)
    {
        "id": "ur_horror_001",
        "name": "خوفناک منظر",
        "category": "horror",
        "template": "ایک خوفناک منظر جس میں {character} {setting} میں {action} کر رہا ہے، {emotion} خوف کے ساتھ",
        "variables": ["character", "setting", "action", "emotion"],
        "language": "ur",
        "tags": ["horror", "scary", "fear"]
    },
    {
        "id": "ur_horror_002",
        "name": "بھوت کا منظر",
        "category": "horror",
        "template": "ایک بھوت کا خوفناک منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["ghost", "horror", "supernatural"]
    },
    {
        "id": "ur_horror_003",
        "name": "پراسرار گھر",
        "category": "horror",
        "template": "ایک پراسرار گھر کا منظر جس میں {character} {setting} میں {emotion} محسوس کر رہا ہے",
        "variables": ["character", "setting", "emotion"],
        "language": "ur",
        "tags": ["haunted house", "horror", "mysterious"]
    },
    # Comedy (3)
    {
        "id": "ur_comedy_001",
        "name": "مزاحیہ منظر",
        "category": "comedy",
        "template": "ایک مزاحیہ منظر جس میں {character} {setting} میں {action} کر رہا ہے، {emotion} کے ساتھ",
        "variables": ["character", "setting", "action", "emotion"],
        "language": "ur",
        "tags": ["comedy", "funny", "entertaining"]
    },
    {
        "id": "ur_comedy_002",
        "name": "طنزیہ منظر",
        "category": "comedy",
        "template": "ایک طنزیہ منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
        "variables": ["character", "character2", "setting", "action"],
        "language": "ur",
        "tags": ["satire", "comedy", "witty"]
    },
    {
        "id": "ur_comedy_003",
        "name": "مضحکہ خیز صورتحال",
        "category": "comedy",
        "template": "ایک مضحکہ خیز صورتحال جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["hilarious", "comedy", "funny"]
    },
    # Thriller (3)
    {
        "id": "ur_thriller_001",
        "name": "سنسنی خیز منظر",
        "category": "thriller",
        "template": "ایک سنسنی خیز منظر جس میں {character} {setting} میں {action} کر رہا ہے، {emotion} کے ساتھ",
        "variables": ["character", "setting", "action", "emotion"],
        "language": "ur",
        "tags": ["thriller", "suspense", "intense"]
    },
    {
        "id": "ur_thriller_002",
        "name": "خطرناک کھیل",
        "category": "thriller",
        "template": "ایک خطرناک کھیل کا منظر جس میں {character} اور {character2} {setting} میں شامل ہیں",
        "variables": ["character", "character2", "setting"],
        "language": "ur",
        "tags": ["dangerous game", "thriller", "suspense"]
    },
    {
        "id": "ur_thriller_003",
        "name": "تعاقب کا منظر",
        "category": "thriller",
        "template": "ایک تعاقب کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["chase", "thriller", "suspense"]
    },
    # Sci-Fi (3)
    {
        "id": "ur_scifi_001",
        "name": "سائنس فکشن منظر",
        "category": "scifi",
        "template": "ایک مستقبل کا سائنس فکشن منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["scifi", "future", "technology"]
    },
    {
        "id": "ur_scifi_002",
        "name": "روبوٹ کا منظر",
        "category": "scifi",
        "template": "ایک روبوٹ کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["robot", "scifi", "future"]
    },
    {
        "id": "ur_scifi_003",
        "name": "خلائی منظر",
        "category": "scifi",
        "template": "ایک خلائی منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["space", "scifi", "adventure"]
    },
    # Adventure (3)
    {
        "id": "ur_adventure_001",
        "name": "ایڈونچر منظر",
        "category": "adventure",
        "template": "ایک ایڈونچر منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["adventure", "exciting", "journey"]
    },
    {
        "id": "ur_adventure_002",
        "name": "دریافت کا منظر",
        "category": "adventure",
        "template": "ایک دریافت کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["discovery", "adventure", "explore"]
    },
    {
        "id": "ur_adventure_003",
        "name": "جنگل کا منظر",
        "category": "adventure",
        "template": "ایک جنگل کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["jungle", "adventure", "wild"]
    },
    # Mystery (3)
    {
        "id": "ur_mystery_001",
        "name": "پراسرار منظر",
        "category": "mystery",
        "template": "ایک پراسرار منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["mystery", "suspense", "intrigue"]
    },
    {
        "id": "ur_mystery_002",
        "name": "تحقیق کا منظر",
        "category": "mystery",
        "template": "ایک تحقیق کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["investigation", "mystery", "detective"]
    },
    {
        "id": "ur_mystery_003",
        "name": "راز کا منظر",
        "category": "mystery",
        "template": "ایک راز کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["secret", "mystery", "hidden"]
    },
    # Romantic Comedy (3)
    {
        "id": "ur_romcom_001",
        "name": "رومانوی کامیڈی",
        "category": "romantic_comedy",
        "template": "ایک رومانوی کامیڈی منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
        "variables": ["character", "character2", "setting", "action"],
        "language": "ur",
        "tags": ["romantic", "comedy", "funny"]
    },
    {
        "id": "ur_romcom_002",
        "name": "مضحکہ خیز محبت",
        "category": "romantic_comedy",
        "template": "ایک مضحکہ خیز محبت کا منظر جس میں {character} {character2} کو {action} کر رہا ہے",
        "variables": ["character", "character2", "action"],
        "language": "ur",
        "tags": ["love", "comedy", "funny"]
    },
    {
        "id": "ur_romcom_003",
        "name": "ہنسی مذاق کا منظر",
        "category": "romantic_comedy",
        "template": "ایک ہنسی مذاق کا منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
        "variables": ["character", "character2", "setting", "action"],
        "language": "ur",
        "tags": ["laughter", "comedy", "romance"]
    },
    # Musical (3)
    {
        "id": "ur_musical_001",
        "name": "موسیقی کا منظر",
        "category": "musical",
        "template": "ایک موسیقی کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["music", "song", "rhythm"]
    },
    {
        "id": "ur_musical_002",
        "name": "رقص کا منظر",
        "category": "musical",
        "template": "ایک رقص کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["dance", "music", "performance"]
    },
    {
        "id": "ur_musical_003",
        "name": "گانے کا منظر",
        "category": "musical",
        "template": "ایک گانے کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["singing", "music", "melody"]
    },
    # Sports (3)
    {
        "id": "ur_sports_001",
        "name": "کھیل کا منظر",
        "category": "sports",
        "template": "ایک کھیل کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["sports", "game", "competition"]
    },
    {
        "id": "ur_sports_002",
        "name": "مقابلہ کا منظر",
        "category": "sports",
        "template": "ایک مقابلہ کا منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
        "variables": ["character", "character2", "setting", "action"],
        "language": "ur",
        "tags": ["competition", "sports", "match"]
    },
    {
        "id": "ur_sports_003",
        "name": "جیت کا منظر",
        "category": "sports",
        "template": "ایک جیت کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["victory", "sports", "celebration"]
    },
    # Food (2)
    {
        "id": "ur_food_001",
        "name": "کھانے کا منظر",
        "category": "food",
        "template": "ایک کھانے کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["food", "cooking", "delicious"]
    },
    {
        "id": "ur_food_002",
        "name": "باورچی خانہ",
        "category": "food",
        "template": "ایک باورچی خانہ کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["kitchen", "cooking", "food"]
    },
    # Travel (2)
    {
        "id": "ur_travel_001",
        "name": "سفر کا منظر",
        "category": "travel",
        "template": "ایک سفر کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["travel", "journey", "explore"]
    },
    {
        "id": "ur_travel_002",
        "name": "سیاحت کا منظر",
        "category": "travel",
        "template": "ایک سیاحت کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["tourist", "travel", "sightseeing"]
    },
    # Wedding (2)
    {
        "id": "ur_wedding_001",
        "name": "شادی کا منظر",
        "category": "wedding",
        "template": "ایک شادی کا منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
        "variables": ["character", "character2", "setting", "action"],
        "language": "ur",
        "tags": ["wedding", "marriage", "celebration"]
    },
    {
        "id": "ur_wedding_002",
        "name": "دولہا دلہن",
        "category": "wedding",
        "template": "ایک دولہا دلہن کا منظر جس میں {character} اور {character2} {setting} میں {action} کر رہے ہیں",
        "variables": ["character", "character2", "setting", "action"],
        "language": "ur",
        "tags": ["bride", "groom", "wedding"]
    },
    # Party (2)
    {
        "id": "ur_party_001",
        "name": "پارٹی کا منظر",
        "category": "party",
        "template": "ایک پارٹی کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["party", "celebration", "fun"]
    },
    {
        "id": "ur_party_002",
        "name": "جشن کا منظر",
        "category": "party",
        "template": "ایک جشن کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["celebration", "party", "festival"]
    },
    # Spiritual (2)
    {
        "id": "ur_spiritual_001",
        "name": "روحانی منظر",
        "category": "spiritual",
        "template": "ایک روحانی منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["spiritual", "soul", "peace"]
    },
    {
        "id": "ur_spiritual_002",
        "name": "عبادت کا منظر",
        "category": "spiritual",
        "template": "ایک عبادت کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["prayer", "spiritual", "devotion"]
    },
    # Cartoon (2)
    {
        "id": "ur_cartoon_001",
        "name": "کارٹون منظر",
        "category": "cartoon",
        "template": "ایک کارٹون منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["cartoon", "animated", "colorful"]
    },
    {
        "id": "ur_cartoon_002",
        "name": "اینیمیٹڈ منظر",
        "category": "cartoon",
        "template": "ایک اینیمیٹڈ منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["animation", "cartoon", "fun"]
    },
    # Fashion (2)
    {
        "id": "ur_fashion_001",
        "name": "فیشن منظر",
        "category": "fashion",
        "template": "ایک فیشن منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["fashion", "style", "design"]
    },
    {
        "id": "ur_fashion_002",
        "name": "ریمپ واک",
        "category": "fashion",
        "template": "ایک ریمپ واک کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["runway", "fashion", "model"]
    },
    # Crime (2)
    {
        "id": "ur_crime_001",
        "name": "جرائم کا منظر",
        "category": "crime",
        "template": "ایک جرائم کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["crime", "criminal", "investigation"]
    },
    {
        "id": "ur_crime_002",
        "name": "پولیس کا منظر",
        "category": "crime",
        "template": "ایک پولیس کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["police", "crime", "justice"]
    },
    # War (2)
    {
        "id": "ur_war_001",
        "name": "جنگی منظر",
        "category": "war",
        "template": "ایک جنگی منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["war", "battle", "conflict"]
    },
    {
        "id": "ur_war_002",
        "name": "فوج کا منظر",
        "category": "war",
        "template": "ایک فوج کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["army", "war", "military"]
    },
    # Western (2)
    {
        "id": "ur_western_001",
        "name": "ویسٹرن منظر",
        "category": "western",
        "template": "ایک ویسٹرن منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["western", "cowboy", "frontier"]
    },
    {
        "id": "ur_western_002",
        "name": "کاؤبای منظر",
        "category": "western",
        "template": "ایک کاؤبای منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["cowboy", "western", "wild west"]
    },
    # Noir (2)
    {
        "id": "ur_noir_001",
        "name": "نوار منظر",
        "category": "noir",
        "template": "ایک نوار منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["noir", "dark", "mysterious"]
    },
    {
        "id": "ur_noir_002",
        "name": "جاسوس منظر",
        "category": "noir",
        "template": "ایک جاسوس منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["detective", "noir", "crime"]
    },
    # Superhero (2)
    {
        "id": "ur_superhero_001",
        "name": "سپر ہیرو منظر",
        "category": "superhero",
        "template": "ایک سپر ہیرو منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["superhero", "hero", "powers"]
    },
    {
        "id": "ur_superhero_002",
        "name": "ہیرو کا منظر",
        "category": "superhero",
        "template": "ایک ہیرو کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["hero", "superhero", "rescue"]
    },
    # Mythology (2)
    {
        "id": "ur_mythology_001",
        "name": "دیومالائی منظر",
        "category": "mythology",
        "template": "ایک دیومالائی منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["mythology", "gods", "legends"]
    },
    {
        "id": "ur_mythology_002",
        "name": "افسانوی منظر",
        "category": "mythology",
        "template": "ایک افسانوی منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["mythical", "legend", "ancient"]
    },
    # Epic (2)
    {
        "id": "ur_epic_001",
        "name": "عظیم منظر",
        "category": "epic",
        "template": "ایک عظیم منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["epic", "grand", "heroic"]
    },
    {
        "id": "ur_epic_002",
        "name": "بہادری کا منظر",
        "category": "epic",
        "template": "ایک بہادری کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["bravery", "epic", "heroic"]
    },
    # Steampunk (2)
    {
        "id": "ur_steampunk_001",
        "name": "سٹیمپنک منظر",
        "category": "steampunk",
        "template": "ایک سٹیمپنک منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["steampunk", "victorian", "steam"]
    },
    {
        "id": "ur_steampunk_002",
        "name": "پرانی مشینری",
        "category": "steampunk",
        "template": "ایک پرانی مشینری کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["machinery", "steampunk", "vintage"]
    },
    # Dystopian (2)
    {
        "id": "ur_dystopian_001",
        "name": "ڈسٹوپین منظر",
        "category": "dystopian",
        "template": "ایک ڈسٹوپین منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["dystopian", "future", "dark"]
    },
    {
        "id": "ur_dystopian_002",
        "name": "تاریک مستقبل",
        "category": "dystopian",
        "template": "ایک تاریک مستقبل کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["future", "dark", "dystopian"]
    },
    # Post-Apocalyptic (2)
    {
        "id": "ur_postapocalyptic_001",
        "name": "پوسٹ اپوکیلیپٹک",
        "category": "post_apocalyptic",
        "template": "ایک پوسٹ اپوکیلیپٹک منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["apocalyptic", "survival", "wasteland"]
    },
    {
        "id": "ur_postapocalyptic_002",
        "name": "تباہی کا منظر",
        "category": "post_apocalyptic",
        "template": "ایک تباہی کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["destruction", "apocalyptic", "survival"]
    },
    # Coming of Age (2)
    {
        "id": "ur_comingofage_001",
        "name": "بڑھاپے کا منظر",
        "category": "coming_of_age",
        "template": "ایک بڑھاپے کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["coming of age", "growth", "journey"]
    },
    {
        "id": "ur_comingofage_002",
        "name": "خود کو تلاش کرنا",
        "category": "coming_of_age",
        "template": "ایک خود کو تلاش کرنے کا منظر جس میں {character} {setting} میں {action} کر رہا ہے",
        "variables": ["character", "setting", "action"],
        "language": "ur",
        "tags": ["self discovery", "growth", "coming of age"]
    }
]

# Note: HINDI_TEMPLATES and ENGLISH_TEMPLATES are intentionally empty for now.
# The UI (below) handles this gracefully — it shows an info message instead
# of an empty/broken screen when a language has no templates yet. Add
# templates to these lists later using the same dict structure as
# URDU_TEMPLATES above; no other code changes are needed.
HINDI_TEMPLATES = []
ENGLISH_TEMPLATES = []

# ============================================
# MAIN FUNCTIONS (SAME AS BEFORE BUT WITH ENHANCED CATEGORIES)
# ============================================

def get_all_categories() -> List[str]:
    """Get all available categories"""
    return list(CATEGORIES.keys())


def get_category_info(category: str) -> Optional[Dict]:
    """Get category information"""
    return CATEGORIES.get(category)


def get_all_templates(language: str = "ur") -> List[Dict]:
    """Get all templates for a specific language"""
    lang_map = {
        "ur": URDU_TEMPLATES,
        "hi": HINDI_TEMPLATES,
        "en": ENGLISH_TEMPLATES
    }
    return lang_map.get(language, URDU_TEMPLATES)


def get_templates_by_category(category: str, language: str = "ur") -> List[Dict]:
    """Get templates filtered by category"""
    templates = get_all_templates(language)
    return [t for t in templates if t.get("category") == category]


def get_templates_by_categories(categories: List[str], language: str = "ur") -> List[Dict]:
    """Get templates for multiple categories"""
    templates = get_all_templates(language)
    return [t for t in templates if t.get("category") in categories]


def get_random_template(language: str = "ur", category: str = None) -> Dict:
    """Get a random template"""
    templates = get_all_templates(language)
    if category:
        templates = [t for t in templates if t.get("category") == category]
    
    if not templates:
        return {"error": "No templates found"}
    
    template = random.choice(templates)
    track_template_usage(template.get("id", "unknown"))
    return template


def fill_template(template: Dict, variables: Dict) -> str:
    """Fill a template with variables"""
    try:
        template_text = template.get("template", "")
        required_vars = template.get("variables", [])
        for var in required_vars:
            if var not in variables or variables[var] is None:
                variables[var] = f"{{{var}}}"
        return template_text.format(**variables)
    except KeyError as e:
        logger.warning(f"Missing variable: {e}")
        return template.get("template", "")
    except Exception as e:
        logger.error(f"Failed to fill template: {e}")
        return template.get("template", "")


def search_templates(query: str, language: str = "ur", categories: List[str] = None) -> List[Dict]:
    """Search templates by keyword"""
    templates = get_all_templates(language)
    if categories:
        templates = [t for t in templates if t.get("category") in categories]
    
    results = []
    query_lower = query.lower()
    for t in templates:
        if (query_lower in t.get("name", "").lower() or 
            query_lower in t.get("template", "").lower() or
            any(query_lower in var.lower() for var in t.get("variables", [])) or
            any(query_lower in tag.lower() for tag in t.get("tags", []))):
            results.append(t)
    
    return results


def get_category_templates_count(language: str = "ur") -> Dict[str, int]:
    """Get count of templates per category"""
    templates = get_all_templates(language)
    counts = {}
    for t in templates:
        cat = t.get("category")
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return counts


def get_category_names(language: str = "ur") -> Dict[str, str]:
    """Get category names in specific language"""
    names = {
        "ur": {
            "drama": "ڈرامہ",
            "action": "ایکشن",
            "romance": "رومانس",
            "poetry": "شاعری",
            "nature": "فطرت",
            "city": "شہر",
            "fantasy": "خیالی",
            "horror": "خوفناک",
            "comedy": "مزاحیہ",
            "thriller": "سنسنی خیز",
            "scifi": "سائنس فکشن",
            "adventure": "ایڈونچر",
            "mystery": "پراسرار",
            "historical": "تاریخی",
            "romantic_comedy": "رومانوی کامیڈی",
            "musical": "موسیقی",
            "sports": "کھیل",
            "food": "کھانا",
            "travel": "سفر",
            "wedding": "شادی",
            "party": "پارٹی",
            "spiritual": "روحانی",
            "cartoon": "کارٹون",
            "fashion": "فیشن",
            "crime": "جرائم",
            "war": "جنگ",
            "western": "ویسٹرن",
            "noir": "نوار",
            "superhero": "سپر ہیرو",
            "mythology": "دیومالائی",
            "epic": "عظیم",
            "steampunk": "سٹیمپنک",
            "dystopian": "ڈسٹوپین",
            "post_apocalyptic": "پوسٹ اپوکیلیپٹک",
            "coming_of_age": "بڑھاپے کا سفر"
        },
        "hi": {
            "drama": "नाटक",
            "action": "एक्शन",
            "romance": "रोमांस",
            "poetry": "कविता",
            "nature": "प्रकृति",
            "city": "शहर",
            "fantasy": "काल्पनिक",
            "horror": "भयानक",
            "comedy": "हास्य",
            "thriller": "थ्रिलर",
            "scifi": "साइंस फिक्शन",
            "adventure": "एडवेंचर",
            "mystery": "रहस्यमय",
            "historical": "ऐतिहासिक",
            "romantic_comedy": "रोमांटिक कॉमेडी",
            "musical": "संगीत",
            "sports": "खेल",
            "food": "खाना",
            "travel": "यात्रा",
            "wedding": "शादी",
            "party": "पार्टी",
            "spiritual": "आध्यात्मिक",
            "cartoon": "कार्टून",
            "fashion": "फैशन",
            "crime": "अपराध",
            "war": "युद्ध",
            "western": "वेस्टर्न",
            "noir": "नॉयर",
            "superhero": "सुपर हीरो",
            "mythology": "पौराणिक",
            "epic": "महाकाव्य",
            "steampunk": "स्टीमपंक",
            "dystopian": "डिस्टोपियन",
            "post_apocalyptic": "पोस्ट-एपोकैलिप्टिक",
            "coming_of_age": "बड़े होने का सफर"
        },
        "en": {
            "drama": "Drama",
            "action": "Action",
            "romance": "Romance",
            "poetry": "Poetry",
            "nature": "Nature",
            "city": "City",
            "fantasy": "Fantasy",
            "horror": "Horror",
            "comedy": "Comedy",
            "thriller": "Thriller",
            "scifi": "Sci-Fi",
            "adventure": "Adventure",
            "mystery": "Mystery",
            "historical": "Historical",
            "romantic_comedy": "Romantic Comedy",
            "musical": "Musical",
            "sports": "Sports",
            "food": "Food",
            "travel": "Travel",
            "wedding": "Wedding",
            "party": "Party",
            "spiritual": "Spiritual",
            "cartoon": "Cartoon",
            "fashion": "Fashion",
            "crime": "Crime",
            "war": "War",
            "western": "Western",
            "noir": "Noir",
            "superhero": "Superhero",
            "mythology": "Mythology",
            "epic": "Epic",
            "steampunk": "Steampunk",
            "dystopian": "Dystopian",
            "post_apocalyptic": "Post-Apocalyptic",
            "coming_of_age": "Coming of Age"
        }
    }
    return names.get(language, names["en"])


# ============================================
# JSON PERSISTENCE HELPERS (usage / ratings / custom templates)
# ============================================

def _load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not read {path}: {e} — using default.")
        return default


def _save_json_file(path: str, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Could not write {path}: {e}")
        return False


# ============================================
# USAGE TRACKING (previously called but never defined)
# ============================================

def track_template_usage(template_id: str) -> None:
    """Record that a template was used (increments its usage counter)."""
    global _USAGE_STATS_CACHE
    stats = _load_json_file(USAGE_STATS_FILE, {})
    entry = stats.get(template_id, {"usage_count": 0, "last_used": None})
    entry["usage_count"] = entry.get("usage_count", 0) + 1
    entry["last_used"] = datetime.now().isoformat()
    stats[template_id] = entry
    _save_json_file(USAGE_STATS_FILE, stats)
    _USAGE_STATS_CACHE = stats


def get_template_usage_stats(template_id: str) -> Dict:
    """Return usage stats for a single template (defaults to 0 if never used)."""
    stats = _load_json_file(USAGE_STATS_FILE, {})
    entry = stats.get(template_id, {"usage_count": 0, "last_used": None})
    return {"usage_count": entry.get("usage_count", 0), "last_used": entry.get("last_used")}


def get_popular_templates(language: str = "ur", limit: int = 5) -> List[Dict]:
    """Return the most-used templates for a language, each annotated with usage_count."""
    stats = _load_json_file(USAGE_STATS_FILE, {})
    templates = get_all_templates(language)
    annotated = []
    for t in templates:
        count = stats.get(t.get("id", ""), {}).get("usage_count", 0)
        if count > 0:
            enriched = dict(t)
            enriched["usage_count"] = count
            annotated.append(enriched)
    annotated.sort(key=lambda t: t["usage_count"], reverse=True)
    return annotated[:limit]


# ============================================
# RATINGS (previously called but never defined)
# ============================================

def rate_template(template_id: str, rating: int) -> Dict:
    """Submit a 1-5 star rating for a template."""
    if not (1 <= rating <= 5):
        return {"success": False, "message": "❌ Rating must be between 1 and 5."}
    ratings = _load_json_file(RATINGS_FILE, {})
    entry = ratings.get(template_id, {"ratings": []})
    entry["ratings"].append(rating)
    ratings[template_id] = entry
    _save_json_file(RATINGS_FILE, ratings)
    return {"success": True, "message": "✅ Rating saved."}


def get_template_rating(template_id: str) -> Dict:
    """Return average rating + star display for a template (defaults if unrated)."""
    ratings = _load_json_file(RATINGS_FILE, {})
    entry = ratings.get(template_id, {"ratings": []})
    values = entry.get("ratings", [])
    if not values:
        return {"average_rating": 0, "total_ratings": 0, "stars": "☆☆☆☆☆"}
    avg = round(sum(values) / len(values), 1)
    full_stars = int(round(avg))
    stars = "★" * full_stars + "☆" * (5 - full_stars)
    return {"average_rating": avg, "total_ratings": len(values), "stars": stars}


# ============================================
# CUSTOM TEMPLATES (previously called but never defined)
# ============================================

def save_custom_template(name: str, template: str, category: str, language: str = "ur",
                          variables: List[str] = None, tags: List[str] = None) -> bool:
    """Save a user-created template."""
    if not name or not template:
        return False
    custom = _load_json_file(CUSTOM_TEMPLATES_FILE, [])
    template_id = "custom_" + hashlib.md5(f"{name}{template}{datetime.now().isoformat()}".encode("utf-8")).hexdigest()[:10]
    custom.append({
        "id": template_id,
        "name": name,
        "category": category,
        "template": template,
        "language": language,
        "variables": variables or [],
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    })
    return _save_json_file(CUSTOM_TEMPLATES_FILE, custom)


def get_custom_templates(language: str = "ur") -> List[Dict]:
    """Return all custom templates for a language."""
    custom = _load_json_file(CUSTOM_TEMPLATES_FILE, [])
    return [t for t in custom if t.get("language") == language]


def delete_custom_template(template_id: str) -> bool:
    """Delete a custom template by id."""
    custom = _load_json_file(CUSTOM_TEMPLATES_FILE, [])
    new_list = [t for t in custom if t.get("id") != template_id]
    if len(new_list) == len(custom):
        return False  # nothing was deleted
    return _save_json_file(CUSTOM_TEMPLATES_FILE, new_list)


# ============================================
# UI RENDER FUNCTION (ENHANCED)
# ============================================

def render_feature_10():
    """Render Prompt Templates UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 📋 Prompt Templates")
    st.markdown("*100+ ready-made prompt templates across 35+ categories*")
    
    # Language selector
    language = st.selectbox(
        "Language / زبان",
        ["Urdu", "Hindi", "English"],
        index=0,
        key="template_lang"
    )
    
    lang_map = {"Urdu": "ur", "Hindi": "hi", "English": "en"}
    lang_code = lang_map.get(language, "en")
    
    # Category selector - show as buttons in grid
    st.markdown("### 📂 Categories")
    categories = get_all_categories()
    category_names = get_category_names(lang_code)
    category_info = {cat: CATEGORIES[cat] for cat in categories}
    
    # Show categories in a grid
    cols_per_row = 6
    selected_category = None
    
    # Create rows of category buttons
    for i in range(0, len(categories), cols_per_row):
        row_cats = categories[i:i+cols_per_row]
        cols = st.columns(cols_per_row)
        for j, cat in enumerate(row_cats):
            with cols[j]:
                info = category_info.get(cat, {})
                emoji = info.get("emoji", "📌")
                display_name = category_names.get(cat, cat)
                if st.button(f"{emoji} {display_name}", key=f"cat_{cat}_{lang_code}", use_container_width=True):
                    selected_category = cat
                    st.session_state["selected_category_10"] = cat
                    st.rerun()
    
    if "selected_category_10" in st.session_state:
        selected_category = st.session_state["selected_category_10"]
        info = category_info.get(selected_category, {})
        st.info(f"✅ Selected: {info.get('emoji', '')} {category_names.get(selected_category, selected_category)} - {info.get('description', '')}")
    
    # Get templates
    if selected_category:
        templates = get_templates_by_category(selected_category, lang_code)
    else:
        templates = get_all_templates(lang_code)
    
    # Show template count
    category_counts = get_category_templates_count(lang_code)
    st.caption(f"📊 {len(templates)} templates found")
    
    # Search
    search_query = st.text_input(
        "Search / تلاش کریں",
        placeholder="Search by name, template text, or tags...",
        key="template_search"
    )
    
    if search_query:
        categories_filter = [selected_category] if selected_category else None
        templates = search_templates(search_query, lang_code, categories_filter)
        st.caption(f"🔍 Found {len(templates)} matching templates")

    if not templates:
        st.info("ℹ️ Is language mein abhi koi templates nahi hain. 'Urdu' try karo — sabse zyada templates wahan hain.")
    
    # Display templates
    if templates:
        for t in templates[:20]:  # Show first 20
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    # Category badge
                    cat = t.get('category')
                    cat_display = category_names.get(cat, cat)
                    cat_info = category_info.get(cat, {})
                    st.markdown(f"**{cat_info.get('emoji', '')} {t.get('name')}**")
                    st.caption(f"📂 {cat_display}")
                    
                    # Show template with variable placeholders
                    template_text = t.get('template', '')
                    st.code(template_text, language="text")
                    
                    # Show variables
                    variables = t.get('variables', [])
                    if variables:
                        st.caption(f"📝 Variables: {', '.join(variables)}")
                    
                    # Show tags
                    tags = t.get('tags', [])
                    if tags:
                        st.caption(f"🏷️ Tags: {', '.join(tags)}")
                
                with col2:
                    # Rating
                    rating = get_template_rating(t.get('id'))
                    if rating["total_ratings"] > 0:
                        st.caption(f"{rating['stars']} ({rating['average_rating']})")
                    else:
                        st.caption("⭐ No ratings yet")
                    
                    # Usage count
                    usage = get_template_usage_stats(t.get('id'))
                    if usage["usage_count"] > 0:
                        st.caption(f"📊 Used {usage['usage_count']} times")
                    
                    # Action buttons
                    if st.button(f"📝 Use", key=f"use_{t.get('id')}"):
                        st.session_state["selected_template"] = t
                        track_template_usage(t.get('id', 'unknown'))
                        st.success(f"✅ Template loaded: {t.get('name')}")
                        
                        # Show filled template with example values
                        example_vars = {}
                        for var in t.get('variables', []):
                            example_vars[var] = f"[{var}]"
                        
                        filled = fill_template(t, example_vars)
                        st.code(filled, language="text")
                    
                    # Star rating
                    star_choice = st.select_slider(
                        "Rate", options=[1, 2, 3, 4, 5], value=5,
                        key=f"ratepick_{t.get('id')}", label_visibility="collapsed"
                    )
                    if st.button(f"⭐ Submit Rating", key=f"rate_{t.get('id')}"):
                        rate_result = rate_template(t.get('id'), star_choice)
                        if rate_result["success"]:
                            st.success(rate_result["message"])
                            st.rerun()
                        else:
                            st.error(rate_result["message"])
                
                st.divider()
        
        if len(templates) > 20:
            st.info(f"ℹ️ Showing 20 of {len(templates)} templates. Use search to find specific templates.")
    
    # Category stats
    with st.expander("📊 Category Statistics"):
        counts = get_category_templates_count(lang_code)
        for cat, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            info = category_info.get(cat, {})
            name = category_names.get(cat, cat)
            st.caption(f"{info.get('emoji', '')} {name}: {count} templates")
    
    # Custom template section
    st.markdown("---")
    st.markdown("### ✏️ Custom Template")
    st.markdown("*Apna custom template save karein*")
    
    col1, col2 = st.columns(2)
    with col1:
        custom_name = st.text_input("Template Name", placeholder="My Custom Template", key="custom_name")
        custom_category = st.selectbox(
            "Category",
            categories,
            key="custom_category"
        )
    with col2:
        custom_vars = st.text_input(
            "Variables (comma separated)",
            placeholder="character, action, setting",
            key="custom_vars"
        )
        custom_tags = st.text_input(
            "Tags (comma separated)",
            placeholder="custom, personalized",
            key="custom_tags"
        )
    
    custom_template = st.text_area(
        "Template Text",
        placeholder="Enter your template with {variables}...",
        height=100,
        key="custom_template"
    )
    
    if st.button("💾 Save Custom Template", key="save_custom"):
        if not custom_name or not custom_template:
            st.error("❌ Name and template text are required")
        else:
            vars_list = [v.strip() for v in custom_vars.split(",") if v.strip()]
            tags_list = [t.strip() for t in custom_tags.split(",") if t.strip()]
            
            success = save_custom_template(
                name=custom_name,
                template=custom_template,
                category=custom_category,
                language=lang_code,
                variables=vars_list,
                tags=tags_list
            )
            
            if success:
                st.success("✅ Custom template saved successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to save custom template")
    
    # Show custom templates
    custom_templates = get_custom_templates(lang_code)
    if custom_templates:
        st.markdown("### 📂 Custom Templates")
        for ct in custom_templates:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{ct.get('name')}**")
                st.code(ct.get('template'), language="text")
            with col2:
                if st.button(f"🗑️ Delete", key=f"del_{ct.get('id')}"):
                    if delete_custom_template(ct.get('id')):
                        st.success("✅ Deleted!")
                        st.rerun()
            st.divider()
    
    # Popular templates
    st.markdown("---")
    st.markdown("### 🔥 Popular Templates")
    popular = get_popular_templates(lang_code, 5)
    if popular:
        for p in popular:
            if p.get("usage_count", 0) > 0:
                st.markdown(f"**{p.get('name')}** - Used {p.get('usage_count')} times")
                st.code(p.get('template'), language="text")
    else:
        st.info("ℹ️ No usage data yet. Start using templates to see popular ones here!")


# ============================================
# TEST FUNCTION
# ============================================

def test():
    """Test the prompt templates feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_10_prompt_templates.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    # Test categories
    print("\n📝 Test 1: Categories")
    categories = get_all_categories()
    print(f"  Total categories: {len(categories)}")
    for cat in categories[:10]:
        info = CATEGORIES.get(cat, {})
        print(f"    - {cat}: {info.get('emoji')} {info.get('name')}")
    
    # Test templates
    print("\n📝 Test 2: Templates by language")
    ur_templates = get_all_templates("ur")
    hi_templates = get_all_templates("hi")
    en_templates = get_all_templates("en")
    print(f"  Urdu templates: {len(ur_templates)}")
    print(f"  Hindi templates: {len(hi_templates)}")
    print(f"  English templates: {len(en_templates)}")
    
    # Test category counts
    print("\n📝 Test 3: Category counts")
    counts = get_category_templates_count("ur")
    for cat, count in list(counts.items())[:10]:
        print(f"    - {cat}: {count} templates")
    
    # Test random template
    print("\n📝 Test 4: Random template")
    random_template = get_random_template("ur")
    print(f"  Random template: {random_template.get('name')} ({random_template.get('category')})")

    # Test usage tracking / ratings / custom templates (new)
    print("\n📝 Test 5: Usage tracking + ratings + custom templates")
    track_template_usage("ur_drama_001")
    track_template_usage("ur_drama_001")
    usage = get_template_usage_stats("ur_drama_001")
    print(f"  Usage for ur_drama_001: {usage}")
    rate_template("ur_drama_001", 5)
    rate_template("ur_drama_001", 4)
    print(f"  Rating for ur_drama_001: {get_template_rating('ur_drama_001')}")
    saved = save_custom_template("My Test Template", "A {character} does {action}", "action", "ur", ["character", "action"], ["test"])
    print(f"  Custom template saved: {saved}")
    print(f"  Custom templates (ur): {len(get_custom_templates('ur'))}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    test()

# ============================================
# END OF feature_10_prompt_templates.py (ULTIMATE)
# ============================================