import type { ReactNode } from "react";
import { TeamRouteShell } from "@/features/shell/components/team-route-shell";

/**
 * Shared team chrome for all /teams/[teamId]/* routes.
 * Do not wrap in a loading-only Suspense here — that streams dead HTML for the bar.
 * AppShell reads query params without useSearchParams for the same reason.
 */
export default function TeamIdLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <TeamRouteShell>{children}</TeamRouteShell>;
}
