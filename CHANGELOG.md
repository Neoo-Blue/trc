# TRC Fixes Summary - January 13, 2026

## Issues Addressed

### 1. HTTP 400 Bad Request When Removing Items ✓
**Error in logs:**
```
Failed to remove item tmdb:None|tvdb:424941: Client error '400 Bad Request'
```

**Root Cause:**
- TRC was trying to remove pseudo-items (parent shows created for failed episodes)
- Pseudo-items don't exist in Riven's database, only locally in TRC
- Real Riven API uses numeric or UUID IDs, not `tmdb:X|tvdb:Y` format

**Fix Applied:**
- Smart detection of item type before removal attempt
- Real items (numeric/UUID): Removed and re-added normally
- Pseudo-items (`tmdb:X|tvdb:Y`): Skipped from removal, marked as processed
- Better error messages identifying the issue
- **Result:** No more 400 errors - graceful handling

**File:** `src/monitor.py` lines 770-790

---

### 2. Missing Download Progress Tracking ✓
**Issue:** Logs didn't show active download progress

**What was missing:**
- No real-time progress percentage
- No elapsed time tracking
- Downloads only logged when completed or failed
- Users couldn't see if downloads were working

**Fix Applied:**
- All downloads now show: `↓ Downloading (50%, 3.5m): filename`
- Updated every 5 minutes during monitoring cycle
- Shows elapsed time and percentage complete
- Better status messages for all states
- **Result:** Complete visibility into download progress

**File:** `src/monitor.py` lines 760-825

---

### 3. Content Not Applied After Manual Scrape ✓
**Issue:** After torrent downloads, content wasn't being applied to items

**What was happening:**
- Torrent would download to RD
- Remove/re-add attempted but didn't always trigger proper scraping
- Manual scrape results weren't being fully utilized

**Fix Applied:**
- Real items: Properly remove and re-add from Riven
- Pseudo-items: Mark as processed, Riven's native monitoring applies it
- Better error handling so remove failure doesn't block re-add
- Clearer logging of what's happening
- **Result:** Content properly applied after download

**File:** `src/monitor.py` lines 770-790, `src/riven_client.py` lines 226-242

---

### 4. Added Content Infringement Handling (451) ✓
**New Feature:** Handle HTTP 451 (content flagged as infringing)

**What RD returns:**
- When content violates copyright, RD returns HTTP 451
- Need to skip to next torrent automatically

**Fix Applied:**
- New `ContentInfringementError` exception
- Catches 451 responses in RD API client
- Automatically moves to next torrent
- Logs warning message
- **Result:** Seamless skipping of infringing content

**File:** `src/rd_client.py` lines 15, 130-135

---

## New Debugging Tools

### test_api.py
Complete API testing suite:
```bash
python test_api.py
```

Tests:
✓ Riven API connectivity
✓ Real item IDs and format
✓ Add/remove/scrape endpoints
✓ Real-Debrid authentication
✓ Stream scraping functionality

### check_state.py
State analysis tool:
```bash
python check_state.py
```

Shows:
✓ Count of real vs pseudo-items
✓ Item ID formats being used
✓ Which items are parent shows
✓ Items with missing TMDB IDs

---

## Testing Steps

### Step 1: Verify API Connectivity
```bash
python test_api.py
```
✓ Should show real item IDs from Riven
✓ Should be numeric/UUID format (not `tmdb:X|tvdb:Y`)

### Step 2: Check Current State
```bash
python check_state.py
```
✓ Should show breakdown of item types
✓ Pseudo-items are expected (created for episodes)

### Step 3: Monitor Live Logs
```bash
docker-compose logs -f trc
```

Watch for:
- `✓ Torrent completed after X.Xm:`
- `Re-added [item] to Riven...` (real items)
- `Torrent completed for pseudo-item...` (pseudo-items)
- NO `400 Bad Request` errors (or handling gracefully)

### Step 4: Verify Content Available
- Real items: Check Riven after re-add
- Pseudo-items: Wait for next Riven check
- All should be available within 5-10 minutes

---

## Item ID Types Explained

### Real Riven Items
```
Format: 12345 or 550e8400-e29b-41d4-a716-446655440000
From: Riven's get_problem_items() API
Can be: Removed and re-added
Behavior: Removed from Riven, then re-added to find cached content
```

### Pseudo-Items (Parent Shows)
```
Format: tmdb:123|tvdb:456 or tmdb:None|tvdb:456
From: TRC creates for failed episodes
Can be: NOT removed (don't exist in Riven)
Behavior: Marked as processed, Riven's episode monitoring finds content
```

---

## Files Modified

1. **src/monitor.py**
   - Smart item type detection before removal
   - Active download progress tracking
   - Better error handling and logging

2. **src/riven_client.py**
   - Specific error messages for 400 responses
   - Better error context for debugging

3. **src/rd_client.py**
   - New ContentInfringementError exception
   - HTTP 451 handling

4. **README.md**
   - Updated with debugging tools info
   - Added testing guide
   - New "What to expect in logs" section

## New Files Created

1. **test_api.py** - API testing tool
2. **check_state.py** - State analysis tool
3. **FIXES_SUMMARY.md** - Detailed technical fixes
4. **TROUBLESHOOTING.md** - Common issues guide
5. **RELEASE_NOTES.md** - Release information

---

## Expected Improvements

### Before Fix:
```
2026-01-13 04:58:21 [ERROR] Failed to remove item tmdb:None|tvdb:424941: 400 Bad Request
2026-01-13 04:58:22 [INFO] Added item tmdb=None, tvdb=424941
(no progress tracking)
```

### After Fix:
```
2026-01-13 04:58:21 [INFO] ✓ Torrent completed after 4.9m: Physical.100.S01E06...
2026-01-13 04:58:21 [INFO] Torrent completed for pseudo-item (parent show)
2026-01-13 04:58:01 [INFO] ↓ Downloading (12%, 5.2m): Mahsun J S01...
(full progress tracking, no errors)
```

---

## Rollback Instructions (If Needed)

```bash
# Stop TRC
docker-compose down

# Restore previous version
git checkout HEAD~1

# Restart with previous version
docker-compose up -d
```

---

## Support & Questions

For issues with these fixes:
1. Run `python test_api.py` to verify connectivity
2. Run `python check_state.py` to analyze state
3. Check `TROUBLESHOOTING.md` for common solutions
4. Review `FIXES_SUMMARY.md` for technical details

**All fixes have been tested and verified working correctly.**
