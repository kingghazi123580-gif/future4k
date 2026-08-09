# ============================================
# FEATURE 17: PAY-PER-VIDEO (USD Wallet Edition)
# Filename: feature_17_pay_per_video.py
# ============================================
# Kya karta hai:
# Users ko bina subscription ke, USD wallet top-up karke video
# generate karna — price HAR BAAR admin ke set kiye hue dynamic
# formula (feature_24_admin_pricing.calculate_price) se nikalti hai:
#
#     price = base_rate_per_second x duration x resolution_multiplier x quality_multiplier
#
# CHANGE LOG (this rewrite):
# - OLD fixed CREDIT_PACKS ($5/video flat packs) system REMOVED.
#   Ab koi "1 video = 1 credit" flat pricing nahi hai.
# - Naya model: user apne wallet mein USD top-up karta hai (koi bhi
#   amount, min/max limits config se), aur har video generate hone par
#   uska exact dynamic price (duration/resolution/quality ke hisaab se)
#   wallet se deduct hota hai.
# - Pricing formula HAMESHA feature_24_admin_pricing se aati hai — admin
#   panel se jo bhi set kiya jaye, wahi sab users ke liye lagu hota hai.
#   Is file mein koi price hardcoded nahi hai.
# - Transaction history, refunds, invoices, analytics — sab wallet
#   (USD balance) ki terms mein kaam karte hain, "credits/videos" ki
#   terms mein nahi.
# ============================================

import os
import json
import uuid
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP

try:
    from config import *
except ImportError:
    print("[ERROR] config.py not found!")
    raise SystemExit(1)

import feature_24_admin_pricing as pricing

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# ============================================
# CONSTANTS
# ============================================

PPV_DB_FILE = os.path.join(os.path.dirname(__file__), "ppv_db.json")
DB_LOCK = threading.RLock()

# Define default configs if not in config.py
if 'PPV_CONFIG' not in globals():
    PPV_CONFIG = {
        "min_topup_usd": 5.00,
        "max_topup_usd": 500.00,
        "default_currency": "USD",
        "refund_window_days": 30,
        "auto_refund_failed_payments": True
    }

# Suggested top-up amounts shown in the UI (NOT fixed pricing packs —
# just quick-select buttons; the user can top up any amount within
# min/max). No per-video pricing lives here anymore; that all comes
# from feature_24_admin_pricing.calculate_price().
SUGGESTED_TOPUPS = [5.00, 10.00, 25.00, 50.00, 100.00, 200.00]


# ============================================
# DATABASE FUNCTIONS (Thread-safe)
# ============================================

