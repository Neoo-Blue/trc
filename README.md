# TRC - The Riven Companion

TRC is an automated companion service for [Riven](https://github.com/rivenmedia/riven) that monitors for failed/problematic media items and automatically retries or manually scrapes them using Real-Debrid.

## Features

- **Automatic Monitoring**: Periodically checks Riven for items in Failed or Unknown states
- **Smart Retry Logic**: Removes and re-adds failed items to trigger Riven's scraping
- **Season/Episode Handling**: Automatically retries parent shows when seasons or episodes fail
- **Release Date Awareness**: Skips unreleased content that naturally can't be found
- **Manual Scraping Fallback**: After max retries, manually scrapes for torrents and adds to Real-Debrid
- **RD Download Monitoring**: Monitors Real-Debrid downloads and triggers Riven to pick up cached content
- **Smart Torrent Handling**: Properly waits for RD magnet conversion, handles dead/stalled torrents immediately
- **Automatic RD Cleanup**: Periodically scans RD for stuck/orphaned torrents and cleans them up
- **Rate Limiting**: Respects API rate limits for both Riven and Real-Debrid
- **State Persistence**: Saves state to disk so progress survives restarts

## How It Works

1. **Monitor Phase**: TRC queries Riven for items with problem states (Failed, Unknown)
2. **Retry Phase**: For each problematic item:
   - Skips unreleased content (not yet aired/released)
   - For seasons/episodes: adds the parent show to retry the entire series
   - For movies/shows: removes and re-adds the item to trigger fresh scraping
3. **Manual Scrape Phase**: After max retries (default 3), TRC:
   - Uses Riven's scrape API to find torrent streams
   - Adds top-ranked torrents to Real-Debrid (max 3 concurrent)
   - Waits for RD to convert magnet before selecting files
   - Monitors downloads until complete
   - Immediately moves to next torrent if current one is dead (no seeders)
4. **Completion**: When RD download completes, TRC removes and re-adds the item to Riven so it picks up the now-cached content

## Installation

### Docker (Recommended)

TRC is available as a Docker image from Docker Hub: `arrrrrr/trc:latest`

1. Create a `docker-compose.yml` file and edit the environment variables with your settings:
   ```yaml
   version: "3.8"
   services:
     trc:
       image: arrrrrr/trc:latest
       container_name: trc
       restart: unless-stopped
       volumes:
         - ./trc_data:/app/data
       environment:
         - RIVEN_URL=http://your-riven-ip:8080
         - RIVEN_API_KEY=your_riven_api_key
         - RD_API_KEY=your_real_debrid_api_key
         # Optional - see full list of variables below
   ```

2.  Run:
    ```bash
    docker-compose up -d
    ```

For local development, you can still clone the repository and use the provided `docker-compose.yml` to build the image locally.

### Manual Installation

1. Install Python 3.11+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables and run:
   ```bash
   export RIVEN_URL=http://localhost:8083
   export RIVEN_API_KEY=your_key
   export RD_API_KEY=your_rd_key
   python -m src.main
   ```

## Configuration

All configuration is done via environment variables:

### Required

| Variable | Description |
|----------|-------------|
| `RIVEN_URL` | URL to your Riven instance (e.g., `http://192.168.1.100:8083`) |
| `RIVEN_API_KEY` | Riven API key (get from Riven settings) |
| `RD_API_KEY` | Real-Debrid API key (get from https://real-debrid.com/apitoken) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `CHECK_INTERVAL_HOURS` | `6` | How often to check Riven for problem items |
| `RETRY_INTERVAL_MINUTES` | `10` | Minimum time between retry attempts for same item |
| `RD_CHECK_INTERVAL_MINUTES` | `5` | How often to check RD torrent status |
| `RD_MAX_WAIT_HOURS` | `2` | Max time to wait for RD download before considering stalled |
| `RD_CLEANUP_INTERVAL_HOURS` | `1` | How often to run RD cleanup check |
| `RD_STUCK_TORRENT_HOURS` | `24` | Consider a torrent stuck if active for this long with <5% progress |
| `MAX_RIVEN_RETRIES` | `3` | Number of Riven retries before falling back to manual scrape |
| `SKIP_RIVEN_RETRY` | `false` | Skip remove+add retry and go directly to manual RD scraping |
| `SKIP_RD_VALIDATION` | `false` | Skip Real-Debrid API validation on startup (for testing) |
| `MAX_RD_TORRENTS` | `10` | Max torrents to try per item during manual scrape |
| `MAX_ACTIVE_RD_DOWNLOADS` | `3` | Max concurrent active downloads on Real-Debrid |
| `TORRENT_ADD_DELAY_SECONDS` | `30` | Delay between adding torrents to RD |
| `RD_RATE_LIMIT_SECONDS` | `5` | Seconds between Real-Debrid API calls |
| `RIVEN_RATE_LIMIT_SECONDS` | `1` | Seconds between Riven API calls |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

## Logs

View logs in Docker:
```bash
docker-compose logs -f trc
```

## State Persistence

TRC saves its state to `data/trc_state.json` (or `/app/data/trc_state.json` in Docker). This includes:
- Item trackers (retry counts, manual scrape progress)
- Active RD downloads being monitored
- Processed items (to avoid re-processing)

To reset all state, stop TRC and delete the state file from the data directory.

## Troubleshooting

### Items still failing after retries
- Check if the content is actually available (newly released content may not have sources)
- Try increasing `MAX_RD_TORRENTS` to try more sources
- Check Riven logs for specific scraping errors

### RD downloads timing out
- Increase `RD_MAX_WAIT_HOURS` for slow torrents
- Dead torrents (no seeders) are now detected immediately and TRC moves to the next one
- Stalled torrents with <10% progress after timeout will also be skipped

### Rate limiting errors
- Increase `RD_RATE_LIMIT_SECONDS` (default 5s is conservative)
- Real-Debrid allows 250 requests/minute

## License

MIT License

