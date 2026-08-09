# ============================================
# FEATURE 18: LAUNCH DISCOUNT (COMPLETE FIX)
# Filename: feature_18_launch_discount.py
# ============================================
# Kya karta hai:
# First 500 early adopters ke liye lifetime 40% discount
# - 40% discount on all plans (Free, Pro, Pay-Per-Video)
# - Lifetime discount for early adopters
# - Countdown timer for remaining slots
# - Referral bonus (extra 5% per referral, up to 20%)
# - Discount code generation
# - Discount code validation
# - Discount usage tracking
# - Early adopter badge
# - Discount analytics
# ============================================

import os
import sys
import json
import shutil  # ✅ FIXED: Added shutil import
import uuid
import logging
import threading
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from decimal import Decimal, ROUND_HALF_UP
import re

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
if 'LAUNCH_DISCOUNT' not in dir():
    LAUNCH_DISCOUNT = {
        "discount_percent": 40,
        "max_users": 500,
        "duration_months": 6,
        "referral_bonus_percent": 5,
        "max_referral_bonus": 20,
        "code_length": 8
    }

# Safety check - ensure LAUNCH_DISCOUNT is always defined
if 'LAUNCH_DISCOUNT' not in globals():
    LAUNCH_DISCOUNT = {
        "discount_percent": 40,
        "max_users": 500,
        "duration_months": 6,
        "referral_bonus_percent": 5,
        "max_referral_bonus": 20,
        "code_length": 8
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

DISCOUNT_DB_FILE = os.path.join(PATHS.get('library', 'library'), "discount_db.json")
DB_LOCK = threading.RLock()

os.makedirs(PATHS.get('library', 'library'), exist_ok=True)

# Get discount config values
DISCOUNT_PERCENT = LAUNCH_DISCOUNT.get("discount_percent", 40)
MAX_DISCOUNT_USERS = LAUNCH_DISCOUNT.get("max_users", 500)
DISCOUNT_DURATION_MONTHS = LAUNCH_DISCOUNT.get("duration_months", 6)
REFERRAL_BONUS_PERCENT = LAUNCH_DISCOUNT.get("referral_bonus_percent", 5)
MAX_REFERRAL_BONUS = LAUNCH_DISCOUNT.get("max_referral_bonus", 20)
CODE_LENGTH = LAUNCH_DISCOUNT.get("code_length", 8)

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

def _load_discount_db() -> Dict[str, Any]:
    """Load discount database with caching"""
    cache_key = "discount_db"
    if cache_key in _CACHE and _is_cache_valid():
        return _CACHE[cache_key]
    
    with DB_LOCK:
        if not os.path.exists(DISCOUNT_DB_FILE):
            default_data = {
                "discount_users": [],
                "discount_codes": [],
                "referrals": [],
                "version": "2.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "statistics": {
                    "total_applications": 0,
                    "total_referrals": 0,
                    "total_savings": 0.0,
                    "daily_applications": {}
                }
            }
            try:
                with open(DISCOUNT_DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to create discount DB: {e}")
            _CACHE[cache_key] = default_data
            _update_cache_timestamp()
            return default_data
        
        try:
            with open(DISCOUNT_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "discount_users" not in data:
                    data["discount_users"] = []
                if "discount_codes" not in data:
                    data["discount_codes"] = []
                if "referrals" not in data:
                    data["referrals"] = []
                if "statistics" not in data:
                    data["statistics"] = {
                        "total_applications": 0,
                        "total_referrals": 0,
                        "total_savings": 0.0,
                        "daily_applications": {}
                    }
                if "created_at" not in data:
                    data["created_at"] = datetime.now(timezone.utc).isoformat()
                _CACHE[cache_key] = data
                _update_cache_timestamp()
                return data
        except Exception as e:
            logger.error(f"Failed to load discount DB: {e}")
            return {
                "discount_users": [],
                "discount_codes": [],
                "referrals": [],
                "version": "2.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "statistics": {
                    "total_applications": 0,
                    "total_referrals": 0,
                    "total_savings": 0.0,
                    "daily_applications": {}
                }
            }


def _save_discount_db(data: Dict[str, Any]) -> bool:
    """Save discount database with thread safety"""
    with DB_LOCK:
        try:
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Create backup
            if os.path.exists(DISCOUNT_DB_FILE):
                try:
                    backup_path = f"{DISCOUNT_DB_FILE}.backup"
                    shutil.copy2(DISCOUNT_DB_FILE, backup_path)
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")
            
            # Write to temporary file first
            temp_file = DISCOUNT_DB_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            os.replace(temp_file, DISCOUNT_DB_FILE)
            _invalidate_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to save discount data: {e}")
            return False


def _generate_discount_code() -> str:
    """Generate a secure unique discount code"""
    alphabet = string.ascii_uppercase + string.digits
    code = ''.join(secrets.choice(alphabet) for _ in range(CODE_LENGTH))
    return f"FILMAA{code}"


def _is_discount_active() -> bool:
    """Check if launch discount is still active"""
    db = _load_discount_db()
    active_users = len(db.get("discount_users", []))
    
    # Check if max users reached
    if active_users >= MAX_DISCOUNT_USERS:
        return False
    
    # Check if duration expired
    if DISCOUNT_DURATION_MONTHS > 0:
        # Calculate from first discount user or launch date
        if active_users > 0:
            first_user = db["discount_users"][0]
            created_at = first_user.get("created_at", datetime.now(timezone.utc).isoformat())
            start_date = datetime.fromisoformat(created_at)
            expiry_date = start_date + timedelta(days=DISCOUNT_DURATION_MONTHS * 30)
            if datetime.now(timezone.utc) > expiry_date:
                return False
        else:
            # If no users yet, check from DB creation date
            created_at = db.get("created_at")
            if created_at:
                start_date = datetime.fromisoformat(created_at)
                expiry_date = start_date + timedelta(days=DISCOUNT_DURATION_MONTHS * 30)
                if datetime.now(timezone.utc) > expiry_date:
                    return False
    
    return True


def _update_statistics(db: Dict[str, Any], key: str, increment: int = 1) -> None:
    """Update discount statistics"""
    if "statistics" not in db:
        db["statistics"] = {
            "total_applications": 0,
            "total_referrals": 0,
            "total_savings": 0.0,
            "daily_applications": {}
        }
    
    if key == "applications":
        db["statistics"]["total_applications"] = db["statistics"].get("total_applications", 0) + increment
        
        today = datetime.now(timezone.utc).date().isoformat()
        daily = db["statistics"].get("daily_applications", {})
        daily[today] = daily.get(today, 0) + increment
        db["statistics"]["daily_applications"] = daily
    elif key == "referrals":
        db["statistics"]["total_referrals"] = db["statistics"].get("total_referrals", 0) + increment
    elif key == "savings":
        db["statistics"]["total_savings"] = db["statistics"].get("total_savings", 0.0) + increment


def _validate_user_id(user_id: str) -> bool:
    """Validate user ID"""
    if not user_id or len(user_id.strip()) < 3:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', user_id))


# ============================================
# MAIN DISCOUNT FUNCTIONS
# ============================================

def get_discount_status() -> Dict[str, Any]:
    """Get current discount status with detailed information"""
    db = _load_discount_db()
    active_users = len(db.get("discount_users", []))
    is_active = _is_discount_active()
    
    remaining_slots = MAX_DISCOUNT_USERS - active_users if is_active else 0
    
    # Calculate time remaining
    time_remaining = None
    if is_active and active_users > 0:
        first_user = db["discount_users"][0]
        created_at = first_user.get("created_at", datetime.now(timezone.utc).isoformat())
        start_date = datetime.fromisoformat(created_at)
        expiry_date = start_date + timedelta(days=DISCOUNT_DURATION_MONTHS * 30)
        now = datetime.now(timezone.utc)
        
        if expiry_date > now:
            time_remaining = {
                "days": (expiry_date - now).days,
                "hours": ((expiry_date - now).seconds // 3600),
                "total_seconds": (expiry_date - now).total_seconds()
            }
    
    return {
        "is_active": is_active,
        "total_slots": MAX_DISCOUNT_USERS,
        "used_slots": active_users,
        "remaining_slots": max(0, remaining_slots),
        "discount_percent": DISCOUNT_PERCENT,
        "duration_months": DISCOUNT_DURATION_MONTHS,
        "referral_bonus": REFERRAL_BONUS_PERCENT,
        "max_referral_bonus": MAX_REFERRAL_BONUS,
        "time_remaining": time_remaining,
        "fill_percentage": (active_users / MAX_DISCOUNT_USERS * 100) if MAX_DISCOUNT_USERS > 0 else 0,
        "active_users": active_users
    }


def apply_discount(user_id: str, discount_code: str = None) -> Dict[str, Any]:
    """
    Apply launch discount to a user with proper validation.
    
    Parameters:
    - user_id (str): User ID
    - discount_code (str): Optional discount code for referral
    
    Returns:
    - dict: Discount application result
    """
    
    logger.info(f"🎯 Applying launch discount for user: {user_id}")
    
    # Input validation
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID. Must be at least 3 characters."}
    
    # Check if discount is active
    if not _is_discount_active():
        status = get_discount_status()
        return {
            "success": False,
            "message": "Launch discount is no longer available",
            "status": status
        }
    
    # Check if user already has discount
    db = _load_discount_db()
    for user in db.get("discount_users", []):
        if user.get("user_id") == user_id:
            if user.get("is_active", True):
                return {
                    "success": False,
                    "message": "User already has an active launch discount",
                    "discount": user
                }
            else:
                # Reactivate expired discount
                user["is_active"] = True
                user["reactivated_at"] = datetime.now(timezone.utc).isoformat()
                _save_discount_db(db)
                return {
                    "success": True,
                    "message": "Discount reactivated successfully",
                    "discount": user
                }
    
    # Validate discount code if provided
    referral_user_id = None
    if discount_code:
        code_valid = validate_discount_code(discount_code)
        if not code_valid.get("valid", False):
            return {
                "success": False,
                "message": code_valid.get("message", "Invalid discount code"),
                "code": discount_code
            }
        referral_user_id = code_valid.get("referred_by")
        
        # Mark code as used
        _use_discount_code(discount_code, user_id)
    
    # Apply discount
    now = datetime.now(timezone.utc)
    discount_entry = {
        "user_id": user_id,
        "discount_percent": DISCOUNT_PERCENT,
        "discount_code": _generate_discount_code(),
        "referred_by": referral_user_id,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=DISCOUNT_DURATION_MONTHS * 30)).isoformat(),
        "is_active": True,
        "used_count": 0,
        "total_savings": 0.0,
        "last_used": None
    }
    
    db["discount_users"].append(discount_entry)
    
    # Update statistics
    _update_statistics(db, "applications")
    
    # Add referral bonus if applicable
    if referral_user_id:
        referral_entry = {
            "referrer_id": referral_user_id,
            "referred_user_id": user_id,
            "bonus_percent": REFERRAL_BONUS_PERCENT,
            "created_at": now.isoformat(),
            "reward_applied": False
        }
        db["referrals"].append(referral_entry)
        _update_statistics(db, "referrals")
    
    _save_discount_db(db)
    
    logger.info(f"✅ Launch discount applied: {DISCOUNT_PERCENT}% off")
    logger.info(f"   Discount code: {discount_entry['discount_code']}")
    
    return {
        "success": True,
        "message": f"Launch discount applied successfully! {DISCOUNT_PERCENT}% off",
        "discount": discount_entry,
        "status": get_discount_status()
    }


