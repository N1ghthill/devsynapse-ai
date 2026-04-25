# DevSynapse Frontend

This frontend is the operator-facing UI for DevSynapse AI. It is built with React, TypeScript and Vite and currently provides:
- login flow backed by JWT authentication;
- shared session state with protected routes;
- chat interface for interacting with the assistant;
- dashboard for monitoring command/API activity;
- settings page for runtime-adjustable backend options;
- admin page for user project-permission management, project registration and audit visibility.

## Stack

- React 19
- TypeScript
- Vite
- Axios
- React Router
- Recharts

## Local Development

```bash
cd frontend
npm install
npm run dev
```

In local development the app expects the backend at `http://127.0.0.1:8000`.
In production builds, an unset API URL uses the same origin that serves the UI.

You can override that with:

```bash
VITE_API_URL=http://127.0.0.1:8000
```

## Build

```bash
npm run lint
npm run build
```

## Structure

```text
frontend/
├── src/
│   ├── api/         # HTTP client and backend integration
│   ├── components/  # UI building blocks
│   ├── hooks/       # shared React hooks
│   ├── pages/       # route-level pages
│   └── types.ts     # shared frontend contracts
├── public/
└── package.json
```

## Contract Discipline

The frontend should not invent backend payloads. The expected shapes are defined in:
- [src/api/client.ts](src/api/client.ts)
- [src/types.ts](src/types.ts)

When backend contracts change, update those files first and then adapt the pages/components.

## Current State

The frontend is functionally integrated with the current backend, but still early in product maturity. Areas likely to evolve:
- richer chat UX and execution confirmation flow;
- more deliberate dashboard visualizations;
- better settings ergonomics and validation.

Repository-level verification is documented in:
- [../README.md](../README.md)
- [../docs/development/workflow.md](../docs/development/workflow.md)
