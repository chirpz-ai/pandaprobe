import { NextResponse, type NextRequest } from "next/server";

const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "false" ||
  process.env.NODE_ENV !== "development";

const PUBLIC_PATHS = ["/login", "/health", "/_next", "/favicon.ico"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  if (!AUTH_ENABLED) {
    return NextResponse.next();
  }

  // In a full implementation, middleware would verify a session cookie.
  // Since Firebase tokens are in-memory only (per security spec), the
  // client-side AuthProvider handles redirect logic. The middleware
  // layer here is kept lightweight to avoid needing cookie-based sessions.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
