"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { type ReactNode, useRef, useState } from "react";
import { NotificationBell } from "@/features/teams/components/notification-bell";
import { OpenOnYouToast } from "@/features/teams/components/open-on-you-toast";
import { useTeamTenant } from "@/hooks/use-team-tenant";

export function TeamShell({ children }: { children: ReactNode }) {
  const params = useParams<{ locale: string; teamId: string }>();
  const search = useSearchParams();
  const orgId = search.get("orgId");
  const teamId = params.teamId;
  const locale = params.locale;
  const [bellOpen, setBellOpen] = useState(false);
  const bellHostRef = useRef<HTMLDivElement>(null);

  useTeamTenant(orgId, teamId);

  const q = orgId ? `?orgId=${encodeURIComponent(orgId)}` : "";

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-6 p-6">
      <header className="flex flex-wrap items-center gap-3 border-b border-border pb-4">
        <p className="font-medium tracking-tight">Cross-Team</p>
        <nav className="flex flex-wrap gap-2 text-sm">
          <Link className="underline-offset-4 hover:underline" href={`/${locale}/onboarding`}>
            Onboarding
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/profile${q}`}
          >
            Profile
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/documents${q}`}
          >
            Documents
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/members${q}`}
          >
            Members
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/review-items${q}`}
          >
            Conflicts
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/decisions${q}`}
          >
            Decisions
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/compose${q}`}
          >
            Compose
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/channels${q}`}
          >
            Channels
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/suggestions${q}`}
          >
            Suggestions
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/glossary${q}`}
          >
            Glossary
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/admin${q}`}
          >
            Admin
          </Link>
          <Link
            className="underline-offset-4 hover:underline"
            href={`/${locale}/teams/${teamId}/history${q}`}
          >
            History
          </Link>
        </nav>
        <div ref={bellHostRef}>
          <NotificationBell onOpenChange={setBellOpen} />
        </div>
      </header>
      {!orgId ? (
        <p className="text-sm text-muted-foreground">
          Missing <code>orgId</code> query param — set tenant from onboarding first.
        </p>
      ) : null}
      {children}
      {!bellOpen ? (
        <OpenOnYouToast
          onOpenNotifications={() => {
            const button = bellHostRef.current?.querySelector("button");
            button?.click();
          }}
        />
      ) : null}
    </div>
  );
}
