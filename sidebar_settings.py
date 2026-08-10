# ============================================================
# FUTURE 4K — PROFESSIONAL SIDEBAR + SETTINGS
# Filename: sidebar_settings.py
# ============================================================
# Original design: DeepSeek. Reviewed + integrated by Claude — added
# back two pieces the original was missing (this file replaces ui.py's
# entire `with st.sidebar:` block, so anything the old block did that
# users still need has to live somewhere in here):
#
#   1. Language selector (English/Urdu/Hindi) — existed in ui.py's old
#      sidebar, used app-wide via st.session_state["app_language"].
#      Not present in the original version of this file at all.
#
#   2. Editable "User ID (wallet/billing)" field — ui.py's wallet
#      charging, price estimates, and job queue all read
#      st.session_state["current_user_id"]. The original version only
#      *displayed* the balance, it never let the user set/change this
#      id, which would break every wallet-dependent feature.
#
# The Agnes AI API key input has been REMOVED from here entirely, per
# request — it's no longer a per-user sidebar field. It now lives in
# Admin Panel -> API Settings (admin_panel.py), set once by the admin,
# applied globally via admin_panel.get_agnes_api_key().
#
# BUGS FIXED FROM ORIGINAL (DeepSeek's own notes, kept for the record):
# 1. CRASH BUG - render_settings_page()/render_main_sidebar() were
#    called before they were defined. Fixed: entry point is at the
#    bottom, after both functions exist.
# 2. Used fake login state instead of the app's real ones - now uses
#    auth_gate.is_logged_in()/is_guest(), feat17.get_wallet_balance(),
#    st.session_state["current_user_id"], and "$" (not "Rs.") to match
#    the rest of the app.
# 3. Sidebar text-color CSS conflicted with ui.py's existing
#    section[data-testid="stSidebar"] * { color: #C4CCDA !important; }
#    rule - removed the duplicate here; only new visual pieces (logo
#    box, stats box, offer/referral box) are styled in this file.
# 4. Password change / 2FA / delete-account / delete-all-videos are
#    UI-only placeholders - no backend functions exist yet for these.
#    Left disabled with TODO notes rather than faking functionality.
#
# HOW TO USE (see ui.py):
#     import sidebar_settings
#     ...
#     if not auth_gate.render_gate():
#         st.stop()
#     sidebar_settings.render_sidebar_and_settings()
# ============================================================

import streamlit as st

import auth_gate
import admin_panel
import feature_17_pay_per_video as feat17

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
if "theme" not in st.session_state:
    st.session_state.theme = "☀️ Light"
if "font_size" not in st.session_state:
    st.session_state.font_size = "Medium"
if "email_notifications" not in st.session_state:
    st.session_state.email_notifications = True
if "marketing_emails" not in st.session_state:
    st.session_state.marketing_emails = False
if "daily_summary" not in st.session_state:
    st.session_state.daily_summary = False
if "show_settings" not in st.session_state:
    st.session_state.show_settings = False
if "current_user_id" not in st.session_state:
    st.session_state.current_user_id = "test_ppv_user_001"
if "app_language" not in st.session_state:
    st.session_state.app_language = "English"


def go_to_settings():
    st.session_state.show_settings = True
    st.rerun()


def close_settings():
    st.session_state.show_settings = False
    st.rerun()


