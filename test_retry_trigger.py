#!/usr/bin/env python3
"""Test using retry_item to trigger scrape after add."""

import asyncio
from src.config import load_config
from src.riven_client import RivenClient
from src.rd_client import RealDebridClient
from src.rate_limiter import RateLimiterManager

async def test_retry_flow():
    config = load_config()
    rate_limiter = RateLimiterManager()
    riven = RivenClient(config, rate_limiter)
    
    print("=" * 90)
    print("TEST: Using retry_item to trigger scrape after add")
    print("=" * 90)
    
    # Test with The Bear
    tmdb_id = "244418"
    media_type = "show"
    
    print(f"\n[STEP 1] Add item to Riven")
    print(f"  → Calling: riven.add_item(tmdb_id={tmdb_id}, media_type='{media_type}')")
    
    success = await riven.add_item(
        tmdb_id=tmdb_id,
        media_type=media_type,
    )
    
    if not success:
        print(f"  ✗ Failed to add item")
        return
    
    print(f"  ✓ Item added")
    
    # Now try different scrape trigger methods
    print(f"\n[STEP 2] Get all items to find the newly added one")
    
    try:
        items = await riven.get_problem_items(["Failed", "Unknown"], limit=100)
        print(f"  Found {len(items)} problem items")
        
        # Find The Bear in the list
        bear_item = None
        for item in items:
            if "bear" in item.title.lower():
                bear_item = item
                print(f"  ✓ Found The Bear: ID={item.id}, Title={item.title}")
                break
        
        if bear_item:
            print(f"\n[STEP 3] Trigger retry on the found item")
            print(f"  → Calling: riven.retry_item({bear_item.id})")
            
            retry_success = await riven.retry_item(bear_item.id)
            
            if retry_success:
                print(f"  ✓ Retry successful - this should trigger scrape")
            else:
                print(f"  ✗ Retry failed")
        else:
            print(f"  ! The Bear not found in problem items yet")
            print(f"    Try checking again after a few moments")
    
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    await riven.close()

if __name__ == "__main__":
    asyncio.run(test_retry_flow())
