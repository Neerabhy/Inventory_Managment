from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models.auth import User
from app.schemas.logistics import CostEstimationRequest, CostEstimationResponse
from app.ml.cost_prediction import logistics_prediction_engine

router = APIRouter(prefix="/logistics", tags=["Logistics & Shipping"])

@router.post("/estimate-cost", response_model=CostEstimationResponse)
async def estimate_logistics_cost(
    request: CostEstimationRequest,
    current_user: User = Depends(get_current_user)
):
    """Predicts real-time shipping costs via XGBoost regression."""
    predicted_cost = logistics_prediction_engine.predict(
        distance_km=request.distance_km,
        weight_kg=request.weight_kg,
        transportation_mode=request.transportation_mode,
        fragile_flag=request.fragile_flag
    )
    
    return CostEstimationResponse(
        estimated_cost=predicted_cost,
        calculation_currency="INR",
        model_confidence_lower=predicted_cost * 0.90,
        model_confidence_upper=predicted_cost * 1.15
    )