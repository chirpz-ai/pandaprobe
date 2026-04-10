# PandaProbe Frontend Dashboard — Agent Prompt

## 1. Project Overview

PandaProbe is an open-source agent engineering platform (tracing, evaluation, and monitoring for LLM-powered applications). The codebase is a **monorepo** with this structure:

```
pandaprobe/
├── backend/          # Python FastAPI service (API, workers, DB)
├── docs/             # Documentation site (MDX)
├── frontend/         # << YOU WILL CREATE THIS >>
├── docker-compose.dev.yml
├── docker-compose.test.yml
├── Makefile          # Monorepo orchestration (delegates to sub-Makefiles)
├── README.md
└── ...
```

The `backend/` is a fully built FastAPI application with PostgreSQL, Redis, and Celery. Your job is to build the `frontend/` directory from scratch — the dashboard that consumes the backend API.

**CRITICAL FIRST STEP**: Before writing any code, you MUST thoroughly read and understand the entire backend API layer. Start by reading these files in this order:

1. `backend/app/api/v1/router.py` — router structure and sub-router registration order
2. `backend/app/api/dependencies.py` — authentication dependencies (`get_api_context`, `get_data_plane_context`, `require_project`)
3. `backend/app/api/context.py` — `ApiContext` and `AuthMethod` types
4. `backend/app/registry/constants.py` — all enums used across the API
5. `backend/app/registry/settings.py` — `AUTH_ENABLED`, `AUTH_PROVIDER`, `ALLOWED_ORIGINS`
6. `backend/app/api/v1/schemas.py` — shared `PaginatedResponse[T]` schema
7. Every route file in `backend/app/api/v1/routes/` — read each one completely to understand every endpoint, request/response model, query parameter, and auth requirement

Only after you have a complete mental model of the API should you begin designing the frontend architecture.

---

## 2. Backend API Reference

The FastAPI app serves all routes at the root (no `/api/v1` prefix). The OpenAPI schema is available at `GET /openapi.json`. Documentation UIs are at `/docs` (Swagger), `/redoc`, and `/scalar`.

### 2.1 Authentication Model

The backend has two auth layers that the frontend must understand:

**Bearer JWT (management routes)**: All management endpoints use `get_api_context` which requires an `Authorization: Bearer <token>` header. The token comes from the external identity provider (Firebase or Supabase). When the token is verified, the backend upserts the user and JIT-provisions an organization + subscription if it's the user's first sign-in.

**API Key (data-plane routes)**: Data-plane endpoints (`traces`, `sessions`, `evaluations`) use `require_project` which accepts either Bearer JWT + `X-Project-ID` header, or `X-API-Key` + `X-Project-Name` header. The dashboard will use the Bearer JWT path for these.

**`AUTH_ENABLED` toggle**: When `AUTH_ENABLED=false` (development only), the backend accepts requests without any Bearer token. The frontend must detect this and skip Firebase authentication entirely. More details in Section 7.

### 2.2 Common Headers

All management API calls from the dashboard must include:
- `Authorization: Bearer <firebase-id-token>` (when auth is enabled)
- `X-Organization-ID: <uuid>` (optional, to target a specific org when the user belongs to multiple)
- `Content-Type: application/json`

Data-plane calls from the dashboard must include:
- `Authorization: Bearer <firebase-id-token>`
- `X-Project-ID: <uuid>` (to scope to a specific project)

### 2.3 Common Response Pattern

List endpoints return a paginated wrapper:

```typescript
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
```

### 2.4 Complete Endpoint Inventory

Below is every endpoint the frontend client layer must support. Auth column indicates which dependency the backend uses.

#### Health (Public)

| Method | Path | Response | Auth |
|--------|------|----------|------|
| GET | `/health` | `{ status: string }` | None |

#### User Profile (JWT)

| Method | Path | Response |
|--------|------|----------|
| GET | `/user` | `UserProfileResponse` — id, external_id, email, display_name, created_at, organizations list |

#### Organizations (JWT)

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/organizations` | `{ name }` | `OrganizationResponse` |
| GET | `/organizations` | — | `MyOrganizationResponse[]` (includes role) |
| GET | `/organizations/{org_id}` | — | `OrganizationResponse` |
| PATCH | `/organizations/{org_id}` | `{ name }` | `OrganizationResponse` |
| DELETE | `/organizations/{org_id}` | — | 204 |
| GET | `/organizations/{org_id}/members` | — | `MembershipResponse[]` |
| POST | `/organizations/{org_id}/members` | `{ email, role }` | `MembershipResponse` |
| PATCH | `/organizations/{org_id}/members/{user_id}` | `{ role }` | `MembershipResponse` |
| DELETE | `/organizations/{org_id}/members/{user_id}` | — | 204 |

#### Projects (JWT, scoped to org)

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/organizations/{org_id}/projects` | `{ name, description? }` | `ProjectResponse` |
| GET | `/organizations/{org_id}/projects` | — | `ProjectResponse[]` |
| GET | `/organizations/{org_id}/projects/{project_id}` | — | `ProjectResponse` |
| PATCH | `/organizations/{org_id}/projects/{project_id}` | `{ name?, description? }` | `ProjectResponse` |
| DELETE | `/organizations/{org_id}/projects/{project_id}` | — | 204 |

#### API Keys (JWT, scoped to org)

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/organizations/{org_id}/api-keys` | `{ name, expiration? }` | `APIKeyResponse` (includes raw key on creation only) |
| GET | `/organizations/{org_id}/api-keys` | — | `APIKeyResponse[]` |
| GET | `/organizations/{org_id}/api-keys/{key_id}` | — | `APIKeyResponse` |
| POST | `/organizations/{org_id}/api-keys/{key_id}/rotate` | — | `APIKeyResponse` |
| DELETE | `/organizations/{org_id}/api-keys/{key_id}` | `?permanent=bool` | 204 |

#### Subscriptions & Billing (JWT)

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/subscriptions` | — | `SubscriptionResponse` |
| GET | `/subscriptions/usage` | — | `UsageResponse` |
| GET | `/subscriptions/billing` | — | `BillingResponse` (overage breakdown) |
| GET | `/subscriptions/invoices?limit=` | — | `UsageHistoryItem[]` |
| GET | `/subscriptions/plans` | — | `PlanInfo[]` |
| POST | `/subscriptions/checkout` | `{ plan, success_url, cancel_url }` | `{ checkout_url }` |
| POST | `/subscriptions/portal` | `{ return_url }` | `{ portal_url }` |

