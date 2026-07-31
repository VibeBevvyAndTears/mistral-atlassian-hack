import { ConveBrandMark } from "@/components/domain/conve-brand-mark";

export default function OfflinePage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-background px-6 text-foreground">
      <ConveBrandMark size="md" />
      <h1 className="mt-4 text-2xl font-semibold tracking-tight">You&apos;re offline</h1>
      <p className="mt-2 text-muted-foreground">Please check your internet connection.</p>
    </div>
  );
}
