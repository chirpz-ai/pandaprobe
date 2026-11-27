"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { extractErrorMessage } from "@/lib/api/client";
import { resetPassword } from "@/lib/auth/auth-service";
import { useAuth } from "@/components/providers/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";

type View = "sign-in" | "sign-up" | "forgot-password";

function LoginHeader({ subtitle }: { subtitle: string }) {
  return (
    <div className="mb-8 text-start">
      <h1 className="flex items-center gap-2 text-2xl font-mono text-primary tracking-tight">
        <Image
          src="/favicon-96x96.png"
          alt=""
          width={24}
          height={24}
          className="shrink-0"
        />
        PandaProbe
      </h1>
      <p className="mt-1 text-balance text-sm text-text-dim">{subtitle}</p>
    </div>
  );
}

function LoginDivider({ label }: { label: string }) {
  return (
    <p className="mb-5 flex items-center gap-2 text-xs text-text-muted">
      <span aria-hidden="true" className="flex-1 border-t border-divider" />
      {label}
      <span aria-hidden="true" className="flex-1 border-t border-divider" />
    </p>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const { signInWithGoogle, signInWithEmail, signUpWithEmail, authEnabled } =
    useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [view, setView] = useState<View>("sign-in");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authEnabled) {
      router.replace("/");
    }
  }, [authEnabled, router]);

  if (!authEnabled) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  function switchView(next: View) {
    setView(next);
    setShowPassword(false);
    setError(null);
    setSuccess(null);
  }

  async function handleEmailSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (view === "sign-up") {
        await signUpWithEmail(email, password);
      } else {
        await signInWithEmail(email, password);
      }
      router.push(callbackUrl);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetPassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      await resetPassword(email);
      setSuccess("Password reset email sent. Check your inbox.");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogleSignIn() {
    setError(null);
    setSubmitting(true);
    try {
      await signInWithGoogle();
      router.push(callbackUrl);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (view === "forgot-password") {
    return (
      <div className="animate-fade-in">
        <LoginHeader subtitle="Reset your password" />

        <form onSubmit={handleResetPassword} className="space-y-4">
          <div>
            <Input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              autoFocus
            />
          </div>

          {error && <p className="text-xs text-error font-mono">{error}</p>}
          {success && (
            <p className="text-xs text-success font-mono">{success}</p>
          )}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? <Spinner size="sm" /> : "Send reset link"}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-text-muted">
          Remember your password?{" "}
          <button
            type="button"
            onClick={() => switchView("sign-in")}
            className="text-text-dim hover:text-text underline underline-offset-4 transition-colors"
          >
            Back to sign in
          </button>
        </p>
      </div>
    );
  }

  const visibilityLabel = showPassword ? "Hide password" : "Show password";
  const VisibilityIcon = showPassword ? EyeOff : Eye;

  return (
    <div className="animate-fade-in">
      <LoginHeader subtitle="The platform for agent engineering" />
      <LoginDivider
        label={view === "sign-up" ? "Sign up with" : "Sign in with"}
      />

      <Button
        variant="secondary"
        className="w-full mb-5"
        onClick={handleGoogleSignIn}
        disabled={submitting}
      >
        {submitting ? (
          <Spinner size="sm" />
        ) : (
          <>
            <svg className="h-4 w-4" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            Continue with Google
          </>
        )}
      </Button>

      <LoginDivider label="or" />

      <form onSubmit={handleEmailSubmit} className="space-y-4">
        <div>
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div className="relative">
          <Input
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            autoComplete={
              view === "sign-up" ? "new-password" : "current-password"
            }
            minLength={6}
            className="pr-11 [&::-ms-reveal]:hidden"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={visibilityLabel}
            aria-controls="password"
            title={visibilityLabel}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => setShowPassword((visible) => !visible)}
            className="absolute inset-y-0 right-px my-auto h-8 w-9 text-text-muted"
          >
            <VisibilityIcon aria-hidden="true" className="h-4 w-4" />
          </Button>
        </div>

        {view === "sign-in" && (
          <div className="flex justify-start">
            <button
              type="button"
              onClick={() => switchView("forgot-password")}
              className="text-xs text-text-muted hover:text-text underline underline-offset-4 transition-colors"
            >
              Forgot password?
            </button>
          </div>
        )}

        {error && <p className="text-xs text-error font-mono">{error}</p>}

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? (
            <Spinner size="sm" />
          ) : view === "sign-up" ? (
            "Create account"
          ) : (
            "Sign in"
          )}
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-text-muted">
        {view === "sign-up"
          ? "Already have an account?"
          : "Don't have an account?"}{" "}
        <button
          type="button"
          onClick={() => switchView(view === "sign-up" ? "sign-in" : "sign-up")}
          className="text-text-dim hover:text-text underline underline-offset-4 transition-colors"
        >
          {view === "sign-up" ? "Sign in" : "Create one"}
        </button>
      </p>
    </div>
  );
}

export default function LoginPage() {
  useDocumentTitle("Login");
  return (
    <main className="login-page grid min-h-svh w-full">
      <div className="grid min-w-0 place-items-center px-6 py-10">
        <div className="w-full max-w-[22.5rem]">
          <Suspense fallback={<Spinner size="lg" className="mx-auto" />}>
            <LoginForm />
          </Suspense>
        </div>
      </div>
      <div className="login-artwork">
        <figure className="max-w-md rounded-panel border border-divider bg-surface/95 p-6 lg:p-8">
          <blockquote className="text-balance font-sans text-xl leading-snug tracking-tight text-primary lg:text-2xl">
            “Production is where you discover what your agent still needs to
            learn.”
          </blockquote>
          <figcaption className="mt-4 font-sans text-sm text-text-dim">
            Sina Tayebati · Founder, PandaProbe
          </figcaption>
        </figure>
      </div>
    </main>
  );
}
