import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-bg">
      <div className="text-center space-y-4 max-w-md px-6">
        <h1 className="text-6xl font-mono text-primary">404</h1>
        <p className="text-sm text-text-dim">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/"
          className="inline-block px-4 py-2 text-sm font-mono border border-border bg-surface text-text hover:bg-surface-hi transition-colors"
        >
          Go home
        </Link>
      </div>
    </div>
  );
}
