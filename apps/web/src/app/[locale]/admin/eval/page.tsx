import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";
import { EvalGoldenListPanel } from "@/features/eval/components/eval-golden-list-panel";

interface Props {
  params: Promise<{ locale: string }>;
}

export default async function EvalAdminPage({ params }: Readonly<Props>) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);

  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading…</p>}>
      <EvalGoldenListPanel />
    </Suspense>
  );
}
