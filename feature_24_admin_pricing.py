# ============================================================
# FEATURE 24 — ADMIN PRICING & DISCOUNT CONTROL
# ============================================================
# Password-protected admin panel (no separate auth system needed).
# SQLite single source of truth — same DB pattern as AV Guardian's
# cost calculator. Three layers, applied in this priority order:
#   1. Per-user discount (if active and not expired)          <- highest priority
#   2. Global discount (if active)
#   3. Base/global price (always exists, admin-editable anytime)
#
# ------------------------------------------------------------
# NEW: DYNAMIC FORMULA-BASED PRICING ENGINE
# ------------------------------------------------------------
# Admin sets ONE global formula that applies to every user and every
# video-generating tool in the app:
#
#     FINAL PRICE (USD) = base_rate_per_second
#                          x duration_seconds
#                          x resolution_multiplier
#                          x quality_multiplier
#
# Then any active discount (per-user > global) is applied on top.
# All of this lives in the `pricing_formula` table below and is
# 100% admin-editable from the "🧮 Pricing Formula" tab — no code
# changes needed anywhere else in the app. Every feature file just
# calls calculate_price(duration, resolution, quality, user_id) and
# gets the final number back.
#
# This is designed to be extended later (e.g. flat add-on charges
# for voiceover / watermark-removal / character-consistency) without
# breaking the core formula — see EXTRA_CHARGES section, currently
# unused but wired in and ready.
#
# CHANGE LOG (frame-count fix):
# - Added a 4th tab, "🖼️ Frame Rules" — lets the admin add/edit/delete
#   the per-model frame-count / duration rules used by frame_policy.py.
#   This is what lets Shan add a new model (Wan 2.3, Wan 2.6, etc.) and
#   fix its frame-count formula from the UI, with zero code changes to
#   any feature file.
#
# Standalone module. Import render_admin_page() into app.py behind a
# hidden nav item (e.g. "🔐 Admin") or a query param — your call.
# ============================================================

import os
import json
import sqlite3
import time
import streamlit as st

try:
    import config
    ADMIN_PASSWORD = getattr(config, "ADMIN_PASSWORD", "changeme123")
    DB_PATH = getattr(config, "ADMIN_DB_PATH", os.path.join("data", "admin_pricing.db"))
except ImportError:
    ADMIN_PASSWORD = os.environ.get("FILMAA_ADMIN_PASSWORD", "changeme123")
    DB_PATH = os.path.join("data", "admin_pricing.db")

import frame_policy


# ------------------------------------------------------------
# DEFAULTS (only used the very first time the DB is created —
# after that, everything is admin-editable and persisted in SQLite)
# ------------------------------------------------------------
DEFAULT_BASE_RATE_PER_SECOND = 0.50  # USD

DEFAULT_RESOLUTION_MULTIPLIERS = {
    "480p": 0.6,
    "720p": 1.0,
    "1080p": 1.6,
    "2k": 2.2,
    "4k": 3.0,
}

DEFAULT_QUALITY_MULTIPLIERS = {
    "draft": 0.7,
    "standard": 1.0,
    "high": 1.4,
    "ultra": 1.8,
}

MIN_CHARGE_USD = 0.10  # floor, so a 1-second draft-quality clip is never $0.00


