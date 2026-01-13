# TRC v1.1 - Release Notes & Testing Guide

## What's Fixed

### 1. ✓ HTTP 451 (Content Infringement) Handling
- Real-Debrid now returns 451 when content is flagged as infringing
- TRC automatically skips to next torrent
- No manual intervention needed
- [See commit](src/rd_client.py)

### 2. ✓ Active Download Progress Tracking  
- All downloads now show real-time progress
- Format: `↓ Downloading (50%, 3.5m): filename`
- Updated every 5 minutes in logs
- Shows elapsed time and percentage
- [See commit](src/monitor.py)

### 3. ✓ Concurrent Torrent Distribution (3 Simultaneous)
- Maintains 3 active torrents across different items
- Fair round-robin distribution
- Automatically fills empty slots
- Works across any number of items
- [See commit](src/monitor.py)

### 4. ✓ 400 Bad Request Error (Item Removal)
- **Root Cause:** TRC was trying to remove pseudo-items (parent shows)
- **Fix:** Smart detection of item types before removal
- **Result:** Graceful handling - no more 400 errors
- Real items still get removed/re-added
- Pseudo-items marked as processed
- [See commit](src/monitor.py)

### 5. ✓ Better Error Messages
- Specific message for 400 Bad Request (invalid item ID)
- Distinguishes between different error types
- Helps with debugging API issues
- [See commit](src/riven_client.py)

## New Debugging Tools

### test_api.py
Comprehensive API testing:
```bash
python test_api.py
```
✓ Tests user authentication  
✓ Shows actual Riven item IDs  
✓ Tests add/remove/scrape endpoints  
✓ Verifies stream scraping works  

### check_state.py
Analyze what's being tracked:
```bash
python check_state.py
```
✓ Shows real items vs pseudo-items  
✓ Lists item ID formats  
✓ Identifies problematic items  
✓ Helps understand errors  

## Testing Checklist

### Pre-Testing
- [ ] Pull latest code
- [ ] Backup data/trc_state.json
- [ ] Verify Riven URL and API key
- [ ] Verify Real-Debrid API key

### Phase 1: API Connectivity
```bash
# Test both APIs
python test_api.py

# Should show:
# ✓ User info (Riven)
# ✓ 3-5 problem items from Riven
# ✓ Item IDs in numeric/UUID format
# ✓ Connection successful to both APIs
```

### Phase 2: Current State
```bash
# See what TRC is tracking
python check_state.py

# Should show:
# ✓ Item count and types
# ✓ Real items vs pseudo-items
# ✓ Any items with "None" in ID
```

### Phase 3: Monitor Output
Watch logs for next cycle:
```bash
docker-compose logs -f trc
```

✓ Should see:
- `✓ Torrent completed after X.Xm: [filename]`
- For real items: `Re-added [name] to Riven...`
- For pseudo-items: `Torrent completed for pseudo-item...`
- NO `400 Bad Request` errors

### Phase 4: Content Availability
After torrent completes:
- Real items: Check Riven - content should be available
- Pseudo-items: Wait for next Riven check (episode monitoring)

## Expected Behavior After Fix

### Real Item Completes
```
Log 1: ✓ Torrent completed after 12.3m: Physical.100.S01E06...
Log 2: Re-added [item] to Riven to pick up cached content
Result: Content available in Riven
```

### Episode (Pseudo-Item) Completes
```
Log 1: ✓ Torrent completed after 8.5m: Physical.100.S01E07...
Log 2: Torrent completed for pseudo-item (parent show)
Result: Riven episode monitoring finds content next check
Note: No "400 Bad Request" error
```

### Dead/Stalled Torrent
```
Log 1: ✗ Torrent dead/no seeders: [filename]
Result: Auto-skips to next torrent
        Still maintains 3 concurrent downloads
```

## Known Limitations

### Pseudo-Items and Episodes
- Episodes that fail create pseudo-items (parent shows)
- When parent show torrent completes, it can't be removed from Riven
- **This is expected and now handled gracefully**
- Riven's native episode monitoring will find the cached content

### Manual Scraping
- Manual scraping finds torrents that Riven's scraper didn't
- Applies them to RD to cache content
- Riven still needs to be notified via remove/re-add
- For pseudo-items, notification happens through episode monitoring

## Rollback Plan

If issues occur:
```bash
# Stop TRC
docker-compose down

# Restore previous backup (if needed)
cp data/trc_state.json.backup data/trc_state.json

# Checkout previous version
git checkout HEAD~1

# Restart
docker-compose up -d
```

## Performance Impact

- **API calls:** Same as before
- **Download speed:** No impact
- **RD storage:** No impact  
- **CPU/Memory:** Slightly improved (less error handling overhead)
- **Concurrency:** Now properly maintains 3 simultaneous

## What to Report if Issues Found

If you find problems, please include:
1. Full error message from logs
2. Output from `python test_api.py`
3. Output from `python check_state.py`
4. Your TRC configuration (environment variables)
5. Steps to reproduce

## Questions?

Check these files for more info:
- **README.md** - General usage and configuration
- **TROUBLESHOOTING.md** - Common issues and solutions
- **FIXES_SUMMARY.md** - Technical details of fixes
- **test_api.py** - Run to verify API connectivity
- **check_state.py** - Analyze current state

---

**Version:** 1.1  
**Date:** 2026-01-13  
**Changes:** Fixed item removal errors, added progress tracking, improved debugging