#### Traces (JWT + X-Project-ID)

| Method | Path | Body | Response | Query |
|--------|------|------|----------|-------|
| POST | `/traces` | `TraceCreate` | `TraceAccepted` (202) | — |
| GET | `/traces` | — | `PaginatedResponse<TraceListItem>` | limit, offset, session_id, status, user_id, tags, name, started_after, started_before, sort_by, sort_order |
| GET | `/traces/analytics` | — | `AnalyticsBucket[] \| TokenCostBucket[] \| TopModel[]` | metric (required), granularity, started_after (required), started_before (required) |
| GET | `/traces/users` | — | `PaginatedResponse<UserSummary>` | limit, offset |
| POST | `/traces/batch/delete` | `{ trace_ids }` | `BatchDeleteResponse` | — |
| POST | `/traces/batch/tags` | `{ trace_ids, add_tags?, remove_tags? }` | `BatchTagsResponse` | — |
| GET | `/traces/{trace_id}` | — | `TraceResponse` (includes full span tree) | — |
| PATCH | `/traces/{trace_id}` | `TraceUpdate` | `TraceResponse` | — |
| DELETE | `/traces/{trace_id}` | — | 204 | — |
| POST | `/traces/{trace_id}/spans` | `SpanCreate[]` (1-500) | `SpansAccepted` (201) | — |
| PATCH | `/traces/{trace_id}/spans/{span_id}` | `SpanUpdate` | `SpanResponse` | — |

#### Sessions (JWT + X-Project-ID)

| Method | Path | Response | Query |
|--------|------|----------|-------|
| GET | `/sessions` | `PaginatedResponse<SessionSummary>` | limit, offset, user_id, has_error, started_after, started_before, tags, query, sort_by, sort_order |
| GET | `/sessions/analytics` | `SessionAnalyticsBucket[]` | granularity, started_after (required), started_before (required) |
| GET | `/sessions/{session_id}` | `SessionDetail` (includes paginated traces) | limit, offset |
| DELETE | `/sessions/{session_id}` | `SessionDeleteResponse` | — |

#### Evaluations (JWT + X-Project-ID)

**Metric Discovery**

| Method | Path | Response |
|--------|------|----------|
| GET | `/evaluations/providers` | `ProviderInfo[]` |
| GET | `/evaluations/trace-metrics` | `MetricSummary[]` |
| GET | `/evaluations/session-metrics` | `MetricSummary[]` |

**Trace Eval Runs**

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/evaluations/trace-runs/template?metric=` | — | `EvalRunTemplate` |
| POST | `/evaluations/trace-runs` | `CreateEvalRunRequest` | `EvalRunResponse` (202) |
| POST | `/evaluations/trace-runs/batch` | `CreateBatchEvalRunRequest` | `EvalRunResponse` (202) |
| GET | `/evaluations/trace-runs` | — | `PaginatedResponse<EvalRunResponse>` |
| GET | `/evaluations/trace-runs/{run_id}` | — | `EvalRunResponse` |
| DELETE | `/evaluations/trace-runs/{run_id}?delete_scores=` | — | 204 |
| POST | `/evaluations/trace-runs/{run_id}/retry` | — | `EvalRunResponse` (202) |
| GET | `/evaluations/trace-runs/{run_id}/scores` | — | `TraceScoreResponse[]` |

**Trace Scores**

| Method | Path | Body | Response | Query |
|--------|------|------|----------|-------|
| POST | `/evaluations/trace-scores` | `CreateTraceScoreRequest` | `TraceScoreResponse` (201) | — |
| GET | `/evaluations/trace-scores` | — | `PaginatedResponse<TraceScoreResponse>` | trace_id, name, source, status, data_type, eval_run_id, environment, date_from, date_to, limit, offset |
| GET | `/evaluations/trace-scores/{trace_id}` | — | `TraceScoreResponse[]` | — |
| PATCH | `/evaluations/trace-scores/{score_id}` | `UpdateTraceScoreRequest` | `TraceScoreResponse` | — |
| DELETE | `/evaluations/trace-scores/{score_id}` | — | 204 | — |

**Trace Score Analytics**

| Method | Path | Response | Query |
|--------|------|----------|-------|
| GET | `/evaluations/analytics/trace-scores/summary` | `ScoreSummaryItem[]` | date_from, date_to |
| GET | `/evaluations/analytics/trace-scores/trend` | `ScoreTrendItem[]` | metric_name (required), date_from, date_to, granularity |
| GET | `/evaluations/analytics/trace-scores/distribution` | `ScoreDistributionItem[]` | metric_name (required), date_from, date_to, buckets |

**Session Eval Runs**

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/evaluations/session-runs` | `CreateSessionEvalRunRequest` | `EvalRunResponse` (202) |
| POST | `/evaluations/session-runs/batch` | `CreateBatchSessionEvalRunRequest` | `EvalRunResponse` (202) |
| GET | `/evaluations/session-runs` | — | `PaginatedResponse<EvalRunResponse>` |
| GET | `/evaluations/session-runs/{run_id}` | — | `EvalRunResponse` |
| DELETE | `/evaluations/session-runs/{run_id}?delete_scores=` | — | 204 |
| POST | `/evaluations/session-runs/{run_id}/retry` | — | `EvalRunResponse` (202) |
| GET | `/evaluations/session-runs/{run_id}/scores` | — | `SessionScoreResponse[]` |

**Session Scores**

| Method | Path | Response | Query |
|--------|------|----------|-------|
| GET | `/evaluations/session-scores` | `PaginatedResponse<SessionScoreResponse>` | session_id, name, source, status, eval_run_id, date_from, date_to, limit, offset |
| GET | `/evaluations/session-scores/{session_id}` | `SessionScoreResponse[]` | — |
| DELETE | `/evaluations/session-scores/{score_id}` | 204 | — |

