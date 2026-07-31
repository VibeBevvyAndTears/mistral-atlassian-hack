"use client";

import type { ReactNode } from "react";
import { AppShell } from "@/features/shell/components/app-shell";

/** Stable client chrome for all /teams/[teamId]/* routes. */
export function TeamRouteShell({ children }: Readonly<{ children: ReactNode }>) {
  return <AppShell>{children}</AppShell>;
}
