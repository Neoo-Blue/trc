"""Persistence layer for TRC state."""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = "data/trc_state.json"


class StateManager:
    """Manages persistence of TRC state to disk."""
    
    def __init__(self, state_file: str = DEFAULT_STATE_FILE):
        self.state_file = Path(state_file)
        self._state: Dict[str, Any] = {
            "item_trackers": {},
            "rd_downloads": {},
            "processed_items": [],
        }
        self._ensure_state_file()

    def _ensure_state_file(self):
        """Ensure state file path is a file, not a directory."""
        if self.state_file.exists() and self.state_file.is_dir():
            # Can't delete mounted directories, use a file inside instead
            logger.warning(f"State path {self.state_file} is a directory, using file inside it")
            self.state_file = self.state_file / "state.json"

        if not self.state_file.exists():
            # Ensure parent directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            # Create empty state file
            with open(self.state_file, "w") as f:
                json.dump(self._state, f)
            logger.info(f"Created new state file at {self.state_file}")

    def load(self) -> bool:
        """Load state from disk. Returns True if successful."""
        self._ensure_state_file()

        if not self.state_file.exists():
            logger.info(f"No state file found at {self.state_file}, starting fresh")
            return False

        try:
            with open(self.state_file, "r") as f:
                content = f.read().strip()
                if not content:
                    logger.info(f"Empty state file at {self.state_file}, starting fresh")
                    return False
                self._state = json.loads(content)
            logger.info(f"Loaded state from {self.state_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load state from {self.state_file}: {e}")
            return False
    
    def save(self) -> bool:
        """Save state to disk. Returns True if successful."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self._state, f, indent=2, default=self._json_serializer)
            logger.debug(f"Saved state to {self.state_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save state to {self.state_file}: {e}")
            return False
    
    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for datetime objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse ISO format datetime string."""
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    
    # Item tracker methods
    def get_item_trackers(self) -> Dict[str, dict]:
        """Get all item trackers as dicts."""
        return self._state.get("item_trackers", {})
    
    def set_item_tracker(self, item_id: str, tracker_data: dict):
        """Save an item tracker."""
        self._state["item_trackers"][item_id] = tracker_data
        self.save()
    
    def remove_item_tracker(self, item_id: str):
        """Remove an item tracker."""
        if item_id in self._state["item_trackers"]:
            del self._state["item_trackers"][item_id]
            self.save()
    
    def clear_item_trackers(self):
        """Clear all item trackers."""
        self._state["item_trackers"] = {}
        self.save()
    
    # RD download tracker methods
    def get_rd_downloads(self) -> Dict[str, dict]:
        """Get all RD download trackers as dicts."""
        return self._state.get("rd_downloads", {})
    
    def set_rd_download(self, torrent_id: str, download_data: dict):
        """Save an RD download tracker."""
        self._state["rd_downloads"][torrent_id] = download_data
        self.save()
    
    def remove_rd_download(self, torrent_id: str):
        """Remove an RD download tracker."""
        if torrent_id in self._state["rd_downloads"]:
            del self._state["rd_downloads"][torrent_id]
            self.save()
    
    def clear_rd_downloads(self):
        """Clear all RD download trackers."""
        self._state["rd_downloads"] = {}
        self.save()
    
    # Processed items methods
    def get_processed_items(self) -> Set[str]:
        """Get set of processed item IDs."""
        return set(self._state.get("processed_items", []))
    
    def add_processed_item(self, item_id: str):
        """Add an item to processed set."""
        if item_id not in self._state["processed_items"]:
            self._state["processed_items"].append(item_id)
            self.save()
    
    def is_processed(self, item_id: str) -> bool:
        """Check if an item has been processed."""
        return item_id in self._state.get("processed_items", [])
    
    def clear_processed_items(self):
        """Clear processed items set."""
        self._state["processed_items"] = []
        self.save()