def get_user_discount(user_id: str) -> Optional[Dict[str, Any]]:
    """Get discount info for a user"""
    if not _validate_user_id(user_id):
        return None
    
    db = _load_discount_db()
    for user in db.get("discount_users", []):
        if user.get("user_id") == user_id and user.get("is_active", True):
            # Check if expired
            expires_at = user.get("expires_at")
            if expires_at:
                try:
                    expiry_date = datetime.fromisoformat(expires_at)
                    if expiry_date < datetime.now(timezone.utc):
                        user["is_active"] = False
                        _save_discount_db(db)
                        return None
                except:
                    pass
            return user
    return None


def get_user_discount_percent(user_id: str) -> int:
    """Get discount percentage for a user (including referral bonus)"""
    discount = get_user_discount(user_id)
    if not discount:
        return 0
    
    base_discount = discount.get("discount_percent", 0)
    
    # Add referral bonus
    db = _load_discount_db()
    total_bonus = 0
    for referral in db.get("referrals", []):
        if referral.get("referrer_id") == user_id and not referral.get("reward_applied", False):
            total_bonus += REFERRAL_BONUS_PERCENT
            # Mark as applied
            referral["reward_applied"] = True
            _save_discount_db(db)
    
    # Cap at max referral bonus
    total_bonus = min(total_bonus, MAX_REFERRAL_BONUS)
    
    return base_discount + total_bonus


