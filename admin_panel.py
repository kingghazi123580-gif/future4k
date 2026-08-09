# ============================================================
# ADMIN PANEL — Users Directory + Security Log + Block/Unblock + AI Config
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
#   🧠 Scene Planner (AI) — which AI provider/model breaks a long master
#                        prompt into short scenes for Feature 25, plus
#                        the long-form cost multiplier and per-chunk ETA
#                        assumption used when quoting users. See
#                        feature_25_scene_planner.render_admin_settings().
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
from datetime import datetime

import streamlit as st

import auth_gate
import otp_service
import feature_25_scene_planner as scene_planner

try:
    import config
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or getattr(config, "ADMIN_PASSWORD", "")
except ImportError:
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SESSION_KEY = "admin_panel_authed"

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
# TAB 4 — SCENE PLANNER (AI) — Feature 25 admin configuration
# ============================================================

def _render_scene_planner_tab():
    scene_planner.render_admin_settings()


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

    tabs = st.tabs(["👥 All Users", "🚨 Security Log", "🚫 Block / Unblock", "🧠 Scene Planner (AI)"])
    with tabs[0]:
        _render_users_tab()
    with tabs[1]:
        _render_security_log_tab()
    with tabs[2]:
        _render_block_tab()
    with tabs[3]:
        _render_scene_planner_tab()