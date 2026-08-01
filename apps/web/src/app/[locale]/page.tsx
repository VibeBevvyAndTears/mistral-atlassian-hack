import Link from "next/link";
import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { ConveBrandMark } from "@/components/domain/conve-brand-mark";

interface HomePageProps {
  params: Promise<{ locale: string }>;
}

export default async function HomePage({ params }: HomePageProps) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 bg-background px-6 py-16 text-foreground">
      <ConveBrandMark size="lg" priority />
      <p className="max-w-md text-center text-base text-muted-foreground">
        Cross-team channels with conflict review, suggestions, and audience adaptation.
      </p>
      <Link
        className="inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity duration-150 hover:opacity-90"
        href={`/${locale}/login`}
      >
        Sign in
      </Link>
    </main>
  );
}
