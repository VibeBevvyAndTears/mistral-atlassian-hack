import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { SuggestionQueuePanel } from "@/features/review/components/suggestion-queue-panel";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function SuggestionsPage({ params }: Props) {
  const { locale, teamId } = await params;
  setRequestLocale(locale as Locale);
  return (
    <TeamShell>
      <SuggestionQueuePanel teamId={teamId} />
    </TeamShell>
  );
}
