#!/usr/bin/env python3
"""Test Riven scrape endpoint to determine correct format."""

import asyncio
import httpx
from src.config import Config

async def test():
    config = Config()
    async with httpx.AsyncClient() as client:
        # Try POST with JSON body
        print('Testing POST with JSON body...')
        try:
            response = await client.post(
                f'{config.riven_url}/api/v1/scrape',
                json={'tmdb_id': '505642', 'media_type': 'movie'},
                params={'api_key': config.riven_api_key},
                timeout=30
            )
            print(f'Status: {response.status_code}')
            if response.status_code == 200:
                data = response.json()
                print(f'Success! Streams found: {len(data.get("streams", {}))}')
            else:
                print(f'Response: {response.text[:200]}')
        except Exception as e:
            print(f'Error: {e}')
            
        # Try GET with query params
        print()
        print('Testing GET with query params...')
        try:
            response = await client.get(
                f'{config.riven_url}/api/v1/scrape',
                params={'tmdb_id': '505642', 'media_type': 'movie', 'api_key': config.riven_api_key},
                timeout=30
            )
            print(f'Status: {response.status_code}')
            if response.status_code == 200:
                data = response.json()
                print(f'Success! Streams found: {len(data.get("streams", {}))}')
            else:
                print(f'Response: {response.text[:200]}')
        except Exception as e:
            print(f'Error: {e}')

asyncio.run(test())
