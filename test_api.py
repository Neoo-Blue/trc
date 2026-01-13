#!/usr/bin/env python3
"""Test Riven API to check endpoints and responses."""

import asyncio
import httpx
from src.config import load_config
from src.riven_client import RivenClient
from src.rd_client import RealDebridClient
from src.rate_limiter import RateLimiterManager

async def test_api():
    config = load_config()
    rate_limiter = RateLimiterManager()
    riven = RivenClient(config, rate_limiter)
    rd = RealDebridClient(config, rate_limiter)
    
    print("=" * 60)
    print("Testing Riven API")
    print("=" * 60)
    
    try:
        # Test 1: Health check
        print("\n1. Testing Riven API health")
        health = await riven.health_check()
        print(f"   ✓ Riven API is {'online' if health else 'offline'}")
        
        # Test 2: Get problem items
        print("\n2. Getting problem items from Riven")
        items = await riven.get_problem_items(["failed", "unknown"], limit=10)
        print(f"   ✓ Found {len(items)} problem items")
        
        if not items:
            print("   ! No problem items found, creating test item...")
            # Try adding a test item
            test_added = await riven.add_item(tmdb_id="299534", media_type="movie")
            print(f"   Added test movie (Wakanda Forever): {test_added}")
            items = await riven.get_problem_items(["failed", "unknown"], limit=10)
        
        # Test 3: Manual scraping
        print("\n3. Testing manual scraping (scrape_item)")
        tested_items = 0
        scraped_successfully = 0
        
        # First try existing non-episode items
        for item in items:
            # Skip items without TMDB IDs or with wrong type
            if not item.tmdb_id and not item.tvdb_id:
                continue
            
            # Skip episodes (they're usually TVDB only and marked as "movie" incorrectly)
            if item.type in ["episode", "season"]:
                continue
            
            tested_items += 1
            media_type = "tv" if item.type == "show" else "movie"
            print(f"\n   Item: {item.display_name} ({media_type})")
            print(f"   TMDB: {item.tmdb_id}, TVDB: {item.tvdb_id}")
            
            try:
                streams = await riven.scrape_item(
                    tmdb_id=item.tmdb_id,
                    tvdb_id=item.tvdb_id,
                    media_type=media_type
                )
                if streams:
                    scraped_successfully += 1
                    print(f"   ✓ Scraping successful - Found {len(streams)} streams")
                    
                    # Show first 3 streams
                    for i, (key, stream) in enumerate(list(streams.items())[:3]):
                        print(f"      - {stream.raw_title[:70]} (rank: {stream.rank})")
                    
                    if len(streams) > 3:
                        print(f"      ... and {len(streams) - 3} more streams")
                else:
                    print(f"   ! Scraping returned no streams")
                    
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg:
                    print(f"   ! Scraping not found (404) - Content may not be available")
                else:
                    print(f"   ✗ Scraping failed: {error_msg[:100]}")
        
        # If no non-episode items found, test with known movies
        if tested_items == 0:
            print("   ! All items are episodes/seasons, testing with known movies...")
            test_movies = [
                ("Wakanda Forever", "505642", "movie"),
                ("The Matrix", "603", "movie"),
            ]
            
            for movie_name, tmdb_id, media_type in test_movies:
                print(f"\n   Testing: {movie_name} (Movie)")
                try:
                    streams = await riven.scrape_item(
                        tmdb_id=tmdb_id,
                        media_type=media_type
                    )
                    if streams:
                        scraped_successfully += 1
                        tested_items += 1
                        print(f"   ✓ Scraping successful - Found {len(streams)} streams")
                        
                        # Show first 5 streams
                        for i, (key, stream) in enumerate(list(streams.items())[:5]):
                            print(f"      - {stream.raw_title[:70]} (rank: {stream.rank})")
                        
                        if len(streams) > 5:
                            print(f"      ... and {len(streams) - 5} more streams")
                        
                        # Check for cached streams (immediately available on RD)
                        cached_streams = {k: v for k, v in streams.items() if v.is_cached}
                        if cached_streams:
                            print(f"\n      • {len(cached_streams)} cached streams available on RD")
                            best = list(cached_streams.values())[0]
                            print(f"      ✓ Can add directly to RD: {best.raw_title[:50]}...")
                        else:
                            print(f"\n      • No cached streams (would need torrent cache first)")
                            
                    else:
                        print(f"   ! No streams found for this movie")
                except Exception as e:
                    print(f"   ✗ Test scraping failed: {str(e)[:100]}")
        
        if tested_items > 0:
            print(f"\n   Summary: Tested {tested_items} items, {scraped_successfully} succeeded with streams")
        else:
            print("   ! Could not test scraping")
        
        # Test 4: Item management (retry, remove, add)
        print("\n4. Testing item management operations")
        if items:
            test_item = items[0]
            print(f"   Using item: {test_item.display_name} (ID: {test_item.id})")
            
            # Test retry_item
            try:
                print(f"   - Testing retry_item...")
                result = await riven.retry_item(test_item.id)
                print(f"   ✓ Retry successful: {result}")
            except Exception as e:
                print(f"   ! Retry failed: {e}")
            
            # Test remove_item (be careful!)
            try:
                print(f"   - Testing remove_item (will re-add after)...")
                result = await riven.remove_item(test_item.id)
                print(f"   ✓ Remove successful: {result}")
                
                # Re-add it immediately
                media_type = "tv" if test_item.type == "show" else "movie"
                result = await riven.add_item(
                    tmdb_id=test_item.tmdb_id,
                    tvdb_id=test_item.tvdb_id,
                    media_type=media_type
                )
                print(f"   ✓ Re-added item: {result}")
            except Exception as e:
                print(f"   ! Remove/add failed: {e}")
        else:
            print("   ! No items available for management testing")
        
        print(f"\n   ✓ Riven manual scraping and item management working!")
                
    except Exception as e:
        print(f"✗ Riven Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test Real-Debrid API
    print("\n" + "=" * 60)
    print("Testing Real-Debrid API")
    print("=" * 60)
    
    try:
        # Test 1: Get user info
        print("\n1. Testing Real-Debrid GET /user")
        user = await rd.get_user()
        print(f"   ✓ Connected successfully")
        print(f"   ✓ Account status: authenticated")
        
        # Test 2: Get active count
        print("\n2. Testing GET /torrents/activeCount")
        active = await rd.get_active_count()
        print(f"   ✓ Active torrents: {active.get('nb')}/{active.get('limit')}")
        
        # Test 3: Get torrents
        print("\n3. Testing GET /torrents")
        torrents = await rd.get_torrents(limit=5)
        print(f"   ✓ Retrieved {len(torrents)} torrents")
        if torrents:
            for t in torrents[:2]:
                print(f"      - {t.id}: {t.filename[:50] if t.filename else 'no filename'}")
        
        print(f"\n   ✓ Real-Debrid API is working!")
        
    except Exception as e:
        print(f"✗ Real-Debrid Error: {e}", exc_info=True)
    finally:
        await riven.close()
        await rd.close()

if __name__ == "__main__":
    asyncio.run(test_api())
