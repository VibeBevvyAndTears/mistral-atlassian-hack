import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";
import { OrgAdminMetricsPanel } from "@/features/teams/components/org-admin-metrics-panel";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
  searchParams: Promise<{ orgId?: string }>;
}

export default async function AdminPage({ params, searchParams }: Props) {
  const [{ locale }, { orgId }] = await Promise.all([params, searchParams]);
  setRequestLocale(locale as Locale);
  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading…</p>}>
      <TeamShell>
        <OrgAdminMetricsPanel orgId={orgId} />
      </TeamShell>
    </Suspense>
  );
}
