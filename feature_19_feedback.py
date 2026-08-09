# ============================================
# FEATURE 19: FEEDBACK SYSTEM (COMPLETE FIX)
# Filename: feature_19_feedback.py
# ============================================
# Kya karta hai:
# Users ko feedback dene ki facility
# - Video rating (1-5 stars)
# - Video feedback (comments)
# - Feature request submissions
# - Bug reports
# - User satisfaction surveys
# - Feedback analytics
# - Feedback reply system
# - Feedback notifications
# - Sentiment analysis
# - Feedback resolution tracking
# ============================================

import os
import sys
import json
import shutil
import uuid
import logging
import threading
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from enum import Enum
from dataclasses import dataclass, asdict
import hashlib

# UTF-8 stdout safety
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# CONFIG WITH FALLBACKS
# ============================================

try:
    from config import *
except ImportError:
    logger.warning("config.py not found! Using default config.")

# Define default configs if not in config.py
if 'FEEDBACK_CONFIG' not in dir():
    FEEDBACK_CONFIG = {
        "max_rating": 5,
        "min_comment_length": 2,
        "max_comment_length": 5000,
        "min_title_length": 3,
        "max_title_length": 200,
        "allow_attachments": True,
        "max_attachments": 5,
        "max_file_size_mb": 10,
        "notification_enabled": True
    }

# Safety check
if 'FEEDBACK_CONFIG' not in globals():
    FEEDBACK_CONFIG = {
        "max_rating": 5,
        "min_comment_length": 2,
        "max_comment_length": 5000,
        "min_title_length": 3,
        "max_title_length": 200,
        "allow_attachments": True,
        "max_attachments": 5,
        "max_file_size_mb": 10,
        "notification_enabled": True
    }

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# Get PATHS with fallbacks
if 'PATHS' not in dir():
    PATHS = {
        'temp': 'temp',
        'videos': 'videos',
        'library': 'library'
    }

# ============================================
# CONSTANTS
# ============================================

FEEDBACK_DB_FILE = os.path.join(PATHS.get('library', 'library'), "feedback_db.json")
SATISFACTION_DB_FILE = os.path.join(PATHS.get('library', 'library'), "satisfaction_db.json")
DB_LOCK = threading.RLock()

os.makedirs(PATHS.get('library', 'library'), exist_ok=True)

# Enums for better type safety
class FeedbackStatus(Enum):
    OPEN = "open"
    REPLIED = "replied"
    RESOLVED = "resolved"
    CLOSED = "closed"
    SPAM = "spam"

class FeedbackCategory(Enum):
    GENERAL = "general"
    VIDEO = "video"
    FEATURE = "feature"
    UX = "ux"
    PERFORMANCE = "performance"
    BUG = "bug"
    SUPPORT = "support"
    OTHER = "other"

class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Resolution(Enum):
    FIXED = "fixed"
    WONT_FIX = "wontfix"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    COMPLETED = "completed"
    NOT_APPLICABLE = "na"

# Cache
_CACHE = {}
_CACHE_TIMESTAMP = None
_CACHE_TTL = 60


# ============================================
# CACHE MANAGEMENT
# ============================================

def _is_cache_valid() -> bool:
    global _CACHE_TIMESTAMP
    if _CACHE_TIMESTAMP is None:
        return False
    return (datetime.now() - _CACHE_TIMESTAMP).total_seconds() < _CACHE_TTL


def _invalidate_cache():
    global _CACHE, _CACHE_TIMESTAMP
    _CACHE = {}
    _CACHE_TIMESTAMP = None


def _update_cache_timestamp():
    global _CACHE_TIMESTAMP
    _CACHE_TIMESTAMP = datetime.now()


# ============================================
# DATABASE FUNCTIONS
# ============================================

