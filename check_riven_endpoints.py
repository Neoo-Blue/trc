#!/usr/bin/env python3
"""Check available Riven endpoints for scanning/scraping items."""

import asyncio
import httpx
from src.config import load_config

async def check_endpoints():
    config = load_config()
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            print("Fetching OpenAPI spec from Riven...")
            response = await client.get(f"{config.riven_url}/openapi.json")
            data = response.json()
            paths = data.get("paths", {})
            
            print("\nAll available endpoints:")
            print("=" * 80)
            
            scan_related = {}
            for path in sorted(paths.keys()):
                methods = paths[path]
                for method in methods:
                    if isinstance(methods[method], dict):
                        if any(x in path.lower() for x in ["scan", "scrape", "process", "refresh", "retry"]):
                            scan_related[path] = {
                                "methods": list(methods.keys()),
                                "method_details": methods
                            }
                            break
            
            print("\nSCAN/SCRAPE/PROCESS/REFRESH RELATED ENDPOINTS:")
            print("=" * 80)
            for path, details in scan_related.items():
                print(f"\n{path}")
                for method in details["methods"]:
                    if isinstance(details["method_details"][method], dict):
                        op = details["method_details"][method]
                        summary = op.get("summary", "No description")
                        print(f"  {method.upper()}: {summary}")
            
            if not scan_related:
                print("No scan/scrape related endpoints found.")
                print("\nTrying to find any POST endpoints that might trigger actions:")
                for path in sorted(paths.keys()):
                    methods = paths[path]
                    if "post" in methods or "put" in methods:
                        print(f"  {path}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_endpoints())
