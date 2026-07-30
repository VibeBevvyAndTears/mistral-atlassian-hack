# Mistral Atlassian Hackathon Project

## Overview
This repository contains a fullstack application built for the hackathon.

> Note: The original starter template README is preserved in [`README.original.md`](./README.original.md).

## Tech Stack
- **Frontend**: Next.js 16 (React 19, TailwindCSS, next-intl)
- **API**: FastAPI (Python 3.13, SQLAlchemy async)
- **Database & Storage**: Supabase (Postgres + `pgvector` + Storage)
- **AI / LLM**: Mistral Studio API (`mistral-large-latest`, `mistral-embed`)

---

## Local Setup Guide

### 1. Prerequisites & Tooling
Ensure you have the following installed:
- [bun](https://bun.sh/)
- [uv](https://github.com/astral-sh/uv)
- [mise](https://mise.jdx.dev/)

### 2. Install Dependencies
Run the following commands from the project root:
```bash
# Install root & web dependencies
bun install

# Install API python dependencies
cd apps/api && uv sync && cd ../..
```

### 3. Environment Variables Setup

#### **API Environment (`apps/api/.env`)**
Copy the example environment file:
```bash
cp apps/api/.env.example apps/api/.env
```
Fill in the required keys in `apps/api/.env`:
- `DATABASE_URL`: Supabase Pooled Connection String (`postgresql+asyncpg://postgres.[project]:[password]@aws-1-[region].pooler.supabase.com:6543/postgres`)
- `DATABASE_URL_SYNC`: Supabase Direct/Sync Connection String
- `SUPABASE_URL`: Supabase project URL (`https://[project].supabase.co`)
- `SUPABASE_SERVICE_KEY`: Supabase `service_role` secret key
- `MISTRAL_API_KEY`: Your API key from Mistral AI Studio

#### **Web Environment (`apps/web/.env`)**
Copy the example environment file and generate a auth secret:
```bash
cp apps/web/.env.example apps/web/.env
```
Make sure `BETTER_AUTH_SECRET` is set in `apps/web/.env`. You can generate one with:
```bash
openssl rand -base64 32
```

### 4. Run Database Migrations
Apply Alembic database migrations (creates `users` table and enables `pgvector`):
```bash
mise //apps/api:migrate
```

### 5. Start Development Servers
Run both API and Web servers concurrently:
```bash
mise dev:web
```

Access the applications at:
- **Frontend App**: [http://localhost:3000](http://localhost:3000)
- **Backend Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Deployment (Vercel)

1. Import this repository in [Vercel](https://vercel.com).
2. Configure Environment Variables in Vercel Project Settings for **Production**:
   - `DATABASE_URL`
   - `DATABASE_URL_SYNC`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `MISTRAL_API_KEY`
3. Deploy. Production deployments trigger automatically on push to `main` or via CLI (`vercel --prod`).

