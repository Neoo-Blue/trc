# Torrent Manual Deletion Fix

## Problem
When manually deleting torrents from Real-Debrid (RD), the monitor would encounter errors:
1. **404 Error**: Attempting to check status of a torrent that no longer exists (`Error checking torrent 74Z4UJXR7DOUQ: Client error '404 Not Found'`)
2. **Server Disconnection**: Followed by `Server disconnected without sending a response` error when trying to enforce max active torrents

## Root Cause
The code did not handle the following scenarios:
1. When a torrent is manually deleted from RD, subsequent API calls to check its status return 404 (Not Found)
2. The `_enforce_max_active_torrents()` method had no retry logic for transient server connection errors
3. Torrents that no longer exist on RD were not being removed from the monitor's internal tracking

## Solution

### 1. Added `TorrentNotFoundError` Exception
**File**: `src/rd_client.py`
- Added a new exception class specifically for 404 responses
- This allows the code to distinguish between "torrent not found" errors and other types of errors

### 2. Updated API Request Handler
**File**: `src/rd_client.py` - `_request()` method
- Now explicitly checks for HTTP 404 responses
- Raises `TorrentNotFoundError` when a resource is not found
- Logs clearly that the resource wasn't found

### 3. Enhanced Torrent Status Checking
**File**: `src/monitor.py` - torrent monitoring loop
- Added a specific exception handler for `TorrentNotFoundError`
- When a torrent is not found:
  - Logs that it was likely manually deleted
  - Removes it from tracking immediately
  - Marks the tracker for refilling with new streams

### 4. Added Retry Logic for API Calls
**File**: `src/monitor.py` - `_enforce_max_active_torrents()` method
- Implemented retry mechanism (2 attempts) for getting torrent list
- Waits 2 seconds between failed attempts before retrying
- Gracefully handles transient server connection errors
- Logs retry attempts for debugging

## Impact
- **Graceful Handling**: Manually deleted torrents are now properly removed from tracking instead of causing cascading errors
- **Better Recovery**: Server disconnection errors now retry instead of immediately failing
- **Cleaner Logs**: Clear logging of what happened when torrents are not found
- **Automatic Refilling**: When a torrent is removed (manually or due to completion), the system automatically fills RD slots with new streams

## Files Modified
1. `src/rd_client.py` - Added exception and updated request handling
2. `src/monitor.py` - Updated imports, error handling, and retry logic

## Testing
To verify the fix works:
1. Manually delete a torrent from RD while the monitor is running
2. The monitor should:
   - Log: `Torrent {ID} not found on RD (likely manually deleted). Removing from tracking.`
   - Not crash or show 404 errors
   - Continue monitoring other torrents normally
   - Automatically fill the freed slot with a new stream if available
