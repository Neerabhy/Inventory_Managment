# ElectroInventory v3

ElectroInventory v3 is a full-stack supply chain and inventory intelligence app. It combines a FastAPI backend, a React/Vite frontend, SQLite-backed demo data, and ML models for inventory, procurement, logistics, returns, forecasting, fraud/risk, and dynamic pricing workflows.

## Project Structure

- `api-backend/` - FastAPI API server, database models, API routes, services, migrations, and ML integration.
- `web-frontend/` - React frontend built with Vite, TanStack Router, React Query, Tailwind, and Radix UI components.
- `model-training/` - Training scripts for demand, returns, delivery, stockout, supplier risk, fraud, and pricing models.
- `ml-artifacts/` and `api-backend/app/ml/artifacts/` - Serialized ML model artifacts and metadata.
- `support-files/` - Support data, notebooks, helper scripts, tests, legacy dependencies, and archived unused folders.
- `generated-reports/` - Generated CSV reports, email output, and copilot history artifacts.
- `inventory-database/` - Database/migration assets for the full inventory dataset.

## Requirements

- Python 3.10+
- Node.js 20+
- npm

## Backend Setup

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r api-backend\requirements.txt
```

Create a `.env` file in the project root. At minimum, the backend requires:

```env
JWT_SECRET_KEY=change-this-to-a-long-secret-value
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./electro_inventory_v3.db
```

Optional AI/reporting variables include `LLM_PROVIDER`, `OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, SMTP settings, and allowed frontend origins.

## Frontend Setup

```powershell
cd web-frontend
npm install
```

The frontend defaults to `http://127.0.0.1:8000` for API calls. To override it, create `web-frontend/.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Startup Commands

### Start Everything On Windows

From the project root:

```powershell
.\start.bat
```

This starts the FastAPI backend on port `8000`, waits briefly, then starts the React frontend dev server.

### Start Backend Manually

```powershell
cd api-backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Useful backend URLs:

- API health: `http://127.0.0.1:8000/health`
- Swagger docs: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`

### Start Frontend Manually

In a second terminal:

```powershell
cd web-frontend
npm run dev
```

Vite usually serves the app at `http://localhost:5173`.

## Development Commands

Backend tests:

```powershell
python support-files\tests\test_api.py
python support-files\tests\test_endpoints.py
python support-files\tests\test_writes.py
```

Frontend checks:

```powershell
cd web-frontend
npm run lint
npm run build
```

Demo/database helpers:

```powershell
python support-files\scripts\create_tables.py
python support-files\scripts\backfill_data.py
python support-files\scripts\reset_demo_data.py
python support-files\scripts\check_db.py
```

## Notes

- Keep secrets in `.env` or frontend `.env.local` files. Do not commit API keys, JWT secrets, or SMTP credentials.
- SQLite database files and generated reports are local runtime artifacts and are ignored by Git.
- ML artifacts are present in the repository because the app depends on them at runtime.
