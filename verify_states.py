#!/usr/bin/env python3
"""Verify that TRC only processes failed/unknown state items."""

import asyncio
from src.config import load_config
from src.riven_client import RivenClient
from src.rate_limiter import RateLimiterManager

async def verify_states():
    config = load_config()
    rate_limiter = RateLimiterManager()
    riven = RivenClient(config, rate_limiter)
    
    print("\n" + "=" * 70)
    print("VERIFICATION: TRC processes ONLY failed/unknown state items")
    print("=" * 70)
    
    print(f"\n[Config] Problem states configured: {config.problem_states}")
    
    # Get problem items
    print(f"\n[API Call] Requesting items with states: {config.problem_states}")
    items = await riven.get_problem_items(config.problem_states, limit=200)
    
    print(f"[Result] Found {len(items)} items")
    
    if items:
        # Verify all returned items are in the problem states
        invalid_items = [item for item in items if item.state not in config.problem_states]
        
        if invalid_items:
            print(f"\n⚠️ WARNING: Found {len(invalid_items)} items NOT in problem states:")
            for item in invalid_items[:5]:
                print(f"   - {item.display_name}: state={item.state}")
            if len(invalid_items) > 5:
                print(f"   ... and {len(invalid_items) - 5} more")
        else:
            print(f"\n✅ VERIFIED: All {len(items)} returned items are in problem states")
        
        # Show distribution
        state_counts = {}
        for item in items:
            state_counts[item.state] = state_counts.get(item.state, 0) + 1
        
        print(f"\n[Distribution]")
        for state, count in sorted(state_counts.items()):
            print(f"   {state}: {count} items")
    else:
        print("\n✅ VERIFIED: No items found (either all resolved or no problems)")
    
    print("\n" + "=" * 70)
    print("✅ Verification complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(verify_states())
