# ============================================================
# ADMIN PANEL — Users Directory + Security Log + Block/Unblock
# Filename: admin_panel.py
# ============================================================
# What this does (separate from feature_24_admin_pricing.py, which
# only handles pricing/discounts):
#   👥 All Users     — every registered account: email, signup date,
#                        welcome status, current block status
#   🚨 Security Log  — PERMANENT record of every OTP send/verify
#                        attempt (success + failure), so you can see
#                        exactly who tried what, and when — this data
#                        is never erased, even after an OTP expires or
#                        is reused. Repeated-failure emails are flagged
#                        automatically for your review.
#   🚫 Block/Unblock — full admin authority: block ANY user at ANY
#                        time (with a reason/proof note), and unblock
#                        on request. A blocked user cannot log in even
#                        with the correct password, and is kicked out
#                        immediately if blocked while already logged in.
#
# Password-protected — set ADMIN_PASSWORD via environment variable or
# in config.py. Uses its own session flag so it's independent from any
# other admin panel (e.g. feature_24's pricing admin).
#
# Wire this into ui.py's Admin tab, e.g.:
#     import admin_panel
#     ...
#     with admin_tabs[1]:
#         admin_panel.render_admin_page()
# ============================================================

import os
import sqlite3
from datetime import datetime

import streamlit as st

import auth_gate
import otp_service
import manual_payments

try:
    import config
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or getattr(config, "ADMIN_PASSWORD", "")
    SETTINGS_DB_PATH = getattr(config, "SETTINGS_DB_PATH", os.path.join("data", "app_settings.db"))
except ImportError:
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    SETTINGS_DB_PATH = os.path.join("data", "app_settings.db")

SESSION_KEY = "admin_panel_authed"


# ============================================================
# APP SETTINGS (currently: Agnes AI API key) — admin-only control.
# Previously this was a text input every user could see/edit in the
# sidebar. Moved here: one value, set once by the admin, applied to
# every feature module globally. Environment variable AGNES_API_KEY
# (if set) always wins over the stored DB value, so ops/deploy configs
# still work without touching this UI.
# ============================================================

def _get_settings_conn():
    db_dir = os.path.dirname(SETTINGS_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(SETTINGS_DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


def _get_setting(key: str, default: str = "") -> str:
    conn = _get_settings_conn()
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def _set_setting(key: str, value: str) -> None:
    conn = _get_settings_conn()
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_agnes_api_key() -> str:
    """Env var wins if set (ops override); otherwise the admin-configured DB value."""
    env_key = os.environ.get("AGNES_API_KEY", "")
    if env_key:
        return env_key
    return _get_setting("agnes_api_key", "")


def set_agnes_api_key(value: str) -> None:
    _set_setting("agnes_api_key", value.strip())

EVENT_LABELS = {
    "sent": "📧 Code sent",
    "send_failed": "⚠️ Send failed",
    "success": "✅ Verified successfully",
    "fail_wrong_code": "❌ Wrong code entered",
    "fail_expired": "⌛ Code expired",
    "fail_max_attempts": "🚫 Max attempts hit",
    "fail_no_record": "❓ No code was requested",
}


def _fmt_time(ts) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


# ============================================================
# PASSWORD GATE
# ============================================================

def _render_password_gate():
    st.info("🔐 Enter the admin password to view users and security data.")
    if not ADMIN_PASSWORD:
        st.warning("⚠️ ADMIN_PASSWORD isn't set yet. Set it as an environment variable "
                   "(or in config.py) before this panel can be unlocked.")
        return
    pwd = st.text_input("Admin Password", type="password", key="admin_panel_pwd_input")
    if st.button("Unlock", key="admin_panel_unlock_btn"):
        if pwd == ADMIN_PASSWORD:
            st.session_state[SESSION_KEY] = True
            st.rerun()
        else:
            st.error("❌ Incorrect password.")


# ============================================================
# TAB 1 — ALL USERS
# ============================================================

def _render_users_tab():
    st.markdown("### 👥 All Registered Users")
    search = st.text_input("🔍 Search by email", key="admin_users_search", placeholder="type part of an email...")
    users = auth_gate.get_all_users(search)
    st.caption(f"Showing {len(users)} of {auth_gate.get_user_count()} total users")

    if not users:
        st.info("No users found.")
        return

    for u in users:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{u['email']}**")
                st.caption(f"Joined: {_fmt_time(u['created_at'])} · Welcome screen seen: {'Yes' if u['welcome_seen'] else 'No'}")
            with c2:
                if u["blocked"]:
                    st.markdown("🚫 **Blocked**")
                    st.caption(f"Since: {_fmt_time(u['blocked_at'])}")
                    if u["block_reason"]:
                        st.caption(f"Reason: {u['block_reason']}")
                else:
                    st.markdown("✅ Active")
            with c3:
                if u["blocked"]:
                    if st.button("✅ Unblock", key=f"admin_unblock_row_{u['email']}", use_container_width=True):
                        result = auth_gate.unblock_user(u["email"])
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])
                else:
                    if st.button("🚫 Block", key=f"admin_block_row_{u['email']}", use_container_width=True):
                        st.session_state["admin_block_target"] = u["email"]
                        st.rerun()

    # If a "Block" button above was clicked, ask for a reason before finalizing.
    target = st.session_state.get("admin_block_target")
    if target:
        st.divider()
        st.warning(f"Blocking **{target}** — please note a reason (proof/notes) for the record.")
        reason = st.text_area("Reason for blocking", key="admin_block_reason_inline")
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("✅ Confirm Block", key="admin_block_confirm_btn", use_container_width=True):
                result = auth_gate.block_user(target, reason)
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
                st.session_state.pop("admin_block_target", None)
                st.rerun()
        with bc2:
            if st.button("Cancel", key="admin_block_cancel_btn", use_container_width=True):
                st.session_state.pop("admin_block_target", None)
                st.rerun()


