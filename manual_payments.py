import os
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("manual_payments")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s [manual_payments] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    logger.addHandler(handler)

MAX_SINGLE_TOPUP_PKR = int(os.environ.get("MAX_SINGLE_TOPUP_PKR", "50000"))
MIN_SINGLE_TOPUP_PKR = int(os.environ.get("MIN_SINGLE_TOPUP_PKR", "100"))

JAZZCASH_NUMBER = os.environ.get("JAZZCASH_NUMBER", "03XX-XXXXXXX")
JAZZCASH_ACCOUNT_TITLE = os.environ.get("JAZZCASH_ACCOUNT_TITLE", "FUTURE 4K")

# Same "manual transfer, screenshot/txn-ID proof, admin approves" pattern
# extended to every method — each just needs its own account details set
# via env vars. PAYMENT_METHODS is the list users can pick from in the UI.
PAYMENT_METHODS = ["JazzCash", "Easypaisa", "Bank Transfer", "SadaPay", "NayaPay"]

EASYPAISA_NUMBER = os.environ.get("EASYPAISA_NUMBER", "")
EASYPAISA_ACCOUNT_TITLE = os.environ.get("EASYPAISA_ACCOUNT_TITLE", "FUTURE 4K")

SADAPAY_NUMBER = os.environ.get("SADAPAY_NUMBER", "")
SADAPAY_ACCOUNT_TITLE = os.environ.get("SADAPAY_ACCOUNT_TITLE", "FUTURE 4K")

NAYAPAY_NUMBER = os.environ.get("NAYAPAY_NUMBER", "")
NAYAPAY_ACCOUNT_TITLE = os.environ.get("NAYAPAY_ACCOUNT_TITLE", "FUTURE 4K")

BANK_ACCOUNT_TITLE = os.environ.get("BANK_ACCOUNT_TITLE", "")
BANK_ACCOUNT_NUMBER = os.environ.get("BANK_ACCOUNT_NUMBER", "")
BANK_IBAN = os.environ.get("BANK_IBAN", "")
BANK_NAME = os.environ.get("BANK_NAME", "")

try:
    import config
    DB_PATH = getattr(config, "PAYMENTS_DB_PATH", os.path.join("data", "payments.db"))
except ImportError:
    DB_PATH = os.path.join("data", "payments.db")

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
VALID_STATUSES = {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED}

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


def _get_db_connection() -> sqlite3.Connection:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topup_requests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         TEXT NOT NULL,
                user_email      TEXT DEFAULT '',
                amount          REAL NOT NULL,
                txn_id          TEXT NOT NULL,
                status          TEXT DEFAULT 'pending',
                admin_id        TEXT DEFAULT NULL,
                admin_note      TEXT DEFAULT NULL,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                wallet_txn_ref  TEXT DEFAULT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_topup_requests_status 
            ON topup_requests(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_topup_requests_user_id 
            ON topup_requests(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_topup_requests_txn_id 
            ON topup_requests(txn_id)
        """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pending_txn 
            ON topup_requests(txn_id) 
            WHERE status = 'pending'
        """)

        # Safe migration: adds the 'method' column to an existing table
        # without touching existing rows. Old rows (created before this
        # column existed) default to 'JazzCash' since that was the only
        # method available at the time.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(topup_requests)").fetchall()}
        if "method" not in existing_cols:
            conn.execute("ALTER TABLE topup_requests ADD COLUMN method TEXT DEFAULT 'JazzCash'")

        conn.commit()
        logger.info("Database initialized: topup_requests table ready")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        conn.close()


try:
    init_db()
except Exception as e:
    logger.warning(f"Could not auto-init DB on import (may be first run): {e}")


def _validate_amount(amount: float) -> Tuple[bool, str]:
    if not isinstance(amount, (int, float)):
        return False, "Amount must be a number"
    if amount < MIN_SINGLE_TOPUP_PKR:
        return False, f"Minimum top-up amount is Rs. {MIN_SINGLE_TOPUP_PKR}"
    if amount > MAX_SINGLE_TOPUP_PKR:
        return False, f"Maximum single top-up is Rs. {MAX_SINGLE_TOPUP_PKR:,}"
    if amount <= 0:
        return False, "Amount must be greater than zero"
    return True, ""


def _validate_txn_id(txn_id: str) -> Tuple[bool, str]:
    if not txn_id or not isinstance(txn_id, str):
        return False, "Transaction ID is required"
    txn_id = txn_id.strip()
    if len(txn_id) < 4:
        return False, "Transaction ID is too short (minimum 4 characters)"
    if len(txn_id) > 50:
        return False, "Transaction ID is too long (maximum 50 characters)"
    if not all(c.isalnum() or c in '-_' for c in txn_id):
        return False, "Transaction ID contains invalid characters"
    return True, ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row) if row is not None else {}


