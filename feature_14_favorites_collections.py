# ============================================
# FEATURE 14: FAVORITES & COLLECTIONS (COMPLETE FIX)
# Filename: feature_14_favorites_collections.py
# ============================================

import os
import sys
import json
import shutil
import hashlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from collections import defaultdict
import logging

# UTF-8 stdout safety
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from config import *
except ImportError:
    logger.warning("config.py not found! Using default config.")
    # Fallback config
    PATHS = {
        'temp': 'temp',
        'videos': 'videos',
        'library': 'library',
        'collections': 'collections'
    }

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# ============================================
# CONSTANTS
# ============================================

FAVORITES_DB_FILE = os.path.join(PATHS.get('library', 'library'), "favorites_db.json")
COLLECTIONS_DB_FILE = os.path.join(PATHS.get('library', 'library'), "collections_db.json")

os.makedirs(PATHS.get('library', 'library'), exist_ok=True)

# Cache
_CACHE = {}
_CACHE_TIMESTAMP = None
_CACHE_TTL = 60


# ============================================
# CACHE MANAGEMENT
# ============================================

def _is_cache_valid() -> bool:
    global _CACHE_TIMESTAMP
    if _CACHE_TIMESTAMP is None:
        return False
    return (datetime.now() - _CACHE_TIMESTAMP).total_seconds() < _CACHE_TTL


def _invalidate_cache():
    global _CACHE, _CACHE_TIMESTAMP
    _CACHE = {}
    _CACHE_TIMESTAMP = None


def _update_cache_timestamp():
    global _CACHE_TIMESTAMP
    _CACHE_TIMESTAMP = datetime.now()


# ============================================
# DATABASE FUNCTIONS
# ============================================

def _load_favorites_db() -> Dict[str, Any]:
    """Load favorites database with caching"""
    cache_key = "favorites_db"
    if cache_key in _CACHE and _is_cache_valid():
        return _CACHE[cache_key]
    
    if not os.path.exists(FAVORITES_DB_FILE):
        default_data = {
            "favorites": [],
            "version": "1.1",
            "updated_at": datetime.now().isoformat(),
            "total_favorites": 0
        }
        try:
            with open(FAVORITES_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to create favorites DB: {e}")
        _CACHE[cache_key] = default_data
        _update_cache_timestamp()
        return default_data
    
    try:
        with open(FAVORITES_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "version" not in data:
                data["version"] = "1.0"
            if "total_favorites" not in data:
                data["total_favorites"] = len(data.get("favorites", []))
            if "favorites" not in data:
                data["favorites"] = []
            _CACHE[cache_key] = data
            _update_cache_timestamp()
            return data
    except Exception as e:
        logger.error(f"Failed to load favorites DB: {e}")
        return {"favorites": [], "version": "1.1", "updated_at": datetime.now().isoformat(), "total_favorites": 0}


def _save_favorites_db(data: Dict[str, Any]) -> bool:
    """Save favorites database with backup"""
    try:
        data["updated_at"] = datetime.now().isoformat()
        data["total_favorites"] = len(data.get("favorites", []))
        
        if os.path.exists(FAVORITES_DB_FILE):
            try:
                backup_path = f"{FAVORITES_DB_FILE}.backup"
                shutil.copy2(FAVORITES_DB_FILE, backup_path)
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")
        
        with open(FAVORITES_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        _invalidate_cache()
        return True
    except Exception as e:
        logger.error(f"Failed to save favorites DB: {e}")
        return False


def _load_collections_db() -> Dict[str, Any]:
    """Load collections database with caching"""
    cache_key = "collections_db"
    if cache_key in _CACHE and _is_cache_valid():
        return _CACHE[cache_key]
    
    if not os.path.exists(COLLECTIONS_DB_FILE):
        default_data = {
            "collections": [],
            "version": "1.1",
            "updated_at": datetime.now().isoformat(),
            "total_collections": 0,
            "total_videos": 0
        }
        try:
            with open(COLLECTIONS_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to create collections DB: {e}")
        _CACHE[cache_key] = default_data
        _update_cache_timestamp()
        return default_data
    
    try:
        with open(COLLECTIONS_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "version" not in data:
                data["version"] = "1.0"
            if "total_collections" not in data:
                data["total_collections"] = len(data.get("collections", []))
            if "total_videos" not in data:
                data["total_videos"] = sum(c.get("video_count", 0) for c in data.get("collections", []))
            if "collections" not in data:
                data["collections"] = []
            _CACHE[cache_key] = data
            _update_cache_timestamp()
            return data
    except Exception as e:
        logger.error(f"Failed to load collections DB: {e}")
        return {"collections": [], "version": "1.1", "updated_at": datetime.now().isoformat(), "total_collections": 0, "total_videos": 0}


def _save_collections_db(data: Dict[str, Any]) -> bool:
    """Save collections database with backup"""
    try:
        data["updated_at"] = datetime.now().isoformat()
        data["total_collections"] = len(data.get("collections", []))
        data["total_videos"] = sum(c.get("video_count", 0) for c in data.get("collections", []))
        
        if os.path.exists(COLLECTIONS_DB_FILE):
            try:
                backup_path = f"{COLLECTIONS_DB_FILE}.backup"
                shutil.copy2(COLLECTIONS_DB_FILE, backup_path)
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")
        
        with open(COLLECTIONS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        _invalidate_cache()
        return True
    except Exception as e:
        logger.error(f"Failed to save collections DB: {e}")
        return False


def _generate_collection_id() -> str:
    """Generate a unique collection ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_part = uuid.uuid4().hex[:6]
    return f"col_{timestamp}_{random_part}"


def _get_video_metadata(video_id: str) -> Optional[Dict[str, Any]]:
    """Get video metadata from library with caching"""
    if not video_id:
        return None
    
    cache_key = f"video_meta_{video_id}"
    if cache_key in _CACHE and _is_cache_valid():
        return _CACHE[cache_key]
    
    try:
        from feature_12_video_library import get_video_by_id
        video = get_video_by_id(video_id)
        if video:
            _CACHE[cache_key] = video
            _update_cache_timestamp()
            return video
    except ImportError:
        logger.debug("Video library not available")
    
    basic_meta = {
        "id": video_id,
        "filename": f"Video {video_id[:8]}",
        "prompt": "Unknown",
        "resolution": "Unknown",
        "duration": 0,
        "file_path": "",
        "thumbnail": None
    }
    _CACHE[cache_key] = basic_meta
    _update_cache_timestamp()
    return basic_meta


def _validate_collection_name(name: str) -> Dict[str, Any]:
    """Validate collection name"""
    if not name or len(name.strip()) < 1:
        return {"valid": False, "message": "Collection name cannot be empty"}
    
    name = name.strip()
    
    if len(name) > 100:
        return {"valid": False, "message": "Collection name cannot exceed 100 characters"}
    
    forbidden = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\x00']
    for char in forbidden:
        if char in name:
            return {"valid": False, "message": f"Collection name cannot contain '{char}'"}
    
    return {"valid": True, "name": name}


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to readable format"""
    if seconds <= 0:
        return "0s"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def _format_size(bytes_size: int) -> str:
    """Format file size to readable format"""
    if bytes_size <= 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes_size)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"


# ============================================
# FAVORITES FUNCTIONS
# ============================================

def add_to_favorites(
    video_id: str,
    notes: str = "",
    tags: List[str] = None
) -> Dict[str, Any]:
    """Add a video to favorites"""
    
    logger.info(f"⭐ Adding video to favorites: {video_id}")
    
    if not video_id:
        return {"success": False, "message": "Video ID is required"}
    
    video = _get_video_metadata(video_id)
    if not video:
        return {"success": False, "message": f"Video not found: {video_id}"}
    
    db = _load_favorites_db()
    
    for fav in db.get("favorites", []):
        if fav.get("video_id") == video_id:
            return {"success": False, "message": "Video already in favorites"}
    
    favorite_entry = {
        "video_id": video_id,
        "video_title": video.get("filename", "Unknown"),
        "added_at": datetime.now().isoformat(),
        "notes": notes or "",
        "tags": tags or [],
        "video_metadata": {
            "prompt": video.get("prompt", ""),
            "resolution": video.get("resolution", ""),
            "duration": video.get("duration", 0),
            "thumbnail": video.get("thumbnail", ""),
            "category": video.get("category", ""),
            "file_path": video.get("file_path", "")
        }
    }
    
    db["favorites"].append(favorite_entry)
    
    if _save_favorites_db(db):
        logger.info(f"✅ Video added to favorites: {video.get('filename')}")
        return {"success": True, "favorite": favorite_entry}
    else:
        return {"success": False, "message": "Failed to save to database"}


def remove_from_favorites(video_id: str) -> Dict[str, Any]:
    """Remove a video from favorites"""
    
    logger.info(f"⭐ Removing video from favorites: {video_id}")
    
    db = _load_favorites_db()
    favorites = db.get("favorites", [])
    
    for i, fav in enumerate(favorites):
        if fav.get("video_id") == video_id:
            removed = favorites.pop(i)
            db["favorites"] = favorites
            if _save_favorites_db(db):
                logger.info(f"✅ Video removed from favorites: {removed.get('video_title')}")
                return {"success": True, "removed": removed}
            else:
                return {"success": False, "message": "Failed to save to database"}
    
    return {"success": False, "message": "Video not in favorites"}


def toggle_favorite(
    video_id: str,
    notes: str = "",
    tags: List[str] = None
) -> Dict[str, Any]:
    """Toggle favorite status of a video"""
    
    db = _load_favorites_db()
    for fav in db.get("favorites", []):
        if fav.get("video_id") == video_id:
            return remove_from_favorites(video_id)
    
    return add_to_favorites(video_id, notes, tags)


def update_favorite_notes(video_id: str, notes: str) -> Dict[str, Any]:
    """Update notes for a favorite video"""
    
    db = _load_favorites_db()
    for fav in db.get("favorites", []):
        if fav.get("video_id") == video_id:
            fav["notes"] = notes or ""
            if _save_favorites_db(db):
                return {"success": True, "favorite": fav}
            else:
                return {"success": False, "message": "Failed to save to database"}
    
    return {"success": False, "message": "Video not in favorites"}


def get_all_favorites(filter_tags: List[str] = None) -> List[Dict[str, Any]]:
    """Get all favorite videos with optional tag filter"""
    db = _load_favorites_db()
    favorites = db.get("favorites", [])
    
    if filter_tags:
        favorites = [
            f for f in favorites
            if any(tag in f.get("tags", []) for tag in filter_tags)
        ]
    
    enriched = []
    for fav in favorites:
        video_id = fav.get("video_id")
        video = _get_video_metadata(video_id)
        fav_copy = fav.copy()
        if video:
            fav_copy["video_data"] = video
            fav_copy["deleted"] = False
        else:
            fav_copy["video_data"] = None
            fav_copy["deleted"] = True
        enriched.append(fav_copy)
    
    return enriched


def get_favorite_video_ids() -> List[str]:
    """Get list of favorite video IDs"""
    db = _load_favorites_db()
    return [fav.get("video_id") for fav in db.get("favorites", [])]


def is_favorite(video_id: str) -> bool:
    """Check if a video is in favorites"""
    return video_id in get_favorite_video_ids()


def get_favorite_statistics() -> Dict[str, Any]:
    """Get comprehensive statistics about favorites"""
    favorites = get_all_favorites()
    
    total = len(favorites)
    with_notes = len([f for f in favorites if f.get("notes")])
    with_tags = len([f for f in favorites if f.get("tags")])
    
    tag_freq = defaultdict(int)
    for fav in favorites:
        for tag in fav.get("tags", []):
            tag_freq[tag] += 1
    
    sorted_by_date = sorted(favorites, key=lambda x: x.get("added_at", ""), reverse=True)
    recent = sorted_by_date[:5] if sorted_by_date else []
    
    categories = defaultdict(int)
    for fav in favorites:
        cat = fav.get("video_metadata", {}).get("category", "unknown")
        categories[cat] += 1
    
    return {
        "total_favorites": total,
        "with_notes": with_notes,
        "with_tags": with_tags,
        "tag_frequency": dict(tag_freq),
        "category_distribution": dict(categories),
        "recent_favorites": recent,
        "last_updated": datetime.now().isoformat()
    }


def search_favorites(query: str, search_fields: List[str] = None) -> List[Dict[str, Any]]:
    """Search favorites by title, notes, or tags"""
    if not query or not query.strip():
        return get_all_favorites()
    
    favorites = get_all_favorites()
    query_lower = query.lower().strip()
    search_fields = search_fields or ["video_title", "notes", "tags"]
    results = []
    
    for fav in favorites:
        matched = False
        for field in search_fields:
            if field == "tags":
                if any(query_lower in tag.lower() for tag in fav.get("tags", [])):
                    matched = True
                    break
            else:
                value = fav.get(field, "")
                if query_lower in str(value).lower():
                    matched = True
                    break
        
        if matched:
            results.append(fav)
    
    return results


def get_favorite_tags() -> List[str]:
    """Get all tags used in favorites"""
    favorites = get_all_favorites()
    tags = set()
    for fav in favorites:
        tags.update(fav.get("tags", []))
    return sorted(list(tags))


# ============================================
# COLLECTIONS FUNCTIONS
# ============================================

def create_collection(
    name: str,
    description: str = "",
    is_public: bool = False,
    tags: List[str] = None,
    cover_video_id: str = None
) -> Dict[str, Any]:
    """Create a new collection"""
    
    logger.info(f"📁 Creating collection: {name}")
    
    name_validation = _validate_collection_name(name)
    if not name_validation["valid"]:
        return {"success": False, "message": name_validation["message"]}
    
    name = name_validation["name"]
    
    db = _load_collections_db()
    
    for col in db.get("collections", []):
        if col.get("name", "").lower() == name.lower():
            return {"success": False, "message": f"Collection '{name}' already exists"}
    
    collection_id = _generate_collection_id()
    
    new_collection = {
        "id": collection_id,
        "name": name,
        "description": description or "",
        "is_public": is_public,
        "videos": [],
        "video_order": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "video_count": 0,
        "views": 0,
        "tags": tags or [],
        "cover_video_id": cover_video_id,
        "share_code": uuid.uuid4().hex[:8] if is_public else None
    }
    
    db["collections"].append(new_collection)
    
    if _save_collections_db(db):
        logger.info(f"✅ Collection created: {name} (ID: {collection_id})")
        return {"success": True, "collection": new_collection}
    else:
        return {"success": False, "message": "Failed to save to database"}


def get_all_collections(sort_by: str = "created_at", reverse: bool = True) -> List[Dict[str, Any]]:
    """Get all collections with sorting"""
    db = _load_collections_db()
    collections = db.get("collections", [])
    
    sort_keys = {
        "name": "name",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "video_count": "video_count",
        "views": "views"
    }
    
    key = sort_keys.get(sort_by, "created_at")
    try:
        return sorted(collections, key=lambda x: x.get(key, ""), reverse=reverse)
    except Exception as e:
        logger.warning(f"Sort failed: {e}")
        return collections


def get_collection_by_id(collection_id: str) -> Optional[Dict[str, Any]]:
    """Get collection by ID"""
    if not collection_id:
        return None
    
    db = _load_collections_db()
    for collection in db.get("collections", []):
        if collection.get("id") == collection_id:
            return collection
    return None


def add_video_to_collection(
    collection_id: str,
    video_id: str,
    position: int = None
) -> Dict[str, Any]:
    """Add a video to a collection"""
    
    logger.info(f"📹 Adding video to collection: {collection_id}")
    
    collection = get_collection_by_id(collection_id)
    if not collection:
        return {"success": False, "message": "Collection not found"}
    
    video = _get_video_metadata(video_id)
    if not video:
        return {"success": False, "message": f"Video not found: {video_id}"}
    
    db = _load_collections_db()
    
    for col in db.get("collections", []):
        if col.get("id") == collection_id:
            if video_id in col.get("videos", []):
                return {"success": False, "message": "Video already in collection"}
            
            col["videos"].append(video_id)
            
            if "video_order" not in col:
                col["video_order"] = []
            
            if position is not None and 0 <= position <= len(col["video_order"]):
                col["video_order"].insert(position, video_id)
            else:
                col["video_order"].append(video_id)
            
            col["video_count"] = len(col["videos"])
            col["updated_at"] = datetime.now().isoformat()
            break
    
    if _save_collections_db(db):
        logger.info(f"✅ Video added to collection: {video.get('filename')}")
        return {"success": True, "collection_id": collection_id, "video_id": video_id}
    else:
        return {"success": False, "message": "Failed to save to database"}


def remove_video_from_collection(collection_id: str, video_id: str) -> Dict[str, Any]:
    """Remove a video from a collection"""
    
    logger.info(f"📹 Removing video from collection: {collection_id}")
    
    collection = get_collection_by_id(collection_id)
    if not collection:
        return {"success": False, "message": "Collection not found"}
    
    db = _load_collections_db()
    
    for col in db.get("collections", []):
        if col.get("id") == collection_id:
            if video_id not in col.get("videos", []):
                return {"success": False, "message": "Video not in collection"}
            
            col["videos"].remove(video_id)
            if video_id in col.get("video_order", []):
                col["video_order"].remove(video_id)
            col["video_count"] = len(col["videos"])
            col["updated_at"] = datetime.now().isoformat()
            break
    
    if _save_collections_db(db):
        logger.info(f"✅ Video removed from collection")
        return {"success": True, "collection_id": collection_id, "video_id": video_id}
    else:
        return {"success": False, "message": "Failed to save to database"}


def rename_collection(collection_id: str, new_name: str) -> Dict[str, Any]:
    """Rename a collection"""
    
    collection = get_collection_by_id(collection_id)
    if not collection:
        return {"success": False, "message": "Collection not found"}
    
    name_validation = _validate_collection_name(new_name)
    if not name_validation["valid"]:
        return {"success": False, "message": name_validation["message"]}
    
    new_name = name_validation["name"]
    
    db = _load_collections_db()
    
    for col in db.get("collections", []):
        if col.get("id") != collection_id and col.get("name", "").lower() == new_name.lower():
            return {"success": False, "message": f"Collection '{new_name}' already exists"}
    
    old_name = collection.get("name")
    for col in db.get("collections", []):
        if col.get("id") == collection_id:
            col["name"] = new_name
            col["updated_at"] = datetime.now().isoformat()
            break
    
    if _save_collections_db(db):
        logger.info(f"✅ Collection renamed: {old_name} → {new_name}")
        return {"success": True, "collection": get_collection_by_id(collection_id)}
    else:
        return {"success": False, "message": "Failed to save to database"}


def delete_collection(collection_id: str) -> Dict[str, Any]:
    """Delete a collection"""
    
    collection = get_collection_by_id(collection_id)
    if not collection:
        return {"success": False, "message": "Collection not found"}
    
    db = _load_collections_db()
    db["collections"] = [col for col in db.get("collections", []) if col.get("id") != collection_id]
    
    if _save_collections_db(db):
        logger.info(f"✅ Collection deleted: {collection.get('name')}")
        return {"success": True, "message": f"Collection deleted: {collection.get('name')}"}
    else:
        return {"success": False, "message": "Failed to save to database"}


def get_collection_videos(
    collection_id: str,
    order_by: str = "default"
) -> List[Dict[str, Any]]:
    """Get all videos in a collection"""
    
    collection = get_collection_by_id(collection_id)
    if not collection:
        return []
    
    video_ids = collection.get("videos", [])
    video_order = collection.get("video_order", [])
    
    video_map = {}
    for video_id in video_ids:
        video = _get_video_metadata(video_id)
        if video:
            video_map[video_id] = video
    
    if order_by == "default" and video_order:
        ordered_videos = []
        for vid in video_order:
            if vid in video_map:
                ordered_videos.append(video_map[vid])
        for vid, video in video_map.items():
            if vid not in video_order:
                ordered_videos.append(video)
        return ordered_videos
    
    elif order_by == "name":
        return sorted(video_map.values(), key=lambda x: x.get("filename", ""))
    elif order_by == "duration":
        return sorted(video_map.values(), key=lambda x: x.get("duration", 0))
    elif order_by == "date":
        return sorted(video_map.values(), key=lambda x: x.get("created_at", ""), reverse=True)
    else:
        return list(video_map.values())


def get_collection_statistics(collection_id: str = None) -> Dict[str, Any]:
    """Get collection statistics"""
    
    if collection_id:
        collection = get_collection_by_id(collection_id)
        if not collection:
            return {"error": "Collection not found"}
        
        videos = get_collection_videos(collection_id)
        total_duration = sum(v.get("duration", 0) for v in videos)
        total_size = sum(v.get("file_size", 0) for v in videos)
        
        return {
            "collection_name": collection.get("name"),
            "collection_id": collection_id,
            "total_videos": len(videos),
            "total_duration": total_duration,
            "total_duration_formatted": _format_duration(total_duration),
            "total_size": total_size,
            "total_size_formatted": _format_size(total_size),
            "created_at": collection.get("created_at"),
            "updated_at": collection.get("updated_at"),
            "views": collection.get("views", 0),
            "is_public": collection.get("is_public", False),
            "tags": collection.get("tags", [])
        }
    
    collections = get_all_collections()
    total_videos = sum(col.get("video_count", 0) for col in collections)
    total_views = sum(col.get("views", 0) for col in collections)
    
    tag_freq = defaultdict(int)
    for col in collections:
        for tag in col.get("tags", []):
            tag_freq[tag] += 1
    
    return {
        "total_collections": len(collections),
        "total_videos_in_collections": total_videos,
        "public_collections": len([c for c in collections if c.get("is_public", False)]),
        "total_views": total_views,
        "tag_frequency": dict(tag_freq),
        "last_updated": datetime.now().isoformat()
    }


# ============================================
# UI RENDER FUNCTION (FIXED - ALL WIDGETS HAVE KEYS)
# ============================================

def render_feature_14():
    """Render Favorites & Collections UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## ⭐ Favorites & Collections")
    st.markdown("*Apni favorite videos aur collections manage karein*")
    
    # Initialize session state
    if "selected_collection_14" not in st.session_state:
        st.session_state.selected_collection_14 = None
    if "favorites_tab_14" not in st.session_state:
        st.session_state.favorites_tab_14 = "Favorites"
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["⭐ Favorites", "📁 Collections", "📊 Statistics"])
    
    # Tab 1: Favorites
    with tab1:
        st.subheader("⭐ Favorite Videos")
        
        col1, col2 = st.columns(2)
        with col1:
            search_query = st.text_input(
                "🔍 Search favorites",
                placeholder="Search by title, notes, tags...",
                key="fav_search_14"
            )
        with col2:
            tag_filter = st.multiselect(
                "Filter by tags",
                get_favorite_tags(),
                key="fav_tag_filter_14"
            )
        
        if tag_filter:
            favorites = get_all_favorites(filter_tags=tag_filter)
        else:
            favorites = get_all_favorites()
        
        if search_query:
            favorites = search_favorites(search_query)
        
        if favorites:
            for idx, fav in enumerate(favorites):
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{fav.get('video_title')}**")
                        if fav.get("notes"):
                            st.caption(f"📝 {fav.get('notes')}")
                        if fav.get("tags"):
                            st.caption(f"🏷️ {', '.join(fav.get('tags', []))}")
                        if fav.get("video_data"):
                            video = fav.get("video_data")
                            st.caption(f"⏱️ {video.get('duration', 0):.1f}s | {video.get('resolution', 'Unknown')}")
                        st.caption(f"Added: {fav.get('added_at', '')[:10]}")
                    with col2:
                        if st.button(f"📝 Edit Notes", key=f"fav_edit_{fav.get('video_id')}_{idx}"):
                            new_notes = st.text_input("Notes", value=fav.get("notes", ""), key=f"fav_notes_input_{idx}")
                            if st.button("Save Notes", key=f"fav_save_notes_{fav.get('video_id')}_{idx}"):
                                update_favorite_notes(fav.get("video_id"), new_notes)
                                st.rerun()
                    with col3:
                        if st.button(f"⭐ Remove", key=f"fav_remove_{fav.get('video_id')}_{idx}"):
                            remove_from_favorites(fav.get("video_id"))
                            st.rerun()
                    st.divider()
        else:
            st.info("No favorites found. Go to Video Library and star some videos!")
        
        st.markdown("---")
        st.markdown("### ➕ Add to Favorites")
        col1, col2 = st.columns(2)
        with col1:
            fav_video_id = st.text_input("Video ID", placeholder="Enter video ID...", key="fav_add_video_14")
            fav_notes = st.text_input("Notes (optional)", key="fav_add_notes_14")
        with col2:
            fav_tags = st.text_input("Tags (comma separated)", key="fav_add_tags_14")
        
        if st.button("⭐ Add to Favorites", key="fav_add_btn_14"):
            if fav_video_id:
                tags_list = [t.strip() for t in fav_tags.split(",") if t.strip()]
                result = add_to_favorites(fav_video_id, fav_notes, tags_list)
                if result["success"]:
                    st.success("✅ Added to favorites!")
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")
            else:
                st.warning("Please enter a video ID")
    
    # Tab 2: Collections
    with tab2:
        st.subheader("📁 Collections")
        
        with st.expander("➕ Create New Collection", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                new_col_name = st.text_input("Collection Name", key="col_new_name_14")
                new_col_desc = st.text_input("Description (optional)", key="col_new_desc_14")
            with col2:
                new_col_tags = st.text_input("Tags (comma separated)", key="col_new_tags_14")
                new_col_public = st.checkbox("Make Public", key="col_new_public_14")
            
            if st.button("Create Collection", key="col_create_btn_14"):
                if new_col_name:
                    tags_list = [t.strip() for t in new_col_tags.split(",") if t.strip()]
                    result = create_collection(new_col_name, new_col_desc, new_col_public, tags_list)
                    if result["success"]:
                        st.success("✅ Collection created!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['message']}")
                else:
                    st.warning("Please enter a collection name")
        
        collections = get_all_collections()
        
        if collections:
            for idx, col in enumerate(collections):
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**📁 {col.get('name')}**")
                        st.caption(f"Videos: {col.get('video_count', 0)} | Views: {col.get('views', 0)}")
                        if col.get("tags"):
                            st.caption(f"🏷️ {', '.join(col.get('tags', []))}")
                        if col.get("is_public"):
                            st.caption("🔓 Public")
                    with col2:
                        if st.button(f"📂 Open", key=f"col_open_{col.get('id')}_{idx}"):
                            st.session_state.selected_collection_14 = col.get("id")
                            st.rerun()
                    with col3:
                        if st.button(f"🗑️ Delete", key=f"col_del_{col.get('id')}_{idx}"):
                            delete_collection(col.get("id"))
                            st.rerun()
                    st.divider()
        else:
            st.info("No collections created yet. Create your first collection!")
        
        if st.session_state.selected_collection_14:
            collection = get_collection_by_id(st.session_state.selected_collection_14)
            if collection:
                with st.expander(f"📂 {collection.get('name')} - Details", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Collection Info:**")
                        st.json({
                            "Name": collection.get("name"),
                            "Description": collection.get("description", ""),
                            "Videos": collection.get("video_count", 0),
                            "Views": collection.get("views", 0),
                            "Public": "Yes" if collection.get("is_public") else "No",
                            "Created": collection.get("created_at", "")[:10]
                        })
                    with col2:
                        st.markdown("**Add Video:**")
                        add_vid = st.text_input("Video ID", key=f"col_add_vid_{collection.get('id')}_14")
                        if st.button("Add to Collection", key=f"col_add_btn_{collection.get('id')}_14"):
                            if add_vid:
                                result = add_video_to_collection(collection.get("id"), add_vid)
                                if result["success"]:
                                    st.success("✅ Video added!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                            else:
                                st.warning("Please enter a video ID")
                    
                    st.markdown("**Videos in this collection:**")
                    videos = get_collection_videos(collection.get("id"))
                    if videos:
                        for vid_idx, video in enumerate(videos):
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.markdown(f"• {video.get('filename')}")
                            with col2:
                                if st.button(f"Remove", key=f"col_remove_vid_{video.get('id')}_{collection.get('id')}_{vid_idx}"):
                                    remove_video_from_collection(collection.get("id"), video.get("id"))
                                    st.rerun()
                    else:
                        st.caption("No videos in this collection")
                    
                    st.markdown("**Actions:**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        rename_input = st.text_input("Rename to:", key=f"col_rename_{collection.get('id')}_14")
                        if st.button("Rename", key=f"col_rename_btn_{collection.get('id')}_14"):
                            if rename_input:
                                result = rename_collection(collection.get("id"), rename_input)
                                if result["success"]:
                                    st.success("✅ Renamed!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                    with col2:
                        if st.button(f"🔓 {'Make Public' if not collection.get('is_public') else 'Make Private'}", key=f"col_toggle_{collection.get('id')}_14"):
                            # Toggle public status
                            db = _load_collections_db()
                            for c in db.get("collections", []):
                                if c.get("id") == collection.get("id"):
                                    c["is_public"] = not c.get("is_public", False)
                                    if c["is_public"] and not c.get("share_code"):
                                        c["share_code"] = uuid.uuid4().hex[:8]
                                    elif not c["is_public"]:
                                        c["share_code"] = None
                                    break
                            _save_collections_db(db)
                            st.rerun()
                    with col3:
                        if st.button("Close", key=f"col_close_{collection.get('id')}_14"):
                            st.session_state.selected_collection_14 = None
                            st.rerun()
    
    # Tab 3: Statistics
    with tab3:
        st.subheader("📊 Statistics")
        
        fav_stats = get_favorite_statistics()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("⭐ Total Favorites", fav_stats["total_favorites"])
        with col2:
            st.metric("📝 With Notes", fav_stats["with_notes"])
        with col3:
            st.metric("🏷️ With Tags", fav_stats["with_tags"])
        with col4:
            st.metric("📂 Categories", len(fav_stats.get("category_distribution", {})))
        
        col_stats = get_collection_statistics()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📁 Total Collections", col_stats["total_collections"])
        with col2:
            st.metric("🎬 Videos in Collections", col_stats["total_videos_in_collections"])
        with col3:
            st.metric("👁️ Total Views", col_stats["total_views"])
        
        if fav_stats.get("tag_frequency"):
            st.markdown("### 🏷️ Favorite Tags")
            st.json(fav_stats["tag_frequency"])
        
        if fav_stats.get("recent_favorites"):
            st.markdown("### ⏰ Recent Favorites")
            for fav in fav_stats["recent_favorites"][:5]:
                st.markdown(f"• {fav.get('video_title')} - {fav.get('added_at', '')[:10]}")
        
        if fav_stats.get("category_distribution"):
            st.markdown("### 📂 Category Distribution")
            st.json(fav_stats["category_distribution"])


# ============================================
# TEST FUNCTION
# ============================================

def test():
    """Test the favorites and collections feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_14_favorites_collections.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    # Test 1: Add to favorites
    print("\n📝 Test 1: Add to favorites")
    result = add_to_favorites("test_video_1", "Test note", ["test", "demo"])
    print(f"  Result: {result.get('success', False)}")
    
    # Test 2: Get favorites
    print("\n📝 Test 2: Get favorites")
    favorites = get_all_favorites()
    print(f"  Total favorites: {len(favorites)}")
    
    # Test 3: Create collection
    print("\n📝 Test 3: Create collection")
    result = create_collection("Test Collection", "Test description", True, ["test"])
    print(f"  Result: {result.get('success', False)}")
    collection_id = result.get("collection", {}).get("id") if result.get("success") else None
    
    # Test 4: Add video to collection
    print("\n📝 Test 4: Add video to collection")
    if collection_id:
        result = add_video_to_collection(collection_id, "test_video_1")
        print(f"  Result: {result.get('success', False)}")
    
    # Test 5: Get collection videos
    print("\n📝 Test 5: Get collection videos")
    if collection_id:
        videos = get_collection_videos(collection_id)
        print(f"  Videos in collection: {len(videos)}")
    
    # Test 6: Get statistics
    print("\n📝 Test 6: Get statistics")
    fav_stats = get_favorite_statistics()
    print(f"  Total favorites: {fav_stats.get('total_favorites', 0)}")
    col_stats = get_collection_statistics()
    print(f"  Total collections: {col_stats.get('total_collections', 0)}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    test()

# ============================================
# END OF feature_14_favorites_collections.py (COMPLETE FIX)
# ============================================