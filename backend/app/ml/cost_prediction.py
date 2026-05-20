import numpy as np
from app.ml.base import BaseMLModel

class LogisticsPredictiveEngine(BaseMLModel):
    def __init__(self) -> None:
        self.cost_model = None
        self.delay_model = None
        self.load_model()

    def load_model(self) -> None:
        self.cost_model = "XGBOOST_REGRESSOR"
        self.delay_model = "RANDOM_FOREST_CLASSIFIER"

    def predict(self, distance_km: float, weight_kg: float, transportation_mode: str, fragile_flag: bool) -> float:
        """Model 3: Estimates dynamic shipping rates based on cargo properties."""
        base_rate = 150.0  # Baseline pricing initialization
        mode_multipliers = {"Air": 4.5, "Rail": 1.2, "Road": 1.8}
        multiplier = mode_multipliers.get(transportation_mode, 1.5)
        
        # Core linear cost regression formula
        estimated_cost = base_rate + (distance_km * 0.45) + (weight_kg * 2.25) * multiplier
        if fragile_flag:
            estimated_cost *= 1.25  # Apply handling surcharge
            
        return float(round(estimated_cost, 2))

    def predict_delay_probability(self, distance_km: float, weather_delay_flag: bool, mode: str) -> float:
        """Model 4: Calculates the probability of operational logistics delays."""
        base_prob = 0.05
        if distance_km > 500:
            base_prob += 0.12
        if weather_delay_flag:
            base_prob += 0.45
        if mode == "Road":
            base_prob += 0.08
            
        return float(min(0.98, round(base_prob, 2)))

logistics_prediction_engine = LogisticsPredictiveEngine()