def create_request(
    user_id: str,
    amount: float,
    txn_id: str,
    method: str = "JazzCash",
    user_email: str = ""
) -> Dict[str, Any]:
    txn_id = txn_id.strip() if isinstance(txn_id, str) else ""
    user_email = user_email.strip().lower() if user_email else ""
    method = method if method in PAYMENT_METHODS else "JazzCash"

    is_valid, error_msg = _validate_amount(amount)
    if not is_valid:
        logger.warning(f"Amount validation failed for user {user_id}: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "error_code": "INVALID_AMOUNT"
        }

    is_valid, error_msg = _validate_txn_id(txn_id)
    if not is_valid:
        logger.warning(f"Txn ID validation failed for user {user_id}: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "error_code": "INVALID_TXN_ID"
        }

    now = _now_iso()
    conn = _get_db_connection()

    try:
        existing = conn.execute(
            "SELECT id, status FROM topup_requests WHERE txn_id = ? AND status = ?",
            (txn_id, STATUS_PENDING)
        ).fetchone()

        if existing:
            logger.warning(f"Duplicate txn_id attempt: {txn_id} by user {user_id}")
            return {
                "success": False,
                "message": (
                    f"This transaction ID ({txn_id}) has already been submitted "
                    f"and is pending review (Request #{existing['id']}). "
                    f"Please wait for admin approval or contact support."
                ),
                "error_code": "DUPLICATE_TXN_ID_PENDING",
                "existing_request_id": existing["id"]
            }

        existing_approved = conn.execute(
            "SELECT id FROM topup_requests WHERE txn_id = ? AND status = ?",
            (txn_id, STATUS_APPROVED)
        ).fetchone()

        if existing_approved:
            logger.warning(f"Attempt to reuse approved txn_id: {txn_id}")
            return {
                "success": False,
                "message": (
                    f"This transaction ID ({txn_id}) has already been approved "
                    f"(Request #{existing_approved['id']}). It cannot be reused."
                ),
                "error_code": "DUPLICATE_TXN_ID_APPROVED",
                "existing_request_id": existing_approved["id"]
            }

        cursor = conn.execute(
            """
            INSERT INTO topup_requests (user_id, user_email, amount, txn_id, method, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, user_email, amount, txn_id, method, STATUS_PENDING, now, now)
        )
        request_id = cursor.lastrowid
        conn.commit()

        logger.info(
            f"Top-up request #{request_id} created: user={user_id}, "
            f"amount=Rs.{amount}, txn_id={txn_id}"
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": (
                f"Top-up request for Rs. {amount:,.0f} submitted successfully. "
                f"Your request (#{request_id}) is pending admin review."
            ),
            "status": STATUS_PENDING,
            "amount": amount,
            "txn_id": txn_id
        }

    except sqlite3.IntegrityError as e:
        logger.error(f"Integrity error creating request: {e}")
        return {
            "success": False,
            "message": "This transaction ID has already been submitted.",
            "error_code": "DUPLICATE_TXN_ID"
        }
    except Exception as e:
        logger.exception(f"Unexpected error creating request: {e}")
        return {
            "success": False,
            "message": f"An unexpected error occurred. Please try again.",
            "error_code": "INTERNAL_ERROR"
        }
    finally:
        conn.close()


def approve_request(
    request_id: int,
    admin_id: str,
    admin_note: str = ""
) -> Dict[str, Any]:
    try:
        from feature_17_pay_per_video import top_up_wallet
    except ImportError as e:
        logger.critical(f"Cannot import feature_17_pay_per_video: {e}")
        return {
            "success": False,
            "message": "Payment system unavailable. Please check system configuration.",
            "error_code": "WALLET_SYSTEM_UNAVAILABLE"
        }

    now = _now_iso()
    conn = _get_db_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        request = conn.execute(
            "SELECT * FROM topup_requests WHERE id = ?",
            (request_id,)
        ).fetchone()

        if not request:
            conn.execute("ROLLBACK")
            logger.warning(f"Approval failed — request #{request_id} not found")
            return {
                "success": False,
                "message": f"Request #{request_id} not found.",
                "error_code": "REQUEST_NOT_FOUND"
            }

        if request["status"] != STATUS_PENDING:
            conn.execute("ROLLBACK")
            logger.warning(
                f"Approval failed — request #{request_id} is already {request['status']}"
            )
            return {
                "success": False,
                "message": (
                    f"Request #{request_id} is already {request['status']}. "
                    f"Only pending requests can be approved."
                ),
                "error_code": "REQUEST_NOT_PENDING",
                "current_status": request["status"]
            }

        wallet_result = top_up_wallet(
            request["user_id"],
            request["amount"],
            (request["method"] or "manual").lower().replace(" ", "_"),
        )

        if not wallet_result.get("success", False):
            conn.execute("ROLLBACK")
            logger.error(
                f"Wallet top-up failed for request #{request_id}: "
                f"{wallet_result.get('message', 'Unknown error')}"
            )
            return {
                "success": False,
                "message": (
                    f"Failed to credit wallet: {wallet_result.get('message', 'Unknown error')}. "
                    f"The request remains pending. Please try again."
                ),
                "error_code": "WALLET_CREDIT_FAILED"
            }

        wallet_txn_ref = f"topup_request_{request_id}_txn_{request['txn_id']}"

        conn.execute(
            """
            UPDATE topup_requests 
            SET status = ?, admin_id = ?, admin_note = ?, updated_at = ?, wallet_txn_ref = ?
            WHERE id = ?
            """,
            (STATUS_APPROVED, admin_id, admin_note, now, wallet_txn_ref, request_id)
        )
        conn.execute("COMMIT")

        logger.info(
            f"Request #{request_id} APPROVED by {admin_id}: "
            f"Rs. {request['amount']} credited to user {request['user_id']}"
        )

        return {
            "success": True,
            "message": (
                f"Request #{request_id} approved. "
                f"Rs. {request['amount']:,.0f} credited to user's wallet."
            ),
            "request_id": request_id,
            "user_id": request["user_id"],
            "user_email": request["user_email"],
            "amount_credited": request["amount"],
            "wallet_txn_ref": wallet_txn_ref,
            "admin_note": admin_note
        }

    except Exception as e:
        conn.execute("ROLLBACK")
        logger.exception(f"Unexpected error approving request #{request_id}: {e}")
        return {
            "success": False,
            "message": f"An unexpected error occurred during approval: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }
    finally:
        conn.close()


def reject_request(request_id: int, admin_id: str, reason: str = "") -> Dict[str, Any]:
    """Rejects a pending request. Never touches the wallet."""
    now = _now_iso()
    conn = _get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        request = conn.execute(
            "SELECT status FROM topup_requests WHERE id = ?", (request_id,)
        ).fetchone()

        if not request:
            conn.execute("ROLLBACK")
            return {"success": False, "message": f"Request #{request_id} not found.", "error_code": "REQUEST_NOT_FOUND"}

        if request["status"] != STATUS_PENDING:
            conn.execute("ROLLBACK")
            return {
                "success": False,
                "message": f"Request #{request_id} is already {request['status']}.",
                "error_code": "REQUEST_NOT_PENDING",
            }

        conn.execute(
            "UPDATE topup_requests SET status = ?, admin_id = ?, admin_note = ?, updated_at = ? WHERE id = ?",
            (STATUS_REJECTED, admin_id, reason.strip() if reason else "No reason provided", now, request_id),
        )
        conn.execute("COMMIT")
        logger.info(f"Request #{request_id} REJECTED by {admin_id}: {reason}")
        return {"success": True, "message": f"🚫 Request #{request_id} rejected."}
    except Exception as e:
        conn.execute("ROLLBACK")
        logger.exception(f"Unexpected error rejecting request #{request_id}: {e}")
        return {"success": False, "message": f"An unexpected error occurred: {e}", "error_code": "INTERNAL_ERROR"}
    finally:
        conn.close()


def get_pending_requests() -> Dict[str, Any]:
    """All requests currently awaiting admin review, oldest first."""
    conn = _get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM topup_requests WHERE status = ? ORDER BY created_at ASC",
            (STATUS_PENDING,),
        ).fetchall()
        return {"success": True, "requests": [_row_to_dict(r) for r in rows]}
    except Exception as e:
        logger.exception(f"Error fetching pending requests: {e}")
        return {"success": False, "message": str(e), "requests": []}
    finally:
        conn.close()


def get_user_requests(user_id: str, limit: int = DEFAULT_PAGE_LIMIT) -> Dict[str, Any]:
    """A single user's own request history (any status), newest first."""
    limit = min(max(int(limit), 1), MAX_PAGE_LIMIT)
    conn = _get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM topup_requests WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return {"success": True, "requests": [_row_to_dict(r) for r in rows]}
    except Exception as e:
        logger.exception(f"Error fetching requests for user {user_id}: {e}")
        return {"success": False, "message": str(e), "requests": []}
    finally:
        conn.close()


def get_topup_stats() -> Dict[str, Any]:
    """Quick counts for the admin dashboard header."""
    conn = _get_db_connection()
    try:
        pending_count = conn.execute(
            "SELECT COUNT(*) FROM topup_requests WHERE status = ?", (STATUS_PENDING,)
        ).fetchone()[0]
        approved_count = conn.execute(
            "SELECT COUNT(*) FROM topup_requests WHERE status = ?", (STATUS_APPROVED,)
        ).fetchone()[0]
        total_approved_amount = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM topup_requests WHERE status = ?", (STATUS_APPROVED,)
        ).fetchone()[0]
        return {
            "success": True,
            "stats": {
                "pending_count": pending_count,
                "approved_count": approved_count,
                "total_approved_amount": total_approved_amount,
            },
        }
    except Exception as e:
        logger.exception(f"Error computing top-up stats: {e}")
        return {"success": False, "message": str(e), "stats": {}}
    finally:
        conn.close()


