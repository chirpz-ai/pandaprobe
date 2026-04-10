"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark h-full">
      <body className="min-h-full bg-[#18191b] text-[#d1d5db] font-mono antialiased flex items-center justify-center">
        <div className="text-center space-y-4 max-w-md px-6">
          <h1 className="text-lg text-white">Something went wrong</h1>
          <p className="text-sm text-[#6b7280]">
            {error.message || "An unexpected error occurred."}
          </p>
          {error.digest && (
            <p className="text-xs text-[#4b5563]">Error ID: {error.digest}</p>
          )}
          <button
            onClick={reset}
            className="px-4 py-2 text-sm border border-[#3a3b3e] bg-[#1f2022] text-[#d1d5db] hover:bg-[#252628] transition-colors"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
