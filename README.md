# Bridge

A full-stack starter monorepo:

- **Backend** — [FastAPI](https://fastapi.tiangolo.com/) (Python) with an example CRUD router and CORS pre-configured for the frontend.
- **Frontend** — [Nuxt 3](https://nuxt.com/) + [Vue 3](https://vuejs.org/) landing page that talks to the API (health check + item list).

## Project structure

```
bridge/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app entrypoint (CORS + routes)
│   │   └── routers/items.py   # Example in-memory CRUD API
│   └── requirements.txt
└── frontend/
    ├── app.vue                # Root Vue component
    ├── pages/index.vue        # Landing page (calls the API)
    ├── nuxt.config.ts         # Dev proxy: /api/** -> localhost:8000
    └── package.json
```

## Getting started

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is now available at http://localhost:8000 — interactive docs at http://localhost:8000/docs.

### 2. Frontend (Nuxt + Vue)

```bash
cd frontend
npm install
npm run dev
```

The app is now available at http://localhost:3000. During development, all `/api/**`
requests are proxied to the FastAPI backend on port 8000.

## API overview

| Method | Endpoint             | Description           |
| ------ | -------------------- | --------------------- |
| GET    | `/api/health`        | Liveness probe        |
| GET    | `/api/items`         | List all items        |
| POST   | `/api/items`         | Create an item        |
| GET    | `/api/items/{id}`    | Get a single item     |
| DELETE | `/api/items/{id}`    | Delete an item        |
