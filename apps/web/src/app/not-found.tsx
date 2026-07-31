import Link from "next/link";
import { ConveBrandMark } from "@/components/domain/conve-brand-mark";

export default function NotFound() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-background px-6 text-foreground">
      <ConveBrandMark size="md" />
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">404</h1>
      <p className="mt-2 text-muted-foreground">Page not found</p>
      <Link
        href="/"
        className="mt-6 inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity duration-150 hover:opacity-90"
      >
        Go back home
      </Link>
    </div>
  );
}
