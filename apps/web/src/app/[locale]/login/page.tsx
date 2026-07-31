import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { ConveBrandMark } from "@/components/domain/conve-brand-mark";
import { LoginForm } from "@/features/auth/components/login-form";

interface Props {
  params: Promise<{ locale: string }>;
}

export default async function LoginPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 bg-background px-6 py-16 text-foreground">
      <ConveBrandMark size="lg" priority />
      <h1 className="sr-only">Sign up or sign in</h1>
      <LoginForm />
    </main>
  );
}