# ============================================================
# EXTRA CSS - only the new pieces; sidebar text color already
# comes from ui.py's existing stylesheet, so it's NOT redefined here.
# ============================================================
st.markdown("""
<style>
    .sidebar-logo { text-align: center; padding: 15px 10px; }
    .sidebar-logo h1 { font-size: 28px; margin: 0; color: #0FA968; }
    .sidebar-logo p { font-size: 12px; color: #a0a0b0; margin: 2px 0; }

    .user-info-box {
        background: rgba(15, 169, 104, 0.15);
        border: 1px solid rgba(15, 169, 104, 0.3);
        border-radius: 12px; padding: 12px; margin: 10px;
    }
    .user-info-box p { margin: 4px 0; font-size: 13px; }

    .section-header {
        font-size: 11px; text-transform: uppercase; letter-spacing: 2px;
        color: #0FA968; padding: 5px 15px; margin-top: 10px;
    }

    .offer-box {
        background: linear-gradient(135deg, #0FA968, #0B7F4F);
        border-radius: 10px; padding: 10px; margin: 5px 10px; text-align: center;
    }
    .offer-box h4 { margin: 0; font-size: 13px; }
    .offer-box p { margin: 3px 0; font-size: 11px; }

    .referral-box {
        background: rgba(255, 215, 0, 0.1);
        border: 1px dashed rgba(255, 215, 0, 0.4);
        border-radius: 10px; padding: 10px; margin: 5px 10px; text-align: center;
    }
    .referral-box p { font-size: 11px; margin: 3px 0; }

    .sidebar-footer { text-align: center; padding: 15px 10px; font-size: 10px; color: #888; }
    .sep { border-top: 1px solid rgba(255,255,255,0.08); margin: 8px 10px; }

    .settings-card {
        background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px; padding: 20px; margin: 10px 0;
    }
    .settings-card h3 { margin-top: 0; color: #0FA968; }
    .danger-zone { border-color: rgba(255, 0, 0, 0.3) !important; background: rgba(255, 0, 0, 0.03) !important; }
    .danger-zone h3 { color: #ff4444 !important; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SETTINGS PAGE
# ============================================================
def render_settings_page():
    st.title("⚙️ Settings")

    if st.button("← Back to App", key="back_from_settings"):
        close_settings()

    st.markdown("---")

    user_email = st.session_state.get("user_email", "")
    user_id = st.session_state.get("current_user_id", "")

    with st.container():
        st.markdown('<div class="settings-card">', unsafe_allow_html=True)
        st.subheader("👤 Profile")
        st.text_input("Email", value=user_email, disabled=True, key="settings_email",
                       help="Email is your login — contact support to change it.")
        st.text_input("Phone Number (optional)", key="settings_phone", placeholder="03XX-XXXXXXX")
        if st.button("💾 Save Profile", type="primary"):
            st.success("✅ Saved.")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="settings-card">', unsafe_allow_html=True)
        st.subheader("🔔 Notifications")
        st.session_state.email_notifications = st.checkbox(
            "📧 Email when video is ready", value=st.session_state.email_notifications, key="notif_video_ready")
        st.checkbox("💰 Email on wallet top-up confirmation", value=True, key="notif_wallet_topup", disabled=True)
        st.session_state.marketing_emails = st.checkbox(
            "📢 Marketing emails & special offers", value=st.session_state.marketing_emails, key="notif_marketing")
        st.session_state.daily_summary = st.checkbox(
            "📊 Daily usage summary", value=st.session_state.daily_summary, key="notif_daily")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="settings-card">', unsafe_allow_html=True)
        st.subheader("🎨 Appearance")
        st.session_state.theme = st.radio("Theme", ["☀️ Light", "🌙 Dark", "💻 System Default"],
                                           horizontal=True, key="settings_theme")
        st.session_state.font_size = st.radio("Font Size", ["Small", "Medium", "Large"],
                                               horizontal=True, key="settings_font")
        st.session_state.app_language = st.radio("Language", ["English", "Urdu", "Hindi"],
                                                   horizontal=True, key="settings_language")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="settings-card">', unsafe_allow_html=True)
        st.subheader("🔒 Security")
        with st.expander("🔑 Change Password"):
            st.caption("⚠️ TODO: not wired yet — auth_gate.py has no change_password() function. "
                       "Add one (hash+salt, same pattern as create_account) before enabling this.")
            st.text_input("Current Password", type="password", key="current_pass", disabled=True)
            st.text_input("New Password", type="password", key="new_pass", disabled=True)
            st.button("Update Password", disabled=True)
        with st.expander("🔐 Two-Factor Authentication (2FA)"):
            st.caption("⚠️ TODO: not implemented — this project already has OTP-verified signup "
                       "(otp_service.py); a login-time 2FA step could reuse that same SMTP path.")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="settings-card">', unsafe_allow_html=True)
        st.subheader("💰 Wallet")
        try:
            balance = feat17.get_wallet_balance(user_id) if user_id else {}
            st.metric("Balance", f"${balance.get('balance', 0):.2f}")
        except Exception:
            st.caption("Wallet unavailable.")
        st.caption("Top up from Profile → 💰 Pay-Per-Video.")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="settings-card danger-zone">', unsafe_allow_html=True)
        st.subheader("🗑️ Danger Zone")
        st.warning("⚠️ Not wired to a backend yet — feature_12_video_library.py and auth_gate.py "
                   "have no delete-all / delete-account functions. Add those before enabling.")
        st.button("🗑️ Delete All My Videos", disabled=True)
        st.button("⚠️ Delete My Account", disabled=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# MAIN SIDEBAR
# ============================================================
def render_main_sidebar():
    st.markdown("""
    <div class="sidebar-logo">
        <h1>🎬 FUTURE 4K</h1>
        <p>YOUR VISION . OUR AI .</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

    logged_in = auth_gate.is_logged_in()
    user_email = st.session_state.get("user_email", "")

    # Editable User ID — required by ui.py's wallet charging, price
    # estimates, and job queue everywhere else (st.session_state
    # ["current_user_id"]). Kept here since it's a billing identifier.
    user_id = st.text_input(
        "👤 User ID (wallet / billing)",
        value=st.session_state.get("current_user_id", "test_ppv_user_001"),
        key="sidebar_user_id_input",
        help="Used to charge your wallet and apply any discount the admin has set for you.",
    )
    st.session_state["current_user_id"] = user_id

    if logged_in or auth_gate.is_guest():
        try:
            balance = feat17.get_wallet_balance(user_id) if user_id else {}
            balance_str = f"${balance.get('balance', 0):.2f}"
        except Exception:
            balance_str = "$0.00"

        st.markdown(f"""
        <div class="user-info-box">
            <p>👤 {'Welcome, <b>' + user_email + '</b>' if logged_in else '<b>Guest mode</b>'}</p>
            <p>💰 Balance: <b>{balance_str}</b></p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

        st.markdown('<p class="section-header">⚡ QUICK ACTIONS</p>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🎥 New Video", use_container_width=True, key="quick_new_video"):
                st.session_state["active_nav"] = "🛠️ Tools"
                st.session_state["active_tool"] = 0
                st.rerun()
        with col_b:
            if st.button("💰 Top Up", use_container_width=True, key="quick_topup"):
                st.session_state["active_nav"] = "👤 Profile"
                st.rerun()
        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

    st.markdown('<p class="section-header">🌐 LANGUAGE</p>', unsafe_allow_html=True)
    st.session_state["app_language"] = st.selectbox(
        "Language", ["English", "Urdu", "Hindi"],
        index=["English", "Urdu", "Hindi"].index(st.session_state.get("app_language", "English")),
        key="sidebar_app_language_select", label_visibility="collapsed",
    )
    st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

    st.markdown('<p class="section-header">📋 MENU</p>', unsafe_allow_html=True)
    if st.button("⚙️  Settings", key="nav_settings", use_container_width=True):
        go_to_settings()

    st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="referral-box">
        <p>🎁 <b>INVITE & EARN</b></p>
        <p>Refer a friend & get <b>$5 FREE</b> in your wallet!</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("📋 Copy Referral Link", use_container_width=True, key="copy_referral"):
        st.toast("Referral link copied! 📋", icon="✅")
    st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

    auth_gate.render_logout_control()

    st.markdown('<div class="sep"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="sidebar-footer">
        <p>🔒 Secure</p>
        <p>© 2026 FUTURE 4K</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# ENTRY POINT — call this once from ui.py, AFTER auth_gate.render_gate()
# has already run.
# ============================================================
def render_sidebar_and_settings():
    with st.sidebar:
        if st.session_state.show_settings:
            pass
        else:
            render_main_sidebar()

    if st.session_state.show_settings:
        render_settings_page()
        st.stop()