**Session Score Analytics**

| Method | Path | Response | Query |
|--------|------|----------|-------|
| GET | `/evaluations/analytics/session-scores/summary` | `ScoreSummaryItem[]` | date_from, date_to |
| GET | `/evaluations/analytics/session-scores/trend` | `ScoreTrendItem[]` | metric_name (required), date_from, date_to, granularity |
| GET | `/evaluations/analytics/session-scores/distribution` | `ScoreDistributionItem[]` | metric_name (required), date_from, date_to, buckets |
| GET | `/evaluations/analytics/session-scores/history/{session_id}` | `SessionScoreHistoryItem[]` | metric_name, limit |
| GET | `/evaluations/analytics/session-scores/comparison` | `PaginatedResponse<SessionComparisonItem>` | metric_name (required), sort_order, limit, offset |

**Monitors**

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/evaluations/monitors` | `CreateMonitorRequest` | `MonitorResponse` (201) |
| GET | `/evaluations/monitors` | — | `PaginatedResponse<MonitorResponse>` |
| GET | `/evaluations/monitors/{monitor_id}` | — | `MonitorResponse` |
| PATCH | `/evaluations/monitors/{monitor_id}` | `UpdateMonitorRequest` | `MonitorResponse` |
| DELETE | `/evaluations/monitors/{monitor_id}` | — | 204 |
| POST | `/evaluations/monitors/{monitor_id}/pause` | — | `MonitorResponse` |
| POST | `/evaluations/monitors/{monitor_id}/resume` | — | `MonitorResponse` |
| POST | `/evaluations/monitors/{monitor_id}/trigger` | — | `EvalRunResponse` (202) |
| GET | `/evaluations/monitors/{monitor_id}/runs` | — | `PaginatedResponse<EvalRunResponse>` |

#### Webhooks (Internal — not consumed by frontend)

`POST /webhooks/stripe` is for Stripe webhook delivery. The frontend does NOT call this.

### 2.5 Key Enums (from `backend/app/registry/constants.py`)

Your TypeScript types must mirror these exactly:

| Enum | Values |
|------|--------|
| SpanKind | AGENT, TOOL, LLM, RETRIEVER, CHAIN, EMBEDDING, OTHER |
| SpanStatusCode | UNSET, OK, ERROR |
| TraceStatus | PENDING, RUNNING, COMPLETED, ERROR |
| EvaluationStatus | PENDING, RUNNING, COMPLETED, FAILED |
| ScoreSource | AUTOMATED, ANNOTATION, PROGRAMMATIC |
| ScoreStatus | SUCCESS, FAILED, PENDING |
| ScoreDataType | NUMERIC, BOOLEAN, CATEGORICAL |
| MembershipRole | OWNER, ADMIN, MEMBER |
| TraceSortBy | started_at, ended_at, name, latency, status |
| SortOrder | asc, desc |
| AnalyticsMetric | volume, errors, latency, cost, tokens, models |
| SessionSortBy | recent, trace_count, latency, cost |
| AnalyticsGranularity | hour, day, week |
| MonitorStatus | ACTIVE, PAUSED |
| MonitorCadence | every_6h, daily, weekly, custom |
| SubscriptionPlan | HOBBY, PRO, STARTUP, ENTERPRISE, DEVELOPMENT |
| SubscriptionStatus | ACTIVE, PAST_DUE, CANCELED, INCOMPLETE |

---

## 3. Framework & Tooling

### 3.1 Project Initialization

Use the official Vercel CLI to scaffold the Next.js project:

```bash
cd pandaprobe/
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --use-yarn
```

This creates `frontend/` with Next.js 15+ (App Router), TypeScript, Tailwind CSS, and ESLint pre-configured with yarn as the package manager.

### 3.2 Required Dependencies

After scaffolding, install these additional packages:

```bash
cd frontend/
yarn add axios class-variance-authority @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-tabs @radix-ui/react-tooltip @radix-ui/react-select @radix-ui/react-switch @radix-ui/react-popover @radix-ui/react-separator @radix-ui/react-slot @radix-ui/react-avatar @radix-ui/react-toast lucide-react clsx tailwind-merge firebase
yarn add -D @types/node
```

### 3.3 Technology Stack Summary

| Concern | Choice |
|---------|--------|
| Framework | Next.js 15+ (App Router) |
| Language | TypeScript (strict mode) |
| Package Manager | yarn |
| Styling | Tailwind CSS v4 (or v3 with PostCSS) + CVA for component variants |
| UI Primitives | Radix UI (headless, unstyled) |
| Icons | Lucide React |
| HTTP Client | Axios |
| Auth | Firebase SDK (when auth enabled) |
| Architecture | Atomic Design (atoms, molecules, organisms) |

---

## 4. Global Theme & Design System

Implement a **fixed dark theme** with a high-end "Tech/Engineering" aesthetic. There is no light mode. There is no theme toggle.

### 4.1 CSS Variables

Create `frontend/src/styles/theme.css` (imported in your global CSS) with CSS custom properties. **No component may use hardcoded hex values** — always reference these variables.

```css
@import "tailwindcss";

/* ─── Design Tokens ────────────────────────────────────────────────────────── */
@theme inline {
  /* Fonts */
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);

  /* Backgrounds */
  --color-bg:         #18191b;
  --color-surface:    #1f2022;
  --color-surface-hi: #252628;

  /* Borders */
  --color-border:     #2d2e30;
  --color-border-hi:  #3a3b3e;

  /* Typography */
  --color-text:       #d1d5db;
  --color-text-dim:   #6b7280;
  --color-text-muted: #4b5563;

  /* Accents */
  --color-accent:     #e5e7eb;
  --color-primary:    #ffffff;

  /* Radius — sharp everywhere */
  --radius:           0px;
  --radius-sm:        0px;
  --radius-md:        0px;
  --radius-lg:        0px;
  --radius-xl:        0px;
  --radius-full:      0px;

  /* Animations */
  --animate-fade-in:  fadeIn 0.4s ease-out forwards;
  --animate-slide-up: slideUp 0.4s ease-out forwards;
}

