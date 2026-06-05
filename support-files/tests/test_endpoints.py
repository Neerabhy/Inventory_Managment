import asyncio
import aiohttp

async def test():
    async with aiohttp.ClientSession() as session:
        # Test returns history
        async with session.get("http://localhost:8000/api/v1/returns/history", headers={"Authorization": "Bearer admin"}) as r:
            print("Returns History:", r.status, await r.text())
            
        # Test logistics shipments
        async with session.get("http://localhost:8000/api/v1/logistics/shipments", headers={"Authorization": "Bearer admin"}) as r:
            text = await r.text()
            print("Logistics:", r.status, text[:200])

asyncio.run(test())
