import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { SendComposer } from "@/features/channels/components/send-composer";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function ComposePage({ params }: Props) {
  const { locale, teamId } = await params;
  setRequestLocale(locale as Locale);
  return (
    <TeamShell>
      <SendComposer teamId={teamId} />
    </TeamShell>
  );
}
