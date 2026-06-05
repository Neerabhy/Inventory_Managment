# Plan: Connect frontend to your FastAPI backend

Your backend: FastAPI at `http://127.0.0.1:8000`, routers under `/api/v1/{auth,inventory,procurement,logistics,returns,copilot}`, JWT auth, OpenAPI at `/api/docs`.

Note on localhost: `127.0.0.1:8000` is reachable from your browser (since the browser runs on your machine) as long as your FastAPI CORS allows the Lovable preview origin. Add to FastAPI:

```python
allow_origins=["https://id-preview--98ca6d99-eeb9-4d89-8bde-5b4c9e71d47b.lovable.app", "http://localhost:5173"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

## Step 1 — API client foundation (one-time)
- `src/lib/api/client.ts` — typed `fetch` wrapper: base URL from `import.meta.env.VITE_API_BASE_URL` (default `http://127.0.0.1:8000`), auto-attaches `Authorization: Bearer <token>`, parses JSON, throws typed `ApiError`.
- `src/lib/api/token.ts` — JWT stored in `localStorage` + in-memory cache; `getToken`, `setToken`, `clearToken`.
- `src/lib/auth-context.tsx` — React context exposing `{ user, token, login, logout, hasRole }`, hydrates from localStorage on mount, calls `GET /api/v1/auth/me` to validate.
- TanStack Query `QueryClient` already wired in `__root.tsx`.

## Step 2 — Auth wiring
- Replace fake `/login` submit with real `POST /api/v1/auth/login` → store JWT → redirect to `/app/dashboard`.
- Same for `/signup` if a signup endpoint exists (otherwise hide it).
- Add `src/routes/_authenticated.tsx` pathless layout: `beforeLoad` redirects to `/login` if no token.
- Move `src/routes/app.*` files under `_authenticated/` (or check in the existing `app.tsx` layout for token + redirect — simpler, no file moves).
- Top-bar user menu wired to real user + logout.

## Step 3 — Wire modules one at a time
For each module: create a `src/lib/api/<module>.ts` with typed functions + `queryOptions`, then refactor the matching route to use `ensureQueryData` + `useSuspenseQuery`, drop the corresponding mock import. Mutations via `useMutation` + `queryClient.invalidateQueries` + Sonner toasts.

Order (you confirm endpoint paths/response shapes for each before I code it):
1. **Inventory** — list, search, filter by warehouse, stock levels, low-stock alerts → `app.inventory.tsx` + dashboard KPIs
2. **Dashboard KPIs** — aggregated numbers + sparkline series
3. **Products** — catalog + detail page (`app.products.index.tsx`, `app.products.$sku.tsx`)
4. **Procurement** — vendor ranking, PO list/create (`app.procurement.tsx`)
5. **Suppliers** (`app.suppliers.tsx`)
6. **Logistics / shipments** (`app.logistics.tsx`)
7. **Returns** — pending list + approve/decline mutations (`app.returns.index.tsx`, `.history.tsx`)
8. **Copilot** — wire the floating chat to `POST /api/v1/copilot/...` (streaming if your endpoint supports SSE; otherwise non-stream)
9. **Forecasting / Reports / Admin** — last, since they may need extra endpoints

## Step 4 — Cleanup
- Delete `src/lib/mock/data.ts`.
- Move shared TypeScript types to `src/lib/api/types.ts`.
- Add a small "Backend offline" empty state per route when fetch fails.

## What I need from you per module
When we start each module, paste:
- The router file (e.g. `inventory.py`), **or**
- A sample `curl` + JSON response for each endpoint you want wired, **or**
- A link/screenshot of that section of `/api/docs`.

## Out of scope (ask if you want them)
- Persisting auth across server restarts via refresh tokens
- WebSocket / SSE realtime updates
- Optimistic UI for mutations beyond basic invalidation
- Deploying your FastAPI publicly

## Ready?
Approve this plan and then paste your **auth router** (`auth.py`) + **inventory router** so I can start with Step 1, Step 2, and the inventory page in the first build pass.
