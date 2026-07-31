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

Make sure you have the required CLI tools installed:

- **bun** (JS/TS package manager):

  - **macOS / Linux**:
    ```bash
    brew install bun  # or: curl -fsSL https://bun.sh/install | bash
    ```
  - **Windows**:
    ```powershell
    powershell -c "irm bun.sh/install.ps1 | iex"
    ```
- **uv** (Python package manager):

  - **macOS / Linux**:
    ```bash
    brew install uv   # or: curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
  - **Windows**:
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
- **mise** (Task runner):

  - **macOS / Linux**:
    ```bash
    brew install mise # or: curl https://mise.jdx.dev/install.sh | sh
    ```
  - **Windows**:
    ```powershell
    winget install jdx.mise # or: scoop install mise
    ```

### 2. Install Dependencies

Run from the project root (no need to change directories):

```bash
# Install root & web dependencies
bun install

# Install API python dependencies
uv sync --directory apps/api
```

### 3. Environment Variables Setup

Run from the project root:

#### **API Environment (`apps/api/.env`)**

- **macOS / Linux**:
  ```bash
  cp apps/api/.env.example apps/api/.env
  ```
- **Windows (PowerShell)**:
  ```powershell
  Copy-Item apps/api/.env.example apps/api/.env
  ```

Fill in the required keys in `apps/api/.env`:

- `DATABASE_URL`: Supabase Pooled Connection String (`postgresql+asyncpg://postgres.[project]:[password]@aws-1-[region].pooler.supabase.com:6543/postgres`)
- `DATABASE_URL_SYNC`: Supabase Direct/Sync Connection String
- `SUPABASE_URL`: Supabase project URL (`https://[project].supabase.co`)
- `SUPABASE_SERVICE_KEY`: Supabase `service_role` secret key
- `MISTRAL_API_KEY`: Your API key from Mistral AI Studio

#### **Web Environment (`apps/web/.env`)**

- **macOS / Linux**:
  ```bash
  cp apps/web/.env.example apps/web/.env
  ```
- **Windows (PowerShell)**:
  ```powershell
  Copy-Item apps/web/.env.example apps/web/.env
  ```

Make sure `BETTER_AUTH_SECRET` is set in `apps/web/.env`. You can generate one with:

- **macOS / Linux**:
  ```bash
  openssl rand -base64 32
  ```
- **Windows**:
  ```powershell
  powershell -Command "[guid]::NewGuid().ToString()"
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

### 6. Stop Development Servers

To stop the dev servers running in your terminal, press `Ctrl+C`.

If a background process remains running or ports `3000`/`8000` stay blocked, you can kill all running dev processes with:

```bash
mise dev:stop
```

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
