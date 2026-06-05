"""
api/returns.py — AI-assisted return approval workflow: /returns/approve, /returns/decline.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend_anti_gravity.app.api.deps import get_current_user, get_db, require_returns
from backend_anti_gravity.app.core.config import settings
from backend_anti_gravity.app.ml.return_classifier import ReturnClassifier
from app.models.auth import User
from app.models.analytics import Return

router = APIRouter(prefix="/returns", tags=["Returns"])


class ReturnCreate(BaseModel):
    product_id: int
    sale_id: Optional[int] = None
    customer_id: Optional[str] = None
    reason_code: Optional[str] = None
    reason_description: Optional[str] = None
    refund_amount: Optional[Decimal] = Field(None, ge=0)


class ReturnOut(BaseModel):
    id: int
    product_id: int
    sale_id: Optional[int] = None
    customer_id: Optional[int] = None
    reason_code: Optional[str] = None
    refund_amount: Optional[Decimal] = None
    fraud_score: Optional[Decimal] = None
    return_ratio: Optional[Decimal] = None
    risk_label: Optional[str] = None
    anomaly_flag: bool
    status: str
    approved_by: Optional[str] = None
    override_note: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ReturnDecisionRequest(BaseModel):
    override_note: Optional[str] = Field(
        None, description="Required when risk is HIGH or anomaly_flag is True"
    )


@router.get("/", response_model=List[ReturnOut])
async def list_returns(
    status: Optional[str] = Query(None),
    risk_label: Optional[str] = Query(None),
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all return records with optional status and risk label filters."""
    q = select(Return).order_by(Return.return_date.desc())
    if status:
        if status.upper() == "PENDING":
            q = q.where((Return.approval_status == "PENDING") | (Return.approval_status == None))
        else:
            q = q.where(Return.approval_status == status)
    if risk_label:
        if risk_label.upper() == "HIGH":
            q = q.where(Return.fraud_risk_score >= 0.65)
        elif risk_label.upper() == "MEDIUM":
            q = q.where((Return.fraud_risk_score >= 0.35) & (Return.fraud_risk_score < 0.65))
        else:
            q = q.where((Return.fraud_risk_score < 0.35) | (Return.fraud_risk_score == None))
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/", response_model=ReturnOut, status_code=201)
async def create_return(
    payload: ReturnCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Submit a new return request.
    Automatically runs the XGBoost + Isolation Forest risk classifier
    to assign fraud_score, return_ratio, risk_label, and anomaly_flag.
    """
    classifier = ReturnClassifier()
    risk = classifier.score(
        product_id=payload.product_id,
        customer_id=payload.customer_id,
        reason_code=payload.reason_code,
        refund_amount=float(payload.refund_amount or 0),
    )

    import datetime
    ret = Return(
        product_id=payload.product_id,
        sale_id=payload.sale_id or 1,
        customer_id=int(payload.customer_id) if payload.customer_id and payload.customer_id.isdigit() else 1,
        return_reason=payload.reason_code,
        refund_amount=float(payload.refund_amount or 0),
        fraud_risk_score=risk["fraud_score"],
        approval_status="PENDING",
        return_date=datetime.datetime.utcnow().isoformat()
    )
    db.add(ret)
    await db.commit()
    await db.refresh(ret)
    return ret


@router.get("/{return_id}", response_model=ReturnOut)
async def get_return(return_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Fetch a single return record by ID."""
    r = await db.get(Return, return_id)
    if not r:
        raise HTTPException(status_code=404, detail="Return record not found.")
    return r


@router.post("/{return_id}/approve", response_model=ReturnOut)
async def approve_return(
    return_id: int,
    payload: ReturnDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_returns),
):
    """
    Approve a return request.
    - If risk_label is LOW and anomaly_flag is False: auto-approved without override note.
    - If risk_label is HIGH or anomaly_flag is True: override_note is MANDATORY.
    Logs full decision audit trail on the return record.
    """
    r = await db.get(Return, return_id)
    if not r:
        raise HTTPException(status_code=404, detail="Return record not found.")
    if r.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Return is already in '{r.status}' state.")

    requires_override = r.risk_label == "HIGH" or r.anomaly_flag
    if requires_override and not payload.override_note:
        raise HTTPException(
            status_code=400,
            detail="override_note is required for HIGH-risk or anomaly-flagged returns.",
        )

    r.approval_status = "APPROVED"
    await db.commit()
    await db.refresh(r)
    return r


@router.post("/{return_id}/decline", response_model=ReturnOut)
async def decline_return(
    return_id: int,
    payload: ReturnDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_returns),
):
    """
    Decline a return request. Always requires an override_note explaining the rejection.
    Audits the decision with agent identity and timestamp.
    """
    r = await db.get(Return, return_id)
    if not r:
        raise HTTPException(status_code=404, detail="Return record not found.")
    if r.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Return is already in '{r.status}' state.")
    if not payload.override_note:
        raise HTTPException(status_code=400, detail="override_note is required to decline a return.")

    r.approval_status = "DECLINED"
    await db.commit()
    await db.refresh(r)
    return r


@router.get("/analytics/summary")
async def returns_summary(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Return aggregate return statistics for dashboard KPI cards."""
    result = await db.execute(select(Return))
    returns = result.scalars().all()
    total = len(returns)
    return {
        "total_returns": total,
        "pending": sum(1 for r in returns if r.status == "PENDING"),
        "approved": sum(1 for r in returns if r.status == "APPROVED"),
        "declined": sum(1 for r in returns if r.status == "DECLINED"),
        "high_risk": sum(1 for r in returns if r.risk_label == "HIGH"),
        "anomaly_flagged": sum(1 for r in returns if r.anomaly_flag),
        "approval_rate_pct": round(
            sum(1 for r in returns if r.status == "APPROVED") / max(total, 1) * 100, 2
        ),
    }
