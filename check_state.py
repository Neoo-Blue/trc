#!/usr/bin/env python3
"""Check item ID types and state in TRC trackers."""

import json
from pathlib import Path

def check_state():
    """Check the state file for item ID formats."""
    state_file = Path("data/trc_state.json")
    
    if not state_file.exists():
        print("✗ State file not found at data/trc_state.json")
        print("  TRC hasn't been run yet, or state was not persisted.")
        return
    
    print("=" * 70)
    print("TRC State Analysis - Item ID Types")
    print("=" * 70)
    
    with open(state_file) as f:
        state = json.load(f)
    
    trackers = state.get("item_trackers", {})
    print(f"\nTotal items tracked: {len(trackers)}")
    
    real_items = []
    pseudo_items = []
    
    for item_id, tracker_data in trackers.items():
        is_pseudo = item_id.startswith("tmdb:") or item_id.startswith("tvdb:")
        
        item_data = tracker_data.get("item", {})
        title = item_data.get("title", "Unknown")
        item_type = item_data.get("type", "unknown")
        
        if is_pseudo:
            pseudo_items.append({
                "id": item_id,
                "title": title,
                "type": item_type,
            })
        else:
            real_items.append({
                "id": item_id,
                "title": title,
                "type": item_type,
            })
    
    # Display real items
    print(f"\n{'Real Riven Items'} ({len(real_items)}):")
    print("-" * 70)
    if real_items:
        for item in real_items[:10]:  # Show first 10
            print(f"  ID: {item['id']:<20} Type: {item['type']:<10} {item['title']}")
        if len(real_items) > 10:
            print(f"  ... and {len(real_items) - 10} more")
    else:
        print("  (none)")
    
    # Display pseudo items
    print(f"\n{'Pseudo-Items (Parent Shows)'} ({len(pseudo_items)}):")
    print("-" * 70)
    if pseudo_items:
        for item in pseudo_items[:10]:  # Show first 10
            print(f"  ID: {item['id']:<30} Type: {item['type']:<10} {item['title']}")
        if len(pseudo_items) > 10:
            print(f"  ... and {len(pseudo_items) - 10} more")
    else:
        print("  (none)")
    
    # Analysis
    print("\n" + "=" * 70)
    print("Analysis")
    print("=" * 70)
    
    print(f"\n✓ Real items (can be removed/re-added): {len(real_items)}")
    print(f"✓ Pseudo-items (created for failed episodes): {len(pseudo_items)}")
    
    if pseudo_items:
        print(f"\nNote: Pseudo-items with format 'tmdb:X|tvdb:Y' are created for:")
        print("  - Failed episodes (retries the parent show)")
        print("  - Will be handled gracefully when torrents complete")
        print("  - Will NOT cause 400 Bad Request errors (fixed)")
    
    # Check for None IDs
    none_count = sum(1 for item in pseudo_items if "None" in item["id"])
    if none_count > 0:
        print(f"\n⚠ Found {none_count} items with 'None' in ID:")
        for item in pseudo_items:
            if "None" in item["id"]:
                print(f"  - {item['id']}")
        print("  These are parent shows without TMDB ID (using only TVDB)")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_state()
