"""Tests for Real-Debrid client."""

import pytest
from src.rd_client import TorrentStatus, RDTorrent


class TestTorrentStatus:
    """Tests for TorrentStatus enum methods."""

    def test_is_failed_magnet_error(self):
        assert TorrentStatus.is_failed("magnet_error") is True

    def test_is_failed_error(self):
        assert TorrentStatus.is_failed("error") is True

    def test_is_failed_virus(self):
        assert TorrentStatus.is_failed("virus") is True

    def test_is_failed_dead_is_not_failed(self):
        # Dead is stalled, not failed - handled separately
        assert TorrentStatus.is_failed("dead") is False

    def test_is_failed_downloading(self):
        assert TorrentStatus.is_failed("downloading") is False

    def test_is_stalled_dead(self):
        assert TorrentStatus.is_stalled("dead") is True

    def test_is_stalled_downloading(self):
        assert TorrentStatus.is_stalled("downloading") is False

    def test_is_stalled_error(self):
        assert TorrentStatus.is_stalled("error") is False

    def test_is_waiting_selection(self):
        assert TorrentStatus.is_waiting_selection("waiting_files_selection") is True

    def test_is_waiting_selection_other(self):
        assert TorrentStatus.is_waiting_selection("downloading") is False
        assert TorrentStatus.is_waiting_selection("magnet_conversion") is False

    def test_is_active_downloading(self):
        assert TorrentStatus.is_active("downloading") is True

    def test_is_active_queued(self):
        assert TorrentStatus.is_active("queued") is True

    def test_is_active_magnet_conversion(self):
        assert TorrentStatus.is_active("magnet_conversion") is True

    def test_is_active_compressing(self):
        assert TorrentStatus.is_active("compressing") is True

    def test_is_active_uploading(self):
        assert TorrentStatus.is_active("uploading") is True

    def test_is_active_downloaded(self):
        # Downloaded is complete, not active
        assert TorrentStatus.is_active("downloaded") is False

    def test_is_complete(self):
        assert TorrentStatus.is_complete("downloaded") is True

    def test_is_complete_downloading(self):
        assert TorrentStatus.is_complete("downloading") is False


class TestRDTorrent:
    """Tests for RDTorrent dataclass."""

    def test_from_dict(self):
        data = {
            "id": "ABC123",
            "filename": "test.mkv",
            "hash": "abcdef123456",
            "status": "downloading",
            "progress": 50,
            "bytes": 1000000,
            "seeders": 10,
        }
        torrent = RDTorrent.from_dict(data)
        assert torrent.id == "ABC123"
        assert torrent.filename == "test.mkv"
        assert torrent.hash == "abcdef123456"
        assert torrent.status == "downloading"
        assert torrent.progress == 50
        assert torrent.bytes == 1000000
        assert torrent.seeders == 10

    def test_from_dict_missing_fields(self):
        data = {"id": "ABC123"}
        torrent = RDTorrent.from_dict(data)
        assert torrent.id == "ABC123"
        assert torrent.filename == ""
        assert torrent.hash == ""
        assert torrent.status == ""
        assert torrent.progress == 0
        assert torrent.bytes == 0
        assert torrent.seeders is None

    def test_is_failed_property(self):
        torrent = RDTorrent(id="1", filename="", hash="", status="error", progress=0, bytes=0)
        assert torrent.is_failed is True

    def test_is_stalled_property(self):
        torrent = RDTorrent(id="1", filename="", hash="", status="dead", progress=0, bytes=0)
        assert torrent.is_stalled is True

    def test_is_waiting_selection_property(self):
        torrent = RDTorrent(id="1", filename="", hash="", status="waiting_files_selection", progress=0, bytes=0)
        assert torrent.is_waiting_selection is True

    def test_is_active_property(self):
        torrent = RDTorrent(id="1", filename="", hash="", status="downloading", progress=50, bytes=0)
        assert torrent.is_active is True

    def test_is_complete_property(self):
        torrent = RDTorrent(id="1", filename="", hash="", status="downloaded", progress=100, bytes=0)
        assert torrent.is_complete is True

