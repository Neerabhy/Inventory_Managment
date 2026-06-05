import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        # Test 1: Health check
        r = await client.get("/health")
        print("Health Check:", r.status_code, r.json())
        
        # Test 2: System info
        r = await client.get("/api/v1/system/info")
        print("System Info:", r.status_code, r.json())

        # Test 3: Procurement suppliers list (Requires auth?)
        # Wait, many endpoints require authentication.
        signup_data = {
            "username": "admin2",
            "email": "admin2@example.com",
            "password": "password",
            "full_name": "Admin User",
            "roles": ["SYS_ADMIN"]
        }
        r_signup = await client.post("/api/v1/auth/signup", json=signup_data)
        print("Signup:", r_signup.status_code, r_signup.text)
        r = await client.post("/api/v1/auth/login", json={"username": "admin2", "password": "password"})
        if r.status_code == 200:
            token = r.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Test Inventory
            r = await client.get("/api/v1/inventory/products", headers=headers)
            print("Inventory List:", r.status_code)
            
            # Test Procurement
            r = await client.get("/api/v1/procurement/suppliers", headers=headers)
            print("Suppliers List:", r.status_code)
            
            # Test Logistics
            r = await client.get("/api/v1/logistics/shipments", headers=headers)
            print("Shipments List:", r.status_code)
            
            # Test Returns
            r = await client.get("/api/v1/returns/", headers=headers)
            print("Returns List:", r.status_code)
            
            # Test Copilot (dummy query)
            r = await client.post("/api/v1/copilot/query", json={"query": "Show inventory summary"}, headers=headers)
            print("Copilot Query:", r.status_code)
        else:
            print("Login failed:", r.status_code, r.text)

if __name__ == "__main__":
    asyncio.run(main())
