#!/usr/bin/env python3
"""Demonstrate monitor logging with seeder information."""

from src.rd_client import RDTorrent

def test_monitor_logging_with_seeders():
    """Show how monitor will log torrents with seeder information."""
    
    print("=" * 90)
    print("MONITOR LOGGING EXAMPLES WITH SEEDER INFORMATION")
    print("=" * 90)
    
    # Example torrents with different states
    test_cases = [
        {
            "name": "Active with good seeders",
            "data": {
                "id": "ABC123",
                "filename": "Movie.2025.1080p.WEB-DL",
                "hash": "abc123",
                "status": "downloading",
                "progress": 45,
                "bytes": 5000000000,
                "seeders": 15,
            }
        },
        {
            "name": "Active with few seeders",
            "data": {
                "id": "DEF456",
                "filename": "Show.S01E01.1080p",
                "hash": "def456",
                "status": "downloading",
                "progress": 20,
                "bytes": 3000000000,
                "seeders": 2,
            }
        },
        {
            "name": "Dead (0 seeders)",
            "data": {
                "id": "GHI789",
                "filename": "Old.Series.S01.Complete",
                "hash": "ghi789",
                "status": "downloading",
                "progress": 5,
                "bytes": 10000000000,
                "seeders": 0,
            }
        },
        {
            "name": "Unknown seeders",
            "data": {
                "id": "JKL012",
                "filename": "Another.Movie.2024",
                "hash": "jkl012",
                "status": "downloading",
                "progress": 75,
                "bytes": 4000000000,
                "seeders": None,
            }
        },
        {
            "name": "Completed",
            "data": {
                "id": "MNO345",
                "filename": "Cached.Content.Already.Here",
                "hash": "mno345",
                "status": "downloaded",
                "progress": 100,
                "bytes": 6000000000,
                "seeders": None,
            }
        },
    ]
    
    for test_case in test_cases:
        torrent = RDTorrent.from_dict(test_case["data"])
        
        print(f"\n[{test_case['name']}]")
        print("-" * 90)
        
        # Show what would be logged
        if torrent.is_complete:
            print(f"✓ Torrent completed: {torrent.filename[:60]}")
        elif torrent.is_stalled:
            print(f"✗ Torrent dead ({torrent.seeders_status}): {torrent.filename[:60]}")
            print(f"  → Would be deleted and refilled automatically")
        elif torrent.is_active:
            if torrent.seeders is not None:
                print(f"↓ Downloading ({torrent.progress}%, Seeders: {torrent.seeders_status}): {torrent.filename[:60]}")
            else:
                print(f"↓ Downloading ({torrent.progress}%): {torrent.filename[:60]}")
        
        # Show the object properties
        print(f"  Properties:")
        print(f"    • Status: {torrent.status}")
        print(f"    • Progress: {torrent.progress}%")
        print(f"    • Seeders: {torrent.seeders if torrent.seeders is not None else 'Unknown'}")
        print(f"    • Seeder status: {torrent.seeders_status}")
        print(f"    • Is active: {torrent.is_active}")
        print(f"    • Is stalled: {torrent.is_stalled}")
        print(f"    • Is complete: {torrent.is_complete}")
    
    print(f"\n" + "=" * 90)
    print("LOG OUTPUT ENHANCEMENTS")
    print("=" * 90)
    print("""
With seeder information, the monitor will provide much better diagnostics:

Before (current):
  ↓ Downloading (45%, 2.5m): Movie.2025.1080p.WEB-DL
  ⚠ Torrent stalled after 30.0m (progress=0%): Old.Series.S01.Complete

After (with seeders):
  ↓ Downloading (45%, 2.5m | Seeders: high (15 seeders)): Movie.2025.1080p.WEB-DL
  ✗ Torrent dead (0 seeders): Old.Series.S01.Complete

Benefits:
  • Know immediately if a torrent has healthy seeders
  • Dead torrents (0 seeders) are removed immediately instead of waiting
  • Users can see at a glance why a torrent might be slow
  • Reduced bandwidth waste on torrents with no peer sources
    """)

if __name__ == "__main__":
    test_monitor_logging_with_seeders()
