import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { ConveBrandMark } from "@/components/domain/conve-brand-mark";

interface NotFoundPageProps {
  params?: Promise<{ locale: string }>;
}

export default async function NotFoundPage({ params }: NotFoundPageProps) {
  const locale = (await params)?.locale || "en";
  setRequestLocale(locale as Locale);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center bg-background px-6 text-foreground">
      <ConveBrandMark size="md" />
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">404</h1>
      <p className="mt-2 text-muted-foreground">Page not found</p>
    </main>
  );
}
