# Mistral Atlassian Hackathon Project

## Overview
This repository contains a fullstack application built for the hackathon.

> Note: The original starter template README is preserved in [`README.original.md`](./README.original.md).

## Tech Stack
- **Frontend**: Next.js (hosted on Vercel)
- **API**: FastAPI (serverless on Vercel)
- **Database & Storage**: Supabase (Postgres + `pgvector` + Storage)
- **AI / LLM**: Mistral Studio API (`mistral-large-latest`, `mistral-embed`)

## Prerequisites & Local Setup
1. **Tooling**: Make sure `mise` and `uv` are installed.
2. **Environment Variables**:
   Copy `.env.example` in `apps/api/` to `.env` and fill in the required keys:
   ```bash
   cp apps/api/.env.example apps/api/.env
   ```
   Required keys:
   - `DATABASE_URL`: Supabase Pooled Connection String (port 6543, pgbouncer=true)
   - `MISTRAL_API_KEY`: API Key from Mistral Studio
   - `SUPABASE_URL`: Supabase project URL (`https://[project].supabase.co`)
   - `SUPABASE_SERVICE_KEY`: Supabase `service_role` secret key

## Database Migrations
Run Alembic migrations using `mise`:
```bash
mise //apps/api:migrate
```

## Running Dev Servers
Run the development environment:
```bash
mise dev:web
```

## Deployment (Vercel)
1. Import this repository in [Vercel](https://vercel.com).
2. Configure Environment Variables in Vercel Project Settings:
   - `DATABASE_URL`
   - `MISTRAL_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
3. Deploy. Auto-deploy on push to `main` is enabled.
