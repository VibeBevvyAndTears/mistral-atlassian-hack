import Link from "next/link";
import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";

interface HomePageProps {
  params: Promise<{ locale: string }>;
}

export default async function HomePage({ params }: HomePageProps) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-24">
      <h1 className="text-4xl font-bold tracking-tight">Cross-Team</h1>
      <p className="max-w-md text-center text-muted-foreground">
        Cross-team communication with topic graphs, conflict detection, and audience adaptation.
      </p>
      <div className="flex gap-3 text-sm">
        <Link className="underline underline-offset-4" href="/login">
          Sign in
        </Link>
        <Link className="underline underline-offset-4" href={`/${locale}/onboarding`}>
          Onboarding
        </Link>
      </div>
    </main>
  );
}
