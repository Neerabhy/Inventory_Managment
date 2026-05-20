from app.ml.base import BaseMLModel

class VendorRecommendationEngine(BaseMLModel):
    def __init__(self) -> None:
        self.load_model()

    def load_model(self) -> None:
        pass

    def predict(self, vendor_options: list[dict]) -> list[dict]:
        """Model 5: Ranks suppliers using a multi-criteria scoring matrix."""
        scored_vendors = []
        
        # Scoring component weights (Must sum to 1.0)
        w_cost, w_lead, w_qual, w_rel = 0.35, 0.20, 0.25, 0.20

        # Determine reference boundaries for normalization loops
        if not vendor_options:
            return []
            
        costs = [v["supplier_price"] for v in vendor_options]
        leads = [v["lead_time_days"] for v in vendor_options]
        max_cost, min_cost = max(costs) if costs else 1, min(costs) if costs else 1
        max_lead, min_lead = max(leads) if leads else 1, min(leads) if leads else 1

        for vendor in vendor_options:
            # Cost normalization (Lower is better)
            c_norm = (max_cost - vendor["supplier_price"]) / (max_cost - min_cost) if max_cost != min_cost else 1.0
            # Lead time normalization (Lower is better)
            l_norm = (max_lead - vendor["lead_time_days"]) / (max_lead - min_lead) if max_lead != min_lead else 1.0
            
            # Extract standard metrics
            q_norm = vendor["quality_level"] / 5.0  # Scaled from a 5-star baseline
            r_norm = vendor.get("reliability", 0.95)  # Reliability ratio parameter

            # Calculate total weighted score
            final_score = (c_norm * w_cost) + (l_norm * w_lead) + (q_norm * w_qual) + (r_norm * w_rel)
            
            scored_vendors.append({
                "supplier_id": vendor["supplier_id"],
                "supplier_name": vendor["supplier_name"],
                "calculated_score": float(round(final_score * 100, 2)),
                "unit_cost": float(vendor["supplier_price"]),
                "lead_time_days": int(vendor["lead_time_days"]),
                "recommendation_tier": "STANDARD CHOICE"
            })

        # Sort recommendations by highest performance score
        scored_vendors.sort(key=lambda x: x["calculated_score"], reverse=True)

        if len(scored_vendors) > 0:
            scored_vendors[0]["recommendation_tier"] = "BEST CHOICE"
        if len(vendor_options) > 1:
            # Tag specific optimization paths
            lowest_cost_idx = min(range(len(scored_vendors)), key=lambda i: scored_vendors[i]["unit_cost"])
            fastest_lead_idx = min(range(len(scored_vendors)), key=lambda i: scored_vendors[i]["lead_time_days"])
            
            if scored_vendors[lowest_cost_idx]["recommendation_tier"] == "STANDARD CHOICE":
                scored_vendors[lowest_cost_idx]["recommendation_tier"] = "LOWEST COST"
            if scored_vendors[fastest_lead_idx]["recommendation_tier"] == "STANDARD CHOICE":
                scored_vendors[fastest_lead_idx]["recommendation_tier"] = "FASTEST DELIVERY"

        return scored_vendors

vendor_ranker_engine = VendorRecommendationEngine()