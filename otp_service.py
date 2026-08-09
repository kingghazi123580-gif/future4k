# ============================================================
# OTP SERVICE — Real email verification for FUTURE 4K signup
# Filename: otp_service.py
# ============================================================
# What this does:
# - Generates 6-digit OTP codes
# - Sends them via Gmail SMTP using Python's built-in smtplib
#   (no extra pip installs needed — smtplib/ssl/email are stdlib)
# - Stores OTPs in SQLite with expiry (5 min) + resend cooldown (60s)
#   + brute-force attempt limit (5 tries)
# - Verifies user-entered codes
#
# Requires these values (from config.py OR environment variables —
# environment variables win if both are set):
#   SMTP_SERVER          e.g. "smtp.gmail.com"
#   SMTP_PORT            e.g. 587
#   SENDER_EMAIL          your Gmail address that will send the OTPs
#   SENDER_APP_PASSWORD   the 16-character Google "App Password"
#                          (NOT your normal Gmail password — generate
#                          this from Google Account > Security >
#                          2-Step Verification > App Passwords)
#
# Usage (see auth_gate.py for the full signup flow):
#     import otp_service
#     otp_service.create_and_send_otp("user@example.com")
#     otp_service.verify_otp("user@example.com", "123456")
# ============================================================

import os
import random
import smtplib
import sqlite3
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import config
    DB_PATH = getattr(config, "USERS_DB_PATH", os.path.join("data", "users.db"))
except ImportError:
    config = None
    DB_PATH = os.path.join("data", "users.db")

# Environment variables take priority over config.py, so credentials
# never HAVE to be hardcoded in a committed file.
SMTP_SERVER = os.environ.get("SMTP_SERVER") or getattr(config, "SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT") or getattr(config, "SMTP_PORT", 587))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL") or getattr(config, "SENDER_EMAIL", "")
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD") or getattr(config, "SENDER_APP_PASSWORD", "")

OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 5 * 60        # code valid for 5 minutes
OTP_RESEND_COOLDOWN_SECONDS = 60   # must wait 60s between resend requests
OTP_MAX_ATTEMPTS = 5               # max wrong guesses before code is dead

APP_NAME = "FUTURE 4K"


# ============================================================
# DATABASE
# ============================================================

def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS otp_verifications (
            email TEXT NOT NULL,
            purpose TEXT NOT NULL DEFAULT 'signup',
            otp TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            verified INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (email, purpose)
        )
    """)
    # PERMANENT security log — this table is NEVER cleared when an OTP
    # record is reset/reissued/deleted. Every send + every verify attempt
    # (success or fail) is recorded here forever, so admins can see full
    # history of suspicious behaviour (e.g. repeated wrong-code attempts)
    # even long after the OTP itself has expired or been reused.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS otp_attempt_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            purpose TEXT NOT NULL,
            event TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def _log_event(conn, email: str, purpose: str, event: str) -> None:
    """
    event is one of:
      'sent'                — a code was generated & emailed
      'send_failed'         — email sending failed (SMTP error etc.)
      'success'             — correct code entered
      'fail_wrong_code'     — incorrect code entered
      'fail_expired'        — code had already expired
      'fail_max_attempts'   — hit the brute-force attempt limit
      'fail_no_record'      — code entered but no OTP was ever requested
    """
    conn.execute(
        "INSERT INTO otp_attempt_log (email, purpose, event, created_at) VALUES (?, ?, ?, ?)",
        (email, purpose, event, _now()),
    )
    conn.commit()


def _now() -> float:
    return time.time()


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _generate_otp(length: int = OTP_LENGTH) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def is_configured() -> bool:
    """True only when real Gmail SMTP credentials have been set."""
    return bool(SENDER_EMAIL and SENDER_APP_PASSWORD)


def _valid_email_format(email: str) -> bool:
    email = (email or "").strip()
    if not email or "@" not in email:
        return False
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def _otp_email_body(otp: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif; max-width:480px; margin:auto;">
        <h2 style="color:#0FA968; margin-bottom:4px;">{APP_NAME}</h2>
        <p style="color:#14181F;">Your verification code is:</p>
        <div style="font-size:32px; font-weight:800; letter-spacing:8px;
                    background:#F4F5F7; color:#14181F; padding:16px 8px;
                    text-align:center; border-radius:10px; margin:12px 0;">
            {otp}
        </div>
        <p style="color:#626B76; font-size:0.9rem;">
            This code expires in {OTP_EXPIRY_SECONDS // 60} minutes.
            If you didn't request this, you can safely ignore this email.
        </p>
    </div>
    """


def _send_email(to_email: str, subject: str, body_html: str) -> dict:
    if not is_configured():
        return {
            "success": False,
            "message": "❌ Email service not configured. Set SENDER_EMAIL and SENDER_APP_PASSWORD.",
        }
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{APP_NAME} <{SENDER_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(body_html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return {"success": True, "message": "✅ Email sent."}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "message": "❌ Email login failed — check SENDER_EMAIL / App Password."}
    except smtplib.SMTPException as e:
        return {"success": False, "message": f"❌ Email server error: {e}"}
    except (OSError, TimeoutError) as e:
        return {"success": False, "message": f"❌ Could not reach email server: {e}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Could not send email: {e}"}


# ============================================================
# PUBLIC API
# ============================================================

def send_email(to_email: str, subject: str, body_html: str) -> dict:
    """
    Public wrapper around the internal SMTP sender — reused by
    background_worker.py to email job-completion/failure notifications
    using the exact same Gmail SMTP setup as OTP codes.
    """
    return _send_email(to_email, subject, body_html)


def create_and_send_otp(email: str, purpose: str = "signup") -> dict:
    """
    Generates a fresh OTP, stores it, and emails it to the user.
    Enforces a resend cooldown so the same email can't be spammed with requests.
    """
    email = (email or "").strip().lower()
    if not _valid_email_format(email):
        return {"success": False, "message": "❌ Please enter a valid email address."}

    conn = _get_conn()
    row = conn.execute(
        "SELECT created_at FROM otp_verifications WHERE email = ? AND purpose = ?",
        (email, purpose),
    ).fetchone()

    now = _now()
    if row:
        elapsed = now - row[0]
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            wait = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            conn.close()
            return {"success": False, "message": f"⏳ Please wait {wait}s before requesting another code."}

    otp = _generate_otp()
    expires_at = now + OTP_EXPIRY_SECONDS

    conn.execute("""
        INSERT INTO otp_verifications (email, purpose, otp, created_at, expires_at, attempts, verified)
        VALUES (?, ?, ?, ?, ?, 0, 0)
        ON CONFLICT(email, purpose) DO UPDATE SET
            otp = excluded.otp,
            created_at = excluded.created_at,
            expires_at = excluded.expires_at,
            attempts = 0,
            verified = 0
    """, (email, purpose, otp, now, expires_at))
    conn.commit()

    send_result = _send_email(email, f"{APP_NAME} — Your verification code", _otp_email_body(otp))
    _log_event(conn, email, purpose, "sent" if send_result["success"] else "send_failed")
    conn.close()

    if not send_result["success"]:
        return send_result

    return {"success": True, "message": f"✅ Verification code sent to {email}. Check your inbox (and spam folder)."}


def verify_otp(email: str, otp_input: str, purpose: str = "signup") -> dict:
    """
    Checks a user-entered OTP against the stored one.
    Handles expiry and limits brute-force attempts.
    """
    email = (email or "").strip().lower()
    otp_input = (otp_input or "").strip()

    if not otp_input:
        return {"success": False, "message": "❌ Please enter the verification code."}

    conn = _get_conn()
    row = conn.execute(
        "SELECT otp, expires_at, attempts, verified FROM otp_verifications WHERE email = ? AND purpose = ?",
        (email, purpose),
    ).fetchone()

    if not row:
        _log_event(conn, email, purpose, "fail_no_record")
        conn.close()
        return {"success": False, "message": "❌ No verification code found. Please request a new one."}

    stored_otp, expires_at, attempts, verified = row

    if verified:
        conn.close()
        return {"success": True, "message": "✅ Already verified."}

    if _now() > expires_at:
        _log_event(conn, email, purpose, "fail_expired")
        conn.close()
        return {"success": False, "message": "❌ Code expired. Please request a new one."}

    if attempts >= OTP_MAX_ATTEMPTS:
        _log_event(conn, email, purpose, "fail_max_attempts")
        conn.close()
        return {"success": False, "message": "❌ Too many incorrect attempts. Please request a new code."}

    if otp_input != stored_otp:
        conn.execute(
            "UPDATE otp_verifications SET attempts = attempts + 1 WHERE email = ? AND purpose = ?",
            (email, purpose),
        )
        conn.commit()
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        event = "fail_max_attempts" if remaining <= 0 else "fail_wrong_code"
        _log_event(conn, email, purpose, event)
        conn.close()
        if remaining <= 0:
            return {"success": False, "message": "❌ Too many incorrect attempts. Please request a new code."}
        return {"success": False, "message": f"❌ Incorrect code. {remaining} attempt(s) left."}

    conn.execute(
        "UPDATE otp_verifications SET verified = 1 WHERE email = ? AND purpose = ?",
        (email, purpose),
    )
    conn.commit()
    _log_event(conn, email, purpose, "success")
    conn.close()
    return {"success": True, "message": "✅ Email verified!"}


def is_verified(email: str, purpose: str = "signup") -> bool:
    """Check whether an email has a verified (but not-yet-consumed) OTP record."""
    email = (email or "").strip().lower()
    conn = _get_conn()
    row = conn.execute(
        "SELECT verified FROM otp_verifications WHERE email = ? AND purpose = ?",
        (email, purpose),
    ).fetchone()
    conn.close()
    return bool(row and row[0])


def consume_otp(email: str, purpose: str = "signup") -> None:
    """Call this right after the account is successfully created, so a
    verified OTP record can never be reused for a second signup."""
    email = (email or "").strip().lower()
    conn = _get_conn()
    conn.execute("DELETE FROM otp_verifications WHERE email = ? AND purpose = ?", (email, purpose))
    conn.commit()
    conn.close()


# ============================================================
# ADMIN / SECURITY LOG QUERIES
# ============================================================

def get_attempt_log(email: str = None, purpose: str = None, limit: int = 300) -> list:
    """
    Returns permanent log entries (newest first), each a dict with:
    id, email, purpose, event, created_at.
    Optionally filter by email (exact, case-insensitive) and/or purpose.
    This history is NEVER cleared automatically — it survives OTP resets,
    expiries, and even account deletion, so admins have a full record.
    """
    conn = _get_conn()
    query = "SELECT id, email, purpose, event, created_at FROM otp_attempt_log WHERE 1=1"
    params = []
    if email:
        query += " AND email = ?"
        params.append(email.strip().lower())
    if purpose:
        query += " AND purpose = ?"
        params.append(purpose)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [
        {"id": r[0], "email": r[1], "purpose": r[2], "event": r[3], "created_at": r[4]}
        for r in rows
    ]


def get_failed_attempt_count(email: str, purpose: str = "signup", window_seconds: int = None) -> int:
    """Counts fail_* events for an email, optionally only within the last window_seconds."""
    email = (email or "").strip().lower()
    conn = _get_conn()
    query = """
        SELECT COUNT(*) FROM otp_attempt_log
        WHERE email = ? AND purpose = ? AND event LIKE 'fail_%'
    """
    params = [email, purpose]
    if window_seconds is not None:
        query += " AND created_at >= ?"
        params.append(_now() - window_seconds)
    count = conn.execute(query, params).fetchone()[0]
    conn.close()
    return count


def get_suspicious_emails(min_failed_attempts: int = 5, window_seconds: int = 3600, limit: int = 50) -> list:
    """
    Flags emails with repeated failed OTP attempts recently — a strong
    signal of scammers/brute-force guessing. Returns a list of dicts:
    {email, failed_count, last_attempt_at}. This is for the admin to
    REVIEW — it does not auto-block anyone; blocking is always a manual
    admin decision (see auth_gate.block_user).
    """
    conn = _get_conn()
    since = _now() - window_seconds
    rows = conn.execute("""
        SELECT email, COUNT(*) as fail_count, MAX(created_at) as last_at
        FROM otp_attempt_log
        WHERE event LIKE 'fail_%' AND created_at >= ?
        GROUP BY email
        HAVING fail_count >= ?
        ORDER BY fail_count DESC
        LIMIT ?
    """, (since, min_failed_attempts, limit)).fetchall()
    conn.close()
    return [{"email": r[0], "failed_count": r[1], "last_attempt_at": r[2]} for r in rows]


def cleanup_expired() -> int:
    """Optional housekeeping: deletes stale, never-verified OTP rows.
    Safe to call periodically (e.g. once at app startup)."""
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM otp_verifications WHERE verified = 0 AND expires_at < ?",
        (_now(),),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted
