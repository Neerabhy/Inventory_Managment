from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user, RoleChecker
from app.models.auth import User
from app.models.analytics import ReturnRecords
from app.schemas.analytics import ReturnEvaluationRequest, ReturnRecordResponse
from app.ml.return_classifier import return_risk_engine

router = APIRouter(prefix="/returns", tags=["Returns & Fraud Intelligence"])

@router.post("/{return_id}/evaluate", response_model=ReturnRecordResponse)
async def evaluate_return(
    return_id: int,
    eval_req: ReturnEvaluationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["SYS_ADMIN", "RETURN_APPROVER"]))
):
    """Approves or rejects a return. AI scores dictate if a human override justification is required."""
    result = await db.execute(select(ReturnRecords).where(ReturnRecords.id == return_id))
    return_record = result.scalars().first()

    if not return_record:
        raise HTTPException(status_code=404, detail="Return record not found.")

    # Get live AI Risk assessment
    active_risk = return_risk_engine.predict_return_risk(product_return_rate=0.12, customer_history_size=5)
    fraud_prob = return_risk_engine.detect_fraudulent_anomaly(active_risk_score=active_risk, loyalty_level="BRONZE")

    # If AI flags high risk (>0.7), and user approves anyway, mandate override justification
    is_override = False
    if fraud_prob > 0.70 and eval_req.refund_status == "APPROVED":
        if not eval_req.override_justification:
            raise HTTPException(
                status_code=400, 
                detail="High AI fraud risk detected. You must provide a text justification to override."
            )
        is_override = True

    return_record.refund_status = eval_req.refund_status
    return_record.ai_risk_score = fraud_prob
    return_record.is_human_override = is_override
    return_record.override_justification = eval_req.override_justification

    await db.commit()
    await db.refresh(return_record)

    return return_record