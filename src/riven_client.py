"""Riven API client."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from .config import Config
from .rate_limiter import RateLimiterManager

logger = logging.getLogger(__name__)


@dataclass
class ParentIds:
    """Parent IDs for seasons/episodes."""
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None
    tvdb_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["ParentIds"]:
        if not data:
            return None
        return cls(
            imdb_id=data.get("imdb_id"),
            tmdb_id=str(data.get("tmdb_id")) if data.get("tmdb_id") else None,
            tvdb_id=str(data.get("tvdb_id")) if data.get("tvdb_id") else None,
        )


@dataclass
class MediaItem:
    """Represents a Riven media item."""
    id: str
    title: str
    state: str
    type: str
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None
    tvdb_id: Optional[str] = None
    scraped_times: int = 0
    parent_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    parent_ids: Optional[ParentIds] = None
    aired_at: Optional[str] = None  # ISO datetime string

    @classmethod
    def from_dict(cls, data: dict) -> "MediaItem":
        return cls(
            id=str(data.get("id")),
            title=data.get("title", ""),
            state=data.get("state", ""),
            type=data.get("type", ""),
            imdb_id=data.get("imdb_id"),
            tmdb_id=str(data.get("tmdb_id")) if data.get("tmdb_id") else None,
            tvdb_id=str(data.get("tvdb_id")) if data.get("tvdb_id") else None,
            scraped_times=data.get("scraped_times", 0),
            parent_title=data.get("parent_title"),
            season_number=data.get("season_number"),
            episode_number=data.get("episode_number"),
            parent_ids=ParentIds.from_dict(data.get("parent_ids")),
            aired_at=data.get("aired_at"),
        )

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        if self.type == "episode" and self.season_number and self.episode_number:
            return f"{self.parent_title or self.title} S{self.season_number:02d}E{self.episode_number:02d}"
        elif self.type == "season" and self.season_number:
            return f"{self.parent_title or self.title} Season {self.season_number}"
        return self.title

    def is_released(self) -> bool:
        """Check if the item has been released (aired)."""
        if not self.aired_at:
            # If no release date, assume it's released
            return True
        try:
            from datetime import datetime
            # Parse the aired_at date (format: "2025-12-30 22:38:36.105213" or similar)
            aired_dt = datetime.fromisoformat(self.aired_at.replace(" ", "T").split(".")[0])
            return aired_dt <= datetime.now()
        except (ValueError, TypeError):
            # If parsing fails, assume released
            return True

    def get_parent_show_ids(self) -> tuple[Optional[str], Optional[str]]:
        """Get parent show's tmdb_id and tvdb_id for seasons/episodes."""
        if self.parent_ids:
            return self.parent_ids.tmdb_id, self.parent_ids.tvdb_id
        return None, None


@dataclass
class Stream:
    """Represents a scraped stream result."""
    infohash: str
    raw_title: str
    rank: int
    is_cached: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> "Stream":
        return cls(
            infohash=data.get("infohash", ""),
            raw_title=data.get("raw_title", ""),
            rank=data.get("rank", 0),
            is_cached=data.get("is_cached", False),
        )


