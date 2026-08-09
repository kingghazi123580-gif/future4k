# ============================================================
# AUTH GATE — Welcome screen + real login/signup (OTP-verified) + guest mode
# Filename: auth_gate.py
# ============================================================
# What this does:
# - Shows a black-text welcome message (FUTURE 4K intro) on a background
#   that matches ui.py's theme, BEFORE the rest of the app loads.
# - Real login/signup: accounts are stored in a local SQLite database
#   (hashed + salted passwords — never stored in plain text).
# - Signup now REQUIRES real email verification via a one-time code
#   (OTP) sent through Gmail SMTP (see otp_service.py). An account is
#   only created in the database after the OTP is confirmed — so a
#   fake/typo'd email like "asdasd@asdasd.com" can never be registered,
#   because no working inbox means no code, means no verification.
# - Guest mode: lets anyone browse the whole app and watch the demo video,
#   but is NOT tied to any account, so there's no way to remember a guest
#   between visits. Welcome screen shows every time for guests.
# - For real accounts: the welcome screen is shown exactly once, ever
#   (tracked per-account in the database), then skipped on every future
#   login from that account.
# - PERSISTENT LOGIN ("Remember Me"): once a user logs in or signs up,
#   a session token is created (see session_manager.py) and stored both
#   in the database and in a browser cookie. On future visits — new tab,
#   browser restart, next day — render_gate() silently checks that cookie
#   BEFORE showing the login screen, and if it's valid, logs the user in
#   automatically. No more re-login every single time. Sessions last
#   session_manager.SESSION_DURATION_DAYS (default 30) days, and logging
#   out (or an admin block) destroys the session everywhere.
#
# NOTE ON "Continue with Google": a real Google login needs OAuth
# credentials from Google Cloud Console and a redirect flow — that's a
# separate integration (happy to help set that up later). Faking a
# "Google button" that doesn't actually authenticate would be dishonest
# functionality, so it's left out here. Only Email + Password (real,
# OTP-verified) and Guest are included.
#
# Usage in ui.py (at the very top, before drawing sidebar/nav):
#     import auth_gate
#     if not auth_gate.render_gate():
#         st.stop()
#
# To lock a "real work" button (generate/buy/add) behind login:
#     if auth_gate.guest_locked("video generation"):
#         pass   # message already shown, nothing else runs
#     else:
#         ... normal generate logic ...
#
# REQUIRES: pip install extra-streamlit-components  (for the "Remember Me"
# cookie — see session_manager.py). If that package isn't installed, the
# app still works exactly as before, it just won't remember logins across
# tab closes/refreshes (session_manager degrades gracefully).
# ============================================================

import os
import hashlib
import secrets
import sqlite3
import time
import streamlit as st

import otp_service
import session_manager

# DB_PATH is resolved as an ABSOLUTE path anchored to this file's own
# folder — NOT to the current working directory. Previously it was a
# relative path ("data/users.db"), which meant running the app from a
# different terminal location (e.g. `cd` into a different folder before
# `streamlit run`) silently created/opened a DIFFERENT, empty database.
# That produced exactly the "wrong password" / "no account found" bug
# even when the email+password typed were 100% correct — the account
# simply existed in a different users.db file than the one being checked.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    import config
    _configured_path = getattr(config, "USERS_DB_PATH", None)
    if _configured_path and not os.path.isabs(_configured_path):
        DB_PATH = os.path.join(_APP_DIR, _configured_path)
    else:
        DB_PATH = _configured_path or os.path.join(_APP_DIR, "data", "users.db")
except ImportError:
    DB_PATH = os.path.join(_APP_DIR, "data", "users.db")

SIGNUP_PURPOSE = "signup"


# ============================================================
# DATABASE
# ============================================================

def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            welcome_seen INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)
    _ensure_block_columns(conn)
    conn.commit()
    return conn


def _ensure_block_columns(conn) -> None:
    """
    Safe migration: adds blocking-related columns to an existing users
    table without touching any existing rows/data. Runs every time a
    connection is opened — harmless no-op once the columns already exist.
    """
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "blocked" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0")
    if "block_reason" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN block_reason TEXT")
    if "blocked_at" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN blocked_at REAL")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def email_exists(email: str) -> bool:
    email = (email or "").strip().lower()
    conn = _get_conn()
    row = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return bool(row)


