"""Core monitoring logic for TRC - The Riven Companion."""

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from .config import Config
from .riven_client import RivenClient, MediaItem, Stream
from .rd_client import RealDebridClient, RDTorrent
from .persistence import StateManager

logger = logging.getLogger(__name__)


@dataclass
class ItemTracker:
    """Tracks retry attempts for an item."""
    item_id: str
    item: MediaItem
    retry_count: int = 0
    last_retry: Optional[datetime] = None
    manual_scrape_started: bool = False
    streams: List[Stream] = field(default_factory=list)
    stream_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for persistence."""
        parent_ids_dict = None
        if self.item.parent_ids:
            parent_ids_dict = {
                "imdb_id": self.item.parent_ids.imdb_id,
                "tmdb_id": self.item.parent_ids.tmdb_id,
                "tvdb_id": self.item.parent_ids.tvdb_id,
            }
        return {
            "item_id": self.item_id,
            "item": {
                "id": self.item.id,
                "title": self.item.title,
                "state": self.item.state,
                "type": self.item.type,
                "imdb_id": self.item.imdb_id,
                "tmdb_id": self.item.tmdb_id,
                "tvdb_id": self.item.tvdb_id,
                "scraped_times": self.item.scraped_times,
                "parent_title": self.item.parent_title,
                "season_number": self.item.season_number,
                "episode_number": self.item.episode_number,
                "parent_ids": parent_ids_dict,
                "aired_at": self.item.aired_at,
            },
            "retry_count": self.retry_count,
            "last_retry": self.last_retry.isoformat() if self.last_retry else None,
            "manual_scrape_started": self.manual_scrape_started,
            "streams": [{"infohash": s.infohash, "raw_title": s.raw_title, "rank": s.rank, "is_cached": s.is_cached} for s in self.streams],
            "stream_index": self.stream_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItemTracker":
        """Deserialize from dict."""
        item = MediaItem.from_dict(data["item"])
        streams = [Stream.from_dict(s) for s in data.get("streams", [])]
        last_retry = None
        if data.get("last_retry"):
            try:
                last_retry = datetime.fromisoformat(data["last_retry"])
            except (ValueError, TypeError):
                pass
        return cls(
            item_id=data["item_id"],
            item=item,
            retry_count=data.get("retry_count", 0),
            last_retry=last_retry,
            manual_scrape_started=data.get("manual_scrape_started", False),
            streams=streams,
            stream_index=data.get("stream_index", 0),
        )


@dataclass
class RDDownloadTracker:
    """Tracks an RD download being monitored."""
    torrent_id: str
    infohash: str
    item_tracker: ItemTracker
    stream_index: int
    started_at: datetime = field(default_factory=datetime.now)
    last_check: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "torrent_id": self.torrent_id,
            "infohash": self.infohash,
            "item_tracker": self.item_tracker.to_dict(),
            "stream_index": self.stream_index,
            "started_at": self.started_at.isoformat(),
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RDDownloadTracker":
        """Deserialize from dict."""
        item_tracker = ItemTracker.from_dict(data["item_tracker"])
        started_at = datetime.now()
        if data.get("started_at"):
            try:
                started_at = datetime.fromisoformat(data["started_at"])
            except (ValueError, TypeError):
                pass
        last_check = None
        if data.get("last_check"):
            try:
                last_check = datetime.fromisoformat(data["last_check"])
            except (ValueError, TypeError):
                pass
        return cls(
            torrent_id=data["torrent_id"],
            infohash=data["infohash"],
            item_tracker=item_tracker,
            stream_index=data.get("stream_index", 0),
            started_at=started_at,
            last_check=last_check,
        )


class TRCMonitor:
    """Main monitoring class for The Riven Companion."""

    def __init__(self, config: Config, riven: RivenClient, rd: RealDebridClient,
                 state_manager: Optional[StateManager] = None):
        self.config = config
        self.riven = riven
        self.rd = rd
        self.state = state_manager or StateManager()

        # Tracking state
        self.item_trackers: Dict[str, ItemTracker] = {}
        self.rd_downloads: Dict[str, RDDownloadTracker] = {}  # torrent_id -> tracker
        self.processed_items: Set[str] = set()  # Items we've already tried manual scrape on

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

        # Load persisted state
        self._load_state()

    def _load_state(self):
        """Load state from persistence."""
        if not self.state.load():
            return

        # Load item trackers
        for item_id, data in self.state.get_item_trackers().items():
            try:
                self.item_trackers[item_id] = ItemTracker.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to restore tracker for {item_id}: {e}")

        # Load RD downloads
        for torrent_id, data in self.state.get_rd_downloads().items():
            try:
                self.rd_downloads[torrent_id] = RDDownloadTracker.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to restore RD download {torrent_id}: {e}")

        # Load processed items
        self.processed_items = self.state.get_processed_items()

        logger.info(f"Restored state: {len(self.item_trackers)} trackers, {len(self.rd_downloads)} downloads, {len(self.processed_items)} processed")

    def _save_state(self):
        """Save current state to persistence."""
        # Save all item trackers
        for item_id, tracker in self.item_trackers.items():
            self.state.set_item_tracker(item_id, tracker.to_dict())

        # Save all RD downloads
        for torrent_id, download in self.rd_downloads.items():
            self.state.set_rd_download(torrent_id, download.to_dict())

    async def start(self):
        """Start the monitoring loop."""
        logger.info("Starting TRC Monitor...")
        self._running = True

        # Validate connections
        if not await self.riven.health_check():
            logger.error("Cannot connect to Riven API!")
            return

        if self.config.skip_rd_validation:
            logger.warning("Skipping Real-Debrid validation (SKIP_RD_VALIDATION=true)")
        else:
            try:
                user = await self.rd.get_user()
                logger.info(f"Connected to Real-Debrid as {user.get('username')}")
            except Exception as e:
                logger.error(f"Cannot connect to Real-Debrid API: {e}")
                return

        logger.info(f"TRC Monitor started. Check interval: {self.config.check_interval_hours}h")

        # Run main loops as tasks so we can cancel them
        self._tasks = [
            asyncio.create_task(self._main_check_loop()),
            asyncio.create_task(self._rd_monitor_loop()),
            asyncio.create_task(self._rd_cleanup_loop()),
        ]

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.debug("Monitor tasks cancelled")

    async def stop(self):
        """Stop the monitoring loop."""
        logger.info("Stopping TRC Monitor...")
        self._running = False
        self._shutdown_event.set()

        # Cancel all running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to finish with a timeout
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        logger.info("TRC Monitor stopped")
    
    async def _interruptible_sleep(self, seconds: float):
        """Sleep that can be interrupted by shutdown event."""
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=seconds
            )
            # If we get here, shutdown was requested
            return True
        except asyncio.TimeoutError:
            # Normal timeout, continue running
            return False

    async def _main_check_loop(self):
        """Main loop that checks Riven for problem items."""
        while self._running:
            try:
                await self._check_problem_items()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in main check loop: {e}", exc_info=True)

            # Wait for next check interval (interruptible)
            logger.info(f"Next check in {self.config.check_interval_hours} hours")
            if await self._interruptible_sleep(self.config.check_interval_seconds):
                break  # Shutdown requested

    async def _rd_monitor_loop(self):
        """Monitor active RD downloads."""
        while self._running:
            try:
                await self._monitor_rd_downloads()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in RD monitor loop: {e}", exc_info=True)

            if await self._interruptible_sleep(self.config.rd_check_interval_seconds):
                break  # Shutdown requested

    async def _rd_cleanup_loop(self):
        """Periodically check and clean up stuck/orphaned torrents in RD."""
        while self._running:
            try:
                await self._cleanup_rd_torrents()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in RD cleanup loop: {e}", exc_info=True)

            if await self._interruptible_sleep(self.config.rd_cleanup_interval_seconds):
                break  # Shutdown requested

    async def _cleanup_rd_torrents(self):
        """Check all RD torrents and clean up stuck/dead ones."""
        logger.info("Running RD torrent cleanup check...")

        try:
            # Get active count info
            active_info = await self.rd.get_active_count()
            active_count = active_info.get("nb", 0)
            active_limit = active_info.get("limit", 0)
            logger.info(f"RD active torrents: {active_count}/{active_limit}")

            # Get all torrents from RD
            all_torrents = await self.rd.get_torrents(limit=100)
            logger.info(f"Total torrents in RD: {len(all_torrents)}")

            # Track which torrent IDs we're monitoring
            tracked_ids = set(self.rd_downloads.keys())

            cleaned_count = 0
            now = datetime.now()

            for torrent in all_torrents:
                should_delete = False
                reason = ""

                # Check if torrent is dead/failed
                if torrent.is_failed:
                    should_delete = True
                    reason = f"failed ({torrent.status})"
                elif torrent.is_stalled:
                    should_delete = True
                    reason = "dead/no seeders"
                elif torrent.is_waiting_selection:
                    # Orphaned - waiting for file selection but not tracked
                    if torrent.id not in tracked_ids:
                        # Check if it's old enough to be considered orphaned
                        if torrent.added:
                            try:
                                added_time = datetime.fromisoformat(torrent.added.replace('Z', '+00:00'))
                                # Make comparison timezone-naive
                                if added_time.tzinfo:
                                    added_time = added_time.replace(tzinfo=None)
                                age_seconds = (now - added_time).total_seconds()
                                if age_seconds > 3600:  # Orphaned for > 1 hour
                                    should_delete = True
                                    reason = "orphaned (waiting selection > 1h)"
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Could not parse added time for {torrent.id}: {e}")
                elif torrent.is_active and torrent.progress < 5:
                    # Check for stuck torrents (active but no progress for too long)
                    if torrent.id not in tracked_ids and torrent.added:
                        try:
                            added_time = datetime.fromisoformat(torrent.added.replace('Z', '+00:00'))
                            if added_time.tzinfo:
                                added_time = added_time.replace(tzinfo=None)
                            age_seconds = (now - added_time).total_seconds()
                            if age_seconds > self.config.rd_stuck_torrent_seconds:
                                should_delete = True
                                reason = f"stuck (active {age_seconds/3600:.1f}h with {torrent.progress}% progress)"
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Could not parse added time for {torrent.id}: {e}")

                if should_delete:
                    logger.warning(f"Cleaning up torrent {torrent.id}: {reason} - {torrent.filename[:50] if torrent.filename else 'unknown'}")
                    await self.rd.delete_torrent(torrent.id)
                    # Also remove from our tracking if present
                    if torrent.id in self.rd_downloads:
                        del self.rd_downloads[torrent.id]
                        self.state.remove_rd_download(torrent.id)
                    cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} stuck/orphaned torrents from RD")
            else:
                logger.debug("No stuck torrents found")

        except Exception as e:
            logger.error(f"Error during RD cleanup: {e}", exc_info=True)

    async def _check_problem_items(self):
        """Check for and handle problem items."""
        logger.info("Checking for problem items in Riven...")

        items = await self.riven.get_problem_items(self.config.problem_states, limit=200)
        logger.info(f"Found {len(items)} items with problem states")

        # Track parent shows we've already queued for retry (to avoid duplicates)
        parent_shows_queued: Set[str] = set()

        for item in items:
            # Skip unreleased items - they will naturally fail
            if not item.is_released():
                logger.debug(f"Skipping unreleased item: {item.display_name} (aired_at={item.aired_at})")
                continue

            # Handle seasons and episodes by retrying their parent show
            if item.type in ["season", "episode"]:
                await self._handle_season_episode(item, parent_shows_queued)
                continue

            # Get or create tracker for movies/shows
            if item.id not in self.item_trackers:
                self.item_trackers[item.id] = ItemTracker(item_id=item.id, item=item)

            tracker = self.item_trackers[item.id]
            await self._handle_problem_item(tracker)

    async def _handle_season_episode(self, item: MediaItem, parent_shows_queued: Set[str]):
        """Handle a failed season or episode by retrying the parent show."""
        parent_tmdb_id, parent_tvdb_id = item.get_parent_show_ids()
        parent_imdb_id = item.parent_ids.imdb_id if item.parent_ids else None

        if not parent_tmdb_id and not parent_tvdb_id:
            logger.warning(f"Cannot retry {item.display_name}: no parent IDs available")
            return

        # Create a unique key for the parent show
        parent_key = f"tmdb:{parent_tmdb_id}|tvdb:{parent_tvdb_id}"

        # Skip if we've already queued this parent show in this check cycle
        if parent_key in parent_shows_queued:
            logger.debug(f"Parent show already queued for {item.display_name}")
            return

        parent_shows_queued.add(parent_key)

        # Get or create tracker for the parent show (using parent_key as item_id)
        if parent_key not in self.item_trackers:
            # Create a pseudo-item for the parent show
            parent_item = MediaItem(
                id=parent_key,
                title=item.parent_title or item.title.split()[0],  # Use parent title or first word
                type="show",
                state=item.state,
                tmdb_id=parent_tmdb_id,
                tvdb_id=parent_tvdb_id,
                imdb_id=parent_imdb_id,
                parent_ids=None,
                aired_at=item.aired_at,
            )
            self.item_trackers[parent_key] = ItemTracker(item_id=parent_key, item=parent_item)

        tracker = self.item_trackers[parent_key]

        # If skip_riven_retry is enabled, go directly to manual scrape
        if self.config.skip_riven_retry:
            if not tracker.manual_scrape_started:
                logger.info(f"Skipping Riven retry (SKIP_RIVEN_RETRY=true), starting manual scrape for parent show {tracker.item.display_name}...")
                await self._start_manual_scrape(tracker)
            return

        # Check if we've exceeded retries for this parent show
        if tracker.retry_count >= self.config.max_riven_retries:
            if not tracker.manual_scrape_started:
                logger.info(f"Max retries exceeded for parent show {tracker.item.display_name}, starting manual scrape...")
                await self._start_manual_scrape(tracker)
            return

        # Try re-adding the parent show
        now = datetime.now()
        if tracker.last_retry is None or (now - tracker.last_retry).total_seconds() > self.config.retry_interval_seconds:
            tracker.retry_count += 1
            tracker.last_retry = now
            # Persist state after updating
            self.state.set_item_tracker(parent_key, tracker.to_dict())

            logger.info(f"Retrying parent show for {item.display_name} (tmdb={parent_tmdb_id}, tvdb={parent_tvdb_id}) - attempt {tracker.retry_count}")

            # Add the parent show back to Riven
            added = await self.riven.add_item(tmdb_id=parent_tmdb_id, tvdb_id=parent_tvdb_id, media_type="show")
            if added:
                logger.info(f"Successfully re-added parent show for {item.display_name}")
            else:
                logger.error(f"Failed to re-add parent show for {item.display_name}")
    
    async def _handle_problem_item(self, tracker: ItemTracker):
        """Handle a single problem item."""
        item = tracker.item
        logger.info(f"Handling: {item.display_name} (state={item.state}, retries={tracker.retry_count})")

        # If skip_riven_retry is enabled, go directly to manual scrape
        if self.config.skip_riven_retry:
            if not tracker.manual_scrape_started:
                logger.info(f"Skipping Riven retry (SKIP_RIVEN_RETRY=true), starting manual scrape for {item.display_name}...")
                await self._start_manual_scrape(tracker)
            return

        # Check if we've exceeded retries
        if tracker.retry_count >= self.config.max_riven_retries:
            if not tracker.manual_scrape_started:
                logger.info(f"Max retries exceeded for {item.display_name}, starting manual scrape...")
                await self._start_manual_scrape(tracker)
            return

        # Try a Riven remove+add (removes item and adds it back fresh)
        now = datetime.now()
        if tracker.last_retry is None or (now - tracker.last_retry).total_seconds() > self.config.retry_interval_seconds:
            logger.info(f"Retrying {item.display_name} via remove+add (attempt {tracker.retry_count + 1})")

            # Grab IDs before removing
            tmdb_id = item.tmdb_id
            tvdb_id = item.tvdb_id
            media_type = "movie" if item.type == "movie" else "show"

            # Remove the item first
            removed = await self.riven.remove_item(item.id)
            if removed:
                # Add it back using the saved IDs
                added = await self.riven.add_item(tmdb_id=tmdb_id, tvdb_id=tvdb_id, media_type=media_type)
                if added:
                    logger.info(f"Successfully re-added {item.display_name}")
                    tracker.retry_count += 1
                    tracker.last_retry = now
                    # Persist the updated tracker
                    self.state.set_item_tracker(item.id, tracker.to_dict())
                else:
                    logger.error(f"Failed to re-add {item.display_name}")
            else:
                logger.error(f"Failed to remove {item.display_name}")

    async def _start_manual_scrape(self, tracker: ItemTracker):
        """Start manual scrape process for an item."""
        item = tracker.item
        tracker.manual_scrape_started = True
        # Persist the manual_scrape_started flag immediately
        self.state.set_item_tracker(item.id, tracker.to_dict())

        if item.id in self.processed_items:
            logger.info(f"Already processed manual scrape for {item.display_name}")
            return

        logger.info(f"Starting manual scrape for {item.display_name}")

        # Determine media type and scrape
        media_type = "movie" if item.type == "movie" else "show"

        try:
            streams = await self.riven.scrape_item(
                tmdb_id=item.tmdb_id,
                tvdb_id=item.tvdb_id,
                imdb_id=item.imdb_id,
                media_type=media_type
            )

            # Sort streams by rank and take top 10
            sorted_streams = sorted(streams.values(), key=lambda s: s.rank, reverse=True)[:self.config.max_rd_torrents]

            if not sorted_streams:
                logger.warning(f"No streams found for {item.display_name}")
                self.processed_items.add(item.id)
                self.state.add_processed_item(item.id)
                return

            logger.info(f"Found {len(sorted_streams)} streams for {item.display_name}")
            tracker.streams = sorted_streams
            tracker.stream_index = 0
            # Persist updated streams
            self.state.set_item_tracker(item.id, tracker.to_dict())

            # Add first batch of torrents to RD
            await self._add_streams_to_rd(tracker)

        except Exception as e:
            logger.error(f"Failed to scrape {item.display_name}: {e}")
            self.processed_items.add(item.id)
            self.state.add_processed_item(item.id)

    async def _wait_for_file_selection(self, torrent_id: str, max_wait: int = 30) -> bool:
        """Wait for torrent to be ready for file selection.

        After adding a magnet, RD goes through magnet_conversion before
        reaching waiting_files_selection. We need to wait for that state.

        Returns True if ready for selection, False if failed/timeout.
        """
        for _ in range(max_wait // 2):  # Check every 2 seconds
            try:
                torrent = await self.rd.get_torrent_info(torrent_id)

                if torrent.is_waiting_selection:
                    return True
                elif torrent.is_failed or torrent.is_stalled:
                    logger.warning(f"Torrent {torrent_id} failed during magnet conversion: {torrent.status}")
                    return False
                elif torrent.is_complete:
                    # Already cached! No need to select files
                    logger.info(f"Torrent {torrent_id} is already cached on RD")
                    return True
                elif torrent.is_active:
                    # Already downloading (files were auto-selected or cached)
                    return True

                # Still in magnet_conversion, wait
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error checking torrent {torrent_id} status: {e}")
                return False

        logger.warning(f"Timeout waiting for torrent {torrent_id} to be ready for file selection")
        return False

    async def _add_streams_to_rd(self, tracker: ItemTracker):
        """Add streams to Real-Debrid (max 3 active globally at a time)."""
        # Check TOTAL active downloads across all items (global limit of 3)
        total_active = len(self.rd_downloads)

        if total_active >= self.config.max_active_rd_downloads:
            logger.debug(f"Already at max active RD downloads ({total_active}/{self.config.max_active_rd_downloads})")
            return

        while total_active < self.config.max_active_rd_downloads and tracker.stream_index < len(tracker.streams):
            stream = tracker.streams[tracker.stream_index]

            # Create magnet link from infohash
            magnet = f"magnet:?xt=urn:btih:{stream.infohash}"

            logger.info(f"Adding torrent {tracker.stream_index + 1}/{len(tracker.streams)} to RD: {stream.raw_title[:50]}...")

            try:
                # Rate limiter is already applied in rd.add_magnet
                result = await self.rd.add_magnet(magnet)
                torrent_id = result.get("id")

                if torrent_id:
                    # Wait for RD to finish magnet conversion before selecting files
                    if await self._wait_for_file_selection(torrent_id):
                        # Select all files to start download
                        await self.rd.select_files(torrent_id, "all")

                        # Create download tracker
                        download = RDDownloadTracker(
                            torrent_id=torrent_id,
                            infohash=stream.infohash,
                            item_tracker=tracker,
                            stream_index=tracker.stream_index,
                        )
                        self.rd_downloads[torrent_id] = download
                        # Persist the new download
                        self.state.set_rd_download(torrent_id, download.to_dict())

                        logger.info(f"Added torrent {torrent_id} to RD monitoring (active: {len(self.rd_downloads)}/{self.config.max_active_rd_downloads})")
                        total_active = len(self.rd_downloads)
                    else:
                        # Failed during magnet conversion, delete and try next
                        logger.warning(f"Torrent {torrent_id} failed during setup, trying next stream")
                        await self.rd.delete_torrent(torrent_id)

            except Exception as e:
                logger.error(f"Failed to add torrent to RD: {e}")

            tracker.stream_index += 1
            # Persist stream_index progress
            self.state.set_item_tracker(tracker.item_id, tracker.to_dict())

            # Wait between adding torrents (rate limit + delay)
            if tracker.stream_index < len(tracker.streams) and total_active < self.config.max_active_rd_downloads:
                logger.info(f"Waiting {self.config.torrent_add_delay_seconds}s before next torrent...")
                await asyncio.sleep(self.config.torrent_add_delay_seconds)

    async def _monitor_rd_downloads(self):
        """Monitor active RD downloads and handle completion/failure."""
        if not self.rd_downloads:
            return

        logger.debug(f"Monitoring {len(self.rd_downloads)} RD downloads...")

        to_remove = []
        trackers_to_refill = []

        for torrent_id, download in list(self.rd_downloads.items()):
            try:
                torrent = await self.rd.get_torrent_info(torrent_id)
                download.last_check = datetime.now()

                elapsed = (datetime.now() - download.started_at).total_seconds()

                if torrent.is_complete:
                    logger.info(f"✓ Torrent completed: {torrent.filename[:50]}")
                    # Torrent is on RD, now remove+add item in Riven so it picks up the cached content
                    item = download.item_tracker.item
                    media_type = "movie" if item.type == "movie" else "show"

                    # Remove and re-add to trigger Riven to find the now-cached content
                    await self.riven.remove_item(item.id)
                    await self.riven.add_item(tmdb_id=item.tmdb_id, tvdb_id=item.tvdb_id, media_type=media_type)

                    to_remove.append(torrent_id)
                    self.processed_items.add(download.item_tracker.item_id)
                    self.state.add_processed_item(download.item_tracker.item_id)
                    logger.info(f"Re-added {item.display_name} to Riven to pick up cached content")

                elif torrent.is_failed:
                    # Immediate failure (magnet_error, error, virus)
                    logger.warning(f"✗ Torrent failed ({torrent.status}): {torrent.filename[:50]}")
                    await self.rd.delete_torrent(torrent_id)
                    to_remove.append(torrent_id)
                    trackers_to_refill.append(download.item_tracker)

                elif torrent.is_stalled:
                    # Dead torrent - no seeders available, try next immediately
                    logger.warning(f"✗ Torrent dead/no seeders ({torrent.status}): {torrent.filename[:50]}")
                    await self.rd.delete_torrent(torrent_id)
                    to_remove.append(torrent_id)
                    trackers_to_refill.append(download.item_tracker)

                elif elapsed > self.config.rd_max_wait_seconds:
                    if torrent.is_active and torrent.progress < 10:
                        # Stalled - very slow progress, delete and try next
                        logger.warning(f"⚠ Torrent stalled (progress={torrent.progress}%): {torrent.filename[:50]}")
                        await self.rd.delete_torrent(torrent_id)
                        to_remove.append(torrent_id)
                        trackers_to_refill.append(download.item_tracker)
                    elif torrent.is_active:
                        # Still downloading with progress, let it continue
                        logger.info(f"↓ Still downloading ({torrent.progress}%): {torrent.filename[:50]}")
                else:
                    logger.debug(f"⏳ Waiting ({torrent.status}, {torrent.progress}%): {torrent.filename[:50]}")

            except Exception as e:
                logger.error(f"Error checking torrent {torrent_id}: {e}")

        # Remove completed/failed downloads from tracking and persistence
        for torrent_id in to_remove:
            del self.rd_downloads[torrent_id]
            self.state.remove_rd_download(torrent_id)

        # Try to add more streams for trackers that had failures
        for tracker in trackers_to_refill:
            if tracker.stream_index < len(tracker.streams):
                await self._add_streams_to_rd(tracker)

