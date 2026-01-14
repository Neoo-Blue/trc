"""Core monitoring logic for TRC - The Riven Companion."""

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from .config import Config
from .riven_client import RivenClient, MediaItem, Stream
from .rd_client import RealDebridClient, RDTorrent, ContentInfringementError, TorrentNotFoundError
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

        # Round-robin index for fairly distributing stream adds across trackers
        self._rr_index = 0

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
                # After checking items, ensure RD slots are filled
                await self._fill_rd_slots()
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
                # After monitoring, try to fill any empty slots
                await self._fill_rd_slots()
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

            # Enforce max active torrents limit
            await self._enforce_max_active_torrents()

        except Exception as e:
            logger.error(f"Error during RD cleanup: {e}", exc_info=True)

    async def _enforce_max_active_torrents(self):
        """Ensure we don't have more than MAX_ACTIVE_RD_DOWNLOADS active torrents."""
        max_active = self.config.max_active_rd_downloads

        try:
            # Get fresh list of all torrents - retry on connection errors
            max_retries = 2
            all_torrents = None
            
            for attempt in range(max_retries):
                try:
                    all_torrents = await self.rd.get_torrents(limit=100)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Failed to get torrents (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                        await asyncio.sleep(2)
                    else:
                        raise

            if not all_torrents:
                logger.debug("No torrents found or unable to retrieve torrent list")
                return

            # Filter to only active torrents (downloading, queued, etc.)
            active_torrents = [t for t in all_torrents if t.is_active]

            if len(active_torrents) <= max_active:
                logger.debug(f"Active torrents ({len(active_torrents)}) within limit ({max_active})")
                return

            logger.warning(f"Too many active torrents: {len(active_torrents)}/{max_active}")

            # Sort by progress (lowest first) so we remove least-progressed ones
            # Torrents with 0% that are not tracked are prioritized for removal
            tracked_ids = set(self.rd_downloads.keys())

            def sort_key(t):
                # Prioritize keeping: 1) tracked by TRC, 2) higher progress
                is_tracked = 1 if t.id in tracked_ids else 0
                return (is_tracked, t.progress)

            active_torrents.sort(key=sort_key)

            # Remove excess torrents (lowest priority first)
            excess_count = len(active_torrents) - max_active
            for torrent in active_torrents[:excess_count]:
                logger.warning(
                    f"Removing excess torrent {torrent.id} ({torrent.progress}% progress): "
                    f"{torrent.filename[:50] if torrent.filename else 'unknown'}"
                )
                await self.rd.delete_torrent(torrent.id)
                # Remove from tracking if present
                if torrent.id in self.rd_downloads:
                    del self.rd_downloads[torrent.id]
                    self.state.remove_rd_download(torrent.id)

            logger.info(f"Removed {excess_count} excess torrents to enforce limit of {max_active}")

        except Exception as e:
            logger.error(f"Error enforcing max active torrents: {e}", exc_info=True)

    async def _check_problem_items(self):
        """Check for and handle ONLY failed/unknown state items from Riven."""
        logger.info(f"Checking for items with states: {self.config.problem_states}...")

        items = await self.riven.get_problem_items(self.config.problem_states, limit=200)
        logger.info(f"Found {len(items)} items with {self.config.problem_states} states")

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
        
        # Validate item is still in a problem state
        if item.state not in self.config.problem_states:
            logger.debug(f"Item {item.display_name} state changed to {item.state}, skipping (no longer in problem states)")
            # Remove from trackers since it's no longer a problem
            if item.id in self.item_trackers:
                del self.item_trackers[item.id]
                self.state.remove_item_tracker(item.id)
            return
        
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

    async def _fill_rd_slots(self):
        """Fill up RD download slots from all trackers that have pending streams.

        This ensures we always have up to MAX_ACTIVE_RD_DOWNLOADS running,
        pulling from different items in round-robin fashion.
        """
        total_active = len(self.rd_downloads)
        max_active = self.config.max_active_rd_downloads

        if total_active >= max_active:
            logger.debug(f"Already at max active RD downloads ({total_active}/{max_active})")
            return

        added_this_round = 0

        # Keep trying to fill slots until we're at max or no more pending streams
        while total_active < max_active:
            # Get all trackers that have pending streams (regenerate each iteration to catch new ones)
            pending_trackers = [
                tracker for tracker in self.item_trackers.values()
                if tracker.manual_scrape_started
                and tracker.streams
                and tracker.stream_index < len(tracker.streams)
            ]

            if not pending_trackers:
                logger.debug("No trackers with pending streams")
                break

            logger.debug(f"Filling RD slots: {total_active}/{max_active} active, {len(pending_trackers)} items with pending streams")

            # Use round-robin to fairly distribute across items
            tracker = pending_trackers[self._rr_index % len(pending_trackers)]
            self._rr_index = (self._rr_index + 1) % len(pending_trackers)

            if await self._try_add_one_stream(tracker):
                total_active = len(self.rd_downloads)
                added_this_round += 1
                logger.info(f"Filled RD slot {total_active}/{max_active} from {tracker.item.display_name}")

            # Delay between adding torrents
            if total_active < max_active:
                await asyncio.sleep(self.config.torrent_add_delay_seconds)

        if added_this_round > 0:
            logger.info(f"Added {added_this_round} torrents to RD (now {len(self.rd_downloads)}/{max_active} active)")

    async def _try_add_one_stream(self, tracker: ItemTracker) -> bool:
        """Try to add the next stream from a tracker to RD.

        Returns True if successfully added, False otherwise.
        Always increments stream_index.
        """
        if tracker.stream_index >= len(tracker.streams):
            return False

        stream = tracker.streams[tracker.stream_index]
        magnet = f"magnet:?xt=urn:btih:{stream.infohash}"
        item_name = tracker.item.display_name if tracker.item else tracker.item_id

        logger.info(f"[{item_name}] Adding torrent {tracker.stream_index + 1}/{len(tracker.streams)}: {stream.raw_title[:50]}...")

        success = False
        try:
            result = await self.rd.add_magnet(magnet)
            torrent_id = result.get("id")

            if torrent_id:
                if await self._wait_for_file_selection(torrent_id):
                    files_selected = await self.rd.select_files(torrent_id, "all")
                    
                    if files_selected:
                        download = RDDownloadTracker(
                            torrent_id=torrent_id,
                            infohash=stream.infohash,
                            item_tracker=tracker,
                            stream_index=tracker.stream_index,
                        )
                        self.rd_downloads[torrent_id] = download
                        self.state.set_rd_download(torrent_id, download.to_dict())

                        logger.info(f"[{item_name}] Added torrent {torrent_id} (active: {len(self.rd_downloads)}/{self.config.max_active_rd_downloads})")
                        success = True
                    else:
                        logger.warning(f"[{item_name}] Failed to select files for {torrent_id}, will try next")
                        await self.rd.delete_torrent(torrent_id)
                else:
                    logger.warning(f"[{item_name}] Torrent {torrent_id} failed during setup, will try next")
                    await self.rd.delete_torrent(torrent_id)

        except ContentInfringementError:
            logger.warning(f"[{item_name}] Content flagged as infringing by Real-Debrid, skipping")

        except Exception as e:
            logger.error(f"[{item_name}] Failed to add torrent: {e}")

        tracker.stream_index += 1
        self.state.set_item_tracker(tracker.item_id, tracker.to_dict())

        return success

    async def _add_streams_to_rd(self, tracker: ItemTracker):
        """Add streams from a tracker to RD. Wraps _fill_rd_slots for compatibility."""
        # This is now just a trigger to fill slots globally
        await self._fill_rd_slots()

    async def _monitor_rd_downloads(self):
        """Monitor active RD downloads and handle completion/failure."""
        if not self.rd_downloads:
            return

        logger.info(f"Monitoring {len(self.rd_downloads)} RD downloads...")

        to_remove = []
        trackers_to_refill = []

        for torrent_id, download in list(self.rd_downloads.items()):
            try:
                torrent = await self.rd.get_torrent_info(torrent_id)
                download.last_check = datetime.now()

                elapsed = (datetime.now() - download.started_at).total_seconds()
                elapsed_mins = elapsed / 60

                if torrent.is_complete:
                    logger.info(f"✓ Torrent completed after {elapsed_mins:.1f}m: {torrent.filename[:50]}")
                    item = download.item_tracker.item

                    # Always attempt to ensure Riven sees the completed stream.
                    # Strategy:
                    # 1) Run a manual scrape for the item (use parent IDs for episodes/seasons)
                    # 2) If the scrape finds a stream matching the completed infohash, trigger add_item
                    #    (and remove existing item first if it's a real Riven item id)
                    # 3) If not found, still trigger an add_item as a fallback to force a scan.

                    completed_infohash = download.infohash

                    # Determine scrape identifiers: for episodes/seasons use parent IDs
                    scrape_tmdb, scrape_tvdb = (item.tmdb_id, item.tvdb_id)
                    if item.type in ("episode", "season") and item.parent_ids:
                        scrape_tmdb = item.parent_ids.tmdb_id
                        scrape_tvdb = item.parent_ids.tvdb_id

                    media_type = "movie" if (item.type == "movie") else "show"

                    try:
                        streams = await self.riven.scrape_item(
                            tmdb_id=scrape_tmdb,
                            tvdb_id=scrape_tvdb,
                            imdb_id=item.imdb_id,
                            media_type=media_type,
                        )

                        # streams is a dict of id->Stream
                        found_match = any(s.infohash.lower() == completed_infohash.lower() for s in streams.values())

                        if found_match:
                            logger.info(f"Completed torrent matched scraped stream for '{item.display_name}'. Applying to Riven.")
                            # If this is a real item id, try remove then add so Riven re-processes it
                            if not (item.id.startswith("tmdb:") or item.id.startswith("tvdb:")):
                                if await self.riven.remove_item(item.id):
                                    await self.riven.add_item(tmdb_id=item.tmdb_id, tvdb_id=item.tvdb_id, media_type=media_type)
                                    # Trigger retry to immediately scan for streams
                                    if await self.riven.retry_item(item.id):
                                        logger.info(f"Re-applied completed torrent to {item.display_name} in Riven and triggered retry scan.")
                                    else:
                                        logger.warning(f"Failed to trigger retry scan for {item.display_name}")
                                else:
                                    logger.warning(f"Failed to remove real item {item.id} before re-adding; will still try add")
                                    await self.riven.add_item(tmdb_id=item.tmdb_id, tvdb_id=item.tvdb_id, media_type=media_type)
                                    # Try retry as fallback
                                    if await self.riven.retry_item(item.id):
                                        logger.info(f"Triggered retry scan for {item.display_name}")
                            else:
                                # pseudo-item: just add to trigger a scan on parent show
                                await self.riven.add_item(tmdb_id=scrape_tmdb, tvdb_id=scrape_tvdb, media_type=media_type)
                                # Find the parent item and retry it to scan
                                parent_item = await self.riven.get_item_by_ids(tmdb_id=scrape_tmdb, tvdb_id=scrape_tvdb)
                                if parent_item:
                                    if await self.riven.retry_item(parent_item.id):
                                        logger.info(f"Triggered retry scan for parent '{item.display_name}'.")
                                    else:
                                        logger.debug(f"Could not trigger retry for parent {scrape_tmdb}/{scrape_tvdb}")
                                else:
                                    # Item not found in problem items - likely hasn't been scanned yet
                                    # Log for info but don't fail - Riven will scan it on next cycle
                                    logger.debug(f"Parent item {scrape_tmdb}/{scrape_tvdb} not in problem items yet (may be in Available/Unavailable state)")

                        else:
                            logger.info(f"Completed torrent not found in scrape results for '{item.display_name}'. Triggering Riven add and retry as fallback.")
                            await self.riven.add_item(tmdb_id=scrape_tmdb, tvdb_id=scrape_tvdb, media_type=media_type)
                            # Find the item and trigger retry to scan for any available content
                            found_item = await self.riven.get_item_by_ids(tmdb_id=scrape_tmdb, tvdb_id=scrape_tvdb)
                            if found_item:
                                if await self.riven.retry_item(found_item.id):
                                    logger.info(f"Triggered retry scan for {found_item.display_name}")
                                else:
                                    logger.debug(f"Could not trigger retry for {found_item.display_name}")
                            else:
                                # Item not found in problem items - may be in other state
                                logger.debug(f"Item {scrape_tmdb}/{scrape_tvdb} not in problem items yet (may be Available/Unavailable)")

                    except Exception as e:
                        logger.error(f"Error during scrape/add for '{item.display_name}': {e}", exc_info=True)

                    to_remove.append(torrent_id)
                    self.processed_items.add(download.item_tracker.item_id)
                    self.state.add_processed_item(download.item_tracker.item_id)

                elif torrent.is_failed:
                    # Immediate failure (magnet_error, error, virus)
                    logger.warning(f"✗ Torrent failed ({torrent.status}): {torrent.filename[:50]}")
                    await self.rd.delete_torrent(torrent_id)
                    to_remove.append(torrent_id)
                    trackers_to_refill.append(download.item_tracker)

                elif torrent.is_stalled:
                    # Dead torrent - no seeders available, try next immediately
                    logger.warning(f"✗ Torrent dead ({torrent.seeders_status}): {torrent.filename[:50]}")
                    await self.rd.delete_torrent(torrent_id)
                    to_remove.append(torrent_id)
                    trackers_to_refill.append(download.item_tracker)

                elif elapsed > self.config.rd_max_wait_seconds:
                    if torrent.is_active and torrent.progress < 10:
                        # Stalled - very slow progress, delete and try next
                        logger.warning(f"⚠ Torrent stalled after {elapsed_mins:.1f}m (progress={torrent.progress}%): {torrent.filename[:50]}")
                        await self.rd.delete_torrent(torrent_id)
                        to_remove.append(torrent_id)
                        trackers_to_refill.append(download.item_tracker)
                    elif torrent.is_active:
                        # Still downloading with progress, let it continue
                        logger.info(f"↓ Still downloading after {elapsed_mins:.1f}m ({torrent.progress}%): {torrent.filename[:50]}")
                else:
                    # Actively downloading - show progress with seeder info
                    if torrent.is_active:
                        seeder_info = f" | Seeders: {torrent.seeders_status}" if torrent.seeders is not None else ""
                        logger.info(f"↓ Downloading ({torrent.progress}%, {elapsed_mins:.1f}m{seeder_info}): {torrent.filename[:50]}")
                    else:
                        logger.info(f"⏳ Waiting ({torrent.status}, {torrent.progress}%): {torrent.filename[:50]}")

            except TorrentNotFoundError:
                # Torrent was manually deleted from RD - validate and remove from tracking
                try:
                    # Verify deletion by checking active count
                    active_info = await self.rd.get_active_count()
                    active_count = active_info.get("active", 0)
                    
                    logger.warning(
                        f"Torrent {torrent_id} not found on RD (likely manually deleted). "
                        f"Current active torrents: {active_count}. Removing from tracking."
                    )
                except Exception as e:
                    logger.debug(f"Could not validate active count for deleted torrent {torrent_id}: {e}")
                    logger.warning(f"Torrent {torrent_id} not found on RD (manually deleted). Removing from tracking.")
                
                to_remove.append(torrent_id)
                trackers_to_refill.append(download.item_tracker)

            except Exception as e:
                logger.error(f"Error checking torrent {torrent_id}: {e}")

        # Remove completed/failed downloads from tracking and persistence
        for torrent_id in to_remove:
            if torrent_id in self.rd_downloads:
                del self.rd_downloads[torrent_id]
                self.state.remove_rd_download(torrent_id)

        # If we removed any downloads, try to fill the slots from all pending trackers
        if to_remove:
            await self._fill_rd_slots()