# ------------------------------------------------------------
# DB layer
# ------------------------------------------------------------
def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feature_prices (
            feature_id TEXT PRIMARY KEY,
            base_price REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS global_discount (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            percent REAL NOT NULL,
            active INTEGER NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_discount (
            user_id TEXT PRIMARY KEY,
            percent REAL NOT NULL,
            active INTEGER NOT NULL,
            expires_at REAL,
            updated_at REAL NOT NULL
        )
    """)
    # --- Dynamic pricing formula (single row, id=1) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pricing_formula (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            base_rate_per_second REAL NOT NULL,
            min_charge_usd REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    # --- Resolution multipliers (admin-editable list) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resolution_multipliers (
            resolution TEXT PRIMARY KEY,
            multiplier REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    # --- Quality multipliers (admin-editable list) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_multipliers (
            quality TEXT PRIMARY KEY,
            multiplier REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    # --- Extra charges (future use — flat USD add-ons per toggle,
    #     e.g. "remove_watermark": 1.50, "voiceover": 0.75 ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS extra_charges (
            charge_id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            amount_usd REAL NOT NULL,
            active INTEGER NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.commit()

    # Seed defaults exactly once (only if tables are empty)
    row = conn.execute("SELECT id FROM pricing_formula WHERE id = 1").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO pricing_formula (id, base_rate_per_second, min_charge_usd, updated_at) VALUES (1, ?, ?, ?)",
            (DEFAULT_BASE_RATE_PER_SECOND, MIN_CHARGE_USD, time.time()),
        )
    existing_res = {r[0] for r in conn.execute("SELECT resolution FROM resolution_multipliers").fetchall()}
    for res, mult in DEFAULT_RESOLUTION_MULTIPLIERS.items():
        if res not in existing_res:
            conn.execute(
                "INSERT INTO resolution_multipliers (resolution, multiplier, updated_at) VALUES (?, ?, ?)",
                (res, mult, time.time()),
            )
    existing_q = {r[0] for r in conn.execute("SELECT quality FROM quality_multipliers").fetchall()}
    for q, mult in DEFAULT_QUALITY_MULTIPLIERS.items():
        if q not in existing_q:
            conn.execute(
                "INSERT INTO quality_multipliers (quality, multiplier, updated_at) VALUES (?, ?, ?)",
                (q, mult, time.time()),
            )
    conn.commit()
    conn.close()
    return {"success": True, "message": "✅ Admin pricing DB ready."}


def init_db():
    return _get_conn_and_seed()


def _get_conn_and_seed():
    return _get_conn()


def verify_admin_password(entered_password):
    return entered_password == ADMIN_PASSWORD


# ------------------------------------------------------------
# Legacy flat per-feature price (kept for backward compatibility /
# non-duration features). Still usable, but video-generating tools
# now use calculate_price() below instead.
# ------------------------------------------------------------
def set_global_price(feature_id, price):
    if price < 0:
        return {"success": False, "message": "❌ Price cannot be negative."}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO feature_prices (feature_id, base_price, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(feature_id) DO UPDATE SET base_price=excluded.base_price, updated_at=excluded.updated_at",
        (feature_id, price, time.time()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"✅ Price for '{feature_id}' set to {price}."}


def get_all_prices():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT feature_id, base_price, updated_at FROM feature_prices ORDER BY feature_id").fetchall()
    conn.close()
    return [{"feature_id": r[0], "base_price": r[1], "updated_at": r[2]} for r in rows]


def set_global_discount(percent, active):
    if not (0 <= percent <= 100):
        return {"success": False, "message": "❌ Discount must be 0-100."}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO global_discount (id, percent, active, updated_at) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET percent=excluded.percent, active=excluded.active, updated_at=excluded.updated_at",
        (percent, int(active), time.time()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"✅ Global discount set to {percent}% ({'ON' if active else 'OFF'})."}


def get_global_discount():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT percent, active FROM global_discount WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {"percent": 0, "active": False}
    return {"percent": row[0], "active": bool(row[1])}


def set_user_discount(user_id, percent, active=True, expires_at=None):
    if not user_id:
        return {"success": False, "message": "❌ User ID required."}
    if not (0 <= percent <= 100):
        return {"success": False, "message": "❌ Discount must be 0-100."}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO user_discount (user_id, percent, active, expires_at, updated_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET percent=excluded.percent, active=excluded.active, "
        "expires_at=excluded.expires_at, updated_at=excluded.updated_at",
        (user_id, percent, int(active), expires_at, time.time()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"✅ Discount for user '{user_id}' set to {percent}%."}


def get_all_user_discounts():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT user_id, percent, active, expires_at FROM user_discount ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [{"user_id": r[0], "percent": r[1], "active": bool(r[2]), "expires_at": r[3]} for r in rows]


def _get_active_discount_for_user(user_id):
    """Returns (percent, source) — per-user beats global beats none."""
    now = time.time()
    if user_id:
        conn = sqlite3.connect(DB_PATH)
        user_row = conn.execute(
            "SELECT percent, active, expires_at FROM user_discount WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.close()
        if user_row and user_row[1] and (user_row[2] is None or user_row[2] > now):
            return user_row[0], "per_user"

    global_d = get_global_discount()
    if global_d["active"]:
        return global_d["percent"], "global"

    return 0, "none"


def get_effective_price(user_id, feature_id):
    """Resolves final price a specific user pays for a FLAT (non-duration) feature."""
    conn = sqlite3.connect(DB_PATH)
    price_row = conn.execute("SELECT base_price FROM feature_prices WHERE feature_id = ?", (feature_id,)).fetchone()
    conn.close()
    if not price_row:
        return {"success": False, "message": f"❌ No price set for '{feature_id}'. Admin must set one first."}
    base_price = price_row[0]

    percent, source = _get_active_discount_for_user(user_id)
    final_price = base_price * (1 - percent / 100)
    return {"success": True, "base_price": base_price, "discount_percent": percent,
            "discount_source": source, "final_price": round(final_price, 2)}


# ------------------------------------------------------------
# DYNAMIC PRICING ENGINE — used by every video-generating tool
# ------------------------------------------------------------
def get_pricing_formula():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT base_rate_per_second, min_charge_usd FROM pricing_formula WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {"base_rate_per_second": DEFAULT_BASE_RATE_PER_SECOND, "min_charge_usd": MIN_CHARGE_USD}
    return {"base_rate_per_second": row[0], "min_charge_usd": row[1]}


def set_pricing_formula(base_rate_per_second, min_charge_usd):
    if base_rate_per_second < 0 or min_charge_usd < 0:
        return {"success": False, "message": "❌ Values cannot be negative."}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO pricing_formula (id, base_rate_per_second, min_charge_usd, updated_at) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET base_rate_per_second=excluded.base_rate_per_second, "
        "min_charge_usd=excluded.min_charge_usd, updated_at=excluded.updated_at",
        (base_rate_per_second, min_charge_usd, time.time()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "✅ Base pricing formula updated."}


def get_resolution_multipliers():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT resolution, multiplier FROM resolution_multipliers ORDER BY multiplier").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def set_resolution_multiplier(resolution, multiplier):
    resolution = (resolution or "").strip().lower()
    if not resolution:
        return {"success": False, "message": "❌ Resolution name required."}
    if multiplier < 0:
        return {"success": False, "message": "❌ Multiplier cannot be negative."}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO resolution_multipliers (resolution, multiplier, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(resolution) DO UPDATE SET multiplier=excluded.multiplier, updated_at=excluded.updated_at",
        (resolution, multiplier, time.time()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"✅ Resolution '{resolution}' multiplier set to {multiplier}x."}


def delete_resolution_multiplier(resolution):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM resolution_multipliers WHERE resolution = ?", (resolution,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"🗑️ Removed resolution '{resolution}'."}


def get_quality_multipliers():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT quality, multiplier FROM quality_multipliers ORDER BY multiplier").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def set_quality_multiplier(quality, multiplier):
    quality = (quality or "").strip().lower()
    if not quality:
        return {"success": False, "message": "❌ Quality name required."}
    if multiplier < 0:
        return {"success": False, "message": "❌ Multiplier cannot be negative."}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO quality_multipliers (quality, multiplier, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(quality) DO UPDATE SET multiplier=excluded.multiplier, updated_at=excluded.updated_at",
        (quality, multiplier, time.time()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"✅ Quality '{quality}' multiplier set to {multiplier}x."}


def delete_quality_multiplier(quality):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM quality_multipliers WHERE quality = ?", (quality,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"🗑️ Removed quality '{quality}'."}


def _normalize_key(value, table_map):
    """Case/format-insensitive lookup against an admin-defined multiplier map.
    Falls back to multiplier 1.0 if admin hasn't defined this key yet, so a
    generation is never blocked just because pricing metadata is missing."""
    if value is None:
        return 1.0, None
    key = str(value).strip().lower()
    if key in table_map:
        return table_map[key], key
    # try stripping non-alphanumeric (e.g. "1920x1080" vs "1080p")
    for k, v in table_map.items():
        if k in key or key in k:
            return v, k
    return 1.0, None


def calculate_price(duration_seconds, resolution, quality, user_id=None, extra_charge_ids=None):
    """
    THE single source of truth for video pricing across the whole app.
    Formula: base_rate_per_second x duration_seconds x resolution_multiplier x quality_multiplier
    Then any admin discount (per-user > global) is applied, then any active
    extra charges are added on top (flat USD, not yet exposed in UI).

    Every video-generating tool should call this before generating and after
    the user picks duration/resolution/quality, to (a) show a live estimate
    and (b) determine the actual amount to deduct from the user's wallet.
    """
    try:
        duration_seconds = max(0.0, float(duration_seconds or 0))
    except (TypeError, ValueError):
        duration_seconds = 0.0

    formula = get_pricing_formula()
    base_rate = formula["base_rate_per_second"]
    min_charge = formula["min_charge_usd"]

    res_map = get_resolution_multipliers()
    qual_map = get_quality_multipliers()

    res_multiplier, res_matched = _normalize_key(resolution, res_map)
    qual_multiplier, qual_matched = _normalize_key(quality, qual_map)

    base_total = base_rate * duration_seconds * res_multiplier * qual_multiplier

    extras_total = 0.0
    extras_applied = []
    if extra_charge_ids:
        conn = sqlite3.connect(DB_PATH)
        for cid in extra_charge_ids:
            row = conn.execute(
                "SELECT label, amount_usd, active FROM extra_charges WHERE charge_id = ?", (cid,)
            ).fetchone()
            if row and row[2]:
                extras_total += row[1]
                extras_applied.append({"charge_id": cid, "label": row[0], "amount_usd": row[1]})
        conn.close()

    pre_discount_total = base_total + extras_total
    pre_discount_total = max(pre_discount_total, min_charge)

    percent, discount_source = _get_active_discount_for_user(user_id)
    final_price = pre_discount_total * (1 - percent / 100)
    final_price = round(max(final_price, 0.0), 2)

    return {
        "success": True,
        "duration_seconds": duration_seconds,
        "base_rate_per_second": base_rate,
        "resolution": resolution,
        "resolution_multiplier": res_multiplier,
        "quality": quality,
        "quality_multiplier": qual_multiplier,
        "base_total": round(base_total, 2),
        "extras_total": round(extras_total, 2),
        "extras_applied": extras_applied,
        "pre_discount_total": round(pre_discount_total, 2),
        "discount_percent": percent,
        "discount_source": discount_source,
        "final_price": final_price,
        "currency": "USD",
    }


# ------------------------------------------------------------
# Streamlit admin UI (password gate + management screens)
# ------------------------------------------------------------
def render_admin_page():
    init_db()
    st.subheader("🔐 Admin — Pricing & Discounts")

    if "admin_authed" not in st.session_state:
        st.session_state["admin_authed"] = False

    if not st.session_state["admin_authed"]:
        pw = st.text_input("Admin Password", type="password", key="admin_pw_input")
        if st.button("Login", key="admin_login_btn"):
            if verify_admin_password(pw):
                st.session_state["admin_authed"] = True
                st.rerun()
            else:
                st.error("❌ Wrong password.")
        return

    tab0, tab1, tab2, tab3, tab4 = st.tabs(
        ["🧮 Pricing Formula", "💵 Flat Feature Prices", "🌍 Global Discount", "👤 Per-User Discount", "🖼️ Frame Rules"]
    )

    with tab0:
        _render_pricing_formula_tab()

    with tab1:
        st.markdown("### Set/Update Flat Feature Price (legacy / non-duration features)")
        c1, c2 = st.columns(2)
        with c1:
            feature_id = st.text_input("Feature ID (e.g. text_to_video)", key="admin_feat_id")
        with c2:
            price = st.number_input("Price (USD)", min_value=0.0, step=0.5, key="admin_feat_price")
        if st.button("💾 Save Price", key="admin_save_price"):
            result = set_global_price(feature_id, price)
            st.success(result["message"]) if result["success"] else st.error(result["message"])
        st.divider()
        st.markdown("### Current Prices")
        for p in get_all_prices():
            st.write(f"**{p['feature_id']}** — ${p['base_price']:.2f}")

    with tab2:
        st.markdown("### Global Discount (applies to everyone)")
        current = get_global_discount()
        g_percent = st.slider("Discount %", 0, 100, int(current["percent"]), key="admin_global_pct")
        g_active = st.checkbox("Active", value=current["active"], key="admin_global_active")
        if st.button("💾 Save Global Discount", key="admin_save_global"):
            result = set_global_discount(g_percent, g_active)
            st.success(result["message"]) if result["success"] else st.error(result["message"])

    with tab3:
        st.markdown("### Per-User Discount (overrides global)")
        c1, c2 = st.columns(2)
        with c1:
            u_id = st.text_input("User ID", key="admin_user_id")
        with c2:
            u_pct = st.number_input("Discount %", min_value=0.0, max_value=100.0, step=1.0, key="admin_user_pct")
        u_active = st.checkbox("Active", value=True, key="admin_user_active")
        if st.button("💾 Save User Discount", key="admin_save_user"):
            result = set_user_discount(u_id, u_pct, u_active)
            st.success(result["message"]) if result["success"] else st.error(result["message"])
        st.divider()
        st.markdown("### Current Per-User Discounts")
        for u in get_all_user_discounts():
            status = "🟢" if u["active"] else "⚪"
            st.write(f"{status} **{u['user_id']}** — {u['percent']}%")

    with tab4:
        _render_frame_rules_tab()


def _render_pricing_formula_tab():
    st.markdown("### 🧮 Global Video Pricing Formula")
    st.caption(
        "This ONE formula sets the price for every video-generating tool in the app "
        "(Text-to-Video, Image-to-Video, Clips, Character Consistency, Camera Motion, "
        "Frame-to-Frame, Stitching, Pay-Per-Video, etc.). Every user is charged according "
        "to this — there is no separate per-user pricing formula, only per-user discounts "
        "(see the Per-User Discount tab)."
    )
    st.info(
        "**Formula:**  Final Price (USD) = Base Rate/sec  ×  Duration (s)  ×  "
        "Resolution Multiplier  ×  Quality Multiplier   *(then discount applied)*"
    )

    formula = get_pricing_formula()
    c1, c2 = st.columns(2)
    with c1:
        new_base_rate = st.number_input(
            "Base rate per second (USD)", min_value=0.0, step=0.01,
            value=float(formula["base_rate_per_second"]), format="%.4f", key="admin_base_rate"
        )
    with c2:
        new_min_charge = st.number_input(
            "Minimum charge per video (USD)", min_value=0.0, step=0.05,
            value=float(formula["min_charge_usd"]), key="admin_min_charge"
        )
    if st.button("💾 Save Base Formula", key="admin_save_formula", type="primary"):
        result = set_pricing_formula(new_base_rate, new_min_charge)
        st.success(result["message"]) if result["success"] else st.error(result["message"])
        st.rerun()

    st.divider()
    st.markdown("### 📐 Resolution Multipliers")
    res_map = get_resolution_multipliers()
    if res_map:
        for res, mult in res_map.items():
            rc1, rc2, rc3 = st.columns([2, 2, 1])
            rc1.write(f"**{res}**")
            rc2.write(f"{mult}x")
            if rc3.button("🗑️", key=f"admin_del_res_{res}"):
                delete_resolution_multiplier(res)
                st.rerun()
    else:
        st.caption("No resolution multipliers set yet.")

    with st.form("admin_add_res_form", clear_on_submit=True):
        fc1, fc2, fc3 = st.columns([2, 2, 1])
        with fc1:
            add_res = st.text_input("Resolution (e.g. 1080p)", key="admin_new_res_name")
        with fc2:
            add_res_mult = st.number_input("Multiplier", min_value=0.0, step=0.1, value=1.0, key="admin_new_res_mult")
        with fc3:
            st.write("")
            submitted = st.form_submit_button("➕ Add/Update")
        if submitted:
            result = set_resolution_multiplier(add_res, add_res_mult)
            st.success(result["message"]) if result["success"] else st.error(result["message"])
            st.rerun()

    st.divider()
    st.markdown("### 🎯 Quality Multipliers")
    qual_map = get_quality_multipliers()
    if qual_map:
        for q, mult in qual_map.items():
            qc1, qc2, qc3 = st.columns([2, 2, 1])
            qc1.write(f"**{q}**")
            qc2.write(f"{mult}x")
            if qc3.button("🗑️", key=f"admin_del_qual_{q}"):
                delete_quality_multiplier(q)
                st.rerun()
    else:
        st.caption("No quality multipliers set yet.")

    with st.form("admin_add_qual_form", clear_on_submit=True):
        fc1, fc2, fc3 = st.columns([2, 2, 1])
        with fc1:
            add_q = st.text_input("Quality (e.g. high)", key="admin_new_qual_name")
        with fc2:
            add_q_mult = st.number_input("Multiplier", min_value=0.0, step=0.1, value=1.0, key="admin_new_qual_mult")
        with fc3:
            st.write("")
            submitted_q = st.form_submit_button("➕ Add/Update")
        if submitted_q:
            result = set_quality_multiplier(add_q, add_q_mult)
            st.success(result["message"]) if result["success"] else st.error(result["message"])
            st.rerun()

    st.divider()
    st.markdown("### 🧪 Test the Formula")
    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        test_dur = st.number_input("Duration (s)", min_value=1, value=10, key="admin_test_dur")
    with tc2:
        test_res = st.selectbox("Resolution", list(res_map.keys()) or ["720p"], key="admin_test_res")
    with tc3:
        test_qual = st.selectbox("Quality", list(qual_map.keys()) or ["standard"], key="admin_test_qual")
    with tc4:
        st.write("")
        st.write("")
        if st.button("Calculate", key="admin_test_calc"):
            result = calculate_price(test_dur, test_res, test_qual)
            st.success(f"💰 ${result['final_price']:.2f} USD")
            st.json(result)


# ------------------------------------------------------------
# Frame Rules tab — config-driven model frame/duration policy
# (this is the answer to the "8*n+1 frame error" problem: instead of
# every feature file hardcoding a formula, the admin manages it here,
# and frame_policy.py is the single place feature files read from)
# ------------------------------------------------------------
def _render_frame_rules_tab():
    st.markdown("### 🖼️ Model Frame / Duration Rules")
    st.caption(
        "Controls how many frames (or which durations) each video model is "
        "allowed to receive. When you add a new model (Wan 2.3, Wan 2.6, a "
        "future LTX version, etc.), add its rule here — no code changes "
        "needed in any feature file."
    )

    st.markdown("#### Current Rules")
    rules = frame_policy.get_all_rules()
    if not rules:
        st.info("No rules configured yet.")
    else:
        for model_name, rule in rules.items():
            with st.container(border=True):
                cols = st.columns([3, 4, 1])
                with cols[0]:
                    st.markdown(f"**{model_name}**")
                with cols[1]:
                    formula = rule.get("formula")
                    if formula in ("8n+1", "4n+1", "multiple_of_8", "multiple_of_16"):
                        st.caption(
                            f"Formula: `{formula}` · min {rule.get('min_frames')} / "
                            f"max {rule.get('max_frames')} frames · {rule.get('fps', 24)} fps"
                        )
                    elif formula == "fixed_durations":
                        st.caption(f"Formula: `fixed_durations` · allowed: {rule.get('allowed_durations')}s")
                    else:
                        st.caption(
                            f"Formula: `any` (duration-based) · min {rule.get('min_duration')}s / "
                            f"max {rule.get('max_duration')}s"
                        )
                with cols[2]:
                    if st.button("🗑️", key=f"frmrule_del_{model_name}"):
                        result = frame_policy.delete_rule(model_name)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])

    st.divider()
    st.markdown("#### Add / Update a Rule")

    c1, c2 = st.columns(2)
    with c1:
        model_name = st.text_input(
            "Model name (must match AGNES_AI_MODEL / LTX model string / WAN model string exactly)",
            key="frmrule_model_name",
            placeholder="e.g. agnes-video-v2.0, wan-2.3, ltx-2-3-pro",
        )
    with c2:
        formula = st.selectbox(
            "Formula",
            ["8n+1", "4n+1", "multiple_of_8", "multiple_of_16", "fixed_durations", "any"],
            key="frmrule_formula",
            help=(
                "8n+1 / 4n+1 / multiple_of_8 / multiple_of_16 = this model needs raw "
                "frame counts snapped to that pattern.\n"
                "fixed_durations = this model only accepts an exact list of durations "
                "(e.g. WAN 2.6 R2V: 5 or 10 seconds).\n"
                "any = this model takes duration directly, just clamp min/max."
            ),
        )

    fps = st.number_input("FPS (used to convert seconds → frames)", min_value=1, max_value=60, value=24, key="frmrule_fps")

    min_frames = max_frames = None
    allowed_durations_list = None
    min_duration = max_duration = None

    if formula in ("8n+1", "4n+1", "multiple_of_8", "multiple_of_16"):
        c3, c4 = st.columns(2)
        with c3:
            min_frames = st.number_input("Min frames", min_value=1, value=9, key="frmrule_min_frames")
        with c4:
            max_frames = st.number_input("Max frames", min_value=1, value=480, key="frmrule_max_frames")
    elif formula == "fixed_durations":
        allowed_str = st.text_input(
            "Allowed durations (comma-separated seconds)", value="5, 10", key="frmrule_allowed_durations"
        )
        try:
            allowed_durations_list = [int(x.strip()) for x in allowed_str.split(",") if x.strip()]
        except ValueError:
            allowed_durations_list = None
            st.warning("⚠️ Enter allowed durations as whole numbers separated by commas, e.g. 5, 10")
    else:  # "any"
        c3, c4 = st.columns(2)
        with c3:
            min_duration = st.number_input("Min duration (s)", min_value=1, value=3, key="frmrule_min_duration")
        with c4:
            max_duration = st.number_input("Max duration (s)", min_value=1, value=20, key="frmrule_max_duration")

    if st.button("💾 Save Rule", key="frmrule_save", type="primary"):
        result = frame_policy.upsert_rule(
            model_name=model_name,
            formula=formula,
            min_frames=min_frames,
            max_frames=max_frames,
            allowed_durations=allowed_durations_list,
            min_duration=min_duration,
            max_duration=max_duration,
            fps=fps,
        )
        if result["success"]:
            st.success(result["message"])
            st.rerun()
        else:
            st.error(result["message"])

    st.divider()
    st.markdown("#### Test a Rule")
    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        test_model = st.text_input("Model name", key="frmrule_test_model", placeholder="agnes-video-v2.0")
    with tc2:
        test_seconds = st.number_input("Duration (s)", min_value=1, value=10, key="frmrule_test_seconds")
    with tc3:
        if st.button("🧪 Compute Frames", key="frmrule_test_btn"):
            if test_model:
                computed = frame_policy.get_frames_for_duration(test_model, test_seconds)
                st.info(f"→ {computed} frames")
            else:
                st.warning("Enter a model name first.")


if __name__ == "__main__":
    print(init_db())
    print(set_pricing_formula(0.5, 0.10))
    print(set_resolution_multiplier("720p", 1.0))
    print(set_resolution_multiplier("1080p", 1.6))
    print(set_quality_multiplier("standard", 1.0))
    print(set_quality_multiplier("high", 1.4))
    print(set_global_discount(10, True))
    print(set_user_discount("shan_test", 25, True))
    print(calculate_price(10, "1080p", "high", "shan_test"))
    print(calculate_price(10, "1080p", "high", "random_user"))