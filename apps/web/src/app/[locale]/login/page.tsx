import type { Locale } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { LoginForm } from "@/features/auth/components/login-form";

interface Props {
  params: Promise<{ locale: string }>;
}

export default async function LoginPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <h1 className="sr-only">Sign up or sign in</h1>
      <LoginForm />
    </main>
  );
}
