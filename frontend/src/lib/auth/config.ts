/**
 * Shared auth configuration. Safe to import from Edge middleware and client code.
 *
 * Respects the NEXT_PUBLIC_AUTH_ENABLED env var at runtime (injected via
 * docker-entrypoint.sh for production images). Defaults to true when unset.
 */

export const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "false";

export const SESSION_COOKIE_NAME = "__pp_session";
