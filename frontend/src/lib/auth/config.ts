/**
 * Shared auth configuration. Safe to import from Edge middleware and client code.
 *
 * Production safety: AUTH_ENABLED is forced ON when NODE_ENV !== "development",
 * mirroring the backend's _apply_environment_settings behaviour.
 */

const envFlag = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "false";

export const AUTH_ENABLED =
  process.env.NODE_ENV !== "development" ? true : envFlag;

export const SESSION_COOKIE_NAME = "__pp_session";
