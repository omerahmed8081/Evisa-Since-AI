# Frontend

Put the frontend app here (e.g. the exported Lovable project), so the repository looks like:

```
frontend/
├── package.json
├── src/
└── ...
```

Run it (typical Vite/React project):
```bash
cd frontend
npm install
npm run dev
```

Connect it to the backend by creating `frontend/.env.local` (not committed):
```
VITE_API_BASE_URL=http://localhost:8000
```

The API contract (endpoints, request/response shapes, streaming events) is in
[../backend/api/README.md](../backend/api/README.md) and live at http://localhost:8000/docs.