def calculate_discounted_price(original_price: float, user_id: str) -> Dict[str, Any]:
    """Calculate discounted price for a user"""
    if not _validate_user_id(user_id):
        return {
            "original_price": original_price,
            "discount_percent": 0,
            "discount_amount": 0,
            "final_price": original_price,
            "has_discount": False,
            "error": "Invalid user ID"
        }
    
    discount_percent = get_user_discount_percent(user_id)
    
    if discount_percent == 0:
        return {
            "original_price": original_price,
            "discount_percent": 0,
            "discount_amount": 0,
            "final_price": original_price,
            "has_discount": False
        }
    
    discount_amount = original_price * (discount_percent / 100)
    final_price = original_price - discount_amount
    
    # Round to 2 decimal places
    final_price = Decimal(str(final_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    discount_amount = Decimal(str(discount_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Update user's total savings
    db = _load_discount_db()
    for user in db.get("discount_users", []):
        if user.get("user_id") == user_id:
            user["total_savings"] = user.get("total_savings", 0.0) + float(discount_amount)
            user["used_count"] = user.get("used_count", 0) + 1
            user["last_used"] = datetime.now(timezone.utc).isoformat()
            break
    _save_discount_db(db)
    
    # Update global statistics
    _update_statistics(db, "savings", float(discount_amount))
    
    return {
        "original_price": float(original_price),
        "discount_percent": discount_percent,
        "discount_amount": float(discount_amount),
        "final_price": float(final_price),
        "has_discount": True,
        "savings": float(discount_amount)
    }


# ============================================
# DISCOUNT CODE FUNCTIONS
# ============================================

def generate_discount_code(user_id: str = None, custom_code: str = None) -> Dict[str, Any]:
    """Generate a new discount code"""
    
    if custom_code:
        # Validate custom code
        if not custom_code.isalnum() or len(custom_code) < 6:
            return {"success": False, "message": "Custom code must be alphanumeric and at least 6 characters"}
        
        # Check if code already exists
        db = _load_discount_db()
        for entry in db.get("discount_codes", []):
            if entry.get("code") == custom_code:
                return {"success": False, "message": "Code already exists"}
        code = custom_code
    else:
        code = _generate_discount_code()
    
    db = _load_discount_db()
    code_entry = {
        "code": code,
        "created_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_used": False,
        "used_by": None,
        "used_at": None,
        "max_uses": 1,
        "use_count": 0,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    }
    
    if "discount_codes" not in db:
        db["discount_codes"] = []
    
    db["discount_codes"].append(code_entry)
    _save_discount_db(db)
    
    logger.info(f"✅ Discount code generated: {code}")
    
    return {
        "success": True,
        "code": code,
        "message": "Discount code generated successfully"
    }


def validate_discount_code(code: str) -> Dict[str, Any]:
    """Validate a discount code"""
    if not code:
        return {"valid": False, "message": "Code is required"}
    
    if not code.startswith("FILMAA") or len(code) != 5 + CODE_LENGTH:
        return {"valid": False, "message": "Invalid code format"}
    
    db = _load_discount_db()
    
    for entry in db.get("discount_codes", []):
        if entry.get("code") == code:
            # Check if expired
            expires_at = entry.get("expires_at")
            if expires_at:
                try:
                    expiry_date = datetime.fromisoformat(expires_at)
                    if expiry_date < datetime.now(timezone.utc):
                        return {"valid": False, "message": "Discount code has expired"}
                except:
                    pass
            
            # Check usage limit
            max_uses = entry.get("max_uses", 1)
            use_count = entry.get("use_count", 0)
            if use_count >= max_uses:
                return {"valid": False, "message": "Discount code has reached maximum uses"}
            
            if entry.get("is_used", False):
                return {"valid": False, "message": "Discount code has already been used"}
            
            return {
                "valid": True,
                "message": "Discount code is valid",
                "referred_by": entry.get("created_by"),
                "code_data": entry
            }
    
    return {"valid": False, "message": "Invalid discount code"}


def _use_discount_code(code: str, user_id: str) -> bool:
    """Mark a discount code as used"""
    db = _load_discount_db()
    for entry in db.get("discount_codes", []):
        if entry.get("code") == code:
            entry["is_used"] = True
            entry["used_by"] = user_id
            entry["used_at"] = datetime.now(timezone.utc).isoformat()
            entry["use_count"] = entry.get("use_count", 0) + 1
            _save_discount_db(db)
            return True
    return False


def use_discount_code(code: str, user_id: str) -> Dict[str, Any]:
    """Use a discount code (public API)"""
    
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    validation = validate_discount_code(code)
    if not validation.get("valid", False):
        return {"success": False, "message": validation.get("message")}
    
    if _use_discount_code(code, user_id):
        return {
            "success": True,
            "message": "Discount code used successfully",
            "code": code
        }
    
    return {"success": False, "message": "Failed to use discount code"}


# ============================================
# EARLY ADOPTER BADGE FUNCTIONS
# ============================================

def get_early_adopter_badge(user_id: str) -> Dict[str, Any]:
    """Get early adopter badge info for a user"""
    if not _validate_user_id(user_id):
        return {
            "has_badge": False,
            "message": "Invalid user ID"
        }
    
    discount = get_user_discount(user_id)
    
    if not discount:
        return {
            "has_badge": False,
            "message": "User is not an early adopter"
        }
    
    created_at = datetime.fromisoformat(discount.get("created_at"))
    now = datetime.now(timezone.utc)
    days_since = (now - created_at).days
    
    rank = get_early_adopter_rank(user_id)
    
    # Determine badge tier
    if rank <= 100:
        tier = "Diamond"
        color = "#FF6B6B"
        emoji = "💎"
    elif rank <= 250:
        tier = "Gold"
        color = "#FFD700"
        emoji = "🥇"
    elif rank <= 400:
        tier = "Silver"
        color = "#C0C0C0"
        emoji = "🥈"
    else:
        tier = "Bronze"
        color = "#CD7F32"
        emoji = "🥉"
    
    return {
        "has_badge": True,
        "badge_name": f"{emoji} {tier} Early Adopter",
        "badge_color": color,
        "badge_description": f"One of the first {MAX_DISCOUNT_USERS} users to join Filmaa",
        "discount_percent": discount.get("discount_percent", DISCOUNT_PERCENT),
        "joined_at": discount.get("created_at"),
        "days_since": days_since,
        "rank": rank,
        "tier": tier,
        "total_savings": discount.get("total_savings", 0.0)
    }


def get_early_adopter_rank(user_id: str) -> int:
    """Get early adopter rank (1-500)"""
    if not _validate_user_id(user_id):
        return 0
    
    db = _load_discount_db()
    discount_users = db.get("discount_users", [])
    
    # Sort by creation date
    sorted_users = sorted(discount_users, key=lambda x: x.get("created_at", ""))
    
    for i, user in enumerate(sorted_users):
        if user.get("user_id") == user_id:
            return i + 1
    
    return 0


def get_early_adopter_list(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Get list of early adopters with pagination"""
    db = _load_discount_db()
    discount_users = db.get("discount_users", [])
    
    # Sort by creation date
    discount_users.sort(key=lambda x: x.get("created_at", ""))
    
    total = len(discount_users)
    paginated = discount_users[offset:offset + limit]
    
    result = []
    for i, user in enumerate(paginated):
        result.append({
            "rank": offset + i + 1,
            "user_id": user.get("user_id"),
            "joined_at": user.get("created_at"),
            "discount_percent": user.get("discount_percent", DISCOUNT_PERCENT),
            "is_active": user.get("is_active", True),
            "total_savings": user.get("total_savings", 0.0)
        })
    
    return {
        "users": result,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total
    }


# ============================================
# REFERRAL FUNCTIONS
# ============================================

def get_referral_stats(user_id: str) -> Dict[str, Any]:
    """Get referral statistics for a user"""
    if not _validate_user_id(user_id):
        return {"error": "Invalid user ID"}
    
    db = _load_discount_db()
    referrals = db.get("referrals", [])
    
    user_referrals = [r for r in referrals if r.get("referrer_id") == user_id]
    total_referrals = len(user_referrals)
    
    # Calculate bonus
    total_bonus = total_referrals * REFERRAL_BONUS_PERCENT
    total_bonus = min(total_bonus, MAX_REFERRAL_BONUS)
    
    # Check if user has discount
    has_discount = get_user_discount(user_id) is not None
    
    return {
        "user_id": user_id,
        "total_referrals": total_referrals,
        "total_bonus_percent": total_bonus,
        "next_referral_bonus": REFERRAL_BONUS_PERCENT,
        "max_bonus_percent": MAX_REFERRAL_BONUS,
        "referrals_remaining": max(0, (MAX_REFERRAL_BONUS // REFERRAL_BONUS_PERCENT) - total_referrals),
        "has_discount": has_discount,
        "referrals": user_referrals
    }


def get_referral_link(user_id: str) -> Dict[str, Any]:
    """Generate a referral link for a user"""
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    discount = get_user_discount(user_id)
    
    if not discount:
        return {
            "success": False,
            "message": "User must have launch discount to refer others"
        }
    
    code = discount.get("discount_code", "")
    
    referral_link = f"https://filmaa.com/signup?ref={code}"
    
    return {
        "success": True,
        "referral_link": referral_link,
        "code": code,
        "message": "Share this link to earn referral bonuses!",
        "bonus_per_referral": REFERRAL_BONUS_PERCENT,
        "max_bonus": MAX_REFERRAL_BONUS
    }


# ============================================
# DISCOUNT ANALYTICS
# ============================================

def get_discount_analytics(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """Get detailed discount analytics with date filtering"""
    db = _load_discount_db()
    discount_users = db.get("discount_users", [])
    referrals = db.get("referrals", [])
    
    # Filter by date if provided
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            discount_users = [u for u in discount_users if datetime.fromisoformat(u.get("created_at", "")) >= start]
            referrals = [r for r in referrals if datetime.fromisoformat(r.get("created_at", "")) >= start]
        except:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            discount_users = [u for u in discount_users if datetime.fromisoformat(u.get("created_at", "")) <= end]
            referrals = [r for r in referrals if datetime.fromisoformat(r.get("created_at", "")) <= end]
        except:
            pass
    
    total_users = len(discount_users)
    active_users = len([u for u in discount_users if u.get("is_active", True)])
    expired_users = total_users - active_users
    
    total_referrals = len(referrals)
    unique_referrers = len(set(r.get("referrer_id") for r in referrals))
    
    # Calculate average discount
    discounts = [u.get("discount_percent", 0) for u in discount_users]
    avg_discount = sum(discounts) / total_users if total_users > 0 else 0
    
    # Calculate total savings
    total_savings = sum(u.get("total_savings", 0.0) for u in discount_users)
    
    # Daily signups
    daily_signups = {}
    for user in discount_users:
        try:
            date = datetime.fromisoformat(user.get("created_at", datetime.now(timezone.utc).isoformat())).date().isoformat()
            daily_signups[date] = daily_signups.get(date, 0) + 1
        except:
            pass
    
    # Referral conversion rate
    conversion_rate = (total_referrals / total_users * 100) if total_users > 0 else 0
    
    # Projected remaining time
    remaining_slots = MAX_DISCOUNT_USERS - total_users
    days_remaining = None
    if remaining_slots > 0 and total_users > 0 and DISCOUNT_DURATION_MONTHS > 0:
        first_user = db.get("discount_users", [])[0] if db.get("discount_users") else None
        if first_user:
            try:
                start_date_actual = datetime.fromisoformat(first_user.get("created_at", datetime.now(timezone.utc).isoformat()))
                expiry_date_actual = start_date_actual + timedelta(days=DISCOUNT_DURATION_MONTHS * 30)
                now = datetime.now(timezone.utc)
                if expiry_date_actual > now:
                    days_remaining = (expiry_date_actual - now).days
            except:
                pass
    
    return {
        "total_early_adopters": total_users,
        "active_discounts": active_users,
        "expired_discounts": expired_users,
        "total_referrals": total_referrals,
        "unique_referrers": unique_referrers,
        "average_discount_percent": round(avg_discount, 2),
        "referral_conversion_rate": round(conversion_rate, 2),
        "daily_signups": daily_signups,
        "remaining_slots": max(0, remaining_slots),
        "is_active": _is_discount_active(),
        "total_savings": round(total_savings, 2),
        "days_remaining": days_remaining,
        "fill_percentage": (total_users / MAX_DISCOUNT_USERS * 100) if MAX_DISCOUNT_USERS > 0 else 0,
        "statistics": db.get("statistics", {})
    }


def reset_discount_stats() -> Dict[str, Any]:
    """Reset discount statistics (admin function)"""
    
    if DRY_RUN:
        return {"success": True, "message": "Statistics would be reset (dry run)"}
    
    db = _load_discount_db()
    db["statistics"] = {
        "total_applications": 0,
        "total_referrals": 0,
        "total_savings": 0.0,
        "daily_applications": {},
        "reset_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Reset individual user savings
    for user in db.get("discount_users", []):
        user["total_savings"] = 0.0
        user["used_count"] = 0
        user["last_used"] = None
    
    _save_discount_db(db)
    
    return {
        "success": True,
        "message": "Statistics reset successfully"
    }


# ============================================
# ADMIN FUNCTIONS
# ============================================

def get_all_discount_codes(include_used: bool = False) -> List[Dict[str, Any]]:
    """Get all discount codes (admin function)"""
    db = _load_discount_db()
    codes = db.get("discount_codes", [])
    
    if not include_used:
        codes = [c for c in codes if not c.get("is_used", False)]
    
    return codes


def revoke_discount(user_id: str, reason: str = "") -> Dict[str, Any]:
    """Revoke a user's discount (admin function)"""
    
    if not _validate_user_id(user_id):
        return {"success": False, "message": "Invalid user ID"}
    
    db = _load_discount_db()
    found = False
    
    for user in db.get("discount_users", []):
        if user.get("user_id") == user_id:
            user["is_active"] = False
            user["revoked_at"] = datetime.now(timezone.utc).isoformat()
            user["revoke_reason"] = reason
            found = True
            break
    
    if not found:
        return {"success": False, "message": "User not found in discount list"}
    
    _save_discount_db(db)
    logger.info(f"🔒 Discount revoked for user: {user_id}")
    
    return {
        "success": True,
        "message": f"Discount revoked for user: {user_id}",
        "user_id": user_id,
        "reason": reason
    }


# ============================================
# UI RENDER FUNCTION (For Streamlit)
# ============================================

def render_feature_18():
    """Render Launch Discount UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 🎯 Launch Discount")
    st.markdown("*First 500 early adopters ko lifetime 40% discount*")
    
    # Get discount status
    status = get_discount_status()
    
    # Show status
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎟️ Total Slots", status.get("total_slots", 500))
    with col2:
        st.metric("✅ Used Slots", status.get("used_slots", 0))
    with col3:
        st.metric("📊 Remaining", status.get("remaining_slots", 0))
    with col4:
        st.metric("🎯 Discount", f"{status.get('discount_percent', 40)}%")
    
    # Progress bar
    fill_pct = status.get("fill_percentage", 0)
    st.progress(fill_pct / 100)
    st.caption(f"🔥 {fill_pct:.1f}% filled - {status.get('remaining_slots', 0)} slots remaining")
    
    # Time remaining
    time_remaining = status.get("time_remaining")
    if time_remaining:
        st.info(f"⏰ {time_remaining.get('days', 0)} days {time_remaining.get('hours', 0)} hours remaining")
    else:
        st.warning("⚠️ Discount offer has expired or not started yet")
    
    # Apply discount
    st.markdown("---")
    st.markdown("### 🎯 Apply Discount")
    
    user_id = st.text_input("User ID", placeholder="Enter your user ID...", key="discount_user_id_18")
    discount_code = st.text_input("Referral Code (optional)", placeholder="Enter referral code...", key="discount_code_input_18")
    
    if st.button("Apply Launch Discount", key="apply_discount_btn_18"):
        if user_id:
            result = apply_discount(user_id, discount_code if discount_code else None)
            if result["success"]:
                st.success(f"✅ {result['message']}")
                st.json(result.get("discount", {}))
            else:
                st.error(f"❌ {result['message']}")
        else:
            st.warning("Please enter a user ID")
    
    # Get user discount
    st.markdown("---")
    st.markdown("### 🔍 Check User Discount")
    
    check_user = st.text_input("Check User ID", placeholder="Enter user ID to check...", key="check_user_id_18")
    if st.button("Check Discount", key="check_discount_btn_18"):
        if check_user:
            discount = get_user_discount(check_user)
            if discount:
                st.success(f"✅ User has {discount.get('discount_percent')}% discount")
                st.json(discount)
            else:
                st.warning("No active discount found for this user")
        else:
            st.warning("Please enter a user ID")
    
    # Early adopters list
    with st.expander("🏆 Early Adopters List"):
        limit = st.slider("Show", 10, 100, 50, key="early_adopter_limit_18")
        offset = 0
        data = get_early_adopter_list(limit, offset)
        if data.get("users"):
            st.table(data["users"])
            if data.get("has_more"):
                st.caption(f"Showing {len(data['users'])} of {data.get('total', 0)} users")
        else:
            st.info("No early adopters yet. Be the first!")
    
    # Analytics
    with st.expander("📊 Analytics"):
        analytics = get_discount_analytics()
        st.json(analytics)
    
    # Generate discount code (admin)
    with st.expander("🔑 Generate Discount Code (Admin)"):
        custom_code = st.text_input("Custom Code (optional)", key="custom_code_18")
        if st.button("Generate Code", key="gen_code_btn_18"):
            result = generate_discount_code(None, custom_code if custom_code else None)
            if result["success"]:
                st.success(f"✅ Code generated: {result['code']}")
            else:
                st.error(f"❌ {result['message']}")


# ============================================
# TEST FUNCTION
# ============================================

def test():
    """Test the launch discount feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_18_launch_discount.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    test_user1 = "test_discount_user_001"
    test_user2 = "test_discount_user_002"
    
    # Test 1: Get discount status
    print("\n📝 Test 1: Get discount status")
    status = get_discount_status()
    print(f"  Is active: {status.get('is_active')}")
    print(f"  Total slots: {status.get('total_slots')}")
    print(f"  Used slots: {status.get('used_slots')}")
    print(f"  Remaining slots: {status.get('remaining_slots')}")
    print(f"  Discount: {status.get('discount_percent')}%")
    print(f"  Fill percentage: {status.get('fill_percentage'):.1f}%")
    
    # Test 2: Apply discount
    print("\n📝 Test 2: Apply discount")
    result = apply_discount(test_user1)
    print(f"  Success: {result.get('success', False)}")
    if result.get("success"):
        print(f"  Discount code: {result['discount'].get('discount_code')}")
    
    # Test 3: Get user discount
    print("\n📝 Test 3: Get user discount")
    discount = get_user_discount(test_user1)
    if discount:
        print(f"  Discount: {discount.get('discount_percent')}%")
        print(f"  Code: {discount.get('discount_code')}")
    
    # Test 4: Early adopter badge
    print("\n📝 Test 4: Early adopter badge")
    badge = get_early_adopter_badge(test_user1)
    if badge.get("has_badge"):
        print(f"  Badge: {badge.get('badge_name')}")
        print(f"  Rank: {badge.get('rank')}")
    
    # Test 5: Referral link
    print("\n📝 Test 5: Referral link")
    link = get_referral_link(test_user1)
    if link.get("success"):
        print(f"  Link: {link.get('referral_link')}")
    
    # Test 6: Analytics
    print("\n📝 Test 6: Analytics")
    analytics = get_discount_analytics()
    print(f"  Total early adopters: {analytics.get('total_early_adopters')}")
    print(f"  Total savings: ${analytics.get('total_savings')}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    test()

# ============================================
# END OF feature_18_launch_discount.py (COMPLETE FIX)
# ============================================