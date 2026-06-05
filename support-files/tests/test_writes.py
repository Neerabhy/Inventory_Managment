import asyncio
import os
import sys

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "api-backend")
sys.path.insert(0, BACKEND_DIR)

from app.core.database import engine
from app.models.analytics import Return, ReturnHistory
from app.models.logistics import InboundOrder
from app.models.procurement import PurchaseOrder

async def test_writes():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get a pending return
        res = await db.execute(select(Return).where(Return.approval_status == 'Manual Review').limit(1))
        r = res.scalar_one_or_none()
        
        if r:
            print(f"Found pending return {r.id}")
        else:
            print("No pending returns found!")

asyncio.run(test_writes())
