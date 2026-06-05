import asyncio
import aiohttp

async def test():
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/v1/logistics/shipments?direction=INBOUND") as r:
            print(r.status, await r.text())

asyncio.run(test())
