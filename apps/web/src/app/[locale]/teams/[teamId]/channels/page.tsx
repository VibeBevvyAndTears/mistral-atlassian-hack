import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { ChannelFeedPanel } from "@/features/channels/components/channel-feed-panel";

interface Props {
  params: Promise<{ locale: string; teamId: string }>;
}

export default async function ChannelsPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  return <ChannelFeedPanel />;
}
