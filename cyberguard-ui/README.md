# CyberGuard UI

React + TypeScript + Vite frontend for the **AI World Model for Predictive Cyber Defence** project.

---

## Quick Start

### 1. Start the FastAPI backend

```bash
# From project root (D:\Network_Attak_Forecasting)
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Swagger UI: http://127.0.0.1:8000/docs

### 2. Install frontend dependencies

```bash
cd cyberguard-ui
npm install
```

### 3. Configure environment

```bash
# Copy the example and adjust if your backend runs on a different host/port
cp .env.example .env
```

Default `.env`:
```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 4. Start the dev server

```bash
npm run dev
```

Frontend: **http://localhost:5173**

---

## API Connection

The Vite dev server proxies `/api/*` → `http://127.0.0.1:8000/*` (see `vite.config.ts`).

All API calls go through `src/services/api.ts`. Never add `fetch()` calls directly to components.

If the backend is offline, `ErrorState` components display a retry prompt. No data is fabricated.

---

## Page → API Mapping

| Page             | API Endpoints Used                                    |
|------------------|-------------------------------------------------------|
| Dashboard        | `/predict/{id}`, `/forecast/{id}`                     |
| Attack Forecast  | `/forecast/{id}`                                      |
| Attack Stages    | `/predict/{id}`, `/forecast/{id}`                     |
| Network State    | `/forecast/{id}/states`                               |
| Explainability   | `/explain/{id}`                                       |
| Model Performance| `/model/comparison`                                   |
| System Status    | `/health`, `/model/info`                              |

---

## Architecture

```
src/
  types/api.ts          — TypeScript interfaces (API contract)
  services/
    api.ts              — Real API functions (primary)
    mockApi.ts          — Fallback mock data (backend-offline dev)
  context/
    SampleContext.tsx   — Global selected sample state
  hooks/
    useApi.ts           — Generic data-fetching hook
    useSample.ts        — Combined sample + prediction hook
  components/           — Reusable UI components
  layouts/              — Sidebar, Header, MainLayout
  pages/                — One file per route
  utils/constants.ts    — Stage colors, risk levels, MITRE map
```

---

## Important Notes

- **LIVE DEMO / SIMULATED TELEMETRY**: The UI correctly identifies the environment.
  It does not claim real enterprise network traffic.
- **MITRE ATT&CK**: Mappings are prototype stage-to-technique assignments, not direct technique detection.
- **Explainability**: "Sensitivity" = prediction influence. Does not imply causation.
- **Demo alerts**: `AlertCard` is frontend-generated from model probability. Not a real device compromise claim.
- **No backend modification**: This frontend is purely a presentation layer.

---

## Build for Production

```bash
npm run build
# Output: dist/
```

---

## Limitations

- No WebSocket/SSE real-time streaming (REST polling only; architecture is ready to extend)
- Device-level risk UI is demo-mode only (no `/devices` backend endpoint yet)
- Polling interval is manual refresh only
