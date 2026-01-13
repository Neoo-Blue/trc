#!/usr/bin/env python3
"""Debug Riven scrape endpoint response."""

import asyncio
import httpx
from src.config import Config

async def test():
    config = Config()
    async with httpx.AsyncClient() as client:
        print('Testing /scrape/scrape endpoint...')
        try:
            # Add rate limiter
            from src.rate_limiter import RateLimiterManager
            from src.riven_client import RivenClient
            
            rate_limiter = RateLimiterManager()
            riven = RivenClient(config, rate_limiter)
            
            # Test with different movies
            test_items = [
                ("Wakanda Forever", "505642", "movie"),
                ("The Matrix", "603", "movie"),
                ("Breaking Bad", "1396", "tv"),
            ]
            
            for name, tmdb_id, media_type in test_items:
                print(f"\n  {name} (TMDB: {tmdb_id}, Type: {media_type})")
                try:
                    streams = await riven.scrape_item(tmdb_id=tmdb_id, media_type=media_type)
                    if streams:
                        print(f"    ✓ Found {len(streams)} streams")
                        for i, (key, stream) in enumerate(list(streams.items())[:3]):
                            print(f"      - {stream.raw_title[:60]}")
                    else:
                        print(f"    ! No streams found")
                except Exception as e:
                    print(f"    ✗ Error: {str(e)[:100]}")
        except Exception as e:
            print(f'Error: {e}')

asyncio.run(test())
