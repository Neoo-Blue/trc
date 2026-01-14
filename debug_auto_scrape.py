#!/usr/bin/env python3
"""Debug auto-scrape endpoint to determine correct format."""

import asyncio
import httpx
from src.config import load_config

async def debug_auto_scrape():
    config = load_config()
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            print("Checking auto_scrape endpoint details...")
            response = await client.get(f"{config.riven_url}/openapi.json")
            data = response.json()
            
            auto_scrape_spec = data["paths"]["/api/v1/scrape/auto"]["post"]
            
            print("\nAuto-Scrape Endpoint Details:")
            print(f"Summary: {auto_scrape_spec.get('summary', 'N/A')}")
            print(f"Description: {auto_scrape_spec.get('description', 'N/A')}")
            
            if "requestBody" in auto_scrape_spec:
                req_body = auto_scrape_spec["requestBody"]
                print(f"\nRequest Body:")
                print(f"  Required: {req_body.get('required', False)}")
                content = req_body.get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    print(f"  Schema: {schema}")
            
            if "parameters" in auto_scrape_spec:
                print(f"\nParameters:")
                for param in auto_scrape_spec["parameters"]:
                    print(f"  {param['name']}: {param.get('schema', {})}")
        
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_auto_scrape())