def get_payment_instructions(method: str = "JazzCash") -> Dict[str, str]:
    """
    Kept for backward-compat with the existing JazzCash tab in ui.py —
    returns just that one method's details in the old shape.
    """
    all_methods = get_all_payment_instructions()
    match = next((m for m in all_methods if m["method"] == method), None)
    if not match:
        return {"jazzcash_number": "", "account_label": JAZZCASH_ACCOUNT_TITLE}
    return {"jazzcash_number": match.get("number", ""), "account_label": match.get("account_label", "")}


def get_all_payment_instructions() -> List[Dict[str, str]]:
    """
    Returns account details for EVERY configured method (only ones that
    actually have a number/IBAN set via env vars are included) — use this
    to render a method-picker in the UI instead of a JazzCash-only tab.
    Each item: {"method", "account_label", "number", "extra"}
    """
    candidates = [
        {"method": "JazzCash", "account_label": JAZZCASH_ACCOUNT_TITLE, "number": JAZZCASH_NUMBER if JAZZCASH_NUMBER != "03XX-XXXXXXX" else "", "extra": ""},
        {"method": "Easypaisa", "account_label": EASYPAISA_ACCOUNT_TITLE, "number": EASYPAISA_NUMBER, "extra": ""},
        {"method": "SadaPay", "account_label": SADAPAY_ACCOUNT_TITLE, "number": SADAPAY_NUMBER, "extra": ""},
        {"method": "NayaPay", "account_label": NAYAPAY_ACCOUNT_TITLE, "number": NAYAPAY_NUMBER, "extra": ""},
        {"method": "Bank Transfer", "account_label": BANK_ACCOUNT_TITLE, "number": BANK_ACCOUNT_NUMBER, "extra": f"IBAN: {BANK_IBAN} · {BANK_NAME}" if BANK_IBAN else BANK_NAME},
    ]
    return [c for c in candidates if c["number"]]

