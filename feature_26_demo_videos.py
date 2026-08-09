# ============================================================
# FEATURE 26 — DEMO VIDEOS (user uploads, admin-verified before public)
# Filename: feature_26_demo_videos.py
# ============================================================
# What this does:
# - Any logged-in user can upload their own video (any length/size,
#   within MAX_FILE_SIZE_MB) with a short caption, from the Trending tab.
# - It goes in as status='pending' — NOT visible to other users yet.
# - Admin reviews pending uploads (admin_panel.py → 🎬 Demo Video Review
#   tab) and Approves or Rejects (with an optional reason).
# - Only status='approved' videos show up in the public gallery that
#   every user sees on the Trending tab.
#
# Pure logic module — no Streamlit import here. ui.py and admin_panel.py
# handle all rendering; this file only manages storage + the DB.
# ============================================================

import os
import time
import sqlite3
import uuid

try:
    import config
    DB_PATH = getattr(config, "DEMO_VIDEOS_DB_PATH", os.path.join("data", "demo_videos.db"))
    STORAGE_DIR = getattr(config, "DEMO_VIDEOS_DIR", os.path.join("uploads", "demo_videos"))
except ImportError:
    DB_PATH = os.path.join("data", "demo_videos.db")
    STORAGE_DIR = os.path.join("uploads", "demo_videos")

MAX_FILE_SIZE_MB = 200
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}


# ============================================================
# DATABASE
# ============================================================

def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS demo_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            user_email TEXT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            caption TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            reject_reason TEXT,
            reviewed_by TEXT,
            reviewed_at REAL,
            uploaded_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def init_db():
    _get_conn().close()


_COLUMNS = ("id, user_id, user_email, filename, filepath, caption, status, "
            "reject_reason, reviewed_by, reviewed_at, uploaded_at")


def _row_to_dict(row) -> dict:
    (vid, user_id, user_email, filename, filepath, caption, status,
     reject_reason, reviewed_by, reviewed_at, uploaded_at) = row
    return {
        "id": vid, "user_id": user_id, "user_email": user_email,
        "filename": filename, "filepath": filepath, "caption": caption,
        "status": status, "reject_reason": reject_reason,
        "reviewed_by": reviewed_by, "reviewed_at": reviewed_at,
        "uploaded_at": uploaded_at,
    }


# ============================================================
# SUBMIT (user side)
# ============================================================

def submit_demo_video(user_id: str, user_email: str, uploaded_file, caption: str = "") -> dict:
    """uploaded_file is a Streamlit UploadedFile — needs .name and .getbuffer()."""
    if uploaded_file is None:
        return {"success": False, "message": "❌ Pehle koi video select karo."}
    if not user_id:
        return {"success": False, "message": "❌ Sidebar mein User ID set karo pehle."}

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"success": False, "message": f"❌ Sirf {', '.join(ALLOWED_EXTENSIONS)} files allowed hain."}

    buffer = uploaded_file.getbuffer()
    size_mb = len(buffer) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return {"success": False, "message": f"❌ File {size_mb:.0f}MB hai — limit {MAX_FILE_SIZE_MB}MB hai."}
    if size_mb < 0.01:
        return {"success": False, "message": "❌ File khaali ya corrupt lag rahi hai."}

    os.makedirs(STORAGE_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(STORAGE_DIR, unique_name)
    with open(dest_path, "wb") as f:
        f.write(buffer)

    now = time.time()
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO demo_videos (user_id, user_email, filename, filepath, caption, "
        "status, uploaded_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
        (user_id, user_email, uploaded_file.name, dest_path, caption.strip(), now),
    )
    conn.commit()
    video_id = cur.lastrowid
    conn.close()

    return {
        "success": True,
        "video_id": video_id,
        "message": "✅ Upload ho gaya! Admin verify karne ke baad Trending mein sab ko dikhega.",
    }


# ============================================================
# READ (public + admin)
# ============================================================

def get_approved_videos(limit: int = 50) -> list:
    conn = _get_conn()
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM demo_videos WHERE status = 'approved' "
        f"ORDER BY reviewed_at DESC LIMIT ?", (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_pending_videos(limit: int = 100) -> list:
    conn = _get_conn()
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM demo_videos WHERE status = 'pending' "
        f"ORDER BY uploaded_at ASC LIMIT ?", (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_pending_count() -> int:
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM demo_videos WHERE status = 'pending'").fetchone()[0]
    conn.close()
    return count


def get_user_videos(user_id: str, limit: int = 20) -> list:
    conn = _get_conn()
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM demo_videos WHERE user_id = ? "
        f"ORDER BY uploaded_at DESC LIMIT ?", (user_id, limit),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ============================================================
# ADMIN ACTIONS
# ============================================================

def approve_video(video_id: int, reviewed_by: str) -> dict:
    conn = _get_conn()
    conn.execute(
        "UPDATE demo_videos SET status = 'approved', reviewed_by = ?, reviewed_at = ?, "
        "reject_reason = NULL WHERE id = ?",
        (reviewed_by, time.time(), video_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "✅ Video approved — ab Trending mein sab ko dikhegi."}


def reject_video(video_id: int, reviewed_by: str, reason: str = "") -> dict:
    conn = _get_conn()
    conn.execute(
        "UPDATE demo_videos SET status = 'rejected', reviewed_by = ?, reviewed_at = ?, "
        "reject_reason = ? WHERE id = ?",
        (reviewed_by, time.time(), reason.strip() or "No reason provided", video_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "🚫 Video rejected."}


def delete_video(video_id: int) -> dict:
    """Removes the DB row AND the file on disk — for admin cleanup."""
    conn = _get_conn()
    row = conn.execute("SELECT filepath FROM demo_videos WHERE id = ?", (video_id,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "message": "❌ Video not found."}
    filepath = row[0]
    conn.execute("DELETE FROM demo_videos WHERE id = ?", (video_id,))
    conn.commit()
    conn.close()
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass
    return {"success": True, "message": "🗑️ Video deleted."}