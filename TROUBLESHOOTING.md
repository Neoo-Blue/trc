# TRC Quick Reference - Troubleshooting

## Common Issues & Solutions

### Issue 1: 400 Bad Request When Torrent Completes
```
Failed to remove item tmdb:None|tvdb:424941: Invalid item ID (400 Bad Request)
```

**Status:** ✓ FIXED in v1.1

**What it means:**
- Item is a pseudo-item (parent show created for failed episode)
- Can't be removed from Riven (doesn't exist in Riven's database)

**Solution:**
- TRC now detects this automatically
- No error handling needed - logs gracefully and marks as processed
- Riven's native monitoring will find the cached content

**To debug:**
```bash
python check_state.py  # See which items are pseudo-items
```

---

### Issue 2: Torrent Completes But Content Not Available

**Possible causes:**
1. Item was pseudo-item - waiting for Riven's next check
2. Real item removal failed - check logs for actual error
3. Content not actually cached on RD - verify RD account

**Solutions:**

**Step 1:** Identify item type
```bash
python check_state.py
# Look for the item - is it a real item or pseudo-item?
```

**Step 2:** Test API connectivity
```bash
python test_api.py
# Verify Riven API is working
# Check that item IDs are in correct format
```

**Step 3:** Check RD account
- Login to Real-Debrid
- Verify torrent is actually cached/downloaded
- Check account quota not exceeded

**Step 4:** Manual refresh
- For real items: Wait up to 6 hours for next check (or restart TRC)
- For pseudo-items: Riven's episode monitoring will find it automatically

---

### Issue 3: Many 400 Bad Request Errors

**Likely cause:** Most items are pseudo-items (parent shows from episodes)

**What this means:**
- You have many failed episodes
- TRC is creating parent show trackers to retry them
- This is expected behavior

**To see breakdown:**
```bash
python check_state.py
# Compares real items vs pseudo-items
# Shows why some can't be removed
```

**Solution:**
- This is harmless - TRC now handles it gracefully
- Continue monitoring - torrents will still download and be applied
- Consider if episodes should be marked as "ignore" in Riven if they're not wanted

---

### Issue 4: API Errors Like "Connection Refused"

**Causes:**
- Riven URL incorrect
- Riven not running
- API key invalid
- Network connectivity issue

**Quick test:**
```bash
python test_api.py
# If this fails, API connectivity is the issue
# If this succeeds, TRC code is working fine
```

**Debug steps:**

1. Verify Riven is running:
   ```bash
   # Docker
   docker-compose ps
   
   # Or check your Riven setup
   ```

2. Verify RIVEN_URL environment variable:
   ```bash
   echo $RIVEN_URL
   # Should match where Riven actually runs
   # e.g., http://192.168.50.203:8083
   ```

3. Test URL manually:
   ```bash
   curl http://192.168.50.203:8083/api/v1/user \
     -H "X-API-Key: your_api_key"
   # Should return user info
   ```

4. Verify API key:
   - Go to Riven UI → Settings → Get API Key
   - Update RD_API_KEY environment variable
   - Restart TRC

---

## Log Symbols Reference

| Symbol | Meaning | Action |
|--------|---------|--------|
| ✓ | Success/Complete | Good - working as expected |
| ✗ | Failed/Dead | Torrent failed, TRC will try next |
| ⚠ | Warning/Stalled | Torrent progress stuck, TRC will try next |
| ↓ | Downloading | Normal - torrent in progress |
| ⏳ | Waiting | Magnet conversion or file selection in progress |
| ℹ | Info | Status update or state change |
| ⚠ ERROR | Error | Issue occurred, check details |

---

## Understanding Item Types

### Real Items
```
ID format: 12345 or 550e8400-e29b-41d4-a716-446655440000
Source: Riven's database (get_problem_items)
Behavior: Can be removed/re-added
When torrent completes: TRC removes and re-adds to Riven
Result: Content becomes available immediately
```

### Pseudo-Items (Parent Shows)
```
ID format: tmdb:123|tvdb:456 or tmdb:None|tvdb:456
Source: Created by TRC for failed episodes
Behavior: Cannot be removed (don't exist in Riven)
When torrent completes: TRC marks as processed, no removal attempted
Result: Riven's native episode monitoring finds content on next check
```

---

## Debug Workflow

```
Seeing errors in logs?
  ↓
1. Run: python test_api.py
  - Does API work?
  - If NO → Fix connectivity first
  - If YES → Continue
  ↓
2. Run: python check_state.py
  - How many items are pseudo-items?
  - Are they causing the errors?
  ↓
3. Check specific item
  - Look at logs for item name
  - See if it's real or pseudo
  - Understand why it failed
  ↓
4. Take action based on type
  - Real item: Check if removal/re-add worked
  - Pseudo-item: Check if it's just waiting
```

---

## Performance Notes

- **Real Debrid limit:** 3 concurrent downloads
- **Check interval:** Default 6 hours (configurable)
- **RD monitor:** Every 5 minutes
- **Cleanup:** Every 1 hour

If things seem slow:
1. Check RD account limit (250 requests/min)
2. Verify download speeds (might be slow torrent)
3. Check Riven performance (if adding items is slow)

---

## Files Created for Debugging

1. **test_api.py** - Test API connectivity
2. **check_state.py** - Analyze persisted state
3. **FIXES_SUMMARY.md** - Detailed fix information
4. **data/trc_state.json** - Persisted state (created after first run)
5. **Logs** - Check docker-compose logs or terminal output
