import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";
import { TeamMembersPanel } from "@/features/teams/components/team-members-panel";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function TeamMembersPage({ params }: Props) {
  const { locale, teamId } = await params;
  setRequestLocale(locale as Locale);

  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading…</p>}>
      <TeamShell>
        <TeamMembersPanel teamId={teamId} />
      </TeamShell>
    </Suspense>
  );
}
