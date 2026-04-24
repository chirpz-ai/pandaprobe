"use client";

import { Suspense, useEffect, useRef, type ReactNode } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import posthog from "posthog-js";
import { useAuth } from "./AuthProvider";

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "";
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || undefined;

/**
 * PostHog is enabled only when auth is active (i.e. not a self-hosted
 * instance) AND a valid project key has been provided. When either
 * condition is false, this provider renders children with zero
 * side-effects — no scripts loaded, no network requests.
 */
export function isPostHogEnabled(authEnabled: boolean): boolean {
  return authEnabled && POSTHOG_KEY.length > 0;
}

function PageviewTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { authEnabled } = useAuth();

  useEffect(() => {
    if (!isPostHogEnabled(authEnabled) || !pathname) return;

    const url = searchParams.toString()
      ? `${pathname}?${searchParams.toString()}`
      : pathname;

    posthog.capture("$pageview", { $current_url: url });
  }, [pathname, searchParams, authEnabled]);

  return null;
}

export function PostHogProvider({ children }: { children: ReactNode }) {
  const { user, loading, authEnabled } = useAuth();
  const initialized = useRef(false);
  const identifiedUid = useRef<string | null>(null);

  useEffect(() => {
    if (!isPostHogEnabled(authEnabled)) return;
    if (initialized.current) return;

    posthog.init(POSTHOG_KEY, {
      api_host: POSTHOG_HOST,
      capture_pageview: false,
      capture_pageleave: true,
      persistence: "localStorage+cookie",
      autocapture: false,
      disable_session_recording: true,
      session_recording: {
        maskTextSelector: "input, textarea",
        maskAllInputs: true,
        recordCrossOriginIframes: false,
        maskCapturedNetworkRequestFn: (request) => {
          request.requestBody = null;
          request.responseBody = null;
          return request;
        },
      },
    });

    posthog.register({ project_name: "pandaprobe_dashboard" });

    initialized.current = true;
  }, [authEnabled]);

  useEffect(() => {
    if (!initialized.current || loading) return;

    if (user) {
      if (identifiedUid.current !== user.uid) {
        posthog.identify(user.uid, {
          email: user.email ?? undefined,
          display_name: user.displayName ?? undefined,
        });
        identifiedUid.current = user.uid;
      }
    } else {
      if (identifiedUid.current) {
        posthog.reset();
        identifiedUid.current = null;
      }
    }
  }, [user, loading]);

  return (
    <>
      <Suspense fallback={null}>
        <PageviewTracker />
      </Suspense>
      {children}
    </>
  );
}