class RivenClient:
    """Client for Riven API."""
    
    def __init__(self, config: Config, rate_limiter: RateLimiterManager):
        self.config = config
        self.rate_limiter = rate_limiter
        self.base_url = f"{config.riven_url}/api/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a rate-limited API request."""
        await self.rate_limiter.acquire("riven")
        url = f"{self.base_url}{endpoint}"
        
        # Add API key to params
        params = kwargs.get("params", {})
        params["api_key"] = self.config.riven_api_key
        kwargs["params"] = params
        
        logger.debug(f"Riven API: {method} {endpoint}")
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> bool:
        """Check if Riven API is healthy."""
        try:
            result = await self._request("GET", "/health")
            return result.get("message") == "True"
        except Exception as e:
            logger.error(f"Riven health check failed: {e}")
            return False
    
    async def get_problem_items(self, states: List[str], limit: int = 100) -> List[MediaItem]:
        """Get items with problem states (Failed, Unknown)."""
        # Note: States parameter may need special handling depending on Riven API version
        # Using _request with query parameters for states
        try:
            result = await self._request(
                "GET", 
                f"/items?limit={limit}&{'&'.join([f'states={s}' for s in states])}"
            )
            items = result.get("items", [])
            return [MediaItem.from_dict(item) for item in items]
        except Exception as e:
            logger.error(f"Failed to get problem items with state filter: {e}")
            # Try without states as fallback, but filter locally by state
            try:
                result = await self._request("GET", f"/items?limit={limit}")
                all_items = result.get("items", [])
                # Filter locally to only return items with the specified states
                filtered_items = [
                    MediaItem.from_dict(item) for item in all_items
                    if item.get("state") in states
                ]
                logger.info(f"Fallback: Retrieved {len(all_items)} items, filtered to {len(filtered_items)} with states {states}")
                return filtered_items
            except Exception as e2:
                logger.error(f"Failed to get items even without states: {e2}")
                return []

    async def get_item_streams(self, item_id: str) -> List[Stream]:
        """Get available streams for an item."""
        result = await self._request("GET", f"/items/{item_id}/streams")
        streams = result.get("streams", [])
        return [Stream.from_dict(s) for s in streams]

    async def scrape_item(self, tmdb_id: Optional[str] = None,
                          tvdb_id: Optional[str] = None, imdb_id: Optional[str] = None,
                          media_type: str = "movie") -> Dict[str, Stream]:
        """Manually scrape an item for streams.

        Args:
            tmdb_id: TMDB ID for the item
            tvdb_id: TVDB ID for the item
            imdb_id: IMDB ID for the item
            media_type: Either "movie" or "tv" (not "show")
        """
        # Riven API expects "movie" or "tv", not "show"
        api_media_type = "tv" if media_type in ("show", "tv") else "movie"
        params = {"media_type": api_media_type}

        if tmdb_id:
            params["tmdb_id"] = tmdb_id
        if tvdb_id:
            params["tvdb_id"] = tvdb_id
        if imdb_id:
            params["imdb_id"] = imdb_id

        result = await self._request("POST", "/scrape/scrape", params=params)
        streams_data = result.get("streams", {})
        return {k: Stream.from_dict(v) for k, v in streams_data.items()}

    async def retry_item(self, item_id: str) -> bool:
        """Retry a failed item in Riven."""
        try:
            await self._request("POST", "/items/retry", json={"ids": [str(item_id)]})
            logger.info(f"Retried item {item_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to retry item {item_id}: {e}")
            return False

    async def reset_item(self, item_id: str) -> bool:
        """Reset an item to start fresh."""
        try:
            await self._request("POST", "/items/reset", json={"ids": [str(item_id)]})
            logger.info(f"Reset item {item_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to reset item {item_id}: {e}")
            return False

    async def remove_item(self, item_id: str) -> bool:
        """Remove an item from Riven."""
        try:
            await self._request("DELETE", "/items/remove", json={"ids": [str(item_id)]})
            logger.info(f"Removed item {item_id}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.error(f"Failed to remove item {item_id}: Invalid item ID (400 Bad Request). Item ID format may be incorrect.")
            else:
                logger.error(f"Failed to remove item {item_id}: HTTP {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Failed to remove item {item_id}: {e}")
            return False

    async def add_item(self, tmdb_id: Optional[str] = None, tvdb_id: Optional[str] = None,
                       media_type: str = "movie") -> bool:
        """Add an item back to Riven.

        Args:
            tmdb_id: TMDB ID for the item
            tvdb_id: TVDB ID for the item (for TV shows)
            media_type: Either 'movie' or 'show' (will be converted to 'tv' for API)
        
        Returns:
            True if item was added successfully, False otherwise
        """
        try:
            # Riven expects 'movie' or 'tv' as media_type
            api_media_type = "tv" if media_type == "show" else media_type

            # Riven expects tmdb_ids/tvdb_ids as a list of strings in JSON body
            payload: dict[str, Any] = {"media_type": api_media_type}
            if tmdb_id:
                payload["tmdb_ids"] = [str(tmdb_id)]
            if tvdb_id:
                payload["tvdb_ids"] = [str(tvdb_id)]

            await self._request("POST", "/items/add", json=payload)
            logger.info(f"Added item tmdb={tmdb_id}, tvdb={tvdb_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add item: {e}")
            return False

    async def get_item_by_ids(self, tmdb_id: Optional[str] = None, 
                             tvdb_id: Optional[str] = None) -> Optional[MediaItem]:
        """Get an item by its TMDB or TVDB ID.
        
        Args:
            tmdb_id: TMDB ID to search for
            tvdb_id: TVDB ID to search for
        
        Returns:
            MediaItem if found, None otherwise
        """
        try:
            items = await self.get_problem_items(["Failed", "Unknown"], limit=100)
            
            for item in items:
                if tmdb_id and str(item.tmdb_id) == str(tmdb_id):
                    return item
                if tvdb_id and str(item.tvdb_id) == str(tvdb_id):
                    return item
            
            return None
        except Exception as e:
            logger.error(f"Failed to get item by IDs: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

