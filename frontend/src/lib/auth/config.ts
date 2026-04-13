/**
 * Shared auth configuration. Safe to import from Edge middleware and client code.
 *
 * Two-build strategy:
 *   - Public image (GHCR): built with NEXT_PUBLIC_AUTH_ENABLED=false.
 *     The bundler constant-folds the comparison below to "false"
 *   - Private image: built with NEXT_PUBLIC_AUTH_ENABLED=true.
 *     Firebase is initialized and auth flows are active.
 *   - Local dev: reads from .env.development at dev-server time (no bundling).
 *
 * AUTH_ENABLED cannot be toggled at container runtime — Next.js bakes the
 * comparison result into the JS bundle at build time (constant folding).
 */

export const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "false";

export const SESSION_COOKIE_NAME = "__pp_session";
