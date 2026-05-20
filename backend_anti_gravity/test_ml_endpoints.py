import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        # First sign up or log in
        login_response = await client.post("/api/v1/auth/login", json={"username": "admin2", "password": "password"})
        if login_response.status_code != 200:
            print("Login failed:", login_response.text)
            return
            
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test 1: Cost Estimate Endpoint
        cost_payload = {
            "distance_km": 300.0,
            "weight_kg": 15.0,
            "fragile_flag": True,
            "weather_delay_flag": True
        }
        r_cost = await client.post("/api/v1/logistics/cost-estimate", json=cost_payload, headers=headers)
        print("Cost Estimate Status:", r_cost.status_code)
        if r_cost.status_code == 200:
            print("Cost Estimate Response:", r_cost.json())
        else:
            print("Cost Estimate Error:", r_cost.text)
            
        # Test 2: Submit Return Endpoint
        return_payload = {
            "product_id": 10,
            "customer_id": "5",
            "reason_code": "DAMAGED_IN_TRANSIT",
            "refund_amount": 15000.0,
            "sale_id": 10
        }
        r_return = await client.post("/api/v1/returns/", json=return_payload, headers=headers)
        print("Submit Return Status:", r_return.status_code)
        if r_return.status_code == 201:
            print("Submit Return Response:", r_return.json())
        else:
            print("Submit Return Error:", r_return.text)

if __name__ == "__main__":
    asyncio.run(main())