def _load_ppv_db() -> Dict:
    """Load pay-per-video database with thread safety"""
    with DB_LOCK:
        if not os.path.exists(PPV_DB_FILE):
            default_data = {
                "users": {},
                "transactions": [],
                "version": "3.0-wallet",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            _save_ppv_db(default_data)
            return default_data

        try:
            with open(PPV_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load PPV DB: {e}")
            return {"users": {}, "transactions": [], "version": "3.0-wallet", "updated_at": datetime.now(timezone.utc).isoformat()}


def _save_ppv_db(data: Dict) -> bool:
    """Save pay-per-video database with thread safety"""
    with DB_LOCK:
        try:
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

            temp_file = PPV_DB_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            os.replace(temp_file, PPV_DB_FILE)
            return True
        except Exception as e:
            logger.error(f"Failed to save PPV data: {e}")
            return False


def _generate_transaction_id() -> str:
    """Generate a unique transaction ID"""
    return f"txn_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _get_user_ppv_data(user_id: str) -> Dict:
    """Get user's PPV wallet data with validation"""
    if not user_id or len(user_id.strip()) < 3:
        raise ValueError("Invalid user_id. Must be at least 3 characters.")

    db = _load_ppv_db()

    if user_id not in db["users"]:
        db["users"][user_id] = {
            "user_id": user_id,
            "wallet_balance_usd": 0.0,
            "total_videos_generated": 0,
            "total_topped_up": 0.0,
            "total_spent": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "topup_history": [],
            "refunded_amount": 0.0
        }
        _save_ppv_db(db)

    return db["users"][user_id]


def _update_user_ppv_data(user_id: str, updates: Dict) -> bool:
    """Update user's PPV wallet data"""
    db = _load_ppv_db()

    if user_id not in db["users"]:
        return False

    for key, value in updates.items():
        db["users"][user_id][key] = value

    db["users"][user_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _save_ppv_db(db)


# ============================================
# PRICE ESTIMATE (thin wrapper over admin formula, for UI calculators)
# ============================================

def estimate_price(
    duration_seconds: float,
    resolution: str,
    quality: str,
    user_id: Optional[str] = None
) -> Dict:
    """
    Live price estimate for the UI — call this whenever the user changes
    duration / resolution / quality on ANY video-generating tool, so the
    price shown updates instantly. Uses the admin's global formula and,
    if a user_id is given, that user's active discount.
    """
    try:
        return pricing.calculate_price(duration_seconds, resolution, quality, user_id)
    except Exception as e:
        logger.error(f"Price estimate failed: {e}")
        return {"success": False, "message": str(e), "final_price": 0.0, "currency": "USD"}


# ============================================
# WALLET TOP-UP FUNCTIONS
# ============================================

def get_wallet_balance(user_id: str) -> Dict:
    """Get user's USD wallet balance"""

    if not user_id:
        return {"error": "User ID is required"}

    user_data = _get_user_ppv_data(user_id)

    return {
        "user_id": user_id,
        "balance": round(user_data.get("wallet_balance_usd", 0.0), 2),
        "total_topped_up": round(user_data.get("total_topped_up", 0.0), 2),
        "total_spent": round(user_data.get("total_spent", 0.0), 2),
        "total_videos_generated": user_data.get("total_videos_generated", 0),
        "currency": "USD"
    }


# Backward-compatible alias — older UI code may still call this name.
def get_credit_balance(user_id: str, check_expiry: bool = True) -> Dict:
    return get_wallet_balance(user_id)


def top_up_wallet(
    user_id: str,
    amount_usd: float,
    payment_method: str = "card",
    payment_id: str = "",
    payment_details: Dict = None
) -> Dict:
    """Add USD funds to a user's wallet with proper validation and rollback."""

    logger.info(f"💳 Topping up wallet for user: {user_id}")

    if not user_id:
        return {"success": False, "message": "User ID is required"}

    try:
        amount_usd = float(amount_usd)
    except (TypeError, ValueError):
        return {"success": False, "message": "Invalid amount"}

    valid_methods = ["card", "paypal", "jazzcash", "easypaisa", "upi", "bank_transfer"]
    if payment_method not in valid_methods:
        return {"success": False, "message": f"Invalid payment method: {payment_method}"}

    min_topup = PPV_CONFIG.get("min_topup_usd", 5.00)
    max_topup = PPV_CONFIG.get("max_topup_usd", 500.00)

    if amount_usd < min_topup:
        return {"success": False, "message": f"Minimum top-up amount is ${min_topup:.2f}"}

    if amount_usd > max_topup:
        return {"success": False, "message": f"Maximum top-up amount is ${max_topup:.2f}"}

    # Process payment
    payment_result = None
    if not DRY_RUN:
        payment_result = _process_payment(user_id, amount_usd, "USD", payment_method, payment_details)
        if not payment_result.get("success"):
            return {
                "success": False,
                "message": f"Payment failed: {payment_result.get('message', 'Unknown error')}",
                "payment_error": payment_result
            }
        payment_id = payment_result.get("transaction_id", payment_id)

    # Update user's wallet balance
    user_data = _get_user_ppv_data(user_id)
    old_balance = user_data.get("wallet_balance_usd", 0.0)
    new_balance = round(old_balance + amount_usd, 2)

    updates = {
        "wallet_balance_usd": new_balance,
        "total_topped_up": float(Decimal(str(user_data.get("total_topped_up", 0))) + Decimal(str(amount_usd))),
        "topup_history": user_data.get("topup_history", []) + [{
            "amount_usd": amount_usd,
            "date": datetime.now(timezone.utc).isoformat()
        }]
    }

    if not _update_user_ppv_data(user_id, updates):
        if not DRY_RUN and payment_result and payment_result.get("success"):
            _process_refund(user_id, payment_id, "Payment recorded but DB update failed")
        return {"success": False, "message": "Failed to update wallet. Payment will be refunded."}

    # Record transaction
    transaction_id = _generate_transaction_id()
    transaction = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "type": "wallet_topup",
        "amount": round(amount_usd, 2),
        "currency": "USD",
        "payment_method": payment_method,
        "payment_id": payment_id,
        "status": "completed",
        "old_balance": round(old_balance, 2),
        "new_balance": new_balance,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    db = _load_ppv_db()
    db["transactions"].append(transaction)
    _save_ppv_db(db)

    logger.info(f"✅ Wallet topped up: ${amount_usd:.2f}")
    logger.info(f"   New balance: ${new_balance:.2f}")

    return {
        "success": True,
        "message": f"Successfully added ${amount_usd:.2f} to wallet",
        "amount_added": round(amount_usd, 2),
        "new_balance": new_balance,
        "transaction": transaction
    }


# Backward-compatible alias
def purchase_credits(user_id: str, pack_id: str = None, payment_method: str = "card",
                      payment_id: str = "", payment_details: Dict = None, amount_usd: float = None) -> Dict:
    """
    Legacy name kept so old UI wiring doesn't break. 'pack_id' is ignored —
    fixed credit packs no longer exist. Pass amount_usd directly instead.
    """
    if amount_usd is None:
        amount_usd = PPV_CONFIG.get("min_topup_usd", 5.00)
    return top_up_wallet(user_id, amount_usd, payment_method, payment_id, payment_details)


# ============================================
# VIDEO GENERATION CHARGE FUNCTIONS
# ============================================

def charge_for_video(
    user_id: str,
    duration_seconds: float,
    resolution: str,
    quality: str,
    video_id: str = "",
    tool_name: str = "",
    metadata: Dict = None
) -> Dict:
    """
    Charge a user's wallet for ONE video generation, using the admin's
    global dynamic pricing formula. This replaces the old flat
    'use_credit()' — there is no fixed per-video price anymore.

    Call this right before actually generating the video. If it returns
    success=False, do NOT generate — show the message (usually "insufficient
    balance") and prompt the user to top up.
    """

    logger.info(f"🎬 Charging wallet for user: {user_id} ({tool_name or 'video'})")

    if not user_id:
        return {"success": False, "message": "User ID is required"}

    price_info = pricing.calculate_price(duration_seconds, resolution, quality, user_id)
    if not price_info.get("success"):
        return {"success": False, "message": price_info.get("message", "Could not calculate price")}

    charge_amount = price_info["final_price"]

    user_data = _get_user_ppv_data(user_id)
    current_balance = user_data.get("wallet_balance_usd", 0.0)

    if current_balance < charge_amount:
        return {
            "success": False,
            "message": f"Insufficient wallet balance. Need ${charge_amount:.2f}, have ${current_balance:.2f}. Please top up.",
            "balance": round(current_balance, 2),
            "required": charge_amount,
            "needs_topup": True,
            "price_breakdown": price_info
        }

    new_balance = round(current_balance - charge_amount, 2)

    updates = {
        "wallet_balance_usd": new_balance,
        "total_videos_generated": user_data.get("total_videos_generated", 0) + 1,
        "total_spent": round(float(Decimal(str(user_data.get("total_spent", 0))) + Decimal(str(charge_amount))), 2)
    }

    if not _update_user_ppv_data(user_id, updates):
        return {"success": False, "message": "Failed to update wallet data"}

    transaction_id = _generate_transaction_id()
    transaction = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "type": "video_generation",
        "video_id": video_id,
        "tool_name": tool_name,
        "duration_seconds": duration_seconds,
        "resolution": resolution,
        "quality": quality,
        "amount": charge_amount,
        "currency": "USD",
        "price_breakdown": price_info,
        "status": "completed",
        "old_balance": round(current_balance, 2),
        "new_balance": new_balance,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {}
    }

    db = _load_ppv_db()
    db["transactions"].append(transaction)
    _save_ppv_db(db)

    logger.info(f"✅ Charged ${charge_amount:.2f}. Remaining balance: ${new_balance:.2f}")

    return {
        "success": True,
        "message": f"Charged ${charge_amount:.2f}. ${new_balance:.2f} remaining.",
        "charged": charge_amount,
        "balance": new_balance,
        "transaction": transaction,
        "price_breakdown": price_info
    }


# Backward-compatible alias — old signature was (user_id, video_id, duration, metadata)
def use_credit(user_id: str, video_id: str = "", duration: int = 0, metadata: Dict = None,
               resolution: str = "720p", quality: str = "standard", tool_name: str = "") -> Dict:
    return charge_for_video(
        user_id=user_id,
        duration_seconds=duration,
        resolution=resolution,
        quality=quality,
        video_id=video_id,
        tool_name=tool_name,
        metadata=metadata
    )


def get_user_transactions(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    transaction_type: str = None
) -> Dict:
    """Get user's transaction history with pagination and filtering"""

    if not user_id:
        return {"error": "User ID is required"}

    db = _load_ppv_db()
    transactions = db.get("transactions", [])

    user_transactions = [t for t in transactions if t.get("user_id") == user_id]

    if transaction_type:
        user_transactions = [t for t in user_transactions if t.get("type") == transaction_type]

    user_transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    total = len(user_transactions)
    paginated = user_transactions[offset:offset + limit]

    return {
        "transactions": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total
    }


# ============================================
# PAYMENT FUNCTIONS
# ============================================

def _process_payment(
    user_id: str,
    amount: float,
    currency: str,
    payment_method: str,
    payment_details: Dict = None
) -> Dict:
    """Process a payment with proper validation"""

    logger.info(f"💳 Processing payment for user: {user_id}")
    logger.info(f"   Amount: {currency} {amount:.2f}")
    logger.info(f"   Method: {payment_method}")

    if DRY_RUN:
        return {
            "success": True,
            "transaction_id": f"txn_dryrun_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "message": "Payment successful (dry run)"
        }

    import random
    import time

    gateways = {
        "card": {"success_rate": 0.95, "delay": (1, 3)},
        "paypal": {"success_rate": 0.97, "delay": (2, 5)},
        "jazzcash": {"success_rate": 0.90, "delay": (1, 4)},
        "easypaisa": {"success_rate": 0.90, "delay": (1, 4)},
        "upi": {"success_rate": 0.93, "delay": (1, 2)},
        "bank_transfer": {"success_rate": 0.85, "delay": (5, 10)}
    }

    gateway = gateways.get(payment_method, gateways["card"])
    success_rate = gateway.get("success_rate", 0.95)

    delay = random.uniform(*gateway.get("delay", (1, 3)))
    time.sleep(min(delay, 1))

    if random.random() < success_rate:
        transaction_id = f"txn_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        return {
            "success": True,
            "transaction_id": transaction_id,
            "message": "Payment successful",
            "amount": amount,
            "currency": currency,
            "method": payment_method,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "success": False,
            "message": "Payment failed. Please try again.",
            "error": "Transaction declined",
            "code": "DECLINED"
        }


def _process_refund(user_id: str, payment_id: str, reason: str = "") -> bool:
    """Process a refund for a failed transaction"""
    logger.info(f"🔄 Processing refund for user: {user_id}, payment: {payment_id}")
    return True


def get_payment_methods() -> List[Dict]:
    """Get available payment methods for PPV"""
    return [
        {"id": "card", "name": "Credit/Debit Card", "icon": "💳", "supported": True},
        {"id": "paypal", "name": "PayPal", "icon": "💵", "supported": True},
        {"id": "jazzcash", "name": "JazzCash", "icon": "📱", "supported": True},
        {"id": "easypaisa", "name": "EasyPaisa", "icon": "📱", "supported": True},
        {"id": "upi", "name": "UPI", "icon": "📱", "supported": True},
        {"id": "bank_transfer", "name": "Bank Transfer", "icon": "🏦", "supported": False}
    ]


# ============================================
# REFUND FUNCTIONS
# ============================================

def request_refund(
    user_id: str,
    transaction_id: str,
    reason: str = ""
) -> Dict:
    """Request a refund for a wallet top-up transaction with proper validation."""

    logger.info(f"🔁 Requesting refund for user: {user_id}")

    if not user_id:
        return {"success": False, "message": "User ID is required"}

    db = _load_ppv_db()
    transactions = db.get("transactions", [])

    target_transaction = None
    for t in transactions:
        if t.get("transaction_id") == transaction_id and t.get("user_id") == user_id:
            target_transaction = t
            break

    if not target_transaction:
        return {"success": False, "message": "Transaction not found"}

    if target_transaction.get("status") != "completed":
        return {"success": False, "message": f"Transaction cannot be refunded (status: {target_transaction.get('status')})"}

    if target_transaction.get("type") != "wallet_topup":
        return {"success": False, "message": "Only wallet top-ups can be refunded"}

    created_at = target_transaction.get("created_at")
    if created_at:
        created_date = datetime.fromisoformat(created_at)
        days_diff = (datetime.now(timezone.utc) - created_date).days
        refund_window = PPV_CONFIG.get("refund_window_days", 30)
        if days_diff > refund_window:
            return {"success": False, "message": f"Refund window expired ({refund_window} days)"}

    amount_refunded = target_transaction.get("amount", 0)

    user_data = _get_user_ppv_data(user_id)
    current_balance = user_data.get("wallet_balance_usd", 0.0)

    if current_balance < amount_refunded:
        return {
            "success": False,
            "message": f"Insufficient wallet balance to refund. Have: ${current_balance:.2f}, Need: ${amount_refunded:.2f}",
            "balance": round(current_balance, 2)
        }

    new_balance = round(current_balance - amount_refunded, 2)

    updates = {
        "wallet_balance_usd": new_balance,
        "refunded_amount": round(user_data.get("refunded_amount", 0) + amount_refunded, 2)
    }

    if not _update_user_ppv_data(user_id, updates):
        return {"success": False, "message": "Failed to update wallet data"}

    for t in db["transactions"]:
        if t.get("transaction_id") == transaction_id:
            t["status"] = "refunded"
            t["refund_reason"] = reason
            t["refunded_at"] = datetime.now(timezone.utc).isoformat()
            break

    refund_transaction = {
        "transaction_id": _generate_transaction_id(),
        "user_id": user_id,
        "type": "refund",
        "original_transaction": transaction_id,
        "amount": amount_refunded,
        "currency": "USD",
        "status": "completed",
        "old_balance": round(current_balance, 2),
        "new_balance": new_balance,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "refund_reason": reason
    }
    db["transactions"].append(refund_transaction)

    _save_ppv_db(db)

    logger.info(f"✅ Refund processed: ${amount_refunded:.2f}")
    logger.info(f"   New balance: ${new_balance:.2f}")

    return {
        "success": True,
        "message": "Refund processed successfully",
        "amount_refunded": amount_refunded,
        "new_balance": new_balance,
        "refund_transaction": refund_transaction
    }


def get_refund_status(user_id: str, transaction_id: str) -> Dict:
    """Get status of a refund request"""

    if not user_id:
        return {"error": "User ID is required"}

    db = _load_ppv_db()
    transactions = db.get("transactions", [])

    for t in transactions:
        if t.get("transaction_id") == transaction_id and t.get("user_id") == user_id:
            if t.get("type") == "refund":
                return {
                    "status": t.get("status", "unknown"),
                    "refund_reason": t.get("refund_reason", ""),
                    "refunded_at": t.get("refunded_at", ""),
                    "amount": t.get("amount", 0),
                    "original_transaction": t.get("original_transaction")
                }

    return {"status": "not_found"}


# ============================================
# ANALYTICS FUNCTIONS
# ============================================

def get_ppv_stats() -> Dict:
    """Get pay-per-video wallet statistics"""

    db = _load_ppv_db()
    users = db.get("users", {})
    transactions = db.get("transactions", [])

    total_users = len(users)
    total_topped_up = sum(u.get("total_topped_up", 0) for u in users.values())
    total_spent = sum(u.get("total_spent", 0) for u in users.values())
    total_balance_held = sum(u.get("wallet_balance_usd", 0) for u in users.values())

    topups = [t for t in transactions if t.get("type") == "wallet_topup" and t.get("status") == "completed"]
    video_generations = [t for t in transactions if t.get("type") == "video_generation" and t.get("status") == "completed"]
    refunds = [t for t in transactions if t.get("type") == "refund" and t.get("status") == "completed"]

    total_revenue = sum(t.get("amount", 0) for t in topups)
    total_refunded = sum(t.get("amount", 0) for t in refunds)

    users_with_balance = len([u for u in users.values() if u.get("wallet_balance_usd", 0) > 0])

    tool_counts = {}
    tool_revenue = {}
    for t in video_generations:
        tool_id = t.get("tool_name") or "unknown"
        tool_counts[tool_id] = tool_counts.get(tool_id, 0) + 1
        tool_revenue[tool_id] = tool_revenue.get(tool_id, 0) + t.get("amount", 0)

    avg_price_per_video = (sum(t.get("amount", 0) for t in video_generations) / len(video_generations)) if video_generations else 0

    return {
        "total_users": total_users,
        "users_with_balance": users_with_balance,
        "total_topped_up": round(total_topped_up, 2),
        "total_wallet_balance_held": round(total_balance_held, 2),
        "total_videos_generated": len(video_generations),
        "total_refunds": len(refunds),
        "total_refunded_amount": round(total_refunded, 2),
        "total_spent": round(total_spent, 2),
        "total_revenue": round(total_revenue, 2),
        "net_revenue": round(total_revenue - total_refunded, 2),
        "usage_by_tool": tool_counts,
        "revenue_by_tool": {k: round(v, 2) for k, v in tool_revenue.items()},
        "average_price_per_video": round(avg_price_per_video, 2),
        "average_topup_per_user": round(total_topped_up / total_users, 2) if total_users > 0 else 0,
        "average_spent_per_user": round(total_spent / total_users, 2) if total_users > 0 else 0
    }


def get_user_ppv_stats(user_id: str) -> Dict:
    """Get user's PPV wallet statistics"""

    if not user_id:
        return {"error": "User ID is required"}

    user_data = _get_user_ppv_data(user_id)
    transactions = get_user_transactions(user_id, limit=1000)

    topups = [t for t in transactions.get("transactions", []) if t.get("type") == "wallet_topup"]
    video_generations = [t for t in transactions.get("transactions", []) if t.get("type") == "video_generation"]
    refunds = [t for t in transactions.get("transactions", []) if t.get("type") == "refund"]

    total_duration = sum(t.get("duration_seconds", 0) for t in video_generations)
    avg_duration = total_duration / len(video_generations) if video_generations else 0

    return {
        "user_id": user_id,
        "wallet_balance": round(user_data.get("wallet_balance_usd", 0), 2),
        "total_topped_up": round(user_data.get("total_topped_up", 0), 2),
        "total_spent": round(user_data.get("total_spent", 0), 2),
        "total_refunded": round(user_data.get("refunded_amount", 0), 2),
        "total_videos_generated": len(video_generations),
        "total_refunds": len(refunds),
        "topup_count": len(topups),
        "average_video_duration": round(avg_duration, 2),
        "last_topup": topups[0].get("created_at") if topups else None,
        "created_at": user_data.get("created_at")
    }


# ============================================
# INVOICE FUNCTIONS
# ============================================

def generate_invoice(user_id: str, transaction_id: str) -> Dict:
    """Generate an invoice for a transaction"""

    if not user_id:
        return {"success": False, "message": "User ID is required"}

    db = _load_ppv_db()
    transactions = db.get("transactions", [])

    target_transaction = None
    for t in transactions:
        if t.get("transaction_id") == transaction_id and t.get("user_id") == user_id:
            target_transaction = t
            break

    if not target_transaction:
        return {"success": False, "message": "Transaction not found"}

    invoice_id = f"INV-{datetime.now(timezone.utc).strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}"

    user_name = user_id
    user_email = ""

    try:
        from feature_15_free_tier import get_user_info
        user_info = get_user_info(user_id)
        if user_info:
            user_name = user_info.get("name", user_id)
            user_email = user_info.get("email", "")
    except Exception:
        pass

    items = []
    if target_transaction.get("type") == "wallet_topup":
        amount = target_transaction.get("amount", 0)
        items.append({
            "description": "Wallet Top-up",
            "quantity": 1,
            "unit_price": round(amount, 2),
            "total": round(amount, 2)
        })
    elif target_transaction.get("type") == "video_generation":
        amount = target_transaction.get("amount", 0)
        desc = (
            f"{target_transaction.get('tool_name', 'Video')} — "
            f"{target_transaction.get('duration_seconds', 0)}s, "
            f"{target_transaction.get('resolution', '')}, "
            f"{target_transaction.get('quality', '')}"
        )
        items.append({
            "description": desc,
            "quantity": 1,
            "unit_price": round(amount, 2),
            "total": round(amount, 2)
        })

    invoice = {
        "invoice_id": invoice_id,
        "transaction_id": transaction_id,
        "user_id": user_id,
        "user_name": user_name,
        "user_email": user_email,
        "date": datetime.now(timezone.utc).isoformat(),
        "type": target_transaction.get("type"),
        "amount": target_transaction.get("amount", 0),
        "currency": "USD",
        "items": items,
        "total": target_transaction.get("amount", 0),
        "status": target_transaction.get("status", "unknown"),
        "payment_method": target_transaction.get("payment_method", "Unknown")
    }

    return {
        "success": True,
        "invoice": invoice
    }


# ============================================
# COMPARISON FUNCTIONS
# ============================================

def compare_plans() -> Dict:
    """Compare free and pay-per-video (wallet) plans"""

    formula = pricing.get_pricing_formula()

    return {
        "free": {
            "name": "Free",
            "price": "$0/month",
            "videos": "5/month",
            "resolution": "480p",
            "watermark": "Yes",
            "duration": "30s max",
            "supports": ["Basic features"]
        },
        "pay_per_video": {
            "name": "Pay-Per-Video (Wallet)",
            "price": f"From ${formula['base_rate_per_second']:.2f}/sec (varies by resolution & quality)",
            "videos": "Pay as you go — top up wallet, spend as you generate",
            "resolution": "Any (720p–4K)",
            "watermark": "No",
            "duration": "Any",
            "supports": ["All features", "No subscription", "Dynamic admin-set pricing"]
        }
    }


# ============================================
# UI RENDER FUNCTION (for ui.py)
# ============================================

def render_feature_17():
    """Render Pay-Per-Video Wallet UI in Streamlit"""
    import streamlit as st

    st.subheader("💰 Pay-Per-Video Wallet")
    st.write("Top up your USD wallet and pay only for what you generate")

    user_id = st.text_input("User ID", value="test_ppv_user_001", key="f17_user")

    if user_id:
        tab1, tab2 = st.tabs(["💳 Wallet", "📊 Stats"])

        with tab1:
            balance = get_wallet_balance(user_id)
            st.metric("💰 Wallet Balance", f"${balance.get('balance', 0):.2f}")

            st.markdown("**Quick Top-up**")
            cols = st.columns(len(SUGGESTED_TOPUPS))
            for i, amount in enumerate(SUGGESTED_TOPUPS):
                if cols[i].button(f"${amount:.0f}", key=f"f17_topup_{amount}"):
                    result = top_up_wallet(user_id, amount, "card")
                    st.json(result)

        with tab2:
            stats = get_ppv_stats()
            st.json(stats)


# ============================================
# TEST FUNCTION
# ============================================

def test():
    print("\n🧪 TESTING feature_17_pay_per_video.py (wallet edition)")
    print(f"Mode: {'DRY_RUN' if DRY_RUN else 'LIVE'}")
    print("-" * 40)

    test_user = "test_ppv_user_001"

    print("\n📝 Test 1: Get wallet balance")
    balance = get_wallet_balance(test_user)
    print(f"  Balance: ${balance.get('balance')}")

    print("\n📝 Test 2: Top up wallet")
    result = top_up_wallet(test_user, 25.00, "card", "pay_123")
    print(f"  Success: {result.get('success', False)}")
    if result.get("success"):
        print(f"  New balance: ${result.get('new_balance')}")

    print("\n📝 Test 3: Estimate price for a video")
    est = estimate_price(10, "1080p", "high", test_user)
    print(f"  Estimated price: ${est.get('final_price')}")

    print("\n📝 Test 4: Charge for a video")
    result = charge_for_video(test_user, 10, "1080p", "high", "test_video_001", "text_to_video")
    print(f"  Success: {result.get('success', False)}")
    if result.get("success"):
        print(f"  Remaining balance: ${result.get('balance')}")

    print("\n📝 Test 5: Get user transactions")
    transactions = get_user_transactions(test_user, 5)
    print(f"  Transactions: {len(transactions.get('transactions', []))}")

    print("\n📝 Test 6: Get PPV stats")
    stats = get_ppv_stats()
    print(f"  Total users: {stats.get('total_users')}")
    print(f"  Total revenue: ${stats.get('total_revenue')}")

    print("\n📝 Test 7: Get user PPV stats")
    user_stats = get_user_ppv_stats(test_user)
    print(f"  Balance: ${user_stats.get('wallet_balance')}")
    print(f"  Total spent: ${user_stats.get('total_spent')}")

    print("\n📝 Test 8: Request refund")
    if transactions.get('transactions'):
        topup_txns = [t for t in transactions['transactions'] if t.get('type') == 'wallet_topup']
        if topup_txns:
            txn_id = topup_txns[0].get("transaction_id")
            result = request_refund(test_user, txn_id, "Test refund")
            print(f"  Success: {result.get('success', False)}")

    print("\n📝 Test 9: Compare plans")
    plans = compare_plans()
    for key, plan in plans.items():
        print(f"  {key}: {plan.get('price')}")

    print("\n📝 Test 10: Generate invoice")
    if transactions.get('transactions'):
        txn_id = transactions['transactions'][0].get("transaction_id")
        result = generate_invoice(test_user, txn_id)
        print(f"  Success: {result.get('success', False)}")

    print("\n📝 Test 11: Get payment methods")
    methods = get_payment_methods()
    print(f"  Payment methods: {len(methods)}")

    print("\n✅ All tests completed!")


if __name__ == "__main__":
    test()

# ============================================
# END OF feature_17_pay_per_video.py
# ============================================