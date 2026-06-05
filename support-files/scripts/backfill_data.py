import asyncio
import os
import sys

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

async def backfill():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Backfill Return History
        res = await db.execute(select(Return).where(Return.approval_status.in_(["Approved", "Auto Approved", "Rejected"])))
        returns = res.scalars().all()
        for r in returns:
            action = "APPROVED" if r.approval_status in ["Approved", "Auto Approved"] else "DECLINED"
            hist = ReturnHistory(
                return_id=r.id,
                action=action,
                approved_by="system_migration",
                override_note="Migrated from old status",
                created_at=r.return_date
            )
            db.add(hist)
            
        # Backfill Inbound Orders
        res_po = await db.execute(select(PurchaseOrder))
        pos = res_po.scalars().all()
        for po in pos:
            io = InboundOrder(
                product_id=po.product_id,
                supplier_id=po.supplier_id,
                quantity=po.quantity,
                status=po.status,
                created_at=po.order_date
            )
            db.add(io)
            
        await db.commit()
        print(f"Backfilled {len(returns)} returns and {len(pos)} inbound orders.")

if __name__ == "__main__":
    asyncio.run(backfill())
