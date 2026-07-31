import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";
import { ChannelFeedPanel } from "@/features/channels/components/channel-feed-panel";
import { TeamShell } from "@/features/teams/components/team-shell";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function ChannelsPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading…</p>}>
      <TeamShell>
        <ChannelFeedPanel />
      </TeamShell>
    </Suspense>
  );
}
