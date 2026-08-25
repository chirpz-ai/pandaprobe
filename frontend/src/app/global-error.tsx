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
      <body className="min-h-full bg-[#0c0c0b] text-[#d1d5db] font-mono antialiased flex items-center justify-center">
        <div className="text-center space-y-4 max-w-md px-6">
          <h1 className="text-lg text-white">Something went wrong</h1>
          <p className="text-sm text-[#858d9b]">
            {error.message || "An unexpected error occurred."}
          </p>
          {error.digest && (
            <p className="text-xs text-[#737b89]">Error ID: {error.digest}</p>
          )}
          <button
            onClick={reset}
            className="px-4 py-2 text-sm border border-[#2c2c2c] bg-[#111110] text-[#d1d5db] hover:bg-[#171717] transition-colors"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
