# Conve

> Every team speaks a different language: technical, visual, strategic.
> Conve is the shared language your teams never had.

> Built for **The Atlassian x Mistral x AISoc Hack**.
> [Devpost submission](https://devpost.com/software/conve) ·
> [GitHub](https://github.com/VibeBevvyAndTears/mistral-atlassian-hack)
> Note: the original starter-template README is preserved in [`README.original.md`](./README.original.md).

## 1. What is this?

Conve solves a specific failure mode of knowledge handoff between
functional teams: Marketing writes a doc, Design never reads it (or reads it
without the context to act on it), and the decision behind it gets
re-litigated three weeks later because nobody can point to *who decided
what, why*. Conve lets one team share documents and decisions with
another team through AI-mediated "packages" and "posts" — Mistral extracts
claims and decisions from pasted/uploaded documents, flags conflicts inside
a team's own knowledge *before* anything is shared outward, rewrites the
message for the receiving team's tone and vocabulary, judges that rewrite
for fidelity and audience fit, and keeps a full negotiation history (change
requests, suggested edits, dual-team approval, close) so every cross-team
decision is traceable after the fact.

## 2. Who is it for?

Any org with two or more teams that regularly hand off context across a
team boundary — Marketing → Design, Product → Engineering, Sales →
Support — and currently do it over Slack threads or docs nobody reads twice.
It assumes an org/team hierarchy with invite-based membership (owner / lead
/ member / viewer roles), not a single-team tool.

## 3. What does it do?

- **Document ingestion** — paste text or upload a file (native text/DOCX/PDF,
  or scanned PDFs/images via Mistral OCR); Mistral decomposes it into a
  versioned graph of topics and claims (facts, decisions, constraints,
  requirements, metrics, dates, owners).
- **Intra-team conflict detection** — new claims are checked against a
  team's own existing claims before anything is shared, so contradictions
  surface as a review item pre-send, not post-send.
- **AI-adapted cross-team posts** — sending a package rewrites it for the
  receiving team's profile (tone, jargon, audience), with an AI-assigned
  priority (`p0`/`p1`/`p2`) and reason.
- **Fidelity + fit judging** — every AI-adapted rewrite is checked for
  invented/dropped facts and for whether it's pitched at the right level of
  detail for its audience, with automatic retry/fallback to the original
  text when a rewrite doesn't pass.
- **Cross-team negotiation with full history** — suggestions, review
  actions (agree / request changes / blocked), and comments on a post are
  tracked end-to-end; edits that touch shared content require **both**
  teams to approve before they apply (see `docs/adr/ADR-004-dual-team-approval-for-suggestions.md`).
- **Decision tracing** — every promoted claim, every conflict resolution,
  every applied suggestion is a queryable, timestamped record — the
  `GET /posts/{post_id}/history` and `GET /teams/{team_id}/decisions`
  endpoints are the audit trail this product is built around.
- **Per-team glossary + versioned team profiles** — so adaptation and the
  pre-send checklist know which jargon needs explaining before it crosses a
  team boundary.

## 4. How do I try it?

**Live demo:** _not yet deployed — see § Deploy below for the Vercel
config once a production URL exists._

**Run locally in 3 steps** (full detail in [`docs/setup.md`](./docs/setup.md)):

```bash
mise install                         # 1. install every pinned runtime + all deps
cp apps/api/.env.example apps/api/.env && cp apps/web/.env.example apps/web/.env
# ...fill in MISTRAL_API_KEY, DATABASE_URL, BETTER_AUTH_SECRET (see docs/setup.md)...
mise //apps/api:migrate && mise dev:web   # 2. migrate DB, 3. start API + Web
```

Then open `http://localhost:3000`.

## 5. How do I run it locally?

For environment variable meaning (what each key does and which ones are
actually required for local dev), database setup, running tests, and known
first-run gotchas (a stale Turbopack cache error and a job-worker startup
check), see the full walk-through in **[`docs/setup.md`](./docs/setup.md)**.
The condensed version, reproduced here for convenience:

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

## Tech stack

- **Frontend**: Next.js 16 (React 19, TailwindCSS v4, next-intl, TanStack
  Query, Jotai, better-auth)
- **API**: FastAPI (Python, async SQLAlchemy 2.x, Alembic migrations,
  JWE-based stateless auth)
- **Database & storage**: Supabase-hosted Postgres with the `pgvector`
  extension (claim embeddings) + object storage (MinIO locally / GCS/S3 in
  deploy)
- **Background jobs**: in-process asyncio worker polling a Postgres
  `job_queue` table — no external broker (see
  [`docs/adr/ADR-003-in-process-polling-job-worker.md`](./docs/adr/ADR-003-in-process-polling-job-worker.md))
- **AI / LLM**: Mistral Studio API only — `mistral-large-latest` (structured
  extraction/adaptation/judging), `mistral-embed` (claim similarity),
  `mistral-ocr-latest` (scanned document OCR)
- **Monorepo tooling**: `mise` task runner in monorepo mode, `bun` (web),
  `uv` (API)

## Architecture

The system is a monorepo (`apps/api`, `apps/web`, `apps/worker` scaffold,
`apps/mobile` scaffold, `packages/i18n`, `packages/design-tokens`) run
through `mise`. The API follows router → service → repository-style layering
per domain (`auth`, `orgs`, `teams`, `channels`, `review`, `conflict`,
`graph`, `documents`, `profiles`, `glossary`, `eval`, `notifications`), with
tenant scope (`X-Org-Id`/`X-Team-Id`) resolved and validated on every request
before a handler runs. The AI pipeline (decomposition → claim extraction →
linking → conflict → adaptation → judge → prioritization) is invoked from a
single in-process background worker, not the request path — see
[`docs/ai-feature.md`](./docs/ai-feature.md) for how a document or a package
send actually flows through it.

The five architecture decisions most worth reading before touching this
codebase are reverse-engineered as ADRs in [`docs/adr/`](./docs/adr/):
monorepo + `mise` (ADR-001), FastAPI + async SQLAlchemy + Supabase/pgvector
(ADR-002), the in-process job worker instead of Celery/SQS (ADR-003), the
dual-team-approval model for cross-team suggestion edits (ADR-004), and
Mistral as the sole LLM provider (ADR-005). Full HTTP surface is documented
endpoint-by-endpoint in [`docs/api.md`](./docs/api.md).

## AI feature

Conve's AI layer does four things end-to-end without a human
re-transcribing anything: it reads a pasted or uploaded document and pulls
out a structured graph of topics and claims (facts, decisions, constraints,
requirements); it checks new claims against a team's own existing claims so
contradictions get caught before anything is shared outward; when a team
sends a package to another team's channel, it rewrites the message for that
team's tone and vocabulary and then grades its own rewrite for whether it
invented/dropped facts and whether it's explained at the right level for
that audience, falling back to the original text rather than shipping a
rewrite it isn't confident about; and it assigns a priority label with a
reason so receiving teams know what to look at first. Every one of these
steps is logged as a durable trace, which is what makes the decision-history
log ("who decided what, why, and what changed across a team boundary")
possible instead of just an aspiration. All of it runs on the Mistral Studio
API alone — see [`docs/ai-feature.md`](./docs/ai-feature.md) for the model
list, the pipeline stage contracts, configuration, honest limitations (a
real rate-limit ceiling hit during testing, and a job-worker crash bug found
and fixed this session), and cost status.

## Deploy (Vercel)

1. Import this repository in [Vercel](https://vercel.com).
2. Configure Environment Variables in Vercel Project Settings for **Production**:
   - `DATABASE_URL`
   - `DATABASE_URL_SYNC`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `MISTRAL_API_KEY`
3. Deploy. Production deployments trigger automatically on push to `main` or via CLI (`vercel --prod`).

_No production URL is live yet — this section documents the deploy path,
not a working demo link. Once deployed, add the URL to_ **§ 4. How do I try
it?** _above._

## Team

Built in 24 hours for The Atlassian x Mistral x AISoc Hack by:

- Tinnapat Plangsri
- Changrila Souksamlane
- duy mỹ
- NattakritPitayasiri

See the [Devpost submission](https://devpost.com/software/conve) for the full write-up (inspiration, challenges, accomplishments, what's next).
