# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The repo-wide `CLAUDE.md` at the project root covers monorepo layout, the two-plane API model, backend architecture, and a high-level frontend overview. This file adds the frontend-specific details that are easy to get wrong without reading several files.

## Commands

All targets are exposed at the repo root (`make frontend-*`) and as host-side targets in `frontend/Makefile`. From inside `frontend/`:

| Goal | Command |
|---|---|
| Install (locked) | `yarn install --frozen-lockfile` |
| Dev server (host) | `yarn dev` — runs Next.js on `:3000` against `NEXT_PUBLIC_API_URL` |
| Production build | `yarn build` (uses `output: "standalone"` from `next.config.ts`) |
| Lint / autofix | `yarn lint` / `yarn lint:fix` |
| Type check | `yarn typecheck` (`tsc --noEmit`) |
| Format | `yarn format` (write) / `yarn format:check` (CI gate) |
| Unit tests | `yarn test` (Jest + jsdom) |
| Single Jest test | `yarn test src/__tests__/lib/api/traces.test.ts` (or pass `-t "name"`) |
| E2E (Playwright) | `yarn playwright install --with-deps` once, then `yarn test:e2e` |

Playwright's `webServer` runs `yarn dev` on `:3000` and reuses an existing server outside CI — leaving `yarn dev` running while you iterate on E2E is fine.

## Routing model (App Router)

Authenticated UI lives under `src/app/org/[orgId]/project/[projectId]/{traces,sessions,evaluations,analytics}`. Org-level pages without a project context live under `src/app/org/[orgId]/settings/{organization,members,api-keys,projects,plans,billing}`. The `(auth)` route group holds `/login`.

When adding a page that operates on traces, sessions, or evals, nest it under `org/[orgId]/project/[projectId]/...` — `OrganizationProvider` and `ProjectProvider` read from the URL segments, and the API client only injects the `X-Organization-ID` / `X-Project-ID` headers when those providers resolve a context.

`src/middleware.ts` is the auth gate. It redirects unauthenticated requests under `/org/*` to `/login?callbackUrl=...` based on the `__pp_session` cookie (`SESSION_COOKIE_NAME` in `lib/auth/config.ts`). The cookie is a presence flag set by `auth-service.setSessionCookie()` after Firebase sign-in — the real bearer token comes from Firebase on each request. When `NEXT_PUBLIC_AUTH_ENABLED=false`, the middleware no-ops and pages render without auth.

## Auth toggle is build-time

`AUTH_ENABLED` is evaluated from `process.env.NEXT_PUBLIC_AUTH_ENABLED` in `src/lib/auth/config.ts`. Next.js constant-folds the comparison at build time, so the same image cannot be flipped between auth-enabled and auth-disabled at runtime — the public GHCR image is built with auth off, the private image with auth on. If you're changing how auth gating works, remember it has to behave correctly under both build flavors.

## API client and provider order

`src/lib/api/client.ts` is a singleton axios instance. It is configured exactly once via `configureAuth({ getToken, forceRefreshToken, getOrgId, getProjectId, onUnauthorized })`, called from `components/providers/ApiConfigProvider.tsx` at mount. The request interceptor pulls a Firebase ID token via `getToken()` and stamps `Authorization`, `X-Organization-ID`, `X-Project-ID` onto every request. Do not build URLs or attach headers by hand — go through the per-resource modules in `src/lib/api/` (`traces.ts`, `sessions.ts`, `evaluations.ts`, etc.).

The response interceptor handles 401 by calling `forceRefreshToken()` and retrying the original request once. Concurrent 401s share a single in-flight refresh via `refreshPromise`. If refresh fails (or the second attempt 401s), `onUnauthorized()` runs — wired in `ApiConfigProvider` to clear the session cookie and redirect to `/login`.

Provider nesting in `components/providers/Providers.tsx` is load-bearing:
```
AuthProvider → PostHogProvider → ToastProvider → QueryClientProvider → ApiConfigProvider
```
`ApiConfigProvider` must sit inside `AuthProvider` (needs the Firebase user) and inside `QueryClientProvider` (so the unauthorized handler can clear caches). `OrganizationProvider` / `ProjectProvider` are mounted lower, inside the `org/[orgId]` and `project/[projectId]` layouts, because they read URL params.

## Query keys

Always pull cache keys from `src/lib/query/keys.ts` (`queryKeys.traces.detail(traceId)`, `queryKeys.evaluations.monitors.list(projectId, params)`, etc.). Inline tuples will silently miss `invalidateQueries` calls keyed off the helpers. When adding a new resource, extend `keys.ts` rather than scattering string literals.

`src/__tests__/lib/query/keys.test.ts` pins the shapes — update both together.

## Tests

- Jest config (`jest.config.ts`): `jsdom`, `ts-jest`, path alias `@/* → src/*`, tests live at `src/__tests__/**/*.test.ts?(x)`, setup at `src/__tests__/setup.ts`.
- `src/__mocks__/` holds MSW handlers and module mocks used across tests. API tests mock at the network layer with MSW rather than stubbing the axios client.
- E2E tests live in `frontend/e2e/` and run against a real `yarn dev` server. The Playwright config only ships a Chromium project.

## Conventions

- Path alias `@/...` resolves to `src/...` (both `tsconfig.json` and Jest).
- Prettier + ESLint via `eslint-config-next` (flat config in `eslint.config.mjs`). `format:check` is the CI gate.
- `next.config.ts` sets security headers (CSP `frame-ancestors 'self'`, HSTS, etc.) for every route — keep an eye on this when wiring up embeds or third-party iframes.
- The only required public env var is `NEXT_PUBLIC_API_URL`. Firebase keys are required only when `NEXT_PUBLIC_AUTH_ENABLED=true`. `NODE_ENV` is owned by Next.js — never set it in `.env.*`.
