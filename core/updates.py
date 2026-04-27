"""Update checker for OnyxKraken."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

_log = logging.getLogger("updates")

GITHUB_API_URL = "https://api.github.com/repos/20TwentyVizion/OnyxKraken/releases/latest"
CURRENT_VERSION = "0.1.0"
CHECK_INTERVAL_DAYS = 1


def get_cache_file() -> Path:
    """Get the update check cache file."""
    return Path.home() / ".onyxkraken" / "update_check.json"


def should_check_for_updates() -> bool:
    """Check if we should check for updates (rate limiting)."""
    cache_file = get_cache_file()
    
    if not cache_file.exists():
        return True
    
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
        last_check = datetime.fromisoformat(cache.get("last_check", "2000-01-01"))
        
        # Check once per day
        return datetime.now() - last_check > timedelta(days=CHECK_INTERVAL_DAYS)
    except Exception as e:
        _log.warning(f"Error reading update cache: {e}")
        return True


def save_check_cache(latest_version: str, update_available: bool):
    """Save update check results to cache."""
    cache_file = get_cache_file()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    cache = {
        "last_check": datetime.now().isoformat(),
        "latest_version": latest_version,
        "current_version": CURRENT_VERSION,
        "update_available": update_available,
    }
    
    try:
        cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        _log.warning(f"Failed to save update cache: {e}")


def check_for_updates(force: bool = False) -> Optional[dict]:
    """Check for updates from GitHub releases.
    
    Args:
        force: Force check even if recently checked
    
    Returns:
        Update info dict if update available, None otherwise
        {
            "current_version": "0.1.0",
            "latest_version": "0.2.0",
            "release_url": "https://github.com/...",
            "release_notes": "...",
            "published_at": "2026-02-25T12:00:00Z"
        }
    """
    if not force and not should_check_for_updates():
        _log.debug("Skipping update check (recently checked)")
        return None
    
    try:
        _log.info("Checking for updates...")
        response = requests.get(GITHUB_API_URL, timeout=5)
        response.raise_for_status()
        
        release = response.json()
        latest_version = release.get("tag_name", "").lstrip("v")
        
        if not latest_version:
            _log.warning("Could not parse latest version from GitHub")
            return None
        
        # Simple version comparison (assumes semantic versioning)
        update_available = _is_newer_version(latest_version, CURRENT_VERSION)
        
        # Save to cache
        save_check_cache(latest_version, update_available)
        
        if update_available:
            _log.info(f"Update available: {CURRENT_VERSION} -> {latest_version}")
            return {
                "current_version": CURRENT_VERSION,
                "latest_version": latest_version,
                "release_url": release.get("html_url", ""),
                "release_notes": release.get("body", ""),
                "published_at": release.get("published_at", ""),
            }
        else:
            _log.info(f"Already on latest version: {CURRENT_VERSION}")
            return None
    
    except requests.RequestException as e:
        _log.warning(f"Failed to check for updates: {e}")
        return None
    except Exception as e:
        _log.error(f"Unexpected error checking for updates: {e}")
        return None


def _is_newer_version(latest: str, current: str) -> bool:
    """Compare version strings (simple semantic versioning).
    
    Args:
        latest: Latest version string (e.g., "0.2.0")
        current: Current version string (e.g., "0.1.0")
    
    Returns:
        True if latest > current
    """
    try:
        latest_parts = [int(x) for x in latest.split(".")]
        current_parts = [int(x) for x in current.split(".")]
        
        # Pad to same length
        max_len = max(len(latest_parts), len(current_parts))
        latest_parts += [0] * (max_len - len(latest_parts))
        current_parts += [0] * (max_len - len(current_parts))
        
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False


def get_cached_update_info() -> Optional[dict]:
    """Get cached update info without making a network request."""
    cache_file = get_cache_file()
    
    if not cache_file.exists():
        return None
    
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
        
        if cache.get("update_available"):
            return {
                "current_version": cache.get("current_version"),
                "latest_version": cache.get("latest_version"),
                "last_check": cache.get("last_check"),
            }
    except Exception as e:
        _log.warning(f"Error reading cached update info: {e}")
    
    return None


if __name__ == "__main__":
    # Test update checker
    print("Testing update checker...")
    print(f"Current version: {CURRENT_VERSION}")
    
    update_info = check_for_updates(force=True)
    
    if update_info:
        print(f"\n🎉 Update available!")
        print(f"Current: {update_info['current_version']}")
        print(f"Latest: {update_info['latest_version']}")
        print(f"URL: {update_info['release_url']}")
    else:
        print("\n✅ Already on latest version")
