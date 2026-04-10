"use client";

import { useParams, redirect } from "next/navigation";

export default function SettingsPage() {
  const params = useParams();
  redirect(`/org/${params.orgId}/settings/organization`);
}
