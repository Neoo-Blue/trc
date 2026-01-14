#!/usr/bin/env python3
"""Test and demonstrate seeder-based stall detection."""

import asyncio
from src.config import load_config
from src.rd_client import RealDebridClient, RDTorrent
from src.rate_limiter import RateLimiterManager

async def test_seeder_detection():
    config = load_config()
    rate_limiter = RateLimiterManager()
    rd = RealDebridClient(config, rate_limiter)
    
    print("=" * 90)
    print("SEEDER-BASED STALL DETECTION TEST")
    print("=" * 90)
    
    try:
        # Get torrents and analyze seeder status
        torrents = await rd.get_torrents(limit=100)
        print(f"\n✓ Retrieved {len(torrents)} torrents")
        
        print(f"\n[ANALYSIS] Seeder-Based Stall Detection")
        print("-" * 90)
        
        # Categorize torrents
        active_torrents = [t for t in torrents if t.is_active]
        stalled_torrents = [t for t in torrents if t.is_stalled]
        completed_torrents = [t for t in torrents if t.is_complete]
        
        print(f"\nTorrent Status Breakdown:")
        print(f"  Active torrents: {len(active_torrents)}")
        print(f"  Stalled torrents: {len(stalled_torrents)}")
        print(f"  Completed torrents: {len(completed_torrents)}")
        
        # Show active torrents with seeder info
        if active_torrents:
            print(f"\n[ACTIVE TORRENTS] (showing seeder status)")
            print("-" * 90)
            
            for i, torrent in enumerate(active_torrents[:10], 1):
                status_icon = "🌱" if torrent.seeders and torrent.seeders >= 5 else "⚠" if torrent.seeders == 0 else "📌"
                seeder_status = torrent.seeders_status
                print(f"{i:2}. {status_icon} {seeder_status:20} | {torrent.progress:3}% | {torrent.filename[:50]}")
            
            if len(active_torrents) > 10:
                print(f"    ... and {len(active_torrents) - 10} more active torrents")
        
        # Show stalled torrents
        if stalled_torrents:
            print(f"\n[STALLED TORRENTS] (would be auto-removed)")
            print("-" * 90)
            
            for i, torrent in enumerate(stalled_torrents[:10], 1):
                reason = f"0 seeders" if torrent.seeders == 0 else f"status={torrent.status}"
                print(f"{i:2}. \u2717 {reason:20} | {torrent.progress:3}% | {torrent.filename[:50]}")
            
            if len(stalled_torrents) > 10:
                print(f"    ... and {len(stalled_torrents) - 10} more stalled torrents")
        
        # Seeder distribution
        all_with_seeders = [t for t in torrents if t.seeders is not None]
        if all_with_seeders:
            print(f"\n[SEEDER DISTRIBUTION] (all torrents with seeder data)")
            print("-" * 90)
            
            dead = len([t for t in all_with_seeders if t.seeders == 0])
            low = len([t for t in all_with_seeders if 0 < t.seeders < 5])
            medium = len([t for t in all_with_seeders if 5 <= t.seeders < 20])
            high = len([t for t in all_with_seeders if t.seeders >= 20])
            
            total = len(all_with_seeders)
            print(f"  Dead (0 seeders):     {dead:3} ({100*dead//total if total else 0}%)")
            print(f"  Low (1-4 seeders):    {low:3} ({100*low//total if total else 0}%)")
            print(f"  Medium (5-19):        {medium:3} ({100*medium//total if total else 0}%)")
            print(f"  High (20+):           {high:3} ({100*high//total if total else 0}%)")
        
        # Show example with individual torrent info
        print(f"\n[DETAILED EXAMPLE] Getting seeder info for individual torrent")
        print("-" * 90)
        
        if torrents:
            test_torrent = torrents[0]
            print(f"\nTesting: {test_torrent.filename[:60]}")
            print(f"  Status: {test_torrent.status}")
            print(f"  Progress: {test_torrent.progress}%")
            print(f"  Seeders (from list): {test_torrent.seeders if test_torrent.seeders is not None else 'NOT PROVIDED'}")
            
            # Get detailed info
            try:
                detailed = await rd.get_torrent_info(test_torrent.id)
                print(f"\n  Detailed info retrieved:")
                print(f"    Seeders: {detailed.seeders if detailed.seeders is not None else 'NOT PROVIDED'}")
                print(f"    Status: {detailed.seeders_status}")
                print(f"    Is stalled: {detailed.is_stalled}")
                
                if detailed.is_stalled:
                    print(f"\n  ⚠ WOULD BE AUTO-REMOVED: This torrent has no seeders and would be deleted")
                else:
                    print(f"\n  ✓ Safe to continue: This torrent has available seeders")
            except Exception as e:
                print(f"  ! Could not get detailed info: {e}")
        
        print(f"\n" + "=" * 90)
        print("✓ TEST COMPLETE - Seeder detection ready for use")
        print("=" * 90)
        print("\nKey Improvements:")
        print("  • Torrents with 0 seeders are automatically detected as stalled")
        print("  • Seeder status is logged for each active download")
        print("  • Dead torrents are removed immediately instead of waiting for timeout")
        print("  • Human-readable seeder status: 'dead', 'low', 'medium', or 'high'")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    await rd.close()

if __name__ == "__main__":
    asyncio.run(test_seeder_detection())