def create_account(email: str, password: str) -> dict:
    """
    Creates the account row. This should ONLY be called after the email
    has been OTP-verified (see the signup flow below) — this function
    itself does not check verification, so callers are responsible for
    gating it correctly.
    """
    email = (email or "").strip().lower()
    # Strip the password of leading/trailing whitespace ONLY (never lowercase
    # it — passwords must stay case-sensitive). Browser autofill / mobile
    # keyboards sometimes append an invisible trailing space, which used to
    # silently produce a DIFFERENT hash than what the user types on login,
    # causing "incorrect password" even when the visible text matched exactly.
    password = (password or "").strip()
    if not email or "@" not in email:
        return {"success": False, "message": "❌ Please enter a valid email address."}
    if not password or len(password) < 6:
        return {"success": False, "message": "❌ Password must be at least 6 characters."}

    conn = _get_conn()
    existing = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return {"success": False, "message": "❌ An account with this email already exists. Try logging in instead."}

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    conn.execute(
        "INSERT INTO users (email, password_hash, salt, welcome_seen, created_at) VALUES (?, ?, ?, 0, ?)",
        (email, password_hash, salt, time.time()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "✅ Account created!"}


def verify_login(email: str, password: str) -> dict:
    email = (email or "").strip().lower()
    password = (password or "").strip()  # same whitespace fix as create_account
    conn = _get_conn()
    row = conn.execute(
        "SELECT password_hash, salt, blocked, block_reason FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    if not row:
        return {"success": False, "message": "❌ No account found with this email. Try signing up."}
    stored_hash, salt, blocked, block_reason = row
    if _hash_password(password, salt) != stored_hash:
        return {"success": False, "message": "❌ Incorrect password."}
    if blocked:
        reason_txt = f" Reason: {block_reason}" if block_reason else ""
        return {"success": False, "message": f"🚫 This account has been blocked.{reason_txt} Contact support if you believe this is a mistake."}
    return {"success": True, "message": "✅ Logged in!"}


# ============================================================
# ADMIN — FULL BLOCK / UNBLOCK AUTHORITY + USER DIRECTORY
# ============================================================
# The admin can block ANY user at ANY time (even mid-session — the block
# is enforced on their next action via render_gate(), see below) and can
# unblock on request. Nothing here is automatic; every block/unblock is
# a deliberate admin action, logged with a timestamp + reason.
# ============================================================

def block_user(email: str, reason: str = "") -> dict:
    email = (email or "").strip().lower()
    if not email:
        return {"success": False, "message": "❌ Please provide an email."}
    conn = _get_conn()
    existing = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    if not existing:
        conn.close()
        return {"success": False, "message": "❌ No account found with this email."}
    conn.execute(
        "UPDATE users SET blocked = 1, block_reason = ?, blocked_at = ? WHERE email = ?",
        (reason.strip() if reason else "No reason provided", time.time(), email),
    )
    conn.commit()
    conn.close()
    # Kill every persistent session this user has (all devices/browsers) so
    # a block takes effect immediately, not just after their cookie expires.
    session_manager.destroy_all_sessions_for_user(email)
    return {"success": True, "message": f"🚫 {email} has been blocked."}


def unblock_user(email: str) -> dict:
    email = (email or "").strip().lower()
    if not email:
        return {"success": False, "message": "❌ Please provide an email."}
    conn = _get_conn()
    existing = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    if not existing:
        conn.close()
        return {"success": False, "message": "❌ No account found with this email."}
    conn.execute(
        "UPDATE users SET blocked = 0, block_reason = NULL, blocked_at = NULL WHERE email = ?",
        (email,),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"✅ {email} has been unblocked."}


def delete_user(email: str) -> dict:
    """
    PERMANENTLY deletes a user account row from the database. Use this
    from the admin panel for:
      - Cleaning up broken/legacy accounts (e.g. ones created before a
        bug fix, whose password hash can never match again)
      - Removing a user on request (self-delete or admin-initiated)
    This is destructive and cannot be undone — the caller (admin panel UI)
    should confirm with the admin before calling this. Also kills any
    active "remember me" sessions for that email so a deleted account
    can't stay logged in anywhere via a leftover cookie.
    """
    email = (email or "").strip().lower()
    if not email:
        return {"success": False, "message": "❌ Please provide an email."}
    conn = _get_conn()
    existing = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    if not existing:
        conn.close()
        return {"success": False, "message": "❌ No account found with this email."}
    conn.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    session_manager.destroy_all_sessions_for_user(email)
    return {"success": True, "message": f"🗑️ {email} has been permanently deleted."}


def is_blocked(email: str) -> dict:
    """Returns {'blocked': bool, 'reason': str|None} for use in live-session checks."""
    email = (email or "").strip().lower()
    conn = _get_conn()
    row = conn.execute("SELECT blocked, block_reason FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not row:
        return {"blocked": False, "reason": None}
    return {"blocked": bool(row[0]), "reason": row[1]}


def get_all_users(search: str = "") -> list:
    """
    Full user directory for the admin panel: email, signup date,
    welcome-seen status, and current block status/reason. Optional
    case-insensitive substring search on email.
    """
    conn = _get_conn()
    if search:
        rows = conn.execute(
            "SELECT email, created_at, welcome_seen, blocked, block_reason, blocked_at "
            "FROM users WHERE email LIKE ? ORDER BY created_at DESC",
            (f"%{search.strip().lower()}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT email, created_at, welcome_seen, blocked, block_reason, blocked_at "
            "FROM users ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [
        {
            "email": r[0],
            "created_at": r[1],
            "welcome_seen": bool(r[2]),
            "blocked": bool(r[3]),
            "block_reason": r[4],
            "blocked_at": r[5],
        }
        for r in rows
    ]


def get_user_count() -> int:
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def has_seen_welcome(email: str) -> bool:
    email = (email or "").strip().lower()
    conn = _get_conn()
    row = conn.execute("SELECT welcome_seen FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return bool(row and row[0])


def mark_welcome_seen(email: str) -> None:
    email = (email or "").strip().lower()
    conn = _get_conn()
    conn.execute("UPDATE users SET welcome_seen = 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()


# ============================================================
# GUEST-MODE HELPERS (used by ui.py to lock "real work" buttons)
# ============================================================

def is_guest() -> bool:
    return st.session_state.get("auth_mode") == "guest"


def is_logged_in() -> bool:
    return st.session_state.get("auth_mode") == "user"


def guest_locked(action_label: str = "this action") -> bool:
    """
    Call this as the first line inside a generate/buy/add button's if-block.
    Returns True (and shows a message) if the current user is a guest and
    should NOT be allowed to proceed. Returns False for logged-in users.
    """
    if is_guest():
        st.warning(f"🔒 **Login required** — {action_label} sirf logged-in accounts ke liye hai. "
                   f"Guest mode sirf browsing/demo ke liye hai. Upar se logout kar ke login/sign up karo.")
        return True
    return False


# ============================================================
# THEME (matches ui.py's FUTURE 4K palette)
# ============================================================

_GATE_CSS = """
<style>
    .stApp { background-color: #F4F5F7; }

    /* ------------------------------------------------------
       FORCE ALL TEXT BLACK ON THIS SCREEN (welcome / login /
       signup / guest tabs) — everything defaults to dark ink
       so nothing reads as white-on-white. Buttons are
       re-forced to white-on-green further below with a more
       specific selector, so this does not affect them.
       ------------------------------------------------------ */
    .stApp * {
        color: #14181F !important;
    }

    .f4k-title {
        text-align: center; font-family: 'Sora', sans-serif;
        font-size: 2.6rem; font-weight: 800; color: #14181F !important;
        letter-spacing: 1px; margin-bottom: 0.2rem;
    }
    .f4k-tagline {
        text-align: center; font-size: 1.05rem; font-weight: 500;
        color: #626B76 !important; margin-bottom: 2.5rem;
    }
    .f4k-paragraph {
        text-align: center; font-size: 1.05rem; color: #14181F !important;
        line-height: 1.7; max-width: 650px; margin: 0 auto;
    }
    .f4k-subtitle {
        text-align: center; font-size: 1.3rem; font-weight: 800;
        color: #14181F !important; margin-bottom: 0.3rem;
    }
    .f4k-caption {
        text-align: center; font-size: 0.95rem; color: #626B76 !important;
        margin-bottom: 1.8rem;
    }
    .f4k-otp-note {
        text-align: center; font-size: 0.85rem; color: #0B7F4F !important;
        background: #E8F5E9; border-radius: 8px; padding: 0.6rem;
        margin-bottom: 1rem;
    }

    /* Text input fields: black text on white, black labels */
    div[data-testid="stTextInput"] input {
        background-color: #FFFFFF !important; color: #14181F !important;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stTextInput"] label p {
        color: #14181F !important;
    }

    /* Tabs (Login / Sign Up / Guest) — labels black, selected tab green */
    .stTabs [data-baseweb="tab"] {
        color: #14181F !important;
    }
    .stTabs [data-baseweb="tab"] p {
        color: #14181F !important;
    }
    .stTabs [aria-selected="true"] {
        color: #0B7F4F !important;
        font-weight: 700;
    }
    .stTabs [aria-selected="true"] p {
        color: #0B7F4F !important;
    }

    /* --------------------------------------------------------
       ALL BUTTONS ON THIS SCREEN — white text on green fill.
       This selector is more specific than ".stApp *" above so
       it wins and keeps the Login / Sign Up / Guest / Enter
       buttons exactly as before (white-over-green).
       -------------------------------------------------------- */
    div.stButton > button,
    div.stButton > button p,
    div.stButton > button * {
        color: #FFFFFF !important;
    }
    div.stButton > button {
        width: 100%; border-radius: 8px !important; padding: 0.6rem 1rem;
        font-weight: 600; font-size: 0.95rem;
        background-color: #0FA968 !important;
        border: none !important;
    }
    div.stButton > button:hover {
        background-color: #0B7F4F !important;
    }
    div.stButton > button:hover * {
        color: #FFFFFF !important;
    }
</style>
"""


# ============================================================
# SCREENS
# ============================================================

def _render_welcome_screen():
    st.markdown(_GATE_CSS, unsafe_allow_html=True)
    st.markdown('<div class="f4k-title">FUTURE 4K</div>', unsafe_allow_html=True)
    st.markdown('<div class="f4k-tagline">YOUR VISION . OUR AI .</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="f4k-paragraph">
        Welcome to FUTURE 4K.
        <br><br>
        This is the first version of our AI-powered video studio — built for creators like you.
        As an MVP, it's designed to demonstrate our core vision, but we're continuously refining
        and improving. We welcome your honest feedback and suggestions. If you encounter any
        issues, please bear with us — every report helps us build a better product. Together,
        let's make FUTURE 4K the best it can be.
        </div>
    """, unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("Enter →", key="f4k_welcome_enter", use_container_width=True):
            if is_logged_in():
                mark_welcome_seen(st.session_state.get("user_email", ""))
            st.session_state["auth_stage"] = "ready"
            st.rerun()


def _reset_signup_state():
    for k in ("signup_otp_stage", "signup_pending_email", "signup_pending_password"):
        st.session_state.pop(k, None)


def _render_signup_tab():
    """
    Two-step signup:
      Step 1 — user enters email + password → we validate + send an OTP.
      Step 2 — user enters the 6-digit code from their inbox → on match,
               the account is actually created and they're logged in.
    create_account() is NEVER called before the OTP is verified, so a
    fake email (no working inbox) can never finish signup.
    """
    otp_stage = st.session_state.get("signup_otp_stage", False)

    if not otp_stage:
        # ---------- STEP 1: collect details, send OTP ----------
        signup_email = st.text_input("Email", key="auth_signup_email")
        signup_password = st.text_input("Password (min 6 characters)", type="password", key="auth_signup_password")
        signup_password2 = st.text_input("Confirm Password", type="password", key="auth_signup_password2")

        if st.button("Send Verification Code", key="auth_signup_send_otp_btn", use_container_width=True):
            email_clean = (signup_email or "").strip().lower()
            if not email_clean or "@" not in email_clean:
                st.error("❌ Please enter a valid email address.")
            elif not signup_password or len(signup_password) < 6:
                st.error("❌ Password must be at least 6 characters.")
            elif signup_password != signup_password2:
                st.error("❌ Passwords don't match.")
            elif email_exists(email_clean):
                st.error("❌ An account with this email already exists. Try logging in instead.")
            elif not otp_service.is_configured():
                st.error("❌ Email verification isn't configured yet. Please contact the app admin "
                          "(SENDER_EMAIL / SENDER_APP_PASSWORD missing).")
            else:
                with st.spinner("📧 Sending verification code..."):
                    result = otp_service.create_and_send_otp(email_clean, purpose=SIGNUP_PURPOSE)
                if result["success"]:
                    st.session_state["signup_otp_stage"] = True
                    st.session_state["signup_pending_email"] = email_clean
                    st.session_state["signup_pending_password"] = signup_password
                    st.rerun()
                else:
                    st.error(result["message"])

    else:
        # ---------- STEP 2: verify OTP, then actually create the account ----------
        pending_email = st.session_state.get("signup_pending_email", "")
        st.markdown(
            f'<div class="f4k-otp-note">📧 A 6-digit code was sent to <b>{pending_email}</b>. '
            f'Enter it below to finish creating your account.</div>',
            unsafe_allow_html=True,
        )
        otp_code = st.text_input("Verification Code", max_chars=6, key="auth_signup_otp_code")

        c1, c2 = st.columns(2)
        with c1:
            verify_clicked = st.button("Verify & Create Account", key="auth_signup_verify_btn", use_container_width=True)
        with c2:
            resend_clicked = st.button("Resend Code", key="auth_signup_resend_btn", use_container_width=True)

        if verify_clicked:
            result = otp_service.verify_otp(pending_email, otp_code, purpose=SIGNUP_PURPOSE)
            if not result["success"]:
                st.error(result["message"])
            else:
                pending_password = st.session_state.get("signup_pending_password", "")
                account_result = create_account(pending_email, pending_password)
                if not account_result["success"]:
                    st.error(account_result["message"])
                else:
                    otp_service.consume_otp(pending_email, purpose=SIGNUP_PURPOSE)
                    st.session_state["auth_mode"] = "user"
                    st.session_state["user_email"] = pending_email
                    st.session_state["auth_stage"] = "welcome"  # first-ever login always sees welcome
                    session_manager.create_session(pending_email)  # <-- persistent "remember me" session
                    _reset_signup_state()
                    st.rerun()

        if resend_clicked:
            with st.spinner("📧 Resending code..."):
                result = otp_service.create_and_send_otp(pending_email, purpose=SIGNUP_PURPOSE)
            if result["success"]:
                st.success(result["message"])
            else:
                st.error(result["message"])

        if st.button("← Use a different email", key="auth_signup_change_email_btn", use_container_width=True):
            _reset_signup_state()
            st.rerun()


def _render_auth_screen():
    st.markdown(_GATE_CSS, unsafe_allow_html=True)
    st.markdown('<div class="f4k-subtitle">Get Started</div>', unsafe_allow_html=True)
    st.markdown('<div class="f4k-caption">Login for full access, or continue as a guest to browse</div>', unsafe_allow_html=True)

    just_blocked_reason = st.session_state.pop("_just_blocked_message", None)
    if just_blocked_reason:
        st.error(f"🚫 Your account was blocked by an admin. Reason: {just_blocked_reason}")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_signup, tab_guest = st.tabs(["🔑 Login", "✨ Sign Up", "👀 Guest"])

        with tab_login:
            login_email = st.text_input("Email", key="auth_login_email")
            login_password = st.text_input("Password", type="password", key="auth_login_password")
            remember_me = st.checkbox("Mujhe yaad rakho (30 din)", value=True, key="auth_login_remember")
            if st.button("Login", key="auth_login_btn", use_container_width=True):
                result = verify_login(login_email, login_password)
                if result["success"]:
                    email_clean = login_email.strip().lower()
                    st.session_state["auth_mode"] = "user"
                    st.session_state["user_email"] = email_clean
                    if has_seen_welcome(email_clean):
                        st.session_state["auth_stage"] = "ready"
                    else:
                        st.session_state["auth_stage"] = "welcome"
                    session_manager.create_session(email_clean, remember=remember_me)  # <-- persistent login
                    st.rerun()
                else:
                    st.error(result["message"])

        with tab_signup:
            _render_signup_tab()

        with tab_guest:
            st.caption("👀 Browse the whole app and watch the demo — generating/buying needs a real account.")
            if st.button("Continue as Guest", key="auth_guest_btn", use_container_width=True):
                st.session_state["auth_mode"] = "guest"
                st.session_state["auth_stage"] = "welcome"  # guests see it every time
                st.rerun()


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def render_gate() -> bool:
    """
    Call this at the very top of ui.py. Returns True when the app should
    proceed to render normally, False when this function has already drawn
    a gate screen (auth or welcome) and ui.py should st.stop().
    """
    if "auth_stage" not in st.session_state:
        st.session_state["auth_stage"] = "auth"

        # ---- Silent auto-login from a persistent session cookie ----
        # Runs ONLY on a fresh session_state (new tab / refresh / new day).
        # If a valid "remember me" session exists, log the user straight
        # in — no login form, no OTP, nothing. See session_manager.py.
        restored = session_manager.try_restore_session()
        if restored:
            restored_email = restored["email"]
            block_status = is_blocked(restored_email)
            if not block_status["blocked"]:
                st.session_state["auth_mode"] = "user"
                st.session_state["user_email"] = restored_email
                st.session_state["auth_stage"] = "ready" if has_seen_welcome(restored_email) else "welcome"
            else:
                # Cookie is valid but the account got blocked since — don't
                # auto-login, and make sure the stale session is cleaned up.
                session_manager.destroy_all_sessions_for_user(restored_email)

    # If an already-logged-in user gets blocked by the admin mid-session,
    # kick them out on their very next interaction — don't wait for them
    # to log out and back in.
    if is_logged_in():
        block_status = is_blocked(st.session_state.get("user_email", ""))
        if block_status["blocked"]:
            for k in ("auth_mode", "auth_stage", "user_email"):
                st.session_state.pop(k, None)
            _reset_signup_state()
            st.session_state["auth_stage"] = "auth"
            st.session_state["_just_blocked_message"] = block_status["reason"] or "No reason provided"

    stage = st.session_state["auth_stage"]

    if stage == "auth":
        _render_auth_screen()
        return False
    elif stage == "welcome":
        _render_welcome_screen()
        return False
    return True  # stage == "ready"


def render_logout_control():
    """Optional small sidebar control so users can log out / switch accounts."""
    if is_logged_in():
        st.caption(f"👤 {st.session_state.get('user_email', '')}")
        if st.button("🚪 Logout", key="f4k_logout_btn", use_container_width=True):
            session_manager.destroy_session()  # <-- clears DB session + cookie
            for k in ("auth_mode", "auth_stage", "user_email"):
                st.session_state.pop(k, None)
            _reset_signup_state()
            st.rerun()

        # ---- Self-delete (with a confirm step, since this is permanent) ----
        with st.expander("🗑️ Apna Account Delete Karo"):
            st.caption("⚠️ Ye permanent hai — account aur poori history hamesha ke liye mit jayegi.")
            confirm_delete = st.checkbox("Haan, mujhe pakka pata hai, delete kar do", key="f4k_self_delete_confirm")
            if st.button("🗑️ Permanently Delete My Account", key="f4k_self_delete_btn", use_container_width=True, disabled=not confirm_delete):
                email_to_delete = st.session_state.get("user_email", "")
                result = delete_user(email_to_delete)
                if result["success"]:
                    session_manager.destroy_session()
                    for k in ("auth_mode", "auth_stage", "user_email"):
                        st.session_state.pop(k, None)
                    _reset_signup_state()
                    st.success("✅ Account delete ho gaya.")
                    st.rerun()
                else:
                    st.error(result["message"])

    elif is_guest():
        st.caption("👀 Guest mode")
        if st.button("🔑 Login / Sign Up", key="f4k_guest_to_login_btn", use_container_width=True):
            for k in ("auth_mode", "auth_stage", "user_email"):
                st.session_state.pop(k, None)
            _reset_signup_state()
            st.rerun()