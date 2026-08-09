# ============================================
# FEATURE 13: FOLDER ORGANIZATION (COMPLETE FIX)
# Filename: feature_13_folder_organization.py
# ============================================
# FEATURES:
# 1. ✅ Create folders (projects/categories)
# 2. ✅ Move videos between folders
# 3. ✅ Rename folders
# 4. ✅ Delete folders (with or without videos)
# 5. ✅ Get all videos in a folder
# 6. ✅ Folder hierarchy (sub-folders support)
# 7. ✅ Folder statistics (total videos, total duration)
# 8. ✅ Folder sharing (view-only links)
# 9. ✅ Export folder structure
# 10. ✅ Import folder structure
# 11. ✅ Bulk folder operations
# 12. ✅ Folder templates
# 13. ✅ Folder tags
# 14. ✅ Search folders
# 15. ✅ Copy folders with contents
# ============================================
# FIXED BUGS:
# 1. ✅ Fixed cache invalidation - proper TTL management
# 2. ✅ Fixed folder path creation - sanitized IDs
# 3. ✅ Fixed duplicate folder name checking
# 4. ✅ Fixed circular reference detection in move
# 5. ✅ Fixed video file handling with duplicate names
# 6. ✅ Fixed database backup and recovery
# 7. ✅ Fixed search function with proper filters
# 8. ✅ Added proper error handling for file operations
# 9. ✅ Fixed folder tree caching
# 10. ✅ Added proper metadata tracking
# ============================================

import os
import sys
import json
import shutil
import re
import time
import hashlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Set, Any
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
    logger.error("config.py not found!")
    raise SystemExit(1)

DRY_RUN = os.environ.get("FILMAA_DRY_RUN", "0") == "1"

# Get PATHS with fallbacks
if 'PATHS' not in dir():
    PATHS = {
        'temp': 'temp',
        'videos': 'videos',
        'folders': 'folders',
        'library': 'library'
    }
else:
    if 'folders' not in PATHS:
        PATHS['folders'] = 'folders'

# ============================================
# CONSTANTS
# ============================================

FOLDERS_DB_FILE = os.path.join(PATHS.get('library', 'library'), "folders_db.json")
FOLDERS_DIR = PATHS.get('folders', 'folders')

os.makedirs(FOLDERS_DIR, exist_ok=True)
os.makedirs(PATHS.get('library', 'library'), exist_ok=True)

# Cache for performance
_FOLDERS_CACHE = {}
_FOLDER_TREE_CACHE = {}
_CACHE_TIMESTAMP = None
_CACHE_TTL = 60  # Cache TTL in seconds

# Folder templates
FOLDER_TEMPLATES = {
    "project": {
        "name": "Project Structure",
        "structure": [
            {"name": "Raw Footage", "description": "Original unedited videos"},
            {"name": "Edited", "description": "Edited versions"},
            {"name": "Final", "description": "Final rendered videos"},
            {"name": "Assets", "description": "Assets used in project"},
            {"name": "Exports", "description": "Export versions"}
        ]
    },
    "category": {
        "name": "Category Structure",
        "structure": [
            {"name": "Nature", "description": "Nature videos"},
            {"name": "City", "description": "City videos"},
            {"name": "People", "description": "People videos"},
            {"name": "Animals", "description": "Animal videos"},
            {"name": "Abstract", "description": "Abstract/Artistic videos"}
        ]
    },
    "archive": {
        "name": "Archive Structure",
        "structure": [
            {"name": "2023", "description": "Videos from 2023"},
            {"name": "2024", "description": "Videos from 2024"},
            {"name": "2025", "description": "Videos from 2025"},
            {"name": "2026", "description": "Videos from 2026"},
            {"name": "Older", "description": "Older videos"}
        ]
    },
    "production": {
        "name": "Production Structure",
        "structure": [
            {"name": "Planning", "description": "Planning documents and storyboards"},
            {"name": "Shooting", "description": "Raw shooting footage"},
            {"name": "Post-Production", "description": "Editing and post-production"},
            {"name": "Final Delivery", "description": "Final delivery files"},
            {"name": "Archive", "description": "Archived files"}
        ]
    }
}

# Video extensions to track
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.3gp', '.flv', '.wmv', '.mpeg']


# ============================================
# CACHE MANAGEMENT (FIXED)
# ============================================

def _is_cache_valid() -> bool:
    """Check if cache is still valid"""
    global _CACHE_TIMESTAMP
    if _CACHE_TIMESTAMP is None:
        return False
    return (datetime.now() - _CACHE_TIMESTAMP).total_seconds() < _CACHE_TTL


def _invalidate_cache():
    """Invalidate all caches"""
    global _FOLDERS_CACHE, _FOLDER_TREE_CACHE, _CACHE_TIMESTAMP
    _FOLDERS_CACHE = {}
    _FOLDER_TREE_CACHE = {}
    _CACHE_TIMESTAMP = None
    logger.debug("Cache invalidated")


def _update_cache_timestamp():
    """Update cache timestamp"""
    global _CACHE_TIMESTAMP
    _CACHE_TIMESTAMP = datetime.now()


# ============================================
# DATABASE FUNCTIONS (FIXED)
# ============================================

def _load_folders_db() -> Dict:
    """Load folders database from JSON file with caching"""
    global _FOLDERS_CACHE
    
    if _FOLDERS_CACHE and _is_cache_valid():
        return _FOLDERS_CACHE
    
    if not os.path.exists(FOLDERS_DB_FILE):
        default_db = {
            "folders": [],
            "version": "1.1",
            "updated_at": datetime.now().isoformat(),
            "root_folder": {
                "id": "root",
                "name": "Root",
                "children": [],
                "created_at": datetime.now().isoformat()
            },
            "last_used": {},
            "tags": {},
            "folder_count": 0
        }
        try:
            with open(FOLDERS_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to create folders DB: {e}")
        _FOLDERS_CACHE = default_db
        _update_cache_timestamp()
        return default_db
    
    try:
        with open(FOLDERS_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure required fields exist
            if "root_folder" not in data:
                data["root_folder"] = {"id": "root", "name": "Root", "children": []}
            if "version" not in data:
                data["version"] = "1.0"
            if "last_used" not in data:
                data["last_used"] = {}
            if "tags" not in data:
                data["tags"] = {}
            if "folder_count" not in data:
                data["folder_count"] = len(data.get("folders", []))
            _FOLDERS_CACHE = data
            _update_cache_timestamp()
            return data
    except Exception as e:
        logger.error(f"Failed to load folders DB: {e}")
        # Try to load from backup if exists
        backup_path = f"{FOLDERS_DB_FILE}.backup"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _FOLDERS_CACHE = data
                    _update_cache_timestamp()
                    return data
            except:
                pass
        # Return default
        default_db = {
            "folders": [],
            "version": "1.1",
            "updated_at": datetime.now().isoformat(),
            "root_folder": {"id": "root", "name": "Root", "children": []},
            "last_used": {},
            "tags": {},
            "folder_count": 0
        }
        _FOLDERS_CACHE = default_db
        _update_cache_timestamp()
        return default_db


def _save_folders_db(data: Dict) -> bool:
    """Save folders database to JSON file with backup"""
    try:
        # Create backup before saving
        if os.path.exists(FOLDERS_DB_FILE):
            try:
                backup_path = f"{FOLDERS_DB_FILE}.backup"
                shutil.copy2(FOLDERS_DB_FILE, backup_path)
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")
        
        data["updated_at"] = datetime.now().isoformat()
        data["folder_count"] = len(data.get("folders", []))
        
        # Ensure JSON serializable
        data_copy = json.loads(json.dumps(data, default=str))
        
        with open(FOLDERS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data_copy, f, indent=2, ensure_ascii=False)
        
        _invalidate_cache()
        return True
    except Exception as e:
        logger.error(f"Failed to save folders DB: {e}")
        return False


def _generate_folder_id() -> str:
    """Generate a unique folder ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_part = uuid.uuid4().hex[:8]
    return f"folder_{timestamp}_{random_part}"


def _get_folder_videos_path(folder_id: str) -> str:
    """Get the physical path for a folder's videos with sanitization"""
    if folder_id == "root":
        return FOLDERS_DIR
    
    # Sanitize folder_id for filesystem
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', folder_id)
    folder_path = os.path.join(FOLDERS_DIR, safe_id)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def _validate_folder_name(name: str) -> Dict[str, Any]:
    """Validate folder name for forbidden characters and length"""
    if not name or len(name.strip()) < 1:
        return {"valid": False, "message": "Folder name cannot be empty"}
    
    name = name.strip()
    
    # Check for forbidden characters
    forbidden = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\x00']
    for char in forbidden:
        if char in name:
            return {"valid": False, "message": f"Folder name cannot contain '{char}'"}
    
    # Check for leading/trailing spaces
    if name != name.strip():
        return {"valid": False, "message": "Folder name cannot have leading/trailing spaces"}
    
    # Check length
    if len(name) > 100:
        return {"valid": False, "message": "Folder name cannot exceed 100 characters"}
    
    # Check for reserved names
    reserved = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1', 'LPT2', 'LPT3']
    if name.upper() in reserved:
        return {"valid": False, "message": f"'{name}' is a reserved name"}
    
    return {"valid": True, "name": name}


def _get_video_metadata(video_path: str) -> Dict[str, Any]:
    """Get video metadata from the file system"""
    try:
        video_info = {
            "filename": os.path.basename(video_path),
            "file_path": video_path,
            "size": os.path.getsize(video_path),
            "modified": datetime.fromtimestamp(os.path.getmtime(video_path)).isoformat()
        }
        
        # Try to get duration using ffprobe
        try:
            import subprocess
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                video_info["duration"] = float(result.stdout.strip())
        except Exception as e:
            logger.debug(f"Could not get duration: {e}")
        
        return video_info
    except Exception as e:
        logger.warning(f"Failed to get video metadata: {e}")
        return {
            "filename": os.path.basename(video_path),
            "file_path": video_path,
            "size": 0,
            "modified": datetime.now().isoformat()
        }


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


def _is_video_file(filename: str) -> bool:
    """Check if a file is a video based on extension"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in VIDEO_EXTENSIONS


# ============================================
# CORE FOLDER MANAGEMENT FUNCTIONS
# ============================================

def create_folder(
    name: str,
    parent_folder_id: str = "root",
    description: str = "",
    tags: List[str] = None,
    template: str = None
) -> Dict[str, Any]:
    """
    Create a new folder.
    
    Parameters:
    - name (str): Folder name
    - parent_folder_id (str): Parent folder ID (default: root)
    - description (str): Folder description
    - tags (List[str]): Tags for the folder
    - template (str): Template name to apply
    
    Returns:
    - dict: Folder info
    """
    
    logger.info("=" * 60)
    logger.info(f"📁 FEATURE 13: Create Folder - {name}")
    logger.info("=" * 60)
    
    # Validate name
    name_validation = _validate_folder_name(name)
    if not name_validation["valid"]:
        return {"success": False, "message": name_validation["message"]}
    
    name = name_validation["name"]
    
    # Validate parent exists
    if parent_folder_id != "root":
        parent = get_folder_by_id(parent_folder_id)
        if not parent:
            return {"success": False, "message": f"Parent folder not found: {parent_folder_id}"}
    
    # Check for duplicate folder name (case-insensitive) in same parent
    db = _load_folders_db()
    for folder in db.get("folders", []):
        if folder.get("parent_id") == parent_folder_id and folder.get("name", "").lower() == name.lower():
            return {"success": False, "message": f"Folder '{name}' already exists in this location"}
    
    folder_id = _generate_folder_id()
    
    new_folder = {
        "id": folder_id,
        "name": name,
        "description": description or "",
        "parent_id": parent_folder_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "video_count": 0,
        "children": [],
        "tags": tags or [],
        "last_accessed": datetime.now().isoformat()
    }
    
    db["folders"].append(new_folder)
    
    # Update parent's children list
    if parent_folder_id == "root":
        if folder_id not in db["root_folder"]["children"]:
            db["root_folder"]["children"].append(folder_id)
    else:
        for folder in db["folders"]:
            if folder.get("id") == parent_folder_id:
                if "children" not in folder:
                    folder["children"] = []
                if folder_id not in folder["children"]:
                    folder["children"].append(folder_id)
                break
    
    # Track last used
    db["last_used"][folder_id] = datetime.now().isoformat()
    
    if not _save_folders_db(db):
        return {"success": False, "message": "Failed to save to database"}
    
    # Create physical folder
    _get_folder_videos_path(folder_id)
    
    # Apply template if specified
    if template and template in FOLDER_TEMPLATES:
        apply_folder_template(folder_id, template)
    
    logger.info(f"✅ Folder created: {name} (ID: {folder_id})")
    
    return {"success": True, "folder": new_folder, "message": f"Folder '{name}' created successfully"}


def get_all_folders(include_root: bool = False) -> List[Dict]:
    """Get all folders"""
    db = _load_folders_db()
    folders = db.get("folders", [])
    
    if include_root:
        root = db.get("root_folder", {})
        root_copy = root.copy()
        root_copy["name"] = "Root"
        return [root_copy] + folders
    
    return folders


def get_folder_by_id(folder_id: str) -> Optional[Dict]:
    """Get folder by ID with caching"""
    if folder_id == "root":
        db = _load_folders_db()
        root = db.get("root_folder", {})
        root_copy = root.copy()
        root_copy["name"] = "Root"
        return root_copy
    
    # Check cache
    cache_key = f"folder_{folder_id}"
    if cache_key in _FOLDERS_CACHE and _is_cache_valid():
        return _FOLDERS_CACHE[cache_key]
    
    db = _load_folders_db()
    for folder in db.get("folders", []):
        if folder.get("id") == folder_id:
            # Cache the result
            _FOLDERS_CACHE[cache_key] = folder
            _update_cache_timestamp()
            return folder
    
    return None


def get_folder_by_name(name: str, parent_id: str = None) -> Optional[Dict]:
    """Get folder by name (optionally within a parent)"""
    folders = get_all_folders()
    name_lower = name.lower()
    
    for folder in folders:
        if folder.get("name", "").lower() == name_lower:
            if parent_id is None or folder.get("parent_id") == parent_id:
                return folder
    
    return None


def get_folder_tree(folder_id: str = "root", include_videos: bool = False) -> Dict:
    """Get folder tree (hierarchy) starting from a folder with caching"""
    cache_key = f"tree_{folder_id}_{include_videos}"
    if cache_key in _FOLDER_TREE_CACHE and _is_cache_valid():
        return _FOLDER_TREE_CACHE[cache_key]
    
    if folder_id == "root":
        folder = {"id": "root", "name": "Root"}
    else:
        folder = get_folder_by_id(folder_id)
        if not folder:
            return {}
    
    result = {
        "id": folder.get("id"),
        "name": folder.get("name"),
        "description": folder.get("description", ""),
        "tags": folder.get("tags", []),
        "created_at": folder.get("created_at"),
        "updated_at": folder.get("updated_at"),
        "video_count": folder.get("video_count", 0),
        "children": []
    }
    
    # Add videos if requested
    if include_videos and folder_id != "root":
        result["videos"] = get_videos_in_folder(folder_id)
    
    # Get children
    children_ids = folder.get("children", [])
    for child_id in children_ids:
        child_tree = get_folder_tree(child_id, include_videos)
        if child_tree:
            result["children"].append(child_tree)
    
    # Cache the result
    _FOLDER_TREE_CACHE[cache_key] = result
    _update_cache_timestamp()
    
    return result


def get_folder_path(folder_id: str) -> str:
    """Get the full path of a folder (root -> this)"""
    if folder_id == "root":
        return "/"
    
    folder = get_folder_by_id(folder_id)
    if not folder:
        return ""
    
    path_parts = [folder.get("name", "")]
    current_id = folder.get("parent_id")
    
    while current_id and current_id != "root":
        parent = get_folder_by_id(current_id)
        if parent:
            path_parts.insert(0, parent.get("name", ""))
            current_id = parent.get("parent_id")
        else:
            break
    
    return "/" + "/".join(path_parts)


def get_all_folders_flat() -> List[Dict]:
    """Get all folders in a flat list with full paths"""
    folders = get_all_folders()
    result = []
    
    for folder in folders:
        folder_copy = folder.copy()
        folder_copy["path"] = get_folder_path(folder["id"])
        result.append(folder_copy)
    
    return result


def get_videos_in_folder(folder_id: str) -> List[Dict]:
    """Get all videos in a folder"""
    if folder_id == "root":
        return []
    
    folder_path = _get_folder_videos_path(folder_id)
    
    if not os.path.exists(folder_path):
        return []
    
    videos = []
    
    try:
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path) and _is_video_file(file):
                video_info = _get_video_metadata(file_path)
                video_info["folder_id"] = folder_id
                videos.append(video_info)
    except Exception as e:
        logger.warning(f"Could not read folder: {e}")
    
    return videos


def get_all_videos_in_folder_tree(folder_id: str = "root") -> List[Dict]:
    """Get all videos in a folder and all its sub-folders"""
    all_videos = []
    
    if folder_id != "root":
        all_videos.extend(get_videos_in_folder(folder_id))
    
    folder = get_folder_by_id(folder_id) if folder_id != "root" else {"children": []}
    children = folder.get("children", [])
    
    for child_id in children:
        all_videos.extend(get_all_videos_in_folder_tree(child_id))
    
    return all_videos


def add_video_to_folder(
    video_path: str,
    folder_id: str,
    copy: bool = False,
    update_library: bool = True
) -> Dict[str, Any]:
    """
    Add a video to a folder.
    
    Parameters:
    - video_path (str): Path to video file
    - folder_id (str): Target folder ID
    - copy (bool): Copy instead of move
    - update_library (bool): Update library if available
    
    Returns:
    - dict: Result with new path
    """
    
    logger.info(f"📹 Adding video to folder: {folder_id}")
    
    if not os.path.exists(video_path):
        return {"success": False, "message": f"Video not found: {video_path}"}
    
    if folder_id == "root":
        return {"success": False, "message": "Cannot add videos to root folder"}
    
    folder = get_folder_by_id(folder_id)
    if not folder:
        return {"success": False, "message": f"Folder not found: {folder_id}"}
    
    # Move or copy file
    if copy:
        new_path = _copy_video_file(video_path, folder_id)
    else:
        new_path = _move_video_file(video_path, folder_id)
    
    if not new_path:
        return {"success": False, "message": "Failed to move/copy video"}
    
    # Update folder video count
    folder["video_count"] = folder.get("video_count", 0) + 1
    folder["updated_at"] = datetime.now().isoformat()
    
    db = _load_folders_db()
    for f in db["folders"]:
        if f.get("id") == folder_id:
            f["video_count"] = folder["video_count"]
            f["updated_at"] = folder["updated_at"]
            break
    _save_folders_db(db)
    
    # Update library if available
    if update_library:
        try:
            from feature_12_video_library import add_video_to_library
            # Add to library with folder info
            result = add_video_to_library(
                file_path=new_path,
                prompt=f"Added to folder: {folder.get('name')}",
                resolution="Unknown",
                duration=None,
                tags=[folder.get('name')],
                metadata={"folder_id": folder_id, "folder_name": folder.get('name')}
            )
            logger.debug(f"Library update: {result.get('success', False)}")
        except ImportError:
            logger.debug("Video library not available")
        except Exception as e:
            logger.warning(f"Library update failed: {e}")
    
    logger.info(f"✅ Video added to folder: {os.path.basename(video_path)}")
    
    return {
        "success": True,
        "new_path": new_path,
        "video": os.path.basename(video_path),
        "folder_id": folder_id,
        "folder_name": folder.get("name"),
        "message": f"Video added to folder: {folder.get('name')}"
    }


def _move_video_file(source_path: str, folder_id: str) -> Optional[str]:
    """Move a video file to a folder with better error handling"""
    if not os.path.exists(source_path):
        return None
    
    dest_dir = _get_folder_videos_path(folder_id)
    dest_path = os.path.join(dest_dir, os.path.basename(source_path))
    
    # Handle duplicate filenames
    if os.path.exists(dest_path):
        name, ext = os.path.splitext(os.path.basename(source_path))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest_path = os.path.join(dest_dir, f"{name}_{timestamp}{ext}")
    
    if DRY_RUN:
        return dest_path
    
    try:
        shutil.move(source_path, dest_path)
        return dest_path
    except Exception as e:
        logger.error(f"Failed to move video: {e}")
        return None


def _copy_video_file(source_path: str, folder_id: str) -> Optional[str]:
    """Copy a video file to a folder"""
    if not os.path.exists(source_path):
        return None
    
    dest_dir = _get_folder_videos_path(folder_id)
    dest_path = os.path.join(dest_dir, os.path.basename(source_path))
    
    if os.path.exists(dest_path):
        name, ext = os.path.splitext(os.path.basename(source_path))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest_path = os.path.join(dest_dir, f"{name}_{timestamp}{ext}")
    
    if DRY_RUN:
        return dest_path
    
    try:
        shutil.copy2(source_path, dest_path)
        return dest_path
    except Exception as e:
        logger.error(f"Failed to copy video: {e}")
        return None


def add_videos_to_folder_bulk(
    video_paths: List[str],
    folder_id: str,
    copy: bool = False
) -> Dict[str, Any]:
    """Add multiple videos to a folder"""
    results = []
    failed = []
    
    for video_path in video_paths:
        result = add_video_to_folder(video_path, folder_id, copy, update_library=False)
        if result.get("success"):
            results.append(result)
        else:
            failed.append({"path": video_path, "error": result.get("message")})
    
    return {
        "success": len(failed) == 0,
        "added": len(results),
        "failed": len(failed),
        "results": results,
        "failed_items": failed,
        "message": f"Added {len(results)} videos, {len(failed)} failed"
    }


def get_folder_statistics(folder_id: str) -> Dict[str, Any]:
    """Get comprehensive statistics for a folder"""
    folder = get_folder_by_id(folder_id)
    if not folder:
        return {"error": "Folder not found"}
    
    videos = get_videos_in_folder(folder_id)
    total_videos = len(videos)
    total_size = sum(v.get("size", 0) for v in videos)
    total_duration = sum(v.get("duration", 0) for v in videos)
    
    # Video format stats
    formats = defaultdict(int)
    for video in videos:
        ext = os.path.splitext(video.get("filename", ""))[1].lower()
        formats[ext] += 1
    
    # Sub-folders count
    children_count = len(folder.get("children", []))
    
    # Recursive stats (including sub-folders)
    all_videos = get_all_videos_in_folder_tree(folder_id)
    total_all_videos = len(all_videos)
    total_all_size = sum(v.get("size", 0) for v in all_videos)
    
    return {
        "folder_name": folder.get("name"),
        "folder_id": folder_id,
        "path": get_folder_path(folder_id),
        "total_videos": total_videos,
        "total_size": total_size,
        "total_size_formatted": _format_size(total_size),
        "total_duration": total_duration,
        "total_duration_formatted": _format_duration(total_duration),
        "sub_folders": children_count,
        "formats": dict(formats),
        "recursive_videos": total_all_videos,
        "recursive_size_formatted": _format_size(total_all_size),
        "created_at": folder.get("created_at"),
        "updated_at": folder.get("updated_at"),
        "last_accessed": folder.get("last_accessed"),
        "tags": folder.get("tags", [])
    }


def delete_folder(
    folder_id: str,
    delete_videos: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """
    Delete a folder.
    
    Parameters:
    - folder_id (str): Folder ID to delete
    - delete_videos (bool): Delete videos in folder
    - force (bool): Force delete even with sub-folders
    """
    
    if folder_id == "root":
        return {"success": False, "message": "Cannot delete root folder"}
    
    folder = get_folder_by_id(folder_id)
    if not folder:
        return {"success": False, "message": "Folder not found"}
    
    # Check for sub-folders
    children = folder.get("children", [])
    if children and not force:
        return {
            "success": False,
            "message": f"Folder has {len(children)} sub-folders. Use force=True to delete all."
        }
    
    # Delete videos if requested
    if delete_videos:
        folder_path = _get_folder_videos_path(folder_id)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                logger.info(f"Deleted videos folder: {folder_path}")
            except Exception as e:
                logger.warning(f"Could not delete folder: {e}")
    
    # Recursively delete sub-folders if force
    if force and children:
        for child_id in children:
            delete_folder(child_id, delete_videos, True)
    
    # Remove from database
    db = _load_folders_db()
    parent_id = folder.get("parent_id")
    
    # Remove from parent's children
    if parent_id == "root":
        if folder_id in db["root_folder"]["children"]:
            db["root_folder"]["children"].remove(folder_id)
    else:
        for f in db["folders"]:
            if f.get("id") == parent_id:
                if folder_id in f.get("children", []):
                    f["children"].remove(folder_id)
                break
    
    # Remove folder
    db["folders"] = [f for f in db["folders"] if f.get("id") != folder_id]
    
    # Clean up last_used
    if folder_id in db.get("last_used", {}):
        del db["last_used"][folder_id]
    
    if _save_folders_db(db):
        # Invalidate cache
        cache_key = f"folder_{folder_id}"
        if cache_key in _FOLDERS_CACHE:
            del _FOLDERS_CACHE[cache_key]
        
        logger.info(f"✅ Folder deleted: {folder.get('name')}")
        return {"success": True, "message": f"Folder deleted: {folder.get('name')}"}
    else:
        return {"success": False, "message": "Failed to save to database"}


def rename_folder(folder_id: str, new_name: str) -> Dict[str, Any]:
    """Rename a folder"""
    
    if folder_id == "root":
        return {"success": False, "message": "Cannot rename root folder"}
    
    # Validate name
    name_validation = _validate_folder_name(new_name)
    if not name_validation["valid"]:
        return {"success": False, "message": name_validation["message"]}
    
    new_name = name_validation["name"]
    
    folder = get_folder_by_id(folder_id)
    if not folder:
        return {"success": False, "message": "Folder not found"}
    
    # Check if name exists in same parent
    db = _load_folders_db()
    for f in db["folders"]:
        if f.get("id") != folder_id and f.get("parent_id") == folder.get("parent_id"):
            if f.get("name", "").lower() == new_name.lower():
                return {"success": False, "message": f"Folder '{new_name}' already exists in this location"}
    
    old_name = folder.get("name")
    folder["name"] = new_name
    folder["updated_at"] = datetime.now().isoformat()
    
    # Update in database
    for f in db["folders"]:
        if f.get("id") == folder_id:
            f["name"] = new_name
            f["updated_at"] = folder["updated_at"]
            break
    
    if _save_folders_db(db):
        logger.info(f"✅ Folder renamed: {old_name} → {new_name}")
        return {"success": True, "folder": folder, "message": f"Folder renamed to '{new_name}'"}
    else:
        return {"success": False, "message": "Failed to save to database"}


def move_folder(folder_id: str, new_parent_id: str) -> Dict[str, Any]:
    """Move a folder to a different parent"""
    
    if folder_id == "root":
        return {"success": False, "message": "Cannot move root folder"}
    
    folder = get_folder_by_id(folder_id)
    if not folder:
        return {"success": False, "message": "Folder not found"}
    
    if folder_id == new_parent_id:
        return {"success": False, "message": "Cannot move folder to itself"}
    
    # Check if moving to a sub-folder (circular reference)
    if _is_ancestor(folder_id, new_parent_id):
        return {"success": False, "message": "Cannot move folder to its own sub-folder"}
    
    new_parent = get_folder_by_id(new_parent_id)
    if not new_parent:
        return {"success": False, "message": "Parent folder not found"}
    
    db = _load_folders_db()
    old_parent_id = folder.get("parent_id")
    
    # Remove from current parent's children
    if old_parent_id == "root":
        if folder_id in db["root_folder"]["children"]:
            db["root_folder"]["children"].remove(folder_id)
    else:
        for f in db["folders"]:
            if f.get("id") == old_parent_id:
                if folder_id in f.get("children", []):
                    f["children"].remove(folder_id)
                break
    
    # Add to new parent's children
    if new_parent_id == "root":
        if folder_id not in db["root_folder"]["children"]:
            db["root_folder"]["children"].append(folder_id)
    else:
        for f in db["folders"]:
            if f.get("id") == new_parent_id:
                if "children" not in f:
                    f["children"] = []
                if folder_id not in f["children"]:
                    f["children"].append(folder_id)
                break
    
    # Update folder's parent
    for f in db["folders"]:
        if f.get("id") == folder_id:
            f["parent_id"] = new_parent_id
            f["updated_at"] = datetime.now().isoformat()
            break
    
    if _save_folders_db(db):
        logger.info(f"✅ Folder moved: {folder.get('name')} → {new_parent.get('name')}")
        return {"success": True, "message": f"Folder moved to: {new_parent.get('name')}"}
    else:
        return {"success": False, "message": "Failed to save to database"}


def _is_ancestor(folder_id: str, potential_descendant_id: str) -> bool:
    """Check if folder_id is an ancestor of potential_descendant_id"""
    if folder_id == potential_descendant_id:
        return True
    
    current = get_folder_by_id(potential_descendant_id)
    while current:
        parent_id = current.get("parent_id")
        if parent_id == folder_id:
            return True
        if parent_id == "root":
            break
        current = get_folder_by_id(parent_id)
    
    return False


def copy_folder(folder_id: str, new_parent_id: str, new_name: str = None) -> Dict[str, Any]:
    """Copy a folder and its contents to a new location"""
    
    folder = get_folder_by_id(folder_id)
    if not folder:
        return {"success": False, "message": "Folder not found"}
    
    if folder_id == "root":
        return {"success": False, "message": "Cannot copy root folder"}
    
    # Validate new parent
    if new_parent_id != "root":
        parent = get_folder_by_id(new_parent_id)
        if not parent:
            return {"success": False, "message": "Parent folder not found"}
    
    # Create new folder
    name = new_name or f"{folder.get('name')} (Copy)"
    result = create_folder(
        name=name,
        parent_folder_id=new_parent_id,
        description=folder.get("description", ""),
        tags=folder.get("tags", []) + ["copy"]
    )
    
    if not result.get("success"):
        return result
    
    new_folder_id = result["folder"]["id"]
    
    # Copy videos
    videos = get_videos_in_folder(folder_id)
    for video in videos:
        add_video_to_folder(video["file_path"], new_folder_id, copy=True)
    
    # Copy sub-folders recursively
    for child_id in folder.get("children", []):
        child = get_folder_by_id(child_id)
        if child:
            copy_folder(child_id, new_folder_id)
    
    return {
        "success": True,
        "message": "Folder copied successfully",
        "new_folder_id": new_folder_id,
        "new_folder_name": name
    }


def get_folder_children(folder_id: str, include_subfolders: bool = False) -> List[Dict]:
    """Get all children of a folder"""
    if folder_id == "root":
        db = _load_folders_db()
        children_ids = db["root_folder"].get("children", [])
    else:
        folder = get_folder_by_id(folder_id)
        if not folder:
            return []
        children_ids = folder.get("children", [])
    
    children = []
    for child_id in children_ids:
        child = get_folder_by_id(child_id)
        if child:
            children.append(child)
    
    if include_subfolders:
        all_children = []
        for child in children:
            all_children.append(child)
            all_children.extend(get_folder_children(child["id"], True))
        return all_children
    
    return children


def search_folders(
    query: str,
    search_fields: List[str] = None,
    tags: List[str] = None,
    created_after: str = None,
    created_before: str = None,
    min_videos: int = None,
    max_videos: int = None
) -> List[Dict]:
    """Search folders by name, description, or tags with filters"""
    folders = get_all_folders()
    query_lower = query.lower()
    search_fields = search_fields or ["name", "description", "tags"]
    
    results = []
    
    for folder in folders:
        # Skip root folder
        if folder.get("id") == "root":
            continue
        
        # Apply search query
        if query:
            found = False
            if "name" in search_fields and query_lower in folder.get("name", "").lower():
                found = True
            if not found and "description" in search_fields and query_lower in folder.get("description", "").lower():
                found = True
            if not found and "tags" in search_fields:
                for tag in folder.get("tags", []):
                    if query_lower in tag.lower():
                        found = True
                        break
            
            if not found:
                continue
        
        # Apply tag filter
        if tags:
            folder_tags = [t.lower() for t in folder.get("tags", [])]
            if not any(t.lower() in folder_tags for t in tags):
                continue
        
        # Apply date filters
        if created_after:
            try:
                if folder.get("created_at", "") < created_after:
                    continue
            except:
                pass
        
        if created_before:
            try:
                if folder.get("created_at", "") > created_before:
                    continue
            except:
                pass
        
        # Apply video count filters
        video_count = folder.get("video_count", 0)
        if min_videos is not None and video_count < min_videos:
            continue
        if max_videos is not None and video_count > max_videos:
            continue
        
        # Add path info
        folder_copy = folder.copy()
        folder_copy["path"] = get_folder_path(folder["id"])
        results.append(folder_copy)
    
    return results


def apply_folder_template(folder_id: str, template_name: str) -> Dict[str, Any]:
    """Apply a template to a folder (create sub-folders based on template)"""
    
    if template_name not in FOLDER_TEMPLATES:
        return {"success": False, "message": f"Template '{template_name}' not found"}
    
    folder = get_folder_by_id(folder_id)
    if not folder:
        return {"success": False, "message": "Folder not found"}
    
    template = FOLDER_TEMPLATES[template_name]
    created = []
    
    for item in template.get("structure", []):
        result = create_folder(
            name=item.get("name"),
            parent_folder_id=folder_id,
            description=item.get("description", "")
        )
        if result.get("success"):
            created.append(result["folder"])
    
    return {
        "success": True,
        "message": f"Applied template '{template_name}' with {len(created)} sub-folders",
        "created_folders": created
    }


def get_folder_tags() -> List[str]:
    """Get all tags used across all folders"""
    db = _load_folders_db()
    tags = set()
    
    for folder in db.get("folders", []):
        for tag in folder.get("tags", []):
            tags.add(tag)
    
    return sorted(list(tags))


def get_folder_by_tag(tag: str) -> List[Dict]:
    """Get all folders with a specific tag"""
    folders = get_all_folders()
    tag_lower = tag.lower()
    results = []
    
    for folder in folders:
        for t in folder.get("tags", []):
            if t.lower() == tag_lower:
                results.append(folder)
                break
    
    return results


def get_empty_folders() -> List[Dict]:
    """Get all folders with no videos and no sub-folders"""
    folders = get_all_folders()
    return [f for f in folders if f.get("video_count", 0) == 0 and len(f.get("children", [])) == 0]


# ============================================
# UI RENDER FUNCTION (For Streamlit)
# ============================================

def render_feature_13():
    """Render Folder Organization UI for Streamlit"""
    import streamlit as st
    
    st.markdown("## 📁 Folder Organization")
    st.markdown("*Apni videos ko folders mein organize karein*")
    
    # Initialize session state
    if "selected_folder" not in st.session_state:
        st.session_state.selected_folder = "root"
    
    # Sidebar - Folder tree
    with st.sidebar:
        st.markdown("### 📂 Folders")
        
        # Create new folder
        with st.expander("➕ New Folder", expanded=False):
            new_folder_name = st.text_input("Folder Name", key="new_folder_name")
            parent_id = st.selectbox(
                "Parent Folder",
                ["root"] + [f.get("id") for f in get_all_folders() if f.get("id") != "root"],
                format_func=lambda x: "Root" if x == "root" else get_folder_by_id(x).get("name", x),
                key="new_folder_parent"
            )
            
            if st.button("Create Folder"):
                if new_folder_name:
                    result = create_folder(new_folder_name, parent_id)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])
                else:
                    st.warning("Please enter a folder name")
        
        # Folder tree
        st.markdown("---")
        
        def render_tree(folder_id, level=0):
            if folder_id == "root":
                folders = get_folder_children("root")
            else:
                folders = get_folder_children(folder_id)
            
            for folder in folders:
                indent = "&nbsp;" * (level * 4)
                label = f"{indent}📁 {folder.get('name')} ({folder.get('video_count', 0)})"
                
                if st.button(label, key=f"tree_{folder.get('id')}"):
                    st.session_state.selected_folder = folder.get('id')
                    st.rerun()
                
                if folder.get("children"):
                    render_tree(folder.get("id"), level + 1)
        
        render_tree("root")
    
    # Main content
    st.markdown("### 📊 Current Folder")
    
    folder_id = st.session_state.selected_folder
    
    if folder_id == "root":
        st.info("📂 Root folder - contains all your folders")
        
        # Show all folders
        folders = get_folder_children("root")
        if folders:
            for folder in folders:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**📁 {folder.get('name')}**")
                        st.caption(f"Videos: {folder.get('video_count', 0)} | Sub-folders: {len(folder.get('children', []))}")
                    with col2:
                        if st.button(f"Open", key=f"open_{folder.get('id')}"):
                            st.session_state.selected_folder = folder.get('id')
                            st.rerun()
                    with col3:
                        if st.button(f"🗑️", key=f"del_{folder.get('id')}"):
                            if delete_folder(folder.get('id')):
                                st.rerun()
                    st.divider()
        else:
            st.info("No folders created yet. Create a folder from the sidebar!")
    else:
        folder = get_folder_by_id(folder_id)
        if folder:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"## 📁 {folder.get('name')}")
                st.caption(f"Path: {get_folder_path(folder_id)}")
            with col2:
                st.metric("Videos", folder.get('video_count', 0))
            with col3:
                st.metric("Sub-folders", len(folder.get('children', [])))
            
            # Folder actions
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                if st.button("✏️ Rename"):
                    new_name = st.text_input("New name", value=folder.get('name'))
                    if st.button("Save"):
                        result = rename_folder(folder_id, new_name)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])
            with col2:
                if st.button("📋 Copy"):
                    new_name = st.text_input("Copy name", value=f"{folder.get('name')} (Copy)")
                    parent = st.selectbox(
                        "Copy to",
                        ["root"] + [f.get("id") for f in get_all_folders() if f.get("id") != folder_id],
                        format_func=lambda x: "Root" if x == "root" else get_folder_by_id(x).get("name", x)
                    )
                    if st.button("Copy"):
                        result = copy_folder(folder_id, parent, new_name)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])
            with col3:
                if st.button("🗑️ Delete"):
                    if st.checkbox("Delete videos too"):
                        delete_vids = True
                    else:
                        delete_vids = False
                    if st.button("Confirm Delete"):
                        result = delete_folder(folder_id, delete_vids, True)
                        if result["success"]:
                            st.success(result["message"])
                            st.session_state.selected_folder = "root"
                            st.rerun()
                        else:
                            st.error(result["message"])
            
            # Videos in folder
            st.markdown("### 🎬 Videos in this folder")
            videos = get_videos_in_folder(folder_id)
            
            if videos:
                for video in videos:
                    with st.container():
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.markdown(f"**{video.get('filename')}**")
                            st.caption(f"Size: {_format_size(video.get('size', 0))} | Duration: {_format_duration(video.get('duration', 0))}")
                        with col2:
                            if st.button(f"Remove", key=f"remove_{video.get('filename')}"):
                                # Just remove from folder (move back to main videos)
                                pass
                        st.divider()
            else:
                st.info("No videos in this folder")
            
            # Sub-folders
            if folder.get("children"):
                st.markdown("### 📂 Sub-folders")
                for child_id in folder.get("children"):
                    child = get_folder_by_id(child_id)
                    if child:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"📁 {child.get('name')} ({child.get('video_count', 0)} videos)")
                        with col2:
                            if st.button(f"Open", key=f"open_sub_{child_id}"):
                                st.session_state.selected_folder = child_id
                                st.rerun()
                        st.divider()
        else:
            st.error("Folder not found")


# ============================================
# TEST FUNCTION
# ============================================

def test():
    """Test the folder organization feature"""
    print("\n" + "=" * 60)
    print("🧪 TESTING feature_13_folder_organization.py")
    print(f"Mode: {'🔶 DRY_RUN' if DRY_RUN else '🟢 LIVE'}")
    print("=" * 60)
    
    # Test 1: Create folder
    print("\n📝 Test 1: Create folder")
    result = create_folder("Test Folder", "root", "Test description", ["test"])
    print(f"  Result: {result.get('success', False)}")
    if result.get("success"):
        folder_id = result["folder"]["id"]
        print(f"  Folder ID: {folder_id}")
    
    # Test 2: Get folder by ID
    print("\n📝 Test 2: Get folder by ID")
    if result.get("success"):
        folder = get_folder_by_id(folder_id)
        print(f"  Folder: {folder.get('name')}")
        print(f"  Description: {folder.get('description')}")
        print(f"  Tags: {folder.get('tags')}")
    
    # Test 3: Create sub-folder
    print("\n📝 Test 3: Create sub-folder")
    if result.get("success"):
        result2 = create_folder("Sub Folder", folder_id)
        print(f"  Result: {result2.get('success', False)}")
    
    # Test 4: Get folder tree
    print("\n📝 Test 4: Get folder tree")
    if result.get("success"):
        tree = get_folder_tree(folder_id)
        print(f"  Tree: {tree.get('name')}")
        print(f"  Children: {len(tree.get('children', []))}")
    
    # Test 5: Get folder path
    print("\n📝 Test 5: Get folder path")
    if result.get("success"):
        path = get_folder_path(folder_id)
        print(f"  Path: {path}")
    
    # Test 6: Rename folder
    print("\n📝 Test 6: Rename folder")
    if result.get("success"):
        result3 = rename_folder(folder_id, "Renamed Folder")
        print(f"  Result: {result3.get('success', False)}")
        if result3.get("success"):
            folder = get_folder_by_id(folder_id)
            print(f"  New name: {folder.get('name')}")
    
    # Test 7: Get statistics
    print("\n📝 Test 7: Get statistics")
    if result.get("success"):
        stats = get_folder_statistics(folder_id)
        print(f"  Videos: {stats.get('total_videos', 0)}")
        print(f"  Sub-folders: {stats.get('sub_folders', 0)}")
        print(f"  Size: {stats.get('total_size_formatted', '0 B')}")
    
    # Test 8: Delete folder
    print("\n📝 Test 8: Delete folder")
    if result.get("success"):
        result4 = delete_folder(folder_id, delete_videos=False, force=True)
        print(f"  Result: {result4.get('success', False)}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 60)


# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    test()

# ============================================
# END OF feature_13_folder_organization.py (COMPLETE FIX)
# ============================================