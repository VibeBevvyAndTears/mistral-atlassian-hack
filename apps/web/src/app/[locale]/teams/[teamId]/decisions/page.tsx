import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { DecisionRegisterPanel } from "@/features/teams/components/decision-register-panel";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function DecisionsPage({ params }: Props) {
  const { locale, teamId } = await params;
  setRequestLocale(locale as Locale);

  return (
    <TeamShell>
      <DecisionRegisterPanel teamId={teamId} />
    </TeamShell>
  );
}
