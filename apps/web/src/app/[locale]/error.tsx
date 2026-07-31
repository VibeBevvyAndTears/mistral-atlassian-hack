"use client";

import { useEffect } from "react";
import { ConveBrandMark } from "@/components/domain/conve-brand-mark";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center bg-background px-6 text-foreground">
      <ConveBrandMark size="md" />
      <h1 className="mt-4 text-2xl font-semibold tracking-tight text-destructive">Error</h1>
      <p className="mt-2 text-muted-foreground">Something went wrong</p>
      <button
        type="button"
        onClick={reset}
        className="mt-8 inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity duration-150 hover:opacity-90"
      >
        Try again
      </button>
    </main>
  );
}
