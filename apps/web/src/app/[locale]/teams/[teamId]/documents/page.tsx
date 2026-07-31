import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";
import { TeamDocumentsPanel } from "@/features/teams/components/team-documents-panel";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function TeamDocumentsPage({ params }: Props) {
  const { locale, teamId } = await params;
  setRequestLocale(locale as Locale);

  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading…</p>}>
      <TeamShell>
        <TeamDocumentsPanel teamId={teamId} />
      </TeamShell>
    </Suspense>
  );
}
