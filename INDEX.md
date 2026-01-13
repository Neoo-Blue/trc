# TRC Documentation Index

## Quick Start

**For new users:**
1. Start with [README.md](README.md) for setup and configuration
2. Run `python test_api.py` to verify your API setup
3. Check logs with `docker-compose logs -f trc`

**For existing users (upgrading to v1.1):**
1. Read [RELEASE_NOTES.md](RELEASE_NOTES.md) for what's new
2. Review [CHANGELOG.md](CHANGELOG.md) for detailed changes
3. Run debugging tools to verify setup

---

## Documentation Files

### Setup & Configuration
- **[README.md](README.md)** - Installation, setup, configuration, features overview
- **[.env.example](.env.example)** - Environment variable template

### Troubleshooting & Debugging
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues, solutions, debug workflow
- **[RELEASE_NOTES.md](RELEASE_NOTES.md)** - What's new in v1.1, testing checklist
- **[FIXES_SUMMARY.md](FIXES_SUMMARY.md)** - Technical details of fixes, implementation info
- **[CHANGELOG.md](CHANGELOG.md)** - Complete change log and improvements

### Debugging Tools
- **[test_api.py](test_api.py)** - Test Riven API connectivity and endpoints
- **[check_state.py](check_state.py)** - Analyze persisted state and item types

### Source Code
- **[src/](src/)** - Main application code
  - `main.py` - Entry point
  - `monitor.py` - Core monitoring logic (recently updated)
  - `riven_client.py` - Riven API client (recently updated)
  - `rd_client.py` - Real-Debrid API client (updated with 451 handling)
  - `config.py` - Configuration handling
  - `persistence.py` - State persistence
  - `rate_limiter.py` - API rate limiting

### Tests
- **[tests/](tests/)** - Unit tests
  - `test_monitor.py`
  - `test_rd_client.py`

---

## v1.1 Updates Summary

### Fixed Issues
✓ HTTP 400 Bad Request when removing pseudo-items  
✓ Missing download progress tracking  
✓ HTTP 451 (content infringement) handling  
✓ Better error messages and debugging  

### New Features
✓ Real-time download progress in logs  
✓ Active progress tracking (% and elapsed time)  
✓ Smart item type detection  
✓ Content infringement auto-skip  

### New Tools
✓ `test_api.py` - API testing suite  
✓ `check_state.py` - State analysis tool  

---

## Common Tasks

### I want to...

#### Test if my API setup works
```bash
python test_api.py
```
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md#issue-4-api-errors-like-connection-refused)

#### Understand what items TRC is tracking
```bash
python check_state.py
```
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md#understanding-item-types)

#### See real-time download progress
```bash
docker-compose logs -f trc
```
Look for: `↓ Downloading (50%, 3.5m): filename`

#### Fix the "400 Bad Request" error
Read: [FIXES_SUMMARY.md](FIXES_SUMMARY.md#root-cause)  
Status: ✓ Already fixed in v1.1

#### Understand why an item wasn't applied
Read: [TROUBLESHOOTING.md](TROUBLESHOOTING.md#issue-2-torrent-completes-but-content-not-available)

#### See what changed in this version
Read: [RELEASE_NOTES.md](RELEASE_NOTES.md#whats-fixed)

#### Debug a specific error
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the error
2. Run `python test_api.py` to verify APIs
3. Run `python check_state.py` to see state
4. Review specific logs with `docker-compose logs`

---

## File Structure

```
trc/
├── src/                       # Main application
│   ├── main.py               # Entry point
│   ├── monitor.py            # Core logic (UPDATED)
│   ├── riven_client.py        # Riven API (UPDATED)
│   ├── rd_client.py           # Real-Debrid API (UPDATED)
│   ├── config.py
│   ├── persistence.py
│   └── rate_limiter.py
├── tests/                     # Unit tests
│   ├── test_monitor.py
│   └── test_rd_client.py
├── data/                      # Created at runtime
│   └── trc_state.json        # Persisted state
├── test_api.py               # NEW - API testing
├── check_state.py            # NEW - State analysis
├── README.md                 # Setup guide (UPDATED)
├── RELEASE_NOTES.md          # NEW - What's new
├── FIXES_SUMMARY.md          # NEW - Technical fixes
├── TROUBLESHOOTING.md        # NEW - Common issues
├── CHANGELOG.md              # NEW - Change log
├── docker-compose.yml        # Docker configuration
├── Dockerfile                # Docker image
├── requirements.txt          # Python dependencies
└── .env.example             # Configuration template
```

---

## Getting Help

### For Setup Issues
1. Read [README.md](README.md) installation section
2. Run `python test_api.py` to verify API setup
3. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md#issue-4-api-errors-like-connection-refused)

### For 400 Bad Request Errors
✓ **This is fixed in v1.1**
- Read [FIXES_SUMMARY.md](FIXES_SUMMARY.md) for technical details
- Run `python check_state.py` to see item types
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md#issue-1-400-bad-request-when-torrent-completes)

### For Download Progress Issues
1. Check logs with `docker-compose logs -f trc`
2. Look for `↓ Downloading (X%, Y.Zm)` messages
3. Run `python test_api.py` to verify RD connectivity
4. See [README.md](README.md#what-to-expect-in-logs)

### For Other Issues
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for your error
2. Follow the debug workflow in [TROUBLESHOOTING.md](TROUBLESHOOTING.md#debug-workflow)
3. Run debugging tools (`test_api.py`, `check_state.py`)
4. Review relevant documentation file listed above

---

## Version Info

**Current Version:** 1.1  
**Release Date:** January 13, 2026  
**Changes:** Fixed item removal errors, added progress tracking, improved debugging  

For complete change history, see [CHANGELOG.md](CHANGELOG.md)

---

## Quick Command Reference

```bash
# Run API tests
python test_api.py

# Check state and item types
python check_state.py

# View live logs
docker-compose logs -f trc

# Stop TRC
docker-compose down

# Start TRC
docker-compose up -d

# Restart TRC
docker-compose restart trc

# Check if TRC is running
docker-compose ps
```

---

## Documentation Map

```
You are here → This file (INDEX.md)
              ↓
        What do you need?
        ├─→ Getting started? → README.md
        ├─→ What's new? → RELEASE_NOTES.md
        ├─→ Having issues? → TROUBLESHOOTING.md
        ├─→ Need technical details? → FIXES_SUMMARY.md
        ├─→ Want full changelog? → CHANGELOG.md
        ├─→ Need to test APIs? → Run: python test_api.py
        └─→ Need to see state? → Run: python check_state.py
```

---

Last updated: January 13, 2026
