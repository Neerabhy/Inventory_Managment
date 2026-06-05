"""
api/returns.py — AI-assisted return approval workflow: /returns/approve, /returns/decline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_current_user, get_db, require_returns
from ..core.config import settings
from ..models.analytics import Return, ReturnHistory, Sale
from ..models.auth import User
from ..models.inventory import Product
from ..models.predictions import ReturnRiskPrediction
from ..services.prediction_service import save_return_risk_prediction, score_return_risk


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
    reverse_logistics_cost: Optional[float] = None
    gross_margin_lost: float = 0
    estimated_return_loss: float = 0
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


def _return_out(ret: Return, product: Optional[Product] = None) -> ReturnOut:
    unit_margin = 0.0
    if product:
        unit_margin = max(float(product.selling_price or 0) - float(product.manufacturing_cost or 0), 0.0)
    reverse_cost = float(ret.reverse_logistics_cost or 0)
    return ReturnOut(
        id=ret.id,
        product_id=ret.product_id,
        sale_id=ret.sale_id,
        customer_id=ret.customer_id,
        reason_code=ret.return_reason,
        refund_amount=ret.refund_amount,
        reverse_logistics_cost=reverse_cost,
        gross_margin_lost=round(unit_margin, 2),
        estimated_return_loss=round(unit_margin + reverse_cost, 2),
        fraud_score=ret.fraud_risk_score,
        return_ratio=ret.return_ratio,
        risk_label=ret.risk_label,
        anomaly_flag=ret.anomaly_flag,
        status=ret.status,
        approved_by=ret.approved_by,
        override_note=ret.override_note,
        decided_at=ret.decided_at,
        created_at=datetime.fromisoformat(ret.created_at),
    )


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
            q = q.where((Return.approval_status == "Manual Review") | (Return.approval_status == None))
        elif status.upper() == "APPROVED":
            q = q.where(Return.approval_status.in_(["Approved", "Auto Approved"]))
        elif status.upper() == "DECLINED":
            q = q.where(Return.approval_status == "Rejected")
        else:
            q = q.where(Return.approval_status == status)
    if risk_label:
        if risk_label.upper() == "HIGH":
            q = q.where(Return.fraud_risk_score >= 0.65)
        elif risk_label.upper() == "MEDIUM":
            q = q.where((Return.fraud_risk_score >= 0.35) & (Return.fraud_risk_score < 0.65))
        else:
            q = q.where((Return.fraud_risk_score < 0.35) | (Return.fraud_risk_score == None))
    q = q.outerjoin(Product, Product.id == Return.product_id).add_columns(Product)
    result = await db.execute(q.offset(skip).limit(limit))
    return [_return_out(ret, product) for ret, product in result.all()]


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
    risk = await score_return_risk(
        product_id=payload.product_id,
        customer_id=payload.customer_id,
        reason_code=payload.reason_code,
        refund_amount=float(payload.refund_amount or 0),
    )

    customer_id_int = (
        int(payload.customer_id)
        if payload.customer_id and str(payload.customer_id).isdigit()
        else 1
    )
    ret = Return(
        product_id=payload.product_id,
        sale_id=payload.sale_id or 1,
        customer_id=customer_id_int,
        return_reason=payload.reason_code,
        refund_amount=float(payload.refund_amount or 0),
        fraud_risk_score=risk["fraud_score"],
        approval_status="Manual Review",
        return_date=datetime.now(timezone.utc).isoformat(),
    )
    db.add(ret)
    await db.flush()
    await save_return_risk_prediction(
        db,
        return_id=ret.id,
        product_id=payload.product_id,
        customer_id=customer_id_int,
        risk=risk,
    )
    await db.commit()
    await db.refresh(ret)
    return ret


class ReturnHistoryOut(BaseModel):
    id: int
    return_id: int
    product_id: int
    customer_id: Optional[int] = None
    reason_code: Optional[str] = None
    refund_amount: Optional[Decimal] = None
    action: str
    approved_by: Optional[str] = None
    override_note: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/history", response_model=List[ReturnHistoryOut])
async def get_return_history(
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Fetch return decision history."""
    q = select(ReturnHistory, Return).join(Return).order_by(ReturnHistory.created_at.desc())
    result = await db.execute(q.offset(skip).limit(limit))
    rows = result.all()
    
    out = []
    for hist, ret in rows:
        out.append(ReturnHistoryOut(
            id=hist.id,
            return_id=hist.return_id,
            product_id=ret.product_id,
            customer_id=ret.customer_id,
            reason_code=ret.return_reason,
            refund_amount=ret.refund_amount,
            action=hist.action,
            approved_by=hist.approved_by,
            override_note=hist.override_note,
            created_at=hist.created_at
        ))
    return out


