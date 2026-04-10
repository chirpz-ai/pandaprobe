import { redirect } from "next/navigation";

export default function Home() {
  // Primary redirect is handled via next.config.ts redirects (at the routing
  // layer, before any component renders). This server component acts as a
  // fallback in case the config redirect is bypassed.
  redirect("/dashboard");
}
