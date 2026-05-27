# IDEA Portal — Frontend

Vite + React 18 + TypeScript + Ant Design 5 + React Query + Zustand.

## Quick Start

```bash
# Via docker-compose dari root (recommended)
cd ..
docker compose up frontend

# ATAU manual (butuh Node 22+)
cd frontend
npm install
cp .env.example .env
npm run dev
```

Browse: http://localhost:5173

## Struktur Feature-Based

```
src/
├── main.tsx              # Entry — providers (QueryClient, AntD, Router)
├── App.tsx               # Root component
├── index.css             # Global styles + font
├── api/
│   └── client.ts         # Axios + interceptors (JWT, 401 redirect)
├── components/           # Reusable UI primitives (cross-feature)
├── features/             # Per-feature modules (auth, payroll, ...)
├── routes/               # React Router routes
├── store/                # Zustand global stores
└── lib/                  # Utilities, helpers
```

Per CLAUDE.md: organize by feature, not by file type.

## Tech Stack & Versions

| Lib | Versi |
|---|---|
| React | 18.3 |
| TypeScript | 5.6 (strict mode ON) |
| Vite | 5.4 |
| Ant Design | 5.22 |
| React Query | 5.59 |
| Zustand | 5.0 |
| React Hook Form | 7.53 |
| Zod | 3.23 |
| dayjs | 1.11 |

## Konvensi

- **Style:** Functional components + hooks (no class components)
- **State:**
  - Server state → React Query
  - Client/UI state → Zustand
  - Form state → React Hook Form + Zod schema
- **Naming:** camelCase variabel/fn, PascalCase component/type
- **Theme:** Ant Design ConfigProvider — color tokens dari knowledge.md sec.17

## Scripts

```bash
npm run dev         # Dev server (port 5173)
npm run build       # Production build (dist/)
npm run preview     # Preview production build
npm run lint        # ESLint
npm run type-check  # TypeScript check
npm run test        # Vitest
```

## Status

- ✅ Sprint 0: Skeleton siap (Vite + AntD + React Query + health-check page)
- 🚧 Sprint 1 (PH1 M1.1): EP-01 Auth UI (Login page from `GUI html/IDEA_Login.html`)