@router.get("/analytics/summary")
async def returns_summary_live(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Return aggregate return statistics for dashboard KPI cards."""
    result = await db.execute(select(Return, Product).outerjoin(Product, Product.id == Return.product_id))
    joined_rows = result.all()
    returns = [ret for ret, _product in joined_rows]
    total = len(returns)
    gross_margin_lost = 0.0
    reverse_logistics_cost = 0.0
    for ret, product in joined_rows:
        if product:
            gross_margin_lost += max(
                float(product.selling_price or 0) - float(product.manufacturing_cost or 0),
                0.0,
            )
        reverse_logistics_cost += float(ret.reverse_logistics_cost or 0)
    sales_orders = int(
        await db.scalar(text("SELECT COUNT(*) FROM sales"))
        or 0
    )
    return_rate_pct = round(total / sales_orders * 100, 2) if sales_orders else 0.0
    return {
        "total_returns": total,
        "sales_orders": sales_orders,
        "pending": sum(1 for r in returns if r.status == "PENDING"),
        "approved": sum(1 for r in returns if r.status == "APPROVED"),
        "declined": sum(1 for r in returns if r.status == "DECLINED"),
        "high_risk": sum(1 for r in returns if r.risk_label == "HIGH"),
        "anomaly_flagged": sum(1 for r in returns if r.anomaly_flag),
        "approval_rate_pct": round(
            sum(1 for r in returns if r.status == "APPROVED") / max(total, 1) * 100, 2
        ),
        "return_rate_pct": return_rate_pct,
        "gross_margin_lost": round(gross_margin_lost, 2),
        "reverse_logistics_cost": round(reverse_logistics_cost, 2),
        "estimated_return_loss": round(gross_margin_lost + reverse_logistics_cost, 2),
    }





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
    Approve a return request. Also accepts re-approval of DECLINED returns (override required).
    Logs full decision audit trail on the return record.
    """
    r = await db.get(Return, return_id)
    if not r:
        raise HTTPException(status_code=404, detail="Return record not found.")
    # Block only already-approved returns; allow re-approving declined ones
    if r.status == "APPROVED":
        raise HTTPException(status_code=400, detail="Return is already approved.")

    # Override note is required for HIGH-risk, anomaly-flagged, or re-approval of declined returns
    is_reapproval = r.status == "DECLINED"
    requires_override = r.risk_label == "HIGH" or r.anomaly_flag or is_reapproval
    if requires_override and not payload.override_note:
        raise HTTPException(
            status_code=400,
            detail="override_note is required for HIGH-risk, anomaly-flagged, or re-approved returns.",
        )

    r.approval_status = "Approved"
    
    # Write to ReturnHistory with explicit timestamp
    now = datetime.now(timezone.utc).isoformat()
    history = ReturnHistory(
        return_id=r.id,
        action="APPROVED" if not is_reapproval else "REAPPROVED",
        approved_by=current_user.email,
        override_note=payload.override_note,
        created_at=now
    )
    db.add(history)
    
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
    if r.status == "DECLINED":
        raise HTTPException(status_code=400, detail="Return is already declined.")
    if not payload.override_note:
        raise HTTPException(status_code=400, detail="override_note is required to decline a return.")

    r.approval_status = "Rejected"
    
    # Write to ReturnHistory with explicit timestamp
    now = datetime.now(timezone.utc).isoformat()
    history = ReturnHistory(
        return_id=r.id,
        action="DECLINED",
        approved_by=current_user.email,
        override_note=payload.override_note,
        created_at=now
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(r)
    return r


@router.get("/{return_id}/risk")
async def get_return_risk_prediction(
    return_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return persisted ML risk prediction for a return."""
    row = await db.scalar(
        select(ReturnRiskPrediction).where(ReturnRiskPrediction.return_id == return_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Risk prediction not found.")
    return {
        "return_id": row.return_id,
        "product_id": row.product_id,
        "fraud_score": row.fraud_score,
        "return_probability": row.return_probability,
        "return_ratio": row.return_ratio,
        "risk_label": row.risk_label,
        "anomaly_flag": bool(row.anomaly_flag),
        "model_version": row.model_version,
        "created_at": row.created_at,
    }

