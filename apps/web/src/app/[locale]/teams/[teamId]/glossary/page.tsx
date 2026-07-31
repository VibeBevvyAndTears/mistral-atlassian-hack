import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { TeamGlossaryEditor } from "@/features/teams/components/team-glossary-editor";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function GlossaryPage({ params }: Props) {
  const { locale, teamId } = await params;
  setRequestLocale(locale as Locale);
  return (
    <TeamShell>
      <TeamGlossaryEditor teamId={teamId} />
    </TeamShell>
  );
}
