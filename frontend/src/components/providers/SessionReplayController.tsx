"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import posthog from "posthog-js";
import { useAuth } from "./AuthProvider";
import { isPostHogEnabled } from "./PostHogProvider";

/**
 * Routes where session recording is completely disabled.
 */
const BLOCKED_SUFFIXES = [
  "/settings/api-keys",
  "/settings/billing",
  "/settings/plans",
  "/settings/members",
];

function isBlockedRoute(pathname: string): boolean {
  return BLOCKED_SUFFIXES.some((suffix) => pathname.includes(suffix));
}

/**
 * Reads the current route and starts or stops PostHog session recording.
 * Mount once inside the authenticated org layout so only org routes are
 * eligible for replay — login, root, and error pages are never recorded.
 */
export function SessionReplayController() {
  const pathname = usePathname();
  const { authEnabled } = useAuth();
  const recording = useRef(false);

  useEffect(() => {
    if (!isPostHogEnabled(authEnabled)) return;

    const shouldRecord = !isBlockedRoute(pathname);

    if (shouldRecord && !recording.current) {
      posthog.startSessionRecording();
      recording.current = true;
    } else if (!shouldRecord && recording.current) {
      posthog.stopSessionRecording();
      recording.current = false;
    }
  }, [pathname, authEnabled]);

  useEffect(() => {
    return () => {
      if (recording.current) {
        posthog.stopSessionRecording();
        recording.current = false;
      }
    };
  }, []);

  return null;
}