def _load_feedback_db() -> Dict[str, Any]:
    """Load feedback database with caching"""
    cache_key = "feedback_db"
    if cache_key in _CACHE and _is_cache_valid():
        return _CACHE[cache_key]
    
    with DB_LOCK:
        if not os.path.exists(FEEDBACK_DB_FILE):
            default_data = {
                "feedbacks": [],
                "feature_requests": [],
                "bug_reports": [],
                "replies": [],
                "categories": [c.value for c in FeedbackCategory],
                "version": "2.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "statistics": {
                    "total_feedback": 0,
                    "avg_rating": 0,
                    "resolution_rate": 0,
                    "avg_response_time": 0
                }
            }
            try:
                with open(FEEDBACK_DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to create feedback DB: {e}")
            _CACHE[cache_key] = default_data
            _update_cache_timestamp()
            return default_data
        
        try:
            with open(FEEDBACK_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "feedbacks" not in data:
                    data["feedbacks"] = []
                if "feature_requests" not in data:
                    data["feature_requests"] = []
                if "bug_reports" not in data:
                    data["bug_reports"] = []
                if "replies" not in data:
                    data["replies"] = []
                if "statistics" not in data:
                    data["statistics"] = {
                        "total_feedback": 0,
                        "avg_rating": 0,
                        "resolution_rate": 0,
                        "avg_response_time": 0
                    }
                if "categories" not in data:
                    data["categories"] = [c.value for c in FeedbackCategory]
                if "created_at" not in data:
                    data["created_at"] = datetime.now(timezone.utc).isoformat()
                _CACHE[cache_key] = data
                _update_cache_timestamp()
                return data
        except Exception as e:
            logger.error(f"Failed to load feedback DB: {e}")
            # Try backup
            backup_path = f"{FEEDBACK_DB_FILE}.backup"
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        _CACHE[cache_key] = data
                        _update_cache_timestamp()
                        return data
                except:
                    pass
            return {
                "feedbacks": [],
                "feature_requests": [],
                "bug_reports": [],
                "replies": [],
                "categories": [c.value for c in FeedbackCategory],
                "version": "2.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "statistics": {
                    "total_feedback": 0,
                    "avg_rating": 0,
                    "resolution_rate": 0,
                    "avg_response_time": 0
                }
            }


def _save_feedback_db(data: Dict[str, Any]) -> bool:
    """Save feedback database with thread safety"""
    with DB_LOCK:
        try:
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Create backup
            if os.path.exists(FEEDBACK_DB_FILE):
                try:
                    backup_path = f"{FEEDBACK_DB_FILE}.backup"
                    shutil.copy2(FEEDBACK_DB_FILE, backup_path)
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")
            
            # Write to temporary file first
            temp_file = FEEDBACK_DB_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            os.replace(temp_file, FEEDBACK_DB_FILE)
            _invalidate_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to save feedback data: {e}")
            return False


def _load_satisfaction_db() -> Dict[str, Any]:
    """Load satisfaction database with caching"""
    cache_key = "satisfaction_db"
    if cache_key in _CACHE and _is_cache_valid():
        return _CACHE[cache_key]
    
    with DB_LOCK:
        if not os.path.exists(SATISFACTION_DB_FILE):
            default_data = {
                "surveys": [],
                "responses": [],
                "version": "2.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            try:
                with open(SATISFACTION_DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to create satisfaction DB: {e}")
            _CACHE[cache_key] = default_data
            _update_cache_timestamp()
            return default_data
        
        try:
            with open(SATISFACTION_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "surveys" not in data:
                    data["surveys"] = []
                if "responses" not in data:
                    data["responses"] = []
                if "created_at" not in data:
                    data["created_at"] = datetime.now(timezone.utc).isoformat()
                _CACHE[cache_key] = data
                _update_cache_timestamp()
                return data
        except Exception as e:
            logger.error(f"Failed to load satisfaction DB: {e}")
            return {"surveys": [], "responses": [], "version": "2.0", "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}


def _save_satisfaction_db(data: Dict[str, Any]) -> bool:
    """Save satisfaction database with thread safety"""
    with DB_LOCK:
        try:
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            if os.path.exists(SATISFACTION_DB_FILE):
                try:
                    backup_path = f"{SATISFACTION_DB_FILE}.backup"
                    shutil.copy2(SATISFACTION_DB_FILE, backup_path)
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")
            
            temp_file = SATISFACTION_DB_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            os.replace(temp_file, SATISFACTION_DB_FILE)
            _invalidate_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to save satisfaction data: {e}")
            return False


def _generate_id(prefix: str) -> str:
    """Generate a unique ID with timestamp"""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    random_part = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{random_part}"


def _validate_user_id(user_id: str) -> bool:
    """Validate user ID"""
    if not user_id or len(user_id.strip()) < 3:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', user_id))


def _validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ============================================
# SENTIMENT ANALYSIS
# ============================================

class SentimentAnalyzer:
    """Enhanced sentiment analysis with weighted scoring"""
    
    def __init__(self):
        self.positive_words = {
            'good': 2, 'great': 3, 'excellent': 4, 'amazing': 4,
            'love': 3, 'best': 4, 'awesome': 4, 'perfect': 5,
            'nice': 2, 'wonderful': 4, 'fantastic': 4, 'brilliant': 4,
            'outstanding': 5, 'superb': 4, 'terrific': 3,
            'happy': 3, 'satisfied': 3, 'impressed': 3, 'recommend': 3,
            'beautiful': 2, 'like': 2, 'thanks': 2,
            'thank you': 2, 'appreciate': 3, 'helpful': 3,
            'awesome': 4, 'amazing': 4, 'cool': 3, 'excellent': 4
        }
        
        self.negative_words = {
            'bad': -2, 'poor': -2, 'terrible': -4, 'awful': -4,
            'hate': -3, 'worst': -4, 'useless': -3, 'broken': -3,
            'disappointed': -3, 'frustrating': -3, 'annoying': -2,
            'horrible': -4, 'disgusting': -4, 'waste': -2,
            'buggy': -2, 'slow': -2, 'confusing': -2, 'issue': -1,
            'problem': -1, 'error': -2, 'crash': -3, 'fail': -2,
            'difficult': -2, 'hard': -1, 'not working': -3,
            'terrible': -4, 'awful': -4, 'useless': -3
        }
        
        self.intensifiers = {
            'very': 1.5, 'extremely': 2.0, 'really': 1.5,
            'absolutely': 2.0, 'totally': 1.5, 'completely': 1.5,
            'so': 1.3, 'too': 1.3, 'quite': 1.2, 'pretty': 1.2
        }
    
    def analyze(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        if not text or not text.strip():
            return {
                'score': 0,
                'sentiment': 'neutral',
                'confidence': 0,
                'positive_words': [],
                'negative_words': [],
                'summary': 'No text to analyze',
                'word_count': 0
            }
        
        text_lower = text.lower()
        words = text_lower.split()
        
        score = 0
        total_weight = 0
        positive_found = []
        negative_found = []
        
        i = 0
        while i < len(words):
            word = words[i]
            multiplier = 1.0
            
            # Check for two-word phrases
            phrase = word
            if i + 1 < len(words):
                phrase = f"{word} {words[i+1]}"
            
            if phrase in self.positive_words:
                weight = self.positive_words[phrase] * multiplier
                score += weight
                total_weight += abs(weight)
                positive_found.append((phrase, weight))
                i += 2
                continue
            elif phrase in self.negative_words:
                weight = self.negative_words[phrase] * multiplier
                score += weight
                total_weight += abs(weight)
                negative_found.append((phrase, weight))
                i += 2
                continue
            
            # Check for intensifier
            if word in self.intensifiers:
                multiplier = self.intensifiers[word]
                i += 1
                if i >= len(words):
                    break
                word = words[i]
            
            # Single word check
            if word in self.positive_words:
                weight = self.positive_words[word] * multiplier
                score += weight
                total_weight += abs(weight)
                positive_found.append((word, weight))
            elif word in self.negative_words:
                weight = self.negative_words[word] * multiplier
                score += weight
                total_weight += abs(weight)
                negative_found.append((word, weight))
            
            i += 1
        
        # Normalize score
        if total_weight > 0:
            score = max(min(score / (total_weight / 10), 10), -10)
        else:
            score = 0
        
        # Determine sentiment
        if score > 3:
            sentiment = 'positive'
            summary = 'Very positive feedback'
        elif score > 1:
            sentiment = 'somewhat_positive'
            summary = 'Generally positive feedback'
        elif score > -1:
            sentiment = 'neutral'
            summary = 'Neutral feedback'
        elif score > -3:
            sentiment = 'somewhat_negative'
            summary = 'Generally negative feedback'
        else:
            sentiment = 'negative'
            summary = 'Very negative feedback'
        
        total_words = len(words)
        sentiment_words = len(positive_found) + len(negative_found)
        confidence = min(sentiment_words / (max(total_words, 1)) * 1.5, 1.0)
        
        return {
            'score': round(score, 2),
            'sentiment': sentiment,
            'confidence': round(confidence, 2),
            'positive_words': positive_found[:5],
            'negative_words': negative_found[:5],
            'summary': summary,
            'word_count': total_words
        }


# ============================================
# VALIDATION FUNCTIONS
# ============================================

def validate_rating(rating: int) -> Tuple[bool, str]:
    """Validate rating value"""
    max_rating = FEEDBACK_CONFIG.get("max_rating", 5)
    if rating < 0 or rating > max_rating:
        return False, f"Rating must be between 1 and {max_rating}"
    return True, ""


def validate_comment(comment: str) -> Tuple[bool, str]:
    """Validate comment text"""
    min_len = FEEDBACK_CONFIG.get("min_comment_length", 2)
    max_len = FEEDBACK_CONFIG.get("max_comment_length", 5000)
    
    if comment and len(comment.strip()) < min_len:
        return False, f"Comment must be at least {min_len} characters"
    
    if comment and len(comment.strip()) > max_len:
        return False, f"Comment cannot exceed {max_len} characters"
    
    return True, ""


def validate_title(title: str) -> Tuple[bool, str]:
    """Validate title"""
    min_len = FEEDBACK_CONFIG.get("min_title_length", 3)
    max_len = FEEDBACK_CONFIG.get("max_title_length", 200)
    
    if not title or len(title.strip()) < min_len:
        return False, f"Title must be at least {min_len} characters"
    
    if len(title.strip()) > max_len:
        return False, f"Title cannot exceed {max_len} characters"
    
    return True, ""


# ============================================
# FEEDBACK FUNCTIONS
# ============================================

def submit_feedback(
    user_id: str,
    video_id: str = None,
    rating: int = 0,
    comment: str = "",
    category: str = "general",
    tags: List[str] = None,
    email: str = None,
    attachments: List[Dict] = None,
    is_anonymous: bool = False
) -> Dict[str, Any]:
    """Submit feedback for a video or general app experience."""
    
    logger.info(f"💬 Submitting feedback for user: {user_id}")
    
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    if not comment and rating == 0:
        return {"success": False, "message": "Please provide either rating or comment"}
    
    if comment:
        valid, msg = validate_comment(comment)
        if not valid:
            return {"success": False, "message": msg}
    
    if rating > 0:
        valid, msg = validate_rating(rating)
        if not valid:
            return {"success": False, "message": msg}
    
    if email and not _validate_email(email):
        return {"success": False, "message": "Invalid email format"}
    
    valid_categories = [c.value for c in FeedbackCategory]
    if category not in valid_categories:
        return {"success": False, "message": f"Invalid category. Must be one of: {', '.join(valid_categories)}"}
    
    if attachments:
        max_attachments = FEEDBACK_CONFIG.get("max_attachments", 5)
        if len(attachments) > max_attachments:
            return {"success": False, "message": f"Maximum {max_attachments} attachments allowed"}
    
    feedback_id = _generate_id("fb")
    
    sentiment_analyzer = SentimentAnalyzer()
    sentiment = sentiment_analyzer.analyze(comment) if comment else {'score': 0, 'sentiment': 'neutral'}
    
    feedback = {
        "feedback_id": feedback_id,
        "user_id": user_id if not is_anonymous else "anonymous",
        "display_name": "Anonymous User" if is_anonymous else user_id,
        "email": email,
        "video_id": video_id,
        "rating": rating,
        "comment": comment,
        "category": category,
        "tags": tags or [],
        "attachments": attachments or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": FeedbackStatus.OPEN.value,
        "replies": [],
        "is_anonymous": is_anonymous,
        "sentiment_score": sentiment['score'],
        "sentiment": sentiment['sentiment'],
        "sentiment_confidence": sentiment['confidence'],
        "resolution": None,
        "resolved_at": None,
        "resolved_by": None,
        "resolution_notes": None
    }
    
    db = _load_feedback_db()
    db["feedbacks"].append(feedback)
    
    stats = db.get("statistics", {})
    stats["total_feedback"] = stats.get("total_feedback", 0) + 1
    
    if rating > 0:
        all_feedbacks = db.get("feedbacks", [])
        ratings = [f.get("rating", 0) for f in all_feedbacks if f.get("rating", 0) > 0]
        stats["avg_rating"] = sum(ratings) / len(ratings) if ratings else 0
    
    db["statistics"] = stats
    _save_feedback_db(db)
    
    logger.info(f"✅ Feedback submitted: {feedback_id}")
    
    if email and FEEDBACK_CONFIG.get("notification_enabled", True):
        _send_notification(email, "Feedback Received", f"Thank you for your feedback! ID: {feedback_id}")
    
    return {
        "success": True,
        "message": "Feedback submitted successfully",
        "feedback_id": feedback_id,
        "feedback": feedback,
        "sentiment": sentiment
    }


def submit_feature_request(
    user_id: str,
    title: str,
    description: str,
    priority: str = "medium",
    category: str = "general",
    email: str = None
) -> Dict[str, Any]:
    """Submit a feature request."""
    
    logger.info(f"🚀 Submitting feature request from user: {user_id}")
    
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    valid, msg = validate_title(title)
    if not valid:
        return {"success": False, "message": msg}
    
    if not description or len(description.strip()) < 10:
        return {"success": False, "message": "Description must be at least 10 characters"}
    
    valid_priorities = [p.value for p in Priority]
    if priority not in valid_priorities:
        return {"success": False, "message": f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"}
    
    if email and not _validate_email(email):
        return {"success": False, "message": "Invalid email format"}
    
    request_id = _generate_id("fr")
    
    sentiment_analyzer = SentimentAnalyzer()
    sentiment = sentiment_analyzer.analyze(description)
    
    feature_request = {
        "request_id": request_id,
        "user_id": user_id,
        "email": email,
        "title": title,
        "description": description,
        "priority": priority,
        "category": category,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "votes": 0,
        "voters": [],
        "sentiment_score": sentiment['score'],
        "sentiment": sentiment['sentiment'],
        "implemented_at": None,
        "implementation_notes": None,
        "approved_by": None,
        "rejected_reason": None
    }
    
    db = _load_feedback_db()
    db["feature_requests"].append(feature_request)
    _save_feedback_db(db)
    
    logger.info(f"✅ Feature request submitted: {request_id}")
    
    return {
        "success": True,
        "message": "Feature request submitted successfully",
        "request_id": request_id,
        "feature_request": feature_request
    }


def submit_bug_report(
    user_id: str,
    title: str,
    description: str,
    severity: str = "medium",
    steps_to_reproduce: List[str] = None,
    screenshot: str = None,
    device_info: Dict = None,
    email: str = None
) -> Dict[str, Any]:
    """Submit a bug report."""
    
    logger.info(f"🐛 Submitting bug report from user: {user_id}")
    
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    valid, msg = validate_title(title)
    if not valid:
        return {"success": False, "message": msg}
    
    if not description or len(description.strip()) < 10:
        return {"success": False, "message": "Description must be at least 10 characters"}
    
    valid_severity = [p.value for p in Priority]
    if severity not in valid_severity:
        return {"success": False, "message": f"Invalid severity. Must be one of: {', '.join(valid_severity)}"}
    
    if email and not _validate_email(email):
        return {"success": False, "message": "Invalid email format"}
    
    bug_id = _generate_id("bg")
    
    sentiment_analyzer = SentimentAnalyzer()
    sentiment = sentiment_analyzer.analyze(description)
    
    bug_report = {
        "bug_id": bug_id,
        "user_id": user_id,
        "email": email,
        "title": title,
        "description": description,
        "severity": severity,
        "steps_to_reproduce": steps_to_reproduce or [],
        "screenshot": screenshot,
        "device_info": device_info or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "open",
        "sentiment_score": sentiment['score'],
        "sentiment": sentiment['sentiment'],
        "fixed_at": None,
        "fixed_by": None,
        "verified_by": None,
        "resolution_notes": None,
        "assigned_to": None,
        "priority_score": _calculate_priority_score(severity, sentiment['score'])
    }
    
    db = _load_feedback_db()
    db["bug_reports"].append(bug_report)
    _save_feedback_db(db)
    
    logger.info(f"✅ Bug report submitted: {bug_id}")
    
    return {
        "success": True,
        "message": "Bug report submitted successfully",
        "bug_id": bug_id,
        "bug_report": bug_report
    }


def _calculate_priority_score(severity: str, sentiment_score: float) -> float:
    """Calculate priority score for bug report"""
    severity_scores = {
        "critical": 10,
        "high": 8,
        "medium": 5,
        "low": 3
    }
    
    score = severity_scores.get(severity, 5)
    
    if sentiment_score < -5:
        score += 3
    elif sentiment_score < -3:
        score += 2
    
    return min(score, 10)


def reply_to_feedback(
    feedback_id: str,
    admin_id: str,
    message: str,
    admin_name: str = None
) -> Dict[str, Any]:
    """Reply to feedback (admin only)."""
    
    logger.info(f"📨 Replying to feedback: {feedback_id}")
    
    if not feedback_id:
        return {"success": False, "message": "Feedback ID is required"}
    
    if not message or len(message.strip()) < 2:
        return {"success": False, "message": "Message must be at least 2 characters"}
    
    db = _load_feedback_db()
    
    feedback = None
    feedback_index = -1
    for i, f in enumerate(db.get("feedbacks", [])):
        if f.get("feedback_id") == feedback_id:
            feedback = f
            feedback_index = i
            break
    
    if not feedback:
        return {"success": False, "message": "Feedback not found"}
    
    reply = {
        "reply_id": _generate_id("reply"),
        "admin_id": admin_id,
        "admin_name": admin_name or admin_id,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    feedback["replies"].append(reply)
    feedback["status"] = FeedbackStatus.REPLIED.value
    feedback["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    db["feedbacks"][feedback_index] = feedback
    _save_feedback_db(db)
    
    logger.info(f"✅ Reply added to feedback: {feedback_id}")
    
    if feedback.get("email") and FEEDBACK_CONFIG.get("notification_enabled", True):
        _send_notification(
            feedback["email"],
            "New Reply to Your Feedback",
            f"Your feedback #{feedback_id} has received a reply."
        )
    
    return {
        "success": True,
        "message": "Reply added successfully",
        "reply": reply,
        "feedback_status": feedback["status"]
    }


def resolve_feedback(
    feedback_id: str,
    admin_id: str,
    resolution: str,
    resolution_notes: str = ""
) -> Dict[str, Any]:
    """Resolve feedback (admin only)."""
    
    logger.info(f"✅ Resolving feedback: {feedback_id}")
    
    if not feedback_id:
        return {"success": False, "message": "Feedback ID is required"}
    
    valid_resolutions = [r.value for r in Resolution]
    if resolution not in valid_resolutions:
        return {"success": False, "message": f"Invalid resolution. Must be one of: {', '.join(valid_resolutions)}"}
    
    db = _load_feedback_db()
    
    feedback = None
    feedback_index = -1
    for i, f in enumerate(db.get("feedbacks", [])):
        if f.get("feedback_id") == feedback_id:
            feedback = f
            feedback_index = i
            break
    
    if not feedback:
        return {"success": False, "message": "Feedback not found"}
    
    feedback["status"] = FeedbackStatus.RESOLVED.value
    feedback["resolution"] = resolution
    feedback["resolution_notes"] = resolution_notes
    feedback["resolved_at"] = datetime.now(timezone.utc).isoformat()
    feedback["resolved_by"] = admin_id
    feedback["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    db["feedbacks"][feedback_index] = feedback
    _save_feedback_db(db)
    
    logger.info(f"✅ Feedback resolved: {feedback_id}")
    
    return {
        "success": True,
        "message": "Feedback resolved successfully",
        "feedback_id": feedback_id,
        "resolution": resolution,
        "resolved_at": feedback["resolved_at"]
    }


def vote_feature_request(request_id: str, user_id: str) -> Dict[str, Any]:
    """Vote for a feature request."""
    
    logger.info(f"📊 Voting for feature request: {request_id}")
    
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    db = _load_feedback_db()
    
    feature_request = None
    request_index = -1
    for i, fr in enumerate(db.get("feature_requests", [])):
        if fr.get("request_id") == request_id:
            feature_request = fr
            request_index = i
            break
    
    if not feature_request:
        return {"success": False, "message": "Feature request not found"}
    
    if user_id in feature_request.get("voters", []):
        return {"success": False, "message": "You have already voted for this feature"}
    
    feature_request["votes"] = feature_request.get("votes", 0) + 1
    feature_request["voters"] = feature_request.get("voters", []) + [user_id]
    feature_request["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    db["feature_requests"][request_index] = feature_request
    _save_feedback_db(db)
    
    logger.info(f"✅ Vote added for feature request: {request_id}")
    
    return {
        "success": True,
        "message": "Vote added successfully",
        "total_votes": feature_request["votes"],
        "request_id": request_id
    }


# ============================================
# NOTIFICATION FUNCTIONS
# ============================================

def _send_notification(email: str, subject: str, message: str) -> bool:
    """Send email notification (placeholder)"""
    logger.info(f"📧 Notification sent to {email}: {subject}")
    return True


# ============================================
# QUERY FUNCTIONS
# ============================================

def get_feedback_by_user(user_id: str, limit: int = 50) -> Dict[str, Any]:
    """Get all feedback by a user with pagination"""
    if not _validate_user_id(user_id):
        return {"error": "Invalid user ID"}
    
    db = _load_feedback_db()
    feedbacks = db.get("feedbacks", [])
    
    user_feedback = [f for f in feedbacks if f.get("user_id") == user_id]
    user_feedback.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {
        "user_id": user_id,
        "total": len(user_feedback),
        "feedbacks": user_feedback[:limit],
        "has_more": len(user_feedback) > limit
    }


def get_feature_requests_by_user(user_id: str, limit: int = 50) -> Dict[str, Any]:
    """Get all feature requests by a user"""
    if not _validate_user_id(user_id):
        return {"error": "Invalid user ID"}
    
    db = _load_feedback_db()
    requests = db.get("feature_requests", [])
    
    user_requests = [r for r in requests if r.get("user_id") == user_id]
    user_requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {
        "user_id": user_id,
        "total": len(user_requests),
        "requests": user_requests[:limit]
    }


def get_bug_reports_by_user(user_id: str, limit: int = 50) -> Dict[str, Any]:
    """Get all bug reports by a user"""
    if not _validate_user_id(user_id):
        return {"error": "Invalid user ID"}
    
    db = _load_feedback_db()
    bugs = db.get("bug_reports", [])
    
    user_bugs = [b for b in bugs if b.get("user_id") == user_id]
    user_bugs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {
        "user_id": user_id,
        "total": len(user_bugs),
        "bugs": user_bugs[:limit]
    }


def get_all_feedback(
    status: str = None,
    category: str = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Get all feedback with filters"""
    db = _load_feedback_db()
    feedbacks = db.get("feedbacks", [])
    
    if status:
        feedbacks = [f for f in feedbacks if f.get("status") == status]
    
    if category:
        feedbacks = [f for f in feedbacks if f.get("category") == category]
    
    feedbacks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    total = len(feedbacks)
    paginated = feedbacks[offset:offset + limit]
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
        "feedbacks": paginated
    }


def get_all_feature_requests(
    status: str = None,
    sort_by: str = "votes",
    limit: int = 50
) -> Dict[str, Any]:
    """Get all feature requests with sorting"""
    db = _load_feedback_db()
    requests = db.get("feature_requests", [])
    
    if status:
        requests = [r for r in requests if r.get("status") == status]
    
    if sort_by == "votes":
        requests.sort(key=lambda x: x.get("votes", 0), reverse=True)
    elif sort_by == "date":
        requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    elif sort_by == "priority":
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        requests.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 2))
    
    total = len(requests)
    
    return {
        "total": total,
        "limit": limit,
        "requests": requests[:limit]
    }


def get_all_bug_reports(
    status: str = None,
    severity: str = None,
    limit: int = 50
) -> Dict[str, Any]:
    """Get all bug reports with filters"""
    db = _load_feedback_db()
    bugs = db.get("bug_reports", [])
    
    if status:
        bugs = [b for b in bugs if b.get("status") == status]
    
    if severity:
        bugs = [b for b in bugs if b.get("severity") == severity]
    
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    bugs.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 2))
    
    total = len(bugs)
    
    return {
        "total": total,
        "limit": limit,
        "bugs": bugs[:limit]
    }


def get_feedback_analytics() -> Dict[str, Any]:
    """Get comprehensive feedback analytics"""
    db = _load_feedback_db()
    
    feedbacks = db.get("feedbacks", [])
    feature_requests = db.get("feature_requests", [])
    bug_reports = db.get("bug_reports", [])
    
    # Feedback stats
    total_feedback = len(feedbacks)
    ratings = [f.get("rating", 0) for f in feedbacks if f.get("rating", 0) > 0]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    # Rating distribution
    rating_dist = {}
    for r in ratings:
        rating_dist[r] = rating_dist.get(r, 0) + 1
    
    # Status breakdown
    status_breakdown = {}
    for f in feedbacks:
        status = f.get("status", "open")
        status_breakdown[status] = status_breakdown.get(status, 0) + 1
    
    # Category breakdown
    category_breakdown = {}
    for f in feedbacks:
        category = f.get("category", "general")
        category_breakdown[category] = category_breakdown.get(category, 0) + 1
    
    # Sentiment breakdown
    sentiment_breakdown = {"positive": 0, "neutral": 0, "negative": 0}
    for f in feedbacks:
        sentiment = f.get("sentiment", "neutral")
        if sentiment in sentiment_breakdown:
            sentiment_breakdown[sentiment] += 1
    
    # Feature request stats
    fr_status = {}
    for fr in feature_requests:
        status = fr.get("status", "pending")
        fr_status[status] = fr_status.get(status, 0) + 1
    
    # Bug report stats
    bug_severity = {}
    bug_status = {}
    for bug in bug_reports:
        severity = bug.get("severity", "low")
        bug_severity[severity] = bug_severity.get(severity, 0) + 1
        
        status = bug.get("status", "open")
        bug_status[status] = bug_status.get(status, 0) + 1
    
    # Calculate resolution rate
    resolved = status_breakdown.get("resolved", 0) + status_breakdown.get("closed", 0)
    resolution_rate = (resolved / total_feedback * 100) if total_feedback > 0 else 0
    
    return {
        "total_feedback": total_feedback,
        "avg_rating": round(avg_rating, 2),
        "rating_distribution": rating_dist,
        "status_breakdown": status_breakdown,
        "category_breakdown": category_breakdown,
        "sentiment_breakdown": sentiment_breakdown,
        "resolution_rate": round(resolution_rate, 2),
        "feature_requests_total": len(feature_requests),
        "feature_requests_status": fr_status,
        "bug_reports_total": len(bug_reports),
        "bug_reports_severity": bug_severity,
        "bug_reports_status": bug_status
    }


# ============================================
# SURVEY FUNCTIONS
# ============================================

def create_satisfaction_survey(
    title: str,
    questions: List[Dict],
    target_users: str = "all",
    expires_at: str = None
) -> Dict[str, Any]:
    """Create a satisfaction survey."""
    
    logger.info(f"📋 Creating satisfaction survey: {title}")
    
    if not title or len(title.strip()) < 3:
        return {"success": False, "message": "Title must be at least 3 characters"}
    
    if not questions or len(questions) < 1:
        return {"success": False, "message": "At least one question is required"}
    
    survey_id = _generate_id("sv")
    
    survey = {
        "survey_id": survey_id,
        "title": title,
        "questions": questions,
        "target_users": target_users,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
        "is_active": True,
        "responses": [],
        "response_count": 0
    }
    
    db = _load_satisfaction_db()
    db["surveys"].append(survey)
    _save_satisfaction_db(db)
    
    logger.info(f"✅ Survey created: {survey_id}")
    
    return {
        "success": True,
        "message": "Survey created successfully",
        "survey_id": survey_id,
        "survey": survey
    }


def submit_survey_response(
    survey_id: str,
    user_id: str,
    answers: Dict
) -> Dict[str, Any]:
    """Submit a response to a satisfaction survey."""
    
    logger.info(f"📝 Submitting survey response from user: {user_id}")
    
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    db = _load_satisfaction_db()
    
    survey = None
    for s in db.get("surveys", []):
        if s.get("survey_id") == survey_id:
            survey = s
            break
    
    if not survey:
        return {"success": False, "message": "Survey not found"}
    
    if not survey.get("is_active", True):
        return {"success": False, "message": "Survey is no longer active"}
    
    # Check expiration
    expires_at = survey.get("expires_at")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > expiry:
                survey["is_active"] = False
                _save_satisfaction_db(db)
                return {"success": False, "message": "Survey has expired"}
        except:
            pass
    
    # Check if user already responded
    for response in survey.get("responses", []):
        if response.get("user_id") == user_id:
            return {"success": False, "message": "You have already responded to this survey"}
    
    response_entry = {
        "response_id": _generate_id("resp"),
        "user_id": user_id,
        "answers": answers,
        "submitted_at": datetime.now(timezone.utc).isoformat()
    }
    
    survey["responses"] = survey.get("responses", []) + [response_entry]
    survey["response_count"] = len(survey["responses"])
    survey["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    _save_satisfaction_db(db)
    
    logger.info(f"✅ Survey response submitted")
    
    return {
        "success": True,
        "message": "Survey response submitted successfully",
        "response": response_entry
    }


def get_survey_results(survey_id: str) -> Dict[str, Any]:
    """Get results of a satisfaction survey."""
    
    db = _load_satisfaction_db()
    
    survey = None
    for s in db.get("surveys", []):
        if s.get("survey_id") == survey_id:
            survey = s
            break
    
    if not survey:
        return {"error": "Survey not found"}
    
    responses = survey.get("responses", [])
    total_responses = len(responses)
    
    answer_stats = {}
    for response in responses:
        for q_id, answer in response.get("answers", {}).items():
            if q_id not in answer_stats:
                answer_stats[q_id] = []
            answer_stats[q_id].append(answer)
    
    stats = {}
    for q_id, answers in answer_stats.items():
        if answers and isinstance(answers[0], (int, float)):
            stats[q_id] = {
                "type": "numeric",
                "average": round(sum(answers) / len(answers), 2),
                "min": min(answers),
                "max": max(answers),
                "count": len(answers)
            }
        else:
            freq = {}
            for a in answers:
                freq[str(a)] = freq.get(str(a), 0) + 1
            stats[q_id] = {
                "type": "categorical",
                "frequencies": freq,
                "count": len(answers)
            }
    
    return {
        "survey_id": survey_id,
        "title": survey.get("title"),
        "total_responses": total_responses,
        "response_rate": (total_responses / survey.get("response_count", 1)) * 100 if survey.get("response_count", 0) > 0 else 0,
        "statistics": stats,
        "responses": responses
    }


def get_all_surveys(active_only: bool = True) -> Dict[str, Any]:
    """Get all surveys with optional active filter"""
    
    db = _load_satisfaction_db()
    surveys = db.get("surveys", [])
    
    if active_only:
        surveys = [s for s in surveys if s.get("is_active", True)]
    
    surveys.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {
        "total": len(surveys),
        "surveys": surveys
    }


# ============================================
# UI RENDER FUNCTION (For Streamlit)
# ============================================

def render_feature_19():
    """Render Feedback System UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 💬 Feedback System")
    st.markdown("*Apni raaye dein, feature request karein, ya bug report karein*")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Submit Feedback",
        "🚀 Feature Request",
        "🐛 Bug Report",
        "📊 Analytics",
        "📋 Surveys"
    ])
    
    # Tab 1: Submit Feedback
    with tab1:
        st.subheader("📝 Submit Feedback")
        
        user_id = st.text_input("User ID", value="test_user_001", key="fb_user_id_19")
        video_id = st.text_input("Video ID (optional)", key="fb_video_id_19")
        email = st.text_input("Email (optional)", key="fb_email_19")
        
        rating = st.slider("Rating", 1, 5, 4, key="fb_rating_19")
        comment = st.text_area("Comment", height=100, key="fb_comment_19")
        
        category = st.selectbox(
            "Category",
            [c.value for c in FeedbackCategory],
            key="fb_category_19"
        )
        
        is_anonymous = st.checkbox("Submit Anonymously", key="fb_anonymous_19")
        
        if st.button("Submit Feedback", key="fb_submit_btn_19"):
            if not comment and rating == 0:
                st.error("Please provide either rating or comment")
            else:
                result = submit_feedback(
                    user_id=user_id,
                    video_id=video_id if video_id else None,
                    rating=rating,
                    comment=comment,
                    category=category,
                    email=email if email else None,
                    is_anonymous=is_anonymous
                )
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    st.json(result["feedback"])
                else:
                    st.error(f"❌ {result['message']}")
    
    # Tab 2: Feature Request
    with tab2:
        st.subheader("🚀 Feature Request")
        
        fr_user_id = st.text_input("User ID", value="test_user_001", key="fr_user_id_19")
        fr_email = st.text_input("Email (optional)", key="fr_email_19")
        fr_title = st.text_input("Title", key="fr_title_19")
        fr_description = st.text_area("Description", height=100, key="fr_description_19")
        fr_priority = st.selectbox("Priority", [p.value for p in Priority], key="fr_priority_19")
        fr_category = st.selectbox("Category", [c.value for c in FeedbackCategory], key="fr_category_19")
        
        if st.button("Submit Feature Request", key="fr_submit_btn_19"):
            if not fr_title or not fr_description:
                st.error("Title and description are required")
            else:
                result = submit_feature_request(
                    user_id=fr_user_id,
                    title=fr_title,
                    description=fr_description,
                    priority=fr_priority,
                    category=fr_category,
                    email=fr_email if fr_email else None
                )
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    st.json(result["feature_request"])
                else:
                    st.error(f"❌ {result['message']}")
        
        st.markdown("---")
        st.markdown("### 📊 Top Feature Requests")
        top_requests = get_all_feature_requests(sort_by="votes", limit=5)
        for fr in top_requests.get("requests", []):
            with st.expander(f"{fr.get('title')} (⭐ {fr.get('votes', 0)} votes)"):
                st.caption(fr.get('description', ''))
                st.caption(f"Priority: {fr.get('priority')} | Category: {fr.get('category')}")
                if st.button(f"Vote", key=f"vote_{fr.get('request_id')}"):
                    result = vote_feature_request(fr.get('request_id'), fr_user_id)
                    if result["success"]:
                        st.success(f"✅ {result['message']} (Total: {result['total_votes']})")
                        st.rerun()
    
    # Tab 3: Bug Report
    with tab3:
        st.subheader("🐛 Bug Report")
        
        bug_user_id = st.text_input("User ID", value="test_user_001", key="bug_user_id_19")
        bug_email = st.text_input("Email (optional)", key="bug_email_19")
        bug_title = st.text_input("Title", key="bug_title_19")
        bug_description = st.text_area("Description", height=100, key="bug_description_19")
        bug_severity = st.selectbox("Severity", [p.value for p in Priority], key="bug_severity_19")
        bug_steps = st.text_area("Steps to Reproduce", height=80, key="bug_steps_19")
        
        if st.button("Submit Bug Report", key="bug_submit_btn_19"):
            if not bug_title or not bug_description:
                st.error("Title and description are required")
            else:
                steps = [s.strip() for s in bug_steps.split("\n") if s.strip()]
                result = submit_bug_report(
                    user_id=bug_user_id,
                    title=bug_title,
                    description=bug_description,
                    severity=bug_severity,
                    steps_to_reproduce=steps,
                    email=bug_email if bug_email else None
                )
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    st.json(result["bug_report"])
                else:
                    st.error(f"❌ {result['message']}")
    
    # Tab 4: Analytics
    with tab4:
        st.subheader("📊 Feedback Analytics")
        
        if st.button("Refresh Analytics", key="fb_refresh_analytics"):
            analytics = get_feedback_analytics()
            st.json(analytics)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Feedback", analytics.get("total_feedback", 0))
            with col2:
                st.metric("Average Rating", analytics.get("avg_rating", 0))
            with col3:
                st.metric("Resolution Rate", f"{analytics.get('resolution_rate', 0)}%")
            
            st.markdown("### 📊 Distribution")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Category Breakdown**")
                st.json(analytics.get("category_breakdown", {}))
            with col2:
                st.markdown("**Sentiment Breakdown**")
                st.json(analytics.get("sentiment_breakdown", {}))
    
    # Tab 5: Surveys
    with tab5:
        st.subheader("📋 Surveys")
        
        # Create Survey
        with st.expander("📝 Create Survey"):
            survey_title = st.text_input("Survey Title", key="survey_title_19")
            q1 = st.text_input("Question 1", key="survey_q1_19")
            q2 = st.text_input("Question 2 (optional)", key="survey_q2_19")
            q3 = st.text_input("Question 3 (optional)", key="survey_q3_19")
            
            if st.button("Create Survey", key="survey_create_btn_19"):
                if survey_title and q1:
                    questions = [{"id": "q1", "text": q1, "type": "text"}]
                    if q2:
                        questions.append({"id": "q2", "text": q2, "type": "text"})
                    if q3:
                        questions.append({"id": "q3", "text": q3, "type": "text"})
                    
                    result = create_satisfaction_survey(survey_title, questions)
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                    else:
                        st.error(f"❌ {result['message']}")
        
        # List Surveys
        surveys = get_all_surveys(active_only=True)
        st.markdown("### 📋 Active Surveys")
        for survey in surveys.get("surveys", []):
            with st.expander(f"📝 {survey.get('title')}"):
                st.caption(f"Created: {survey.get('created_at', '')[:10]}")
                st.caption(f"Responses: {survey.get('response_count', 0)}")
                questions = survey.get("questions", [])
                for q in questions:
                    st.caption(f"• {q.get('text')}")


# ============================================
# TEST FUNCTION
# ============================================

def test():
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_19_feedback.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    test_user = "test_feedback_user_001"
    admin_user = "admin_001"
    
    # Test 1: Submit feedback
    print("\n📝 Test 1: Submit feedback")
    result = submit_feedback(
        user_id=test_user,
        video_id="video_001",
        rating=4,
        comment="Great app! Very easy to use and the AI works well.",
        category="ux"
    )
    print(f"  Success: {result.get('success', False)}")
    if result.get("success"):
        feedback_id = result["feedback"]["feedback_id"]
        print(f"  Feedback ID: {feedback_id}")
        print(f"  Sentiment: {result['sentiment']['sentiment']}")
    
    # Test 2: Submit feature request
    print("\n📝 Test 2: Submit feature request")
    result = submit_feature_request(
        user_id=test_user,
        title="Add more background music options",
        description="It would be great to have more background music options for videos.",
        priority="high"
    )
    print(f"  Success: {result.get('success', False)}")
    if result.get("success"):
        fr_id = result["feature_request"]["request_id"]
        print(f"  Request ID: {fr_id}")
    
    # Test 3: Submit bug report
    print("\n📝 Test 3: Submit bug report")
    result = submit_bug_report(
        user_id=test_user,
        title="Video generation stuck at 50%",
        description="The video generation gets stuck at 50% progress.",
        severity="high",
        steps_to_reproduce=["Open app", "Generate video", "Wait"]
    )
    print(f"  Success: {result.get('success', False)}")
    if result.get("success"):
        bug_id = result["bug_report"]["bug_id"]
        print(f"  Bug ID: {bug_id}")
    
    # Test 4: Vote for feature request
    if fr_id:
        print("\n📝 Test 4: Vote for feature request")
        result = vote_feature_request(fr_id, test_user)
        print(f"  Success: {result.get('success', False)}")
        if result.get("success"):
            print(f"  Total votes: {result.get('total_votes')}")
    
    # Test 5: Get feedback by user
    print("\n📝 Test 5: Get feedback by user")
    result = get_feedback_by_user(test_user)
    print(f"  Total feedback: {result.get('total', 0)}")
    
    # Test 6: Get all feedback
    print("\n📝 Test 6: Get all feedback")
    result = get_all_feedback(limit=5)
    print(f"  Total: {result.get('total', 0)}")
    
    # Test 7: Get feedback analytics
    print("\n📝 Test 7: Get feedback analytics")
    analytics = get_feedback_analytics()
    print(f"  Total feedback: {analytics.get('total_feedback')}")
    print(f"  Average rating: {analytics.get('avg_rating')}")
    print(f"  Resolution rate: {analytics.get('resolution_rate')}%")
    
    # Test 8: Create satisfaction survey
    print("\n📝 Test 8: Create satisfaction survey")
    questions = [
        {"id": "q1", "text": "How satisfied are you with Filmaa?", "type": "rating", "scale": 5},
        {"id": "q2", "text": "What features would you like to see?", "type": "text"}
    ]
    result = create_satisfaction_survey(
        title="User Satisfaction Survey",
        questions=questions,
        target_users="all"
    )
    print(f"  Success: {result.get('success', False)}")
    if result.get("success"):
        survey_id = result["survey"]["survey_id"]
        print(f"  Survey ID: {survey_id}")
    
    # Test 9: Submit survey response
    if survey_id:
        print("\n📝 Test 9: Submit survey response")
        answers = {"q1": 4, "q2": "More templates please!"}
        result = submit_survey_response(survey_id, test_user, answers)
        print(f"  Success: {result.get('success', False)}")
    
    # Test 10: Reply to feedback
    if feedback_id:
        print("\n📝 Test 10: Reply to feedback")
        result = reply_to_feedback(
            feedback_id=feedback_id,
            admin_id=admin_user,
            message="Thank you for your feedback! We appreciate it."
        )
        print(f"  Success: {result.get('success', False)}")
    
    # Test 11: Resolve feedback
    if feedback_id:
        print("\n📝 Test 11: Resolve feedback")
        result = resolve_feedback(
            feedback_id=feedback_id,
            admin_id=admin_user,
            resolution="fixed",
            resolution_notes="Issue resolved in latest update"
        )
        print(f"  Success: {result.get('success', False)}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    test()

# ============================================
# END OF feature_19_feedback.py (COMPLETE FIX)
# ============================================