export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg bg-dot-grid">
      <div className="bg-hero-glow absolute inset-0 pointer-events-none" />
      {children}
    </div>
  );
}
