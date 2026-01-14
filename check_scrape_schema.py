#!/usr/bin/env python3
"""Check AutoScrapeRequestPayload schema."""

import asyncio
import httpx
import json
from src.config import load_config

async def check_schema():
    config = load_config()
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(f"{config.riven_url}/openapi.json")
            data = response.json()
            
            # Find the schema
            schemas = data.get("components", {}).get("schemas", {})
            
            if "AutoScrapeRequestPayload" in schemas:
                schema = schemas["AutoScrapeRequestPayload"]
                print("AutoScrapeRequestPayload Schema:")
                print(json.dumps(schema, indent=2))
            else:
                print("AutoScrapeRequestPayload not found in schemas")
                print("\nAvailable schemas containing 'scrape':")
                for key in schemas:
                    if "scrape" in key.lower():
                        print(f"  - {key}")
        
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_schema())