# ============================================================
# TAB 2 — SECURITY LOG (permanent OTP attempt history)
# ============================================================

def _render_security_log_tab():
    st.markdown("### 🚨 Security Log — OTP Attempt History")
    st.caption("This history is permanent and is never cleared, even when an OTP resets or expires.")

    suspicious = otp_service.get_suspicious_emails(min_failed_attempts=5, window_seconds=3600)
    if suspicious:
        st.error(f"⚠️ {len(suspicious)} email(s) with 5+ failed attempts in the last hour — possible scammers:")
        for s in suspicious:
            c1, c2, c3 = st.columns([3, 2, 2])
            c1.markdown(f"**{s['email']}**")
            c2.caption(f"{s['failed_count']} failed attempts")
            c3.caption(f"Last: {_fmt_time(s['last_attempt_at'])}")
        st.divider()
    else:
        st.success("✅ No suspicious activity (5+ failures in the last hour) right now.")

    st.markdown("#### Full Log")
    filter_email = st.text_input("Filter by email (optional)", key="admin_log_email_filter")
    logs = otp_service.get_attempt_log(email=filter_email or None, limit=300)

    if not logs:
        st.info("No log entries yet.")
        return

    for entry in logs:
        label = EVENT_LABELS.get(entry["event"], entry["event"])
        is_fail = entry["event"].startswith("fail_")
        line = f"{'🔴' if is_fail else '🟢'} **{entry['email']}** — {label} — _{entry['purpose']}_ — {_fmt_time(entry['created_at'])}"
        if is_fail:
            st.markdown(f"<span style='color:#B00020;'>{line}</span>", unsafe_allow_html=True)
        else:
            st.markdown(line)


# ============================================================
# TAB 3 — BLOCK / UNBLOCK (manual admin authority)
# ============================================================

