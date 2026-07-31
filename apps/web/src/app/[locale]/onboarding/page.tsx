import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { OnboardingTabs } from "@/features/teams/components/onboarding-tabs";

interface Props {
  params: Promise<{ locale: string }>;
}

export default async function OnboardingPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);

  return (
    <main className="min-h-screen p-6">
      <h1 className="sr-only">Onboarding</h1>
      <OnboardingTabs />
    </main>
  );
}
