#!/usr/bin/env python3
"""Test Real-Debrid API to check available seeder info in torrent data."""

import asyncio
import json
from src.config import load_config
from src.rd_client import RealDebridClient
from src.rate_limiter import RateLimiterManager

async def test_rd_seeder_info():
    config = load_config()
    rate_limiter = RateLimiterManager()
    rd = RealDebridClient(config, rate_limiter)
    
    print("=" * 90)
    print("TESTING REAL-DEBRID API: Seeder Information Availability")
    print("=" * 90)
    
    try:
        # Get user info first
        user = await rd.get_user()
        print(f"\n✓ Connected to RD account: {user.get('username', 'Unknown')}")
        
        # Get torrents list
        print(f"\n[TEST 1] Getting torrents list with /torrents?limit=100")
        print("-" * 90)
        
        torrents = await rd.get_torrents(limit=100)
        print(f"✓ Retrieved {len(torrents)} torrents")
        
        if torrents:
            # Show the first few torrents with their fields
            print(f"\nFirst 3 torrents from list:")
            for i, torrent in enumerate(torrents[:3], 1):
                print(f"\n  [{i}] {torrent.filename[:60]}")
                print(f"      ID: {torrent.id}")
                print(f"      Status: {torrent.status}")
                print(f"      Progress: {torrent.progress}%")
                print(f"      Seeders: {torrent.seeders if torrent.seeders is not None else 'NOT PROVIDED'}")
                print(f"      Hash: {torrent.hash}")
        
        # Now test individual torrent info endpoint
        print(f"\n[TEST 2] Getting individual torrent info with /torrents/info/{{id}}")
        print("-" * 90)
        
        if torrents:
            test_torrent = torrents[0]
            print(f"Testing with torrent: {test_torrent.id}")
            
            try:
                info = await rd.get_torrent_info(test_torrent.id)
                print(f"\n✓ Retrieved detailed info for torrent {test_torrent.id}")
                print(f"  Filename: {info.filename[:60]}")
                print(f"  Status: {info.status}")
                print(f"  Progress: {info.progress}%")
                print(f"  Seeders: {info.seeders if info.seeders is not None else 'NOT PROVIDED'}")
                print(f"  Bytes: {info.bytes}")
                print(f"  Added: {info.added if info.added else 'Not specified'}")
                
                # Show raw response to see all available fields
                print(f"\n[TEST 3] Raw API Response Structure")
                print("-" * 90)
                
                # Make a raw request to see full response
                raw_response = await rd._request("GET", f"/torrents/info/{test_torrent.id}")
                print(f"\nFull API response for {test_torrent.id}:")
                print(json.dumps(raw_response, indent=2, default=str))
                
            except Exception as e:
                print(f"✗ Error getting torrent info: {e}")
        else:
            print("No torrents available to test detailed info")
        
        # Check if seeders would be useful for stalled detection
        print(f"\n[ANALYSIS] Seeders Field Usage")
        print("-" * 90)
        
        if torrents:
            with_seeders = [t for t in torrents if t.seeders is not None]
            without_seeders = [t for t in torrents if t.seeders is None]
            
            print(f"Torrents with seeder info: {len(with_seeders)}")
            print(f"Torrents without seeder info: {len(without_seeders)}")
            
            if with_seeders:
                print(f"\nSeeder counts (from torrents with data):")
                seeder_counts = [t.seeders for t in with_seeders if t.seeders is not None]
                if seeder_counts:
                    print(f"  Min: {min(seeder_counts)}")
                    print(f"  Max: {max(seeder_counts)}")
                    print(f"  Avg: {sum(seeder_counts) / len(seeder_counts):.1f}")
                    
                    # Show distribution
                    zero_seeders = len([s for s in seeder_counts if s == 0])
                    low_seeders = len([s for s in seeder_counts if 0 < s < 5])
                    medium_seeders = len([s for s in seeder_counts if 5 <= s < 20])
                    high_seeders = len([s for s in seeder_counts if s >= 20])
                    
                    print(f"\nSeeder distribution:")
                    print(f"  0 seeders (dead): {zero_seeders}")
                    print(f"  1-4 seeders (low): {low_seeders}")
                    print(f"  5-19 seeders (medium): {medium_seeders}")
                    print(f"  20+ seeders (high): {high_seeders}")
        
        print(f"\n" + "=" * 90)
        print("✓ TEST COMPLETE")
        print("=" * 90)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await rd.close()

if __name__ == "__main__":
    asyncio.run(test_rd_seeder_info())
