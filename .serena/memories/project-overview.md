# Fullstack Starter - Project Overview

## Purpose
Production-ready fullstack monorepo template with Next.js 16, FastAPI, Flutter, and GCP infrastructure.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, React 19, TailwindCSS v4, shadcn/ui, TanStack Query, Jotai, next-intl |
| **Backend** | FastAPI, SQLAlchemy (async), PostgreSQL 16, Redis 7, Alembic |
| **Mobile** | Flutter 3.38, Riverpod 3, go_router 17, Firebase Crashlytics, Fastlane, Flutter intl |
| **Worker** | FastAPI + CloudTasks/PubSub |
| **Infrastructure** | Terraform, GCP (Cloud Run, Cloud SQL, Memorystore, GCS, Cloud Tasks, Pub/Sub, CDN) |
| **CI/CD** | GitHub Actions, Workload Identity Federation |
| **Tool Management** | mise (unified Node 24, Python 3.12, Flutter 3, pnpm 10, uv, Terraform 1) |

## Key Features
- Type Safety: TypeScript, Pydantic, Dart
- Authentication: better-auth OAuth (Google, GitHub, Facebook)
- Internationalization: next-intl (web), Flutter ARB (mobile), shared i18n package
- Design Tokens: OKLCH color space, shared tokens for web (TailwindCSS v4) and mobile (Material3)
- Auto-generated API Clients: Orval (web), swagger_parser (mobile)
- Infrastructure as Code: Terraform + GCP
- CI/CD: GitHub Actions + Workload Identity Federation (keyless deployment)
- AI Agent Support: Guidelines in `.agent/rules/`
- mise Monorepo: mise-based task management

## Project Structure
```
fullstack-starter/
├── apps/
│   ├── api/           # FastAPI backend (Python 3.12, uv)
│   ├── web/           # Next.js 16 frontend (Node 24, pnpm)
│   ├── worker/        # Background worker (Python 3.12, uv)
│   ├── mobile/        # Flutter mobile app (Flutter 3.38)
│   └── infra/         # Terraform infrastructure
├── packages/
│   ├── design-tokens/ # Shared design tokens (Source of Truth)
│   └── i18n/          # Shared i18n package (Source of Truth)
├── .agent/rules/      # AI agent guidelines
├── .serena/           # Serena MCP config
└── .github/workflows/ # CI/CD pipelines
```

## Local Infrastructure (via Docker Compose)
- PostgreSQL (port 5432)
- Redis (port 6379)
- MinIO (ports 9000, 9001)
