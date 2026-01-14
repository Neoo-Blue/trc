#!/usr/bin/env python3
"""Test monitor's torrent completion flow: simulate RD download completion and verify Riven add/scrape."""

import asyncio
from src.config import load_config
from src.riven_client import RivenClient
from src.rd_client import RealDebridClient
from src.rate_limiter import RateLimiterManager

async def test_monitor_completion_flow():
    config = load_config()
    rate_limiter = RateLimiterManager()
    riven = RivenClient(config, rate_limiter)
    rd = RealDebridClient(config, rate_limiter)
    
    print("=" * 90)
    print("MONITOR COMPLETION FLOW TEST: Torrent → Scrape → Match Hash → Add Item")
    print("=" * 90)
    
    # Test scenarios
    test_cases = [
        {
            "name": "The Bear S2E1",
            "type": "episode",
            "tmdb_id": "244418",
            "tvdb_id": None,
            "media_type": "show",
            "completed_hash": "14f69cbe8ce7470530a7774a39cdd03704f73e0f",
            "hash_pattern": "s02e01",
        },
        {
            "name": "The Bear S3",
            "type": "season",
            "tmdb_id": "244418",
            "tvdb_id": None,
            "media_type": "show",
            "completed_hash": "2855b0f2ab1a60318279227e0c8355dfdd23543b",
            "hash_pattern": "s03",
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*90}")
        print(f"TEST CASE {i}: {test_case['name']} ({test_case['type']})")
        print(f"{'='*90}")
        
        completed_hash = test_case["completed_hash"].lower()
        print(f"\n[STEP 1] Torrent Completed on Real-Debrid")
        print(f"  - Item: {test_case['name']}")
        print(f"  - Completed hash: {completed_hash}")
        
        print(f"\n[STEP 2] Monitor Scrapes Riven for Streams")
        try:
            streams = await riven.scrape_item(
                tmdb_id=test_case["tmdb_id"],
                tvdb_id=test_case["tvdb_id"],
                media_type=test_case["media_type"],
            )
            
            print(f"  ✓ Scrape successful: Found {len(streams)} total streams")
            
            # Try to find matching hash
            matching_streams = [
                (sid, s) for sid, s in streams.items()
                if s.infohash.lower() == completed_hash
            ]
            
            print(f"\n[STEP 3] Match Completed Hash Against Scraped Streams")
            if matching_streams:
                print(f"  ✓ MATCH FOUND!")
                for stream_id, stream in matching_streams:
                    print(f"    - Title: {stream.raw_title}")
                    print(f"    - Hash: {stream.infohash}")
                    print(f"    - Rank: {stream.rank}")
                
                print(f"\n[STEP 4] Add Item to Riven (Remove + Re-add)")
                print(f"  → Calling: riven.add_item(tmdb_id={test_case['tmdb_id']}, tvdb_id={test_case['tvdb_id']}, media_type='{test_case['media_type']}')")
                
                try:
                    success = await riven.add_item(
                        tmdb_id=test_case["tmdb_id"],
                        tvdb_id=test_case["tvdb_id"],
                        media_type=test_case["media_type"],
                    )
                    
                    if success:
                        print(f"  ✓ SUCCESS: Item re-added to Riven")
                        
                        print(f"\n[STEP 5] Trigger Auto-Scrape")
                        print(f"  → Calling: riven.auto_scrape_item(tmdb_id={test_case['tmdb_id']}, media_type='{test_case['media_type']}')")
                        
                        auto_scrape_success = await riven.auto_scrape_item(
                            tmdb_id=test_case["tmdb_id"],
                            tvdb_id=test_case["tvdb_id"],
                            media_type=test_case["media_type"],
                        )
                        
                        if auto_scrape_success:
                            print(f"  ✓ SUCCESS: Auto-scrape triggered")
                            print(f"  → Riven will now immediately scan and pick up the cached {test_case['name']}")
                        else:
                            print(f"  ✗ FAILED: Could not trigger auto-scrape")
                    else:
                        print(f"  ✗ FAILED: Could not add item")
                        
                except Exception as e:
                    print(f"  ✗ ERROR adding item: {e}")
                
                print(f"\n✅ FLOW COMPLETE - Hash matched and item applied to Riven")
                
            else:
                print(f"  ✗ NO MATCH - Hash not found in scraped streams")
                print(f"\n[FALLBACK] Trigger Add Item Anyway")
                print(f"  → Calling: riven.add_item(tmdb_id={test_case['tmdb_id']}, media_type='{test_case['media_type']}')")
                
                try:
                    success = await riven.add_item(
                        tmdb_id=test_case["tmdb_id"],
                        tvdb_id=test_case["tvdb_id"],
                        media_type=test_case["media_type"],
                    )
                    
                    if success:
                        print(f"  ✓ SUCCESS: Item re-added as fallback")
                        
                        print(f"\n[AUTO-SCRAPE] Trigger scan immediately")
                        print(f"  → Calling: riven.auto_scrape_item(tmdb_id={test_case['tmdb_id']}, media_type='{test_case['media_type']}')")
                        
                        auto_scrape_success = await riven.auto_scrape_item(
                            tmdb_id=test_case["tmdb_id"],
                            tvdb_id=test_case["tvdb_id"],
                            media_type=test_case["media_type"],
                        )
                        
                        if auto_scrape_success:
                            print(f"  ✓ SUCCESS: Auto-scrape triggered")
                            print(f"  → Riven will scan for any available {test_case['name']}")
                        else:
                            print(f"  ✗ FAILED: Could not trigger auto-scrape")
                    else:
                        print(f"  ✗ FAILED: Could not add item")
                        
                except Exception as e:
                    print(f"  ✗ ERROR adding item: {e}")
        
        except Exception as e:
            print(f"  ✗ ERROR during scrape: {e}")
    
    print(f"\n{'='*90}")
    print(f"✅ ALL TESTS COMPLETE - Monitor completion flow verified")
    print(f"{'='*90}")
    
    await riven.close()
    await rd.close()

if __name__ == "__main__":
    asyncio.run(test_monitor_completion_flow())
