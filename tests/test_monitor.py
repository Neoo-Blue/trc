"""Tests for TRC Monitor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.monitor import TRCMonitor, ItemTracker, RDDownloadTracker
from src.rd_client import RDTorrent
from src.riven_client import MediaItem


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock()
    config.max_active_rd_downloads = 3
    config.max_rd_torrents = 10
    config.torrent_add_delay_seconds = 1
    config.rd_max_wait_seconds = 7200
    config.rd_check_interval_seconds = 300
    config.check_interval_seconds = 21600
    config.problem_states = ["Failed", "Unknown"]
    config.max_riven_retries = 3
    config.retry_interval_seconds = 600
    config.skip_riven_retry = False
    config.skip_rd_validation = True
    return config


@pytest.fixture
def mock_riven():
    """Create a mock Riven client."""
    return AsyncMock()


@pytest.fixture
def mock_rd():
    """Create a mock RD client."""
    return AsyncMock()


@pytest.fixture
def mock_state():
    """Create a mock state manager."""
    state = MagicMock()
    state.load.return_value = False
    state.get_item_trackers.return_value = {}
    state.get_rd_downloads.return_value = {}
    state.get_processed_items.return_value = set()
    return state


@pytest.fixture
def monitor(mock_config, mock_riven, mock_rd, mock_state):
    """Create a TRCMonitor instance with mocks."""
    return TRCMonitor(mock_config, mock_riven, mock_rd, mock_state)


class TestWaitForFileSelection:
    """Tests for _wait_for_file_selection method."""

    @pytest.mark.asyncio
    async def test_ready_immediately(self, monitor, mock_rd):
        """Test when torrent is immediately ready for file selection."""
        torrent = RDTorrent(
            id="123", filename="test.mkv", hash="abc",
            status="waiting_files_selection", progress=0, bytes=1000
        )
        mock_rd.get_torrent_info.return_value = torrent

        result = await monitor._wait_for_file_selection("123", max_wait=10)

        assert result is True
        mock_rd.get_torrent_info.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_already_complete(self, monitor, mock_rd):
        """Test when torrent is already cached/complete."""
        torrent = RDTorrent(
            id="123", filename="test.mkv", hash="abc",
            status="downloaded", progress=100, bytes=1000
        )
        mock_rd.get_torrent_info.return_value = torrent

        result = await monitor._wait_for_file_selection("123", max_wait=10)

        assert result is True

    @pytest.mark.asyncio
    async def test_already_downloading(self, monitor, mock_rd):
        """Test when torrent is already downloading (cached scenario)."""
        torrent = RDTorrent(
            id="123", filename="test.mkv", hash="abc",
            status="downloading", progress=50, bytes=1000
        )
        mock_rd.get_torrent_info.return_value = torrent

        result = await monitor._wait_for_file_selection("123", max_wait=10)

        assert result is True

    @pytest.mark.asyncio
    async def test_failed_during_conversion(self, monitor, mock_rd):
        """Test when torrent fails during magnet conversion."""
        torrent = RDTorrent(
            id="123", filename="test.mkv", hash="abc",
            status="magnet_error", progress=0, bytes=0
        )
        mock_rd.get_torrent_info.return_value = torrent

        result = await monitor._wait_for_file_selection("123", max_wait=10)

        assert result is False

    @pytest.mark.asyncio
    async def test_dead_during_conversion(self, monitor, mock_rd):
        """Test when torrent is dead (no seeders) during conversion."""
        torrent = RDTorrent(
            id="123", filename="test.mkv", hash="abc",
            status="dead", progress=0, bytes=0
        )
        mock_rd.get_torrent_info.return_value = torrent

        result = await monitor._wait_for_file_selection("123", max_wait=10)

        assert result is False

    @pytest.mark.asyncio
    async def test_error_during_check(self, monitor, mock_rd):
        """Test error handling during status check."""
        mock_rd.get_torrent_info.side_effect = Exception("API Error")

        result = await monitor._wait_for_file_selection("123", max_wait=4)

        assert result is False


class TestMonitorRDDownloads:
    """Tests for _monitor_rd_downloads method."""

    @pytest.mark.asyncio
    async def test_handles_dead_torrent_immediately(self, monitor, mock_rd, mock_state):
        """Test that dead torrents are handled immediately without waiting for timeout."""
        # Setup a download tracker
        item = MediaItem(id="item1", title="Test Movie", type="movie", state="Failed")
        tracker = ItemTracker(item_id="item1", item=item)
        download = RDDownloadTracker(
            torrent_id="torrent1",
            infohash="abc123",
            item_tracker=tracker,
            stream_index=0,
        )
        monitor.rd_downloads["torrent1"] = download

        # Mock torrent as dead
        dead_torrent = RDTorrent(
            id="torrent1", filename="test.mkv", hash="abc123",
            status="dead", progress=0, bytes=1000
        )
        mock_rd.get_torrent_info.return_value = dead_torrent
        mock_rd.delete_torrent.return_value = True

        await monitor._monitor_rd_downloads()

        # Should have deleted the torrent
        mock_rd.delete_torrent.assert_called_once_with("torrent1")
        # Should have removed from tracking
        assert "torrent1" not in monitor.rd_downloads

    @pytest.mark.asyncio
    async def test_handles_completed_torrent(self, monitor, mock_rd, mock_riven, mock_state):
        """Test that completed torrents trigger Riven re-add."""
        item = MediaItem(id="item1", title="Test Movie", type="movie", state="Failed", tmdb_id=12345)
        tracker = ItemTracker(item_id="item1", item=item)
        download = RDDownloadTracker(
            torrent_id="torrent1",
            infohash="abc123",
            item_tracker=tracker,
            stream_index=0,
        )
        monitor.rd_downloads["torrent1"] = download

        # Mock torrent as completed
        complete_torrent = RDTorrent(
            id="torrent1", filename="test.mkv", hash="abc123",
            status="downloaded", progress=100, bytes=1000
        )
        mock_rd.get_torrent_info.return_value = complete_torrent
        mock_riven.remove_item.return_value = True
        mock_riven.add_item.return_value = True

        await monitor._monitor_rd_downloads()

        # Should have removed and re-added to Riven
        mock_riven.remove_item.assert_called_once_with("item1")
        mock_riven.add_item.assert_called_once()
        # Should have removed from tracking
        assert "torrent1" not in monitor.rd_downloads
        # Should be marked as processed
        assert "item1" in monitor.processed_items

