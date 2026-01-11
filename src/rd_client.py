"""Real-Debrid API client."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

import httpx

from .config import Config
from .rate_limiter import RateLimiterManager

logger = logging.getLogger(__name__)


class TorrentStatus(Enum):
    """Real-Debrid torrent statuses."""
    MAGNET_ERROR = "magnet_error"
    MAGNET_CONVERSION = "magnet_conversion"
    WAITING_FILES_SELECTION = "waiting_files_selection"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    ERROR = "error"
    VIRUS = "virus"
    COMPRESSING = "compressing"
    UPLOADING = "uploading"
    DEAD = "dead"  # Stalled/dead torrent - no seeders

    @classmethod
    def is_failed(cls, status: str) -> bool:
        """Check if status indicates failure (immediate - should try next torrent)."""
        return status in [cls.MAGNET_ERROR.value, cls.ERROR.value, cls.VIRUS.value]

    @classmethod
    def is_stalled(cls, status: str) -> bool:
        """Check if torrent is stalled/dead (no seeders)."""
        return status == cls.DEAD.value

    @classmethod
    def is_waiting_selection(cls, status: str) -> bool:
        """Check if torrent is waiting for file selection."""
        return status == cls.WAITING_FILES_SELECTION.value

    @classmethod
    def is_active(cls, status: str) -> bool:
        """Check if torrent is actively processing."""
        return status in [
            cls.MAGNET_CONVERSION.value, cls.QUEUED.value, cls.DOWNLOADING.value,
            cls.COMPRESSING.value, cls.UPLOADING.value
        ]

    @classmethod
    def is_complete(cls, status: str) -> bool:
        """Check if torrent is complete."""
        return status == cls.DOWNLOADED.value


@dataclass
class RDTorrent:
    """Represents a Real-Debrid torrent."""
    id: str
    filename: str
    hash: str
    status: str
    progress: float
    bytes: int
    seeders: Optional[int] = None
    added: Optional[str] = None  # ISO datetime string when torrent was added

    @classmethod
    def from_dict(cls, data: dict) -> "RDTorrent":
        return cls(
            id=data.get("id", ""),
            filename=data.get("filename", ""),
            hash=data.get("hash", ""),
            status=data.get("status", ""),
            progress=data.get("progress", 0),
            bytes=data.get("bytes", 0),
            seeders=data.get("seeders"),
            added=data.get("added"),
        )
    
    @property
    def is_failed(self) -> bool:
        return TorrentStatus.is_failed(self.status)

    @property
    def is_stalled(self) -> bool:
        return TorrentStatus.is_stalled(self.status)

    @property
    def is_waiting_selection(self) -> bool:
        return TorrentStatus.is_waiting_selection(self.status)

    @property
    def is_active(self) -> bool:
        return TorrentStatus.is_active(self.status)

    @property
    def is_complete(self) -> bool:
        return TorrentStatus.is_complete(self.status)


class RealDebridClient:
    """Client for Real-Debrid API."""
    
    def __init__(self, config: Config, rate_limiter: RateLimiterManager):
        self.config = config
        self.rate_limiter = rate_limiter
        self.base_url = config.rd_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.config.rd_api_key}"}
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make a rate-limited API request."""
        await self.rate_limiter.acquire("rd")
        url = f"{self.base_url}{endpoint}"
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        
        logger.debug(f"RD API: {method} {endpoint}")
        response = await self.client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        
        if response.status_code == 204:
            return None
        return response.json()
    
    async def get_user(self) -> Dict[str, Any]:
        """Get current user info."""
        return await self._request("GET", "/user")
    
    async def get_torrents(self, limit: int = 100) -> List[RDTorrent]:
        """Get list of torrents."""
        result = await self._request("GET", f"/torrents?limit={limit}")
        if isinstance(result, list):
            return [RDTorrent.from_dict(t) for t in result]
        return []
    
    async def get_torrent_info(self, torrent_id: str) -> RDTorrent:
        """Get info about a specific torrent."""
        result = await self._request("GET", f"/torrents/info/{torrent_id}")
        return RDTorrent.from_dict(result)
    
    async def get_active_count(self) -> Dict[str, Any]:
        """Get active torrents count and limit."""
        return await self._request("GET", "/torrents/activeCount")
    
    async def add_magnet(self, magnet: str) -> Dict[str, Any]:
        """Add a magnet link. Returns dict with 'id' and 'uri'."""
        result = await self._request("POST", "/torrents/addMagnet", data={"magnet": magnet})
        return result
    
    async def select_files(self, torrent_id: str, files: str = "all") -> bool:
        """Select files to download. Use 'all' or comma-separated file IDs."""
        try:
            await self._request("POST", f"/torrents/selectFiles/{torrent_id}", data={"files": files})
            return True
        except Exception as e:
            logger.error(f"Failed to select files for torrent {torrent_id}: {e}")
            return False
    
    async def delete_torrent(self, torrent_id: str) -> bool:
        """Delete a torrent."""
        try:
            await self._request("DELETE", f"/torrents/delete/{torrent_id}")
            logger.info(f"Deleted RD torrent {torrent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete torrent {torrent_id}: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

