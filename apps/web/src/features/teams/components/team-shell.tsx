"use client";

import type { ReactNode } from "react";

/** Content padding for team tool pages inside the shared TeamRouteShell layout. */
export function TeamShell({ children }: Readonly<{ children: ReactNode }>) {
  return <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">{children}</div>;
}
