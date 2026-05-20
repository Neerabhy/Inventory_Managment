from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class ShipmentResponse(BaseModel):
    id: int
    tracking_number: str
    shipment_type: str
    origin_location: str
    destination_location: str
    delivery_status: str
    shipping_cost: float
    transportation_mode: str
    distance_km: float
    weight_kg: float
    fragile_flag: bool
    weather_delay_flag: bool
    delay_probability: float
    estimated_delivery: datetime

    class Config:
        from_attributes = True

class CostEstimationRequest(BaseModel):
    distance_km: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    transportation_mode: str = Field(..., description="Road, Air, Rail")
    fragile_flag: bool = False

class CostEstimationResponse(BaseModel):
    estimated_cost: float
    calculation_currency: str = "INR"
    model_confidence_upper: float
    model_confidence_lower: float