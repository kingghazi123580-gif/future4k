# ============================================================
# SESSION MANAGER — Persistent "Remember Me" login
# Filename: session_manager.py
# ============================================================
# PROBLEM THIS SOLVES:
# auth_gate.py stores "is this user logged in" only in st.session_state.
# st.session_state is wiped whenever the browser tab is closed, the page
# is refreshed (F5), or the user comes back the next day — even though
# their ACCOUNT still exists in the users database. So users were being
# asked to log in every single time, which is bad UX.
#
# HOW THIS FIXES IT:
# - On successful login/signup, we generate a random, unguessable session
#   token, save it in a DB table (session_tokens: token -> email, expiry),
#   and ALSO store that same token in a browser cookie (30 day expiry).
# - On every app load, BEFORE showing the login screen, we check the
#   cookie. If a valid, non-expired token is found and it matches a DB
#   record, we log the user in automatically — no form, no OTP, nothing.
# - On logout, both the DB record and the cookie are deleted.
# - Tokens are random secrets.token_hex(32) (256 bits) — not guessable,
#   and expiry is enforced server-side (DB), not just client-side.
#
# Usage in auth_gate.py's render_gate():
#     import session_manager
#     ...
#     if "auth_stage" not in st.session_state:
#         st.session_state["auth_stage"] = "auth"
#         # try silent auto-login from cookie before showing the auth screen
#         restored = session_manager.try_restore_session()
#         if restored:
#             st.session_state["auth_mode"] = "user"
#             st.session_state["user_email"] = restored["email"]
#             st.session_state["auth_stage"] = "ready" if has_seen_welcome(restored["email"]) else "welcome"
#
# After a successful login/signup (in auth_gate.py), call:
#     session_manager.create_session(user_email, remember=True)
#
# On logout (in auth_gate.py's render_logout_control()), call:
#     session_manager.destroy_session()
# ============================================================

import os
import secrets
import sqlite3
import time
import streamlit as st

try:
    import config
    DB_PATH = getattr(config, "USERS_DB_PATH", os.path.join("data", "users.db"))
except ImportError:
    DB_PATH = os.path.join("data", "users.db")

COOKIE_NAME = "f4k_session_token"
SESSION_DURATION_DAYS = 30
SESSION_DURATION_SECONDS = SESSION_DURATION_DAYS * 24 * 60 * 60

# --------------------------------------------------------------
# Cookie manager (extra-streamlit-components) — created ONCE per
# app run and cached in session_state so it doesn't re-init every
# rerun (which would lose track of cookies mid-session).
# --------------------------------------------------------------

def _get_cookie_manager():
    if "_cookie_manager" not in st.session_state:
        try:
            import extra_streamlit_components as stx
        except ImportError:
            st.session_state["_cookie_manager"] = None
            st.session_state["_cookie_manager_missing"] = True
            return None
        st.session_state["_cookie_manager"] = stx.CookieManager(key="f4k_cookie_manager")
    return st.session_state["_cookie_manager"]


def cookies_available() -> bool:
    """True only if the extra-streamlit-components package is installed."""
    return _get_cookie_manager() is not None


# ============================================================
# DATABASE
# ============================================================

def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_tokens (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            last_seen_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def _now() -> float:
    return time.time()


# ============================================================
# CORE SESSION LOGIC
# ============================================================

def create_session(email: str, remember: bool = True) -> str | None:
    """
    Call this right after a successful login or signup. Creates a DB
    session record and writes the token into a browser cookie (if the
    cookie manager package is available). Returns the token, or None
    if cookies aren't available (app still works, just won't persist
    across tab closes/refreshes in that case).
    """
    email = (email or "").strip().lower()
    if not email:
        return None

    token = secrets.token_hex(32)
    now = _now()
    expires_at = now + SESSION_DURATION_SECONDS

    conn = _get_conn()
    conn.execute(
        "INSERT INTO session_tokens (token, email, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
        (token, email, now, expires_at, now),
    )
    conn.commit()
    conn.close()

    if remember:
        cm = _get_cookie_manager()
        if cm is not None:
            expiry_dt = _seconds_to_datetime(expires_at)
            try:
                cm.set(COOKIE_NAME, token, expires_at=expiry_dt, key="f4k_set_cookie")
            except Exception:
                pass  # cookie write failing shouldn't crash login

    return token


def try_restore_session() -> dict | None:
    """
    Called once at app startup, BEFORE showing the login screen. Checks
    the browser cookie for a token, validates it against the DB (exists,
    not expired), and if valid, returns {"email": ...} so the caller can
    silently log the user in. Returns None if no valid session exists —
    in that case, the normal login/signup screen should be shown.
    """
    cm = _get_cookie_manager()
    if cm is None:
        return None

    try:
        token = cm.get(COOKIE_NAME)
    except Exception:
        return None

    if not token:
        return None

    conn = _get_conn()
    row = conn.execute(
        "SELECT email, expires_at FROM session_tokens WHERE token = ?", (token,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    email, expires_at = row
    now = _now()

    if now > expires_at:
        # Expired — clean it up so the table doesn't grow forever
        conn.execute("DELETE FROM session_tokens WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None

    # Sliding expiry: touch last_seen_at so active users don't get logged
    # out mid-use even if they're close to the 30-day mark. (Does not
    # extend expires_at itself — that stays fixed from creation time, so
    # a stolen/forgotten cookie still dies eventually.)
    conn.execute("UPDATE session_tokens SET last_seen_at = ? WHERE token = ?", (now, token))
    conn.commit()
    conn.close()

    return {"email": email}


def destroy_session() -> None:
    """Call on logout. Deletes the DB record and clears the cookie."""
    cm = _get_cookie_manager()
    token = None
    if cm is not None:
        try:
            token = cm.get(COOKIE_NAME)
        except Exception:
            token = None

    if token:
        conn = _get_conn()
        conn.execute("DELETE FROM session_tokens WHERE token = ?", (token,))
        conn.commit()
        conn.close()

    if cm is not None:
        try:
            cm.delete(COOKIE_NAME, key="f4k_delete_cookie")
        except Exception:
            pass


def destroy_all_sessions_for_user(email: str) -> None:
    """
    Optional admin/security helper: kills EVERY logged-in session for a
    given email (e.g. call this from block_user() in auth_gate.py so a
    blocked user can't stay logged in on other devices via their cookie).
    """
    email = (email or "").strip().lower()
    conn = _get_conn()
    conn.execute("DELETE FROM session_tokens WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def cleanup_expired_sessions() -> int:
    """Optional housekeeping: call periodically (e.g. app startup) to
    delete stale expired session rows. Safe no-op if none are expired."""
    conn = _get_conn()
    cur = conn.execute("DELETE FROM session_tokens WHERE expires_at < ?", (_now(),))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


# ============================================================
# HELPERS
# ============================================================

def _seconds_to_datetime(epoch_seconds: float):
    import datetime
    return datetime.datetime.fromtimestamp(epoch_seconds, tz=datetime.timezone.utc)