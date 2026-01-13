# TRC API Error & Download Completion Fixes

## Issues Identified

### 1. 400 Bad Request When Removing Items After Torrent Completion
**Error:** `Failed to remove item tmdb:None|tvdb:424941: Client error '400 Bad Request'`

**Root Cause:** 
- When handling failed episodes, TRC creates pseudo-items with IDs like `tmdb:None|tvdb:424941`
- These are NOT valid Riven item IDs (Riven uses numeric/UUID IDs from its database)
- When torrents completed for these pseudo-items, TRC tried to remove them from Riven using invalid IDs
- This caused 400 Bad Request errors

### 2. Inefficient Torrent Application After Download
**Issue:** After torrent completes and re-adds item, Riven still shows as failed until next check
**Reason:** Remove/re-add only triggers Riven to look for content, but doesn't apply downloaded torrent directly

## Solutions Implemented

### Fix 1: Smart Item ID Validation
**File:** `src/monitor.py` - `_monitor_rd_downloads()` method

```python
if item.id.startswith("tmdb:") or item.id.startswith("tvdb:"):
    # This is a pseudo-item (parent show), don't try to remove it
    logger.info(f"Torrent completed for pseudo-item (parent show)")
else:
    # This is a real Riven item, try to remove and re-add
```

**Benefits:**
- Detects pseudo-items before attempting removal
- Prevents 400 Bad Request errors
- Gracefully handles both real and pseudo items
- Logs appropriate messages for debugging

### Fix 2: Better Error Messages
**File:** `src/riven_client.py` - `remove_item()` method

Added specific error handling for 400 responses:
```python
except httpx.HTTPStatusError as e:
    if e.response.status_code == 400:
        logger.error(f"Invalid item ID (400 Bad Request). Item ID format may be incorrect.")
    else:
        logger.error(f"HTTP {e.response.status_code}")
```

**Benefits:**
- Clear error messages when ID is invalid
- Easier debugging of API issues
- Distinguishes between 400 (bad ID) and other HTTP errors

### Fix 3: API Testing Script
**File:** `test_api.py`

New comprehensive test script that:
- Verifies Riven API connectivity
- Shows actual item IDs from Riven (numeric/UUID format)
- Tests all endpoints used by TRC
- Helps identify pseudo-items vs real items
- Verifies scrape functionality

**Usage:**
```bash
python test_api.py
```

**Output shows:**
- Real Riven item IDs (will be numeric or UUID, never `tmdb:xxx|tvdb:xxx`)
- Item properties (type, TMDB ID, TVDB ID)
- API endpoint responses
- Any connectivity issues

## Item ID Formats

### Real Riven Items
- Source: Returned by `get_problem_items()` from Riven API
- Format: Numeric or UUID (e.g., `12345` or `uuid-string-here`)
- Behavior: Can be removed and re-added
- When torrent completes: TRC will remove/re-add to make content available

### Pseudo-Items (Parent Shows)
- Source: Created by TRC for failed episodes
- Format: `tmdb:123|tvdb:456` or `tmdb:None|tvdb:456`
- Behavior: Cannot be removed from Riven (don't exist in DB)
- When torrent completes: Marked as processed, Riven's native monitoring handles it

## Testing the Fixes

### Step 1: Run API Test
```bash
python test_api.py
```
- Confirms Riven API is accessible
- Shows item ID formats in use
- Verifies add/remove/scrape endpoints work

### Step 2: Monitor Download Completion
Watch logs for:
- Real items: `Re-added [item name] to Riven to pick up cached content`
- Pseudo-items: `Torrent completed for pseudo-item (parent show)`
- No 400 Bad Request errors

### Step 3: Verify Content Application
After torrent completion:
- Real items: Should become available in Riven after re-add
- Pseudo-items: Parent show should pick up content on next Riven check

## Log Output Examples

### Before Fix
```
ERROR: Failed to remove item tmdb:None|tvdb:424941: Client error '400 Bad Request'
INFO: Added item tmdb=None, tvdb=424941
```

### After Fix
```
INFO: ✓ Torrent completed after 4.9m: Physical.100.S01E06...
INFO: Torrent completed for pseudo-item (parent show), marking as processed
INFO: Re-added [Real Item] to Riven to pick up cached content
```

## Remaining Considerations

1. **Pseudo-items and Episode Handling:** When episodes fail and parent show torrents complete, Riven's native episode monitoring will need to pick up the content on next cycle. This is the expected behavior.

2. **Manual Scraping:** For items that still don't get content despite manual scraping, verify:
   - Torrent actually downloaded to RD (check RD account)
   - Riven API is responsive (run `test_api.py`)
   - Item still exists in Riven (might have been deleted)

3. **Rate Limiting:** If seeing many API errors:
   - Check `RD_RATE_LIMIT_SECONDS` and `RIVEN_RATE_LIMIT_SECONDS` settings
   - Verify API keys have required permissions
   - Check API rate limits haven't been exceeded

## Files Modified

- `src/monitor.py`: Smart item ID validation in download completion flow
- `src/riven_client.py`: Better error messages for remove_item
- `test_api.py`: New comprehensive API testing script
- `README.md`: Updated with testing guide and debugging info
