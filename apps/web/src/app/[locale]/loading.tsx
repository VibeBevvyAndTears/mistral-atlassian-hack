import { Spinner } from "@phosphor-icons/react/ssr";

export default function Loading() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center bg-background px-6 text-foreground">
      <Spinner className="size-10 animate-spin text-muted-foreground" />
      <p className="mt-4 text-sm text-muted-foreground">Loading…</p>
    </main>
  );
}
