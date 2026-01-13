# TRC State Filtering - Only Failed/Unknown Items

## Overview

The Riven TRC system is configured to **ONLY process items in the Failed or Unknown states** from Riven. This ensures no items outside these states are affected by the automation.

## Configuration

**File:** `src/config.py`

```python
# States to monitor
problem_states: list = field(default_factory=lambda: ["Failed", "Unknown"])
```

This setting is used in the main check loop to query only items with these states.

---

## How It Works

### 1. Initial Query (Strict Filtering)
**File:** `src/riven_client.py` - `get_problem_items()`

```python
async def get_problem_items(self, states: List[str], limit: int = 100) -> List[MediaItem]:
    """Get items with problem states (Failed, Unknown)."""
    # Primary: Query API with state filter
    result = await self._request(
        "GET", 
        f"/items?limit={limit}&{'&'.join([f'states={s}' for s in states])}"
    )
    
    # Fallback: If API fails, retrieve all items and filter locally
    # This ensures ONLY specified states are returned
    filtered_items = [
        MediaItem.from_dict(item) for item in all_items
        if item.get("state") in states
    ]
```

**Key Point:** Even if the API doesn't support state filtering, the fallback code filters locally to ensure only Failed/Unknown items are returned.

### 2. Main Check Loop (Validation)
**File:** `src/monitor.py` - `_check_problem_items()`

```python
async def _check_problem_items(self):
    """Check for and handle ONLY failed/unknown state items from Riven."""
    # Query with strict state filtering
    items = await self.riven.get_problem_items(self.config.problem_states, limit=200)
    
    for item in items:
        # Additional validation: skip unreleased items
        if not item.is_released():
            continue
        
        # Process only if still in problem state
        await self._handle_problem_item(tracker)
```

### 3. Item Processing (State Re-validation)
**File:** `src/monitor.py` - `_handle_problem_item()`

```python
async def _handle_problem_item(self, tracker: ItemTracker):
    """Handle a single problem item."""
    item = tracker.item
    
    # Re-validate item is still in a problem state
    if item.state not in self.config.problem_states:
        logger.debug(f"Item {item.display_name} state changed to {item.state}, skipping")
        # Remove from trackers if state changed
        if item.id in self.item_trackers:
            del self.item_trackers[item.id]
            self.state.remove_item_tracker(item.id)
        return
    
    # Process item (retry, manual scrape, etc.)
```

---

## Multiple Layers of Filtering

1. **API Level**: Query API with `states=Failed&states=Unknown`
2. **Fallback Level**: If API fails, filter locally on retrieved items
3. **Loop Level**: Main check only processes returned items
4. **Item Level**: Each item validates its state before processing
5. **Cleanup Level**: Items with changed state are removed from tracking

---

## What Items Are Processed

✅ **Items in these states ONLY:**
- Failed
- Unknown

❌ **Items in these states are IGNORED:**
- Downloaded
- Resolved
- Indexed
- Available
- (Any other state)

---

## Verification

Run the verification script to confirm state filtering is working:

```bash
python verify_states.py
```

Expected output:
```
✅ VERIFIED: All N returned items are in problem states

[Distribution]
   Failed: X items
   Unknown: Y items
```

---

## Summary

**The TRC system is configured to work EXCLUSIVELY on items with Failed or Unknown states in Riven. No other states are processed.**

Changes made:
- ✅ Enhanced `get_problem_items()` fallback to filter locally
- ✅ Added state validation in `_handle_problem_item()`
- ✅ Added comprehensive logging of states being processed
- ✅ Created verification script (`verify_states.py`)

**Status: VERIFIED AND LOCKED**