/* ─── Keyframes ────────────────────────────────────────────────────────────── */
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ─── Base ─────────────────────────────────────────────────────────────────── */
@layer base {
  *,
  *::before,
  *::after {
    box-sizing: border-box;
    border-radius: 0 !important;
  }

  html {
    scroll-behavior: smooth;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  body {
    background-color: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-mono), "JetBrains Mono", "Fira Code", monospace;
    line-height: 1.6;
  }

  ::selection {
    background-color: rgba(255, 255, 255, 0.15);
    color: var(--color-primary);
  }

  ::-webkit-scrollbar        { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track  { background: var(--color-bg); }
  ::-webkit-scrollbar-thumb  { background: var(--color-border-hi); }
  ::-webkit-scrollbar-thumb:hover { background: var(--color-text-muted); }
}

/* ─── Components ────────────────────────────────────────────────────────────── */
@layer components {
  /* Engraved card border — 1px border + subtle inner highlight */
  .border-engraved {
    border: 1px solid var(--color-border);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.04),
      0 0 0 1px rgba(255, 255, 255, 0.02);
  }

  /* Dot-grid background */
  .bg-dot-grid {
    background-image:
      radial-gradient(circle, var(--color-border) 1px, transparent 1px);
    background-size: 28px 28px;
  }

  /* Hero radial glow */
  .bg-hero-glow {
    background-image: radial-gradient(
      ellipse 80% 60% at 50% -5%,
      rgba(255, 255, 255, 0.05) 0%,
      transparent 70%
    );
  }

  /* Syntax token helpers for CodeBlock */
  .token-keyword     { color: #c792ea; }
  .token-string      { color: #c3e88d; }
  .token-comment     { color: var(--color-text-dim); font-style: italic; }
  .token-function    { color: #82aaff; }
  .token-number      { color: #f78c6c; }
  .token-operator    { color: #89ddff; }
  .token-punctuation { color: var(--color-text-dim); }
  .token-param       { color: #ffcb6b; }
  .token-class       { color: #ffcb6b; }
}

/* ─── Utilities ─────────────────────────────────────────────────────────────── */
@layer utilities {
  /* Layout width tokens — single source of truth for section/prose widths */
  .section-container { max-width: 1100px; margin-inline: auto; }
  .prose-limit       { max-width: 1050px; }

  .text-gradient {
    background: linear-gradient(135deg, #ffffff 0%, #9ca3af 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .animate-delay-100 { animation-delay: 100ms; }
  .animate-delay-200 { animation-delay: 200ms; }
  .animate-delay-300 { animation-delay: 300ms; }
  .animate-delay-400 { animation-delay: 400ms; }
}
```

### 4.2 Typography

Use a monospaced or highly geometric font for the techy feel. Install `geist` font package (`yarn add geist`) and configure it in `layout.tsx`. Use `--font-mono` for headings, code, and data displays. Use `--font-sans` for body text and UI labels. Text color defaults to `--text-primary` (#D1D5DB light gray/slate).

### 4.3 Component Aesthetic Rules

- **Border radius**: 0px everywhere. No rounded corners on buttons, cards, inputs, modals, or any component. `border-radius: var(--radius-none)`.
- **Borders**: Use thin, high-contrast borders (`1px solid var(--border-default)`) to define sections and cards.
- **Backgrounds**: Layer surfaces using `--bg-primary` → `--bg-secondary` → `--bg-elevated` → `--bg-surface` for visual depth.
- **No shadows**: Use border contrast instead of box-shadow for depth.
- **Transitions**: Subtle, fast (150ms) for hover/focus states.

---

## 5. Frontend Architecture

### 5.1 Directory Structure
below is a viable directory srructured. however, you have full flexibility to design it from scratch by youself and based on best practices.

```
frontend/src/
├── app/                          # Next.js App Router pages
│   ├── layout.tsx                # Root layout (font loading, theme, providers)
│   ├── page.tsx                  # Landing / redirect to dashboard
│   ├── (auth)/                   # Auth route group (no sidebar)
│   │   ├── login/page.tsx
│   │   └── layout.tsx
│   └── (dashboard)/              # Dashboard route group (sidebar layout)
│       ├── layout.tsx            # Sidebar + main content shell
│       ├── page.tsx              # Dashboard home / overview
│       ├── traces/
│       │   ├── page.tsx          # Trace list with filters
│       │   └── [traceId]/page.tsx # Trace detail (span tree view)
│       ├── sessions/
│       │   ├── page.tsx          # Session list
│       │   └── [sessionId]/page.tsx
│       ├── evaluations/
│       │   ├── page.tsx          # Eval overview (runs, scores)
│       │   ├── trace-runs/page.tsx
│       │   ├── session-runs/page.tsx
│       │   └── monitors/page.tsx
│       ├── analytics/
│       │   └── page.tsx          # Charts (trace volume, latency, cost, scores)
│       └── settings/
│           ├── page.tsx          # Settings overview / redirect
│           ├── organization/page.tsx
│           ├── members/page.tsx
│           ├── projects/page.tsx
│           ├── api-keys/page.tsx
│           └── billing/page.tsx
├── components/
│   ├── atoms/                    # Smallest building blocks
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Badge.tsx
│   │   ├── Spinner.tsx
│   │   ├── Icon.tsx
│   │   └── ...
│   ├── molecules/                # Composed from atoms
│   │   ├── SearchBar.tsx
│   │   ├── DateRangePicker.tsx
│   │   ├── Pagination.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── ConfirmDialog.tsx
│   │   └── ...
│   ├── organisms/                # Complex, feature-specific
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx
│   │   ├── TraceTable.tsx
│   │   ├── SpanTreeView.tsx
│   │   ├── SessionTable.tsx
│   │   ├── EvalRunTable.tsx
│   │   ├── MonitorCard.tsx
│   │   ├── UsageChart.tsx
│   │   ├── MemberList.tsx
│   │   ├── ApiKeyList.tsx
│   │   └── ...
│   └── providers/                # React context providers
│       ├── AuthProvider.tsx
│       ├── OrganizationProvider.tsx
│       ├── ProjectProvider.tsx
│       └── ToastProvider.tsx
├── lib/
│   ├── api/                      # API client layer
│   │   ├── client.ts             # Axios instance with interceptors
│   │   ├── types.ts              # TypeScript types mirroring backend schemas
│   │   ├── enums.ts              # TypeScript enums mirroring backend constants
│   │   ├── health.ts             # Health check API
│   │   ├── user.ts               # User profile API
│   │   ├── organizations.ts      # Organization + members CRUD
│   │   ├── projects.ts           # Project CRUD
│   │   ├── api-keys.ts           # API key management
│   │   ├── subscriptions.ts      # Subscriptions, billing, plans, checkout
│   │   ├── traces.ts             # Traces, spans, analytics, batch ops
│   │   ├── sessions.ts           # Sessions, analytics
│   │   └── evaluations.ts        # Eval runs, scores, analytics, monitors
│   ├── auth/
│   │   ├── firebase.ts           # Firebase SDK initialization
│   │   ├── auth-service.ts       # Sign-in, sign-out, token refresh, session mgmt
│   │   └── auth-guard.tsx        # Route protection HOC / component
│   └── utils/
│       ├── cn.ts                 # clsx + tailwind-merge utility
│       ├── format.ts             # Date, duration, cost formatting
│       └── constants.ts          # Frontend-specific constants
├── hooks/
│   ├── useAuth.ts                # Auth state hook (from AuthProvider)
│   ├── useOrganization.ts        # Current org context hook
│   ├── useProject.ts             # Current project context hook
│   ├── useApi.ts                 # Generic data fetching hook with loading/error
│   └── usePagination.ts          # Pagination state management
├── styles/
│   ├── globals.css               # Tailwind directives + theme import
│   └── theme.css                 # CSS custom properties (Section 4.1)
└── middleware.ts                  # Next.js middleware for auth redirect
```

### 5.2 Architecture Principles

- **Separation of concerns**: API client layer (`lib/api/`) is completely independent of React. It exports pure async functions that return typed data. Components never call Axios directly.
- **Atomic Design**: atoms (Button, Input, Badge) compose into molecules (SearchBar, Pagination) compose into organisms (TraceTable, Sidebar). Pages assemble organisms.
- **Context for global state**: Use React Context for auth state, current organization, and current project. These are the three pieces of state that affect nearly every API call.
- **No global state library**: For this project's complexity, React Context + `useState`/`useReducer` is sufficient. Do not add Redux, Zustand, or Jotai.
- **Server components where possible**: Use Next.js server components for static layouts. Client components (`"use client"`) only where interactivity or browser APIs are needed.
- **Colocation**: Keep page-specific types and utilities close to the page. Only promote to `lib/` or `hooks/` when shared across multiple pages.

---

## 6. API Client Layer (Priority 1)

This is the **highest priority deliverable**. Build a complete, typed API client that wraps every backend endpoint.

### 6.1 Axios Instance (`lib/api/client.ts`)

Create a centralized Axios instance:

- **Base URL**: Read from `NEXT_PUBLIC_API_URL` environment variable.
- **Request interceptor**: Attach the Firebase ID token as `Authorization: Bearer <token>` on every request (except when `AUTH_ENABLED=false`). Also attach `X-Organization-ID` and `X-Project-ID` from the current context when available.
- **Response interceptor**: Handle 401 errors by attempting a token refresh. If refresh fails, redirect to login. Handle structured error responses from the backend (`{ detail: string }` for domain errors, `{ detail: string, errors: [...] }` for validation errors).
- **Token refresh on 401**: When receiving a 401, use Firebase's `getIdToken(true)` to force-refresh the token, retry the original request once. If it fails again, sign out.

### 6.2 Type Definitions (`lib/api/types.ts`)

Define TypeScript interfaces for every request and response model. Read each backend route file and transcribe every Pydantic model into a TypeScript interface. Key models include:

- `UserProfileResponse`, `OrganizationResponse`, `MyOrganizationResponse`, `MembershipResponse`
- `ProjectResponse`, `APIKeyResponse`
- `SubscriptionResponse`, `UsageResponse`, `BillingResponse`, `CategoryBreakdown`, `PlanInfo`
- `TraceCreate`, `TraceResponse`, `TraceListItem`, `SpanCreate`, `SpanResponse`
- `SessionSummary`, `SessionDetail`
- `EvalRunResponse`, `TraceScoreResponse`, `SessionScoreResponse`
- `MonitorResponse`, `MetricSummary`, `ProviderInfo`
- All analytics bucket types
- `PaginatedResponse<T>` generic

### 6.3 Enum Definitions (`lib/api/enums.ts`)

TypeScript enums matching the backend's `StrEnum` constants (see Section 2.5). Use `const enum` or string union types.

### 6.4 API Module Files

Each file in `lib/api/` exports functions for its domain. Example pattern:

```typescript
// lib/api/traces.ts
import { client } from './client';
import type { TraceCreate, TraceResponse, TraceListItem, PaginatedResponse } from './types';

export async function createTrace(data: TraceCreate): Promise<TraceResponse> {
  const res = await client.post('/traces', data);
  return res.data;
}

export async function listTraces(params: {
  limit?: number;
  offset?: number;
  status?: string;
  // ... all query params
}): Promise<PaginatedResponse<TraceListItem>> {
  const res = await client.get('/traces', { params });
  return res.data;
}

// ... every trace endpoint
```

Every single endpoint from Section 2.4 must have a corresponding typed function.

---

## 7. Authentication Layer

### 7.1 The `AUTH_ENABLED` Toggle

The backend has an `AUTH_ENABLED` setting. The frontend must have a corresponding environment variable:

```env
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_AUTH_ENABLED=true

# Firebase config (only needed when AUTH_ENABLED=true)
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
```

**When `NEXT_PUBLIC_AUTH_ENABLED=true`** (staging, production):
- Initialize Firebase SDK
- Show login page with Google sign-in and email/password sign-in
- Manage Firebase ID tokens and refresh tokens
- Attach Bearer token to all API calls
- Redirect unauthenticated users to `/login`

**When `NEXT_PUBLIC_AUTH_ENABLED=false`** (local development):
- Do NOT initialize Firebase SDK
- Skip the login page entirely — redirect straight to dashboard
- Make API calls WITHOUT an Authorization header (the backend's `DevelopmentAdapter` handles it)
- The backend auto-provisions a dev user on the first request via `GET /user`
- No token refresh, no sign-out button needed (though showing a "Dev Mode" indicator is good UX)

**Safety guard (mirrors backend):** The backend forces `AUTH_ENABLED=true` when `APP_ENV` is anything other than `development`. The frontend must implement the same pattern using Next.js's built-in `NODE_ENV` (which is `"development"` during `next dev` and `"production"` during `next build`/`next start`). If `NODE_ENV !== 'development'`, the frontend must force auth ON regardless of `NEXT_PUBLIC_AUTH_ENABLED` and log a console warning. There is no need for a separate `APP_ENV` variable in the frontend — `NODE_ENV` already serves this purpose. See the code example in Section 7.2 below.

### 7.2 Firebase Authentication (`lib/auth/firebase.ts`)

Initialize Firebase only when auth is enabled:

```typescript
import { initializeApp, type FirebaseApp } from 'firebase/app';
import { getAuth, type Auth } from 'firebase/auth';

// Safety guard: force auth ON in non-development environments, mirroring
// the backend's _apply_environment_settings behaviour.
const envFlag = process.env.NEXT_PUBLIC_AUTH_ENABLED !== 'false';
const AUTH_ENABLED =
  process.env.NODE_ENV !== 'development' ? true : envFlag;

if (!envFlag && AUTH_ENABLED) {
  console.warn(
    '[auth] NEXT_PUBLIC_AUTH_ENABLED=false is ignored outside development. Forcing auth ON.',
  );
}

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

if (AUTH_ENABLED) {
  app = initializeApp({
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    // ... other config
  });
  auth = getAuth(app);
}

export { app, auth, AUTH_ENABLED };
```

### 7.3 Auth Service (`lib/auth/auth-service.ts`)

Implement these operations:
- `signInWithGoogle()` — Firebase `signInWithPopup` with `GoogleAuthProvider`
- `signInWithEmail(email, password)` — Firebase `signInWithEmailAndPassword`
- `signUpWithEmail(email, password)` — Firebase `createUserWithEmailAndPassword`
- `signOut()` — Firebase `signOut`
- `getCurrentToken()` — returns the current ID token, refreshing if needed
- `onAuthStateChanged(callback)` — wrapper around Firebase's auth state observer

### 7.4 Token Refresh Strategy

Firebase ID tokens expire after 1 hour. Implement proactive refresh:
- Use Firebase's `onIdTokenChanged` listener to track token changes.
- Before each API call, call `user.getIdToken()` which automatically returns a cached token or refreshes if expired (Firebase SDK handles this internally).
- As a safety net, the Axios response interceptor catches 401s and forces a refresh via `user.getIdToken(true)`.
- Store the token in memory only (React state / ref). Do NOT store tokens in localStorage or cookies for security.
- Use the best industry practices to remove any friction for user and respect Firebase rate limits

### 7.5 Auth Provider (`components/providers/AuthProvider.tsx`)

A React context provider that:
- Listens to Firebase `onAuthStateChanged` and `onIdTokenChanged`
- Exposes `user`, `token`, `loading`, `signIn*`, `signOut` to the app
- When auth is disabled, immediately provides a mock "authenticated" state with no Firebase user
- On first load with auth enabled, shows a loading spinner while Firebase initializes

### 7.6 Route Protection

Use Next.js middleware (`middleware.ts`) to redirect:
- Unauthenticated users hitting `/(dashboard)/**` routes → `/login`
- Authenticated users hitting `/login` → `/(dashboard)`
- When auth is disabled, all routes are accessible (no redirects to login)

Additionally, the `(dashboard)/layout.tsx` should wrap content in an auth guard component that shows a loading state while auth is resolving.

---

## 8. Layout & Navigation

### 8.1 Sidebar

A collapsible sidebar (expanded/collapsed state persisted in localStorage) with these navigation groups:

**Main**
- Dashboard (home/overview icon)
- Traces (list icon)
- Sessions (layers icon)
- Evaluations (check-circle icon)
- Analytics (bar-chart icon)

**Management (under a "Settings" expandable section or separate area)**
- Organization
- Members
- Projects
- API Keys
- Billing

**Footer area**
- Org switcher (dropdown showing user's organizations)
- Project switcher (dropdown showing projects in current org)
- User avatar + sign out

The sidebar must show the PandaProbe logo at the top. When collapsed, show only icons with tooltips.

### 8.2 Top Bar

A top bar within the `(dashboard)/layout.tsx` that shows:
- Breadcrumbs for current page context
- Project selector (if on a data-plane page like traces/sessions/evaluations)
- Quick actions or search (can be a future enhancement — just reserve the space)

### 8.3 Organization and Project Context

The dashboard operates within a selected organization and project:
- **Organization**: Selected via sidebar org switcher or on first load (default to first org). Stored in `OrganizationProvider` context. Changes to org reload all data.
- **Project**: Required for traces/sessions/evaluations pages. Selected via a project dropdown. Stored in `ProjectProvider` context. The Axios interceptor reads from this context to set `X-Organization-ID` and `X-Project-ID` headers.

---

## 9. State Management

### 9.1 Context Providers (wrap in `app/layout.tsx`)

```
AuthProvider
  └── OrganizationProvider  (depends on auth — fetches orgs after login)
       └── ProjectProvider  (depends on org — fetches projects for current org)
            └── ToastProvider
                 └── {children}
```

### 9.2 Data Fetching Pattern

For pages that fetch data:
- Use React `useEffect` + `useState` for client-side fetches (most pages are interactive).
- Create a `useApi` hook that handles loading, error, and data states with a consistent pattern.
- For list pages, use a `usePagination` hook that manages limit/offset and integrates with URL search params.
- Refetching: provide a `refetch` function from the hook. Use it after mutations (create, update, delete).
- Do NOT use SWR or React Query — keep dependencies minimal. If caching is needed later, it can be added.

---

## 10. Environment Configuration

### 10.1 Frontend Environment File

Create `frontend/.env.local` (gitignored) and `frontend/.env.example` (committed):

```env
# frontend/.env.example

# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Set to "false" to disable authentication (must match backend AUTH_ENABLED)
NEXT_PUBLIC_AUTH_ENABLED=true

# Firebase Configuration (required when AUTH_ENABLED=true)
# Get these from Firebase Console → Project Settings → General → Your apps
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
NEXT_MEASUREMENT_ID=
```

### 10.2 Monorepo Makefile Refactor

The current top-level `Makefile` has generic targets (`install`, `dev`, `lint`, `format`) that delegate only to `backend/`. With the frontend added, the Makefile must be refactored so that:

1. **Targeted commands** exist for both backend and frontend independently (e.g., `make backend-dev`, `make frontend-dev`, `make backend-lint`, `make frontend-lint`).
2. **Generic commands** (`make install`, `make dev`, `make lint`, `make format`) run **both** backend and frontend together.
3. **Docker Compose commands** (`make up`, `make down`, `make logs`, etc.) continue to work as before but now include the new `frontend` service.
4. A new `logs-frontend` target is added alongside the existing `logs-app`, `logs-worker`, `logs-beat`.

Here is the structure the refactored `Makefile` should follow (adapt to match the existing style):

```makefile
# -- Backend targets ----------------------------------------------------------
backend-install:  ## Install backend dependencies
	$(MAKE) -C backend install

backend-dev:  ## Run the backend API server locally
	$(MAKE) -C backend dev

backend-worker:  ## Run the backend Celery worker locally
	$(MAKE) -C backend worker

backend-lint:  ## Run backend linter
	$(MAKE) -C backend lint

backend-format:  ## Auto-format backend code
	$(MAKE) -C backend format

# -- Frontend targets ---------------------------------------------------------
frontend-install:  ## Install frontend dependencies
	$(MAKE) -C frontend install

frontend-dev:  ## Run the frontend dev server locally
	$(MAKE) -C frontend dev

frontend-build:  ## Build frontend for production
	$(MAKE) -C frontend build

frontend-lint:  ## Run frontend linter
	$(MAKE) -C frontend lint

# -- Combined targets (both backend + frontend) ------------------------------
install:  ## Install all dependencies (backend + frontend)
	$(MAKE) backend-install
	$(MAKE) frontend-install

dev:  ## Run both backend API server and frontend dev server locally
	$(MAKE) backend-dev &
	$(MAKE) frontend-dev

lint:  ## Run all linters (backend + frontend)
	$(MAKE) backend-lint
	$(MAKE) frontend-lint

format:  ## Auto-format all code
	$(MAKE) backend-format

# -- Docker Compose (includes frontend service) ------------------------------
logs-frontend:  ## Tail frontend logs only
	docker compose -f docker-compose.dev.yml logs -f frontend
```

The existing `migration`, `migrate`, `worker` targets remain backend-only (no frontend equivalent needed).

Create `frontend/Makefile`:

```makefile
.PHONY: install dev build lint

install:  ## Install dependencies
	yarn install

dev:  ## Start Next.js dev server
	yarn dev

build:  ## Production build
	yarn build

lint:  ## Run ESLint
	yarn lint
```

### 10.3 Docker Compose — Add Frontend Service

Add a `frontend` service to `docker-compose.dev.yml`. The frontend container must:

- Use `context: ./frontend` as the build context. Create a `frontend/Dockerfile` that installs dependencies and runs `yarn dev` (dev mode with hot reload).
- Map port `3000:3000`.
- Mount `./frontend/src` into the container for live reload.
- Load environment variables from `./frontend/.env.local` (or use the `environment` section to pass `NEXT_PUBLIC_API_URL=http://app:8000` pointing to the backend's Docker service name).
- Depend on the `app` service (so the backend starts first).
- Join the `pandaprobe` network.

Here is the service definition to add to `docker-compose.dev.yml`:

```yaml
  # ---------- Next.js frontend ----------
  frontend:
    build:
      context: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/public:/app/public
    environment:
      - NEXT_PUBLIC_API_URL=http://app:8000
      - NEXT_PUBLIC_AUTH_ENABLED=${AUTH_ENABLED:-true}
    restart: on-failure
    depends_on:
      app:
        condition: service_healthy
    networks:
      - pandaprobe
```

Create `frontend/Dockerfile` for development:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile
COPY . .
EXPOSE 3000
CMD ["yarn", "dev"]
```

CORS is already configured in the backend — `http://localhost:3000` is included in the default `ALLOWED_ORIGINS` in `settings.py`.

---

## 11. Testing

### 11.1 Unit Tests

Set up testing with the tools that come with `create-next-app` or add:

```bash
yarn add -D jest @testing-library/react @testing-library/jest-dom @testing-library/user-event jest-environment-jsdom
```

Write tests for:
- **API client functions**: Mock Axios and verify correct URL, method, headers, and params for each API function. This is the most important test coverage.
- **Auth service**: Test the auth-enabled vs auth-disabled branching, including the safety guard that forces auth ON in non-development environments.
- **Utility functions**: Format helpers, cn() utility.
- **Key components**: Test that organisms render correctly with mock data.

### 11.2 Integration / E2E Tests

Set up Playwright for integration and end-to-end testing:

```bash
yarn add -D @playwright/test
npx playwright install --with-deps
```

Create a `playwright.config.ts` at the frontend root. The integration tests should cover the following critical flows:

- **Auth flow (auth enabled)**: Login page renders → Google sign-in button is present → email/password form works → successful login redirects to dashboard → sign-out returns to login.
- **Auth flow (auth disabled)**: Landing on `/` immediately redirects to dashboard without a login page → API calls succeed without an Authorization header → "Dev Mode" indicator is visible.
- **Navigation**: Sidebar renders all navigation groups → clicking each link navigates to the correct page → sidebar collapse/expand works.
- **CRUD flows**: For key resources (projects, API keys, traces), test the full create → list → view detail → delete cycle using the real API client against a running backend (or a mock server via MSW for isolated CI).
- **Error states**: Verify that API errors (401, 403, 404, 500) are handled gracefully with user-friendly messages.
- **Responsive layout**: Verify the sidebar collapses on smaller viewports.

For CI environments where a real backend is not available, use [MSW (Mock Service Worker)](https://mswjs.io/) to intercept network requests:

```bash
yarn add -D msw
```

Create mock handlers in `frontend/src/__mocks__/handlers.ts` that return realistic responses matching the backend's API schemas defined in Section 2.

### 11.3 Test Structure

```
frontend/src/__tests__/
├── lib/
│   ├── api/         # One test file per API module (unit)
│   └── auth/        # Auth service tests (unit)
├── components/      # Component tests (unit)
└── hooks/           # Hook tests (unit)

frontend/e2e/
├── auth.spec.ts     # Auth flow E2E tests
├── navigation.spec.ts
├── projects.spec.ts
├── traces.spec.ts
└── api-keys.spec.ts
```

Add test targets to `frontend/Makefile`:

```makefile
test-unit:  ## Run unit tests
	yarn jest

test-e2e:  ## Run Playwright E2E tests
	yarn playwright test

test:  ## Run all tests
	$(MAKE) test-unit
	$(MAKE) test-e2e
```

And corresponding targets in the root `Makefile`:

```makefile
frontend-test-unit:  ## Run frontend unit tests
	$(MAKE) -C frontend test-unit

frontend-test-e2e:  ## Run frontend E2E tests
	$(MAKE) -C frontend test-e2e

frontend-test:  ## Run all frontend tests
	$(MAKE) -C frontend test
```

Update the root `test-unit` and `test-all` targets to include frontend:

```makefile
test-unit:  ## Run all unit tests (backend + frontend)
	$(MAKE) test-unit-backend
	$(MAKE) frontend-test-unit

test-all:  ## Run all unit + integration + E2E tests
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) frontend-test-e2e
```

---

## 12. Security Best Practices

- **Tokens in memory only**: Never store Firebase tokens in localStorage, sessionStorage, or cookies. Keep them in React state/ref. The Firebase SDK manages its own persistence securely.
- **CSRF**: Since the API uses Bearer tokens (not cookies), CSRF is not a concern for API calls.
- **XSS**: Use React's built-in escaping. Never use `dangerouslySetInnerHTML` with user-supplied content. Sanitize any rich text before rendering.
- **Environment variables**: All `NEXT_PUBLIC_*` variables are exposed to the browser. Never put secret keys in `NEXT_PUBLIC_*` variables. Firebase client config is safe to expose (it's designed to be public). Backend secrets must never be in the frontend.
- **CORS**: The backend already restricts origins. The frontend must call the backend from the correct origin.
- **Input validation**: Validate user inputs on the frontend before sending to the API. Mirror the backend's validation rules (e.g., resource names: alphanumeric + spaces/hyphens, 1-255 chars).
- **Error handling**: Never expose raw error stack traces to users. Show user-friendly messages. Log detailed errors to the console in development only.
- **Iframing**: make sure to apply proper restrictions to prevent allowing i-framing etc.

---

## 13. Execution Order

Follow this exact order of implementation:

### Phase 1: Foundation
1. Scaffold the Next.js project with `create-next-app`
2. Install all dependencies
3. Set up the theme (`theme.css`, globals, font loading)
4. Create `frontend/.env.example` and `frontend/Dockerfile`
5. Create `frontend/Makefile`, refactor the root `Makefile` (Section 10.2), and add the frontend service to `docker-compose.dev.yml` (Section 10.3)
6. Set up the `cn()` utility and base atom components (Button, Input, Badge, Spinner)

### Phase 2: API Client Layer (HIGHEST PRIORITY)
7. Create `lib/api/enums.ts` with all TypeScript enums
8. Create `lib/api/types.ts` with all TypeScript interfaces
9. Create `lib/api/client.ts` with the Axios instance and interceptors
10. Create every API module file (`user.ts`, `organizations.ts`, `projects.ts`, `api-keys.ts`, `subscriptions.ts`, `traces.ts`, `sessions.ts`, `evaluations.ts`, `health.ts`)
11. Write unit tests for the API client layer

### Phase 3: Authentication
12. Create `lib/auth/firebase.ts` with conditional initialization
13. Create `lib/auth/auth-service.ts` with all auth operations
14. Create `components/providers/AuthProvider.tsx`
15. Create the login page (`(auth)/login/page.tsx`)
16. Create `middleware.ts` for route protection

### Phase 4: Layout & Navigation
17. Create the sidebar organism with navigation groups
18. Create org switcher and project switcher molecules
19. Create `components/providers/OrganizationProvider.tsx` and `ProjectProvider.tsx`
20. Create the `(dashboard)/layout.tsx` shell (sidebar + top bar + content area)
21. Wire up provider nesting in `app/layout.tsx`

### Phase 5: Pages (Skeleton)
22. Build page skeletons for every route in the `(dashboard)` group
23. Connect each page to its corresponding API client functions
24. Implement data tables with pagination for list views
25. Implement detail views for traces, sessions, eval runs

### Phase 6: Integration & E2E Tests
26. Set up Playwright and MSW
27. Write E2E tests for auth flows (enabled and disabled)
28. Write E2E tests for navigation and key CRUD flows

### Phase 7: Polish
29. Add loading states, error states, empty states to all pages
30. Implement toast notifications for mutations (create, update, delete)
31. Add the "Dev Mode" indicator when auth is disabled
32. Run lints and fix all issues
33. Verify the complete flow: login → dashboard → navigate all pages → sign out