def _render_block_tab():
    st.markdown("### 🚫 Block a User")
    st.caption("Use this any time you have proof/reason to believe a user is cheating or abusing the platform. "
               "This works even if the user has done nothing wrong in the OTP system — it's a full manual override.")
    block_email = st.text_input("User email to block", key="admin_block_email_manual")
    block_reason = st.text_area("Reason / proof / notes", key="admin_block_reason_manual",
                                 placeholder="e.g. Multiple chargeback attempts on 2026-08-01, confirmed via payment logs.")
    if st.button("🚫 Block This User", key="admin_block_manual_btn", type="primary", use_container_width=True):
        if not block_email:
            st.error("❌ Please enter an email.")
        else:
            result = auth_gate.block_user(block_email, block_reason)
            if result["success"]:
                st.success(result["message"])
            else:
                st.error(result["message"])

    st.divider()

    st.markdown("### ✅ Unblock a User")
    st.caption("If a user appeals and you're satisfied the issue is resolved, unblock them here.")
    unblock_email = st.text_input("User email to unblock", key="admin_unblock_email_manual")
    if st.button("✅ Unblock This User", key="admin_unblock_manual_btn", use_container_width=True):
        if not unblock_email:
            st.error("❌ Please enter an email.")
        else:
            result = auth_gate.unblock_user(unblock_email)
            if result["success"]:
                st.success(result["message"])
            else:
                st.error(result["message"])

    st.divider()

    st.markdown("### 📋 Currently Blocked Users")
    blocked_users = [u for u in auth_gate.get_all_users() if u["blocked"]]
    if not blocked_users:
        st.info("No users are currently blocked.")
    else:
        for u in blocked_users:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 2])
                c1.markdown(f"**{u['email']}**")
                c1.caption(f"Blocked: {_fmt_time(u['blocked_at'])}")
                c2.caption(u["block_reason"] or "No reason provided")
                if c3.button("✅ Unblock", key=f"admin_quick_unblock_{u['email']}", use_container_width=True):
                    result = auth_gate.unblock_user(u["email"])
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def render_admin_page():
    if not st.session_state.get(SESSION_KEY, False):
        _render_password_gate()
        return

    top_c1, top_c2 = st.columns([5, 1])
    with top_c1:
        st.caption("🔓 Admin session active")
    with top_c2:
        if st.button("Lock", key="admin_panel_lock_btn", use_container_width=True):
            st.session_state[SESSION_KEY] = False
            st.rerun()

    tabs = st.tabs(["👥 All Users", "🚨 Security Log", "🚫 Block / Unblock", "💳 Pending Top-ups", "🔑 API Settings"])
    with tabs[0]:
        _render_users_tab()
    with tabs[1]:
        _render_security_log_tab()
    with tabs[2]:
        _render_block_tab()
    with tabs[3]:
        _render_pending_topups_tab()
    with tabs[4]:
        _render_api_settings_tab()


def _render_api_settings_tab():
    st.markdown("### 🔑 Agnes AI API Key")
    st.caption("Set once here — applies to every feature module for every user. "
               "Users never see or enter this key themselves.")

    env_override = os.environ.get("AGNES_API_KEY", "")
    if env_override:
        st.info("ℹ️ An `AGNES_API_KEY` environment variable is set and is currently overriding "
                "the value below (env var always wins, for safe ops/deploy configs).")

    current = _get_setting("agnes_api_key", "")
    masked = f"{'•' * max(len(current) - 4, 0)}{current[-4:]}" if current else "(not set)"
    st.caption(f"Currently stored: `{masked}`")

    new_key = st.text_input("Agnes AI API Key", type="password", key="admin_agnes_key_input")
    if st.button("💾 Save API Key", key="admin_agnes_key_save"):
        if not new_key.strip():
            st.error("❌ Please enter a key before saving.")
        else:
            set_agnes_api_key(new_key)
            st.success("✅ API key saved. It will apply on the next app reload.")
            st.rerun()


def _render_pending_topups_tab():
    st.markdown("### 💳 Pending JazzCash Top-Ups")
    st.caption("Check your real JazzCash inbox before approving — this is the only manual step "
               "that turns a submitted transaction ID into actual wallet credit.")

    stats = manual_payments.get_topup_stats()
    if stats.get("success"):
        s = stats["stats"]
        c1, c2, c3 = st.columns(3)
        c1.metric("🟡 Pending", s["pending_count"])
        c2.metric("✅ Approved (all-time)", s["approved_count"])
        c3.metric("💰 Total Approved", f"Rs. {s['total_approved_amount']:,.0f}")

    pending = manual_payments.get_pending_requests()
    if not pending.get("success") or not pending.get("requests"):
        st.info("No pending top-up requests.")
        return

    for r in pending["requests"]:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{r['user_id']}**")
                st.caption(f"Rs. {r['amount']:,.0f} — Txn: {r['txn_id']}")
                st.caption(f"Submitted: {r['created_at']}")
            with c2:
                if st.button("✅ Approve", key=f"admin_topup_approve_{r['id']}", use_container_width=True):
                    result = manual_payments.approve_request(r["id"], admin_id="admin", admin_note="Confirmed in JazzCash inbox")
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])
            with c3:
                reject_key = f"admin_topup_reject_reason_{r['id']}"
                reason = st.text_input("Reject reason", key=reject_key, label_visibility="collapsed", placeholder="Reason (required to reject)")
                if st.button("🚫 Reject", key=f"admin_topup_reject_{r['id']}", use_container_width=True):
                    if not reason.strip():
                        st.error("❌ Please enter a reason to reject.")
                    else:
                        result = manual_payments.reject_request(r["id"], admin_id="admin", reason=reason)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])
