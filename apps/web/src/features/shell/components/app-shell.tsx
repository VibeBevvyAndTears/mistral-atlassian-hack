"use client";

import { useParams, usePathname, useRouter } from "next/navigation";
import {
  createContext,
  type FormEvent,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AppSidebarNav, type AppSidebarTeam } from "@/features/shell/components/app-sidebar-nav";
import { AppTopBar } from "@/features/shell/components/app-top-bar";
import { NotificationBell } from "@/features/teams/components/notification-bell";
import { OpenOnYouToast } from "@/features/teams/components/open-on-you-toast";
import { useTeamTenant } from "@/hooks/use-team-tenant";
import { apiClient, setTenantHeaders } from "@/lib/api-client";

const CHANNEL_FEED_PATH_RE = /\/teams\/[^/]+\/channels\/?$/;

export interface AppShellTeam {
  id: string;
  name: string;
}

export interface AppShellContext {
  orgId: string | null;
  teamId: string;
  locale: string;
  orgTeams: AppShellTeam[];
  myTeams: AppShellTeam[];
  conflictCount: number;
  suggestionCount: number;
  selectedOrgTeamId: string | null;
  setSelectedOrgTeamId: (teamId: string | null) => void;
  reloadNav: () => Promise<void>;
  /** Post search query from the channel top bar (`?q=`). Empty on other routes. */
  channelSearchQuery: string;
}

const AppShellReactContext = createContext<AppShellContext | null>(null);

export function useAppShell(): AppShellContext {
  const ctx = useContext(AppShellReactContext);
  if (!ctx) {
    throw new Error("useAppShell must be used within AppShell");
  }
  return ctx;
}

interface SuggestionRow {
  id: string;
  status: string;
  target_team_id: string;
}

const OPEN_SUGGESTION = new Set(["open", "awaiting_approvals"]);

function readSearch(): { orgId: string | null; q: string } {
  if (typeof window === "undefined") return { orgId: null, q: "" };
  const params = new URLSearchParams(window.location.search);
  return { orgId: params.get("orgId"), q: params.get("q") ?? "" };
}

interface AppShellProps {
  children: ReactNode | ((ctx: AppShellContext) => ReactNode);
  mainId?: string;
}

/**
 * Team chrome. Query params are read after mount so SSR HTML matches the first
 * client paint (avoids hydration mismatches that leave the navbar unclickable).
 */
export function AppShell({ children, mainId = "app-main" }: Readonly<AppShellProps>) {
  const params = useParams<{ locale: string; teamId: string }>();
  const pathname = usePathname();
  const router = useRouter();

  const locale = params.locale;
  const teamId = params.teamId;

  // null/"" until mount — must match SSR.
  const [orgId, setOrgId] = useState<string | null>(null);
  const [qParam, setQParam] = useState("");
  const [searchReady, setSearchReady] = useState(false);
  const [_searchEpoch, setSearchEpoch] = useState(0);

  useEffect(() => {
    const { orgId: nextOrg, q } = readSearch();
    setOrgId(nextOrg);
    setQParam(q);
    setSearchReady(true);
  }, []);

  useEffect(() => {
    function onPopState() {
      const { orgId: nextOrg, q } = readSearch();
      setOrgId(nextOrg);
      setQParam(q);
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const isChannelFeed = useMemo(() => CHANNEL_FEED_PATH_RE.test(pathname), [pathname]);

  useTeamTenant(orgId, teamId);

  const [orgTeams, setOrgTeams] = useState<AppSidebarTeam[]>([]);
  const [myTeams, setMyTeams] = useState<AppSidebarTeam[]>([]);
  const [conflictCount, setConflictCount] = useState(0);
  const [suggestionCount, setSuggestionCount] = useState(0);
  const [selectedOrgTeamId, setSelectedOrgTeamId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const bellHostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSearchInput(qParam);
  }, [qParam]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, []);

  const reloadNav = useCallback(async () => {
    if (!teamId || !orgId) return;
    setTenantHeaders(orgId, teamId);
    try {
      const [orgRes, mineRes, conflictsRes, suggestionsRes] = await Promise.all([
        apiClient.get<AppShellTeam[]>(`/api/orgs/${orgId}/teams`),
        apiClient.get<AppShellTeam[]>(`/api/orgs/${orgId}/teams`, {
          params: { mine_only: true },
        }),
        apiClient.get<{ id: string }[]>(`/api/teams/${teamId}/review-items`, {
          params: { status: "open" },
        }),
        apiClient.get<SuggestionRow[]>(`/api/teams/${teamId}/suggestions`),
      ]);
      setOrgTeams(orgRes.data);
      setMyTeams(mineRes.data);
      setConflictCount(conflictsRes.data.length);
      setSuggestionCount(
        suggestionsRes.data.filter(
          (row) => row.target_team_id === teamId && OPEN_SUGGESTION.has(row.status)
        ).length
      );
    } catch {
      // Non-fatal — chrome still renders
    }
  }, [orgId, teamId]);

  useEffect(() => {
    void reloadNav();
  }, [reloadNav]);

  function onSearchSubmit(event?: FormEvent) {
    event?.preventDefault();
    if (!isChannelFeed) return;
    const q = searchInput.trim();
    const next = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
    if (q) next.set("q", q);
    else next.delete("q");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
    setSearchEpoch((n) => n + 1);
  }

  const profileHref = orgId
    ? `/${locale}/teams/${teamId}/profile?orgId=${encodeURIComponent(orgId)}`
    : `/${locale}/teams/${teamId}/profile`;

  const ctx: AppShellContext = {
    orgId,
    teamId,
    locale,
    orgTeams,
    myTeams,
    conflictCount,
    suggestionCount,
    selectedOrgTeamId,
    setSelectedOrgTeamId,
    reloadNav,
    channelSearchQuery: isChannelFeed ? qParam : "",
  };

  const content = typeof children === "function" ? children(ctx) : children;
  const resolvedMainId = isChannelFeed ? "channel-feed" : mainId;

  return (
    <AppShellReactContext.Provider value={ctx}>
      <div data-channel-shell className="flex min-h-svh bg-background text-foreground">
        <a
          href={`#${resolvedMainId}`}
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-3 focus:rounded-md focus:bg-secondary focus:px-3 focus:py-2"
        >
          Skip to content
        </a>

        <AppSidebarNav
          locale={locale}
          orgId={orgId}
          activeTeamId={teamId}
          orgTeams={orgTeams}
          myTeams={myTeams}
          conflictCount={conflictCount}
          suggestionCount={suggestionCount}
          selectedOrgTeamId={selectedOrgTeamId}
          onSelectOrgTeam={setSelectedOrgTeamId}
          mobileOpen={mobileNavOpen}
          onMobileOpenChange={setMobileNavOpen}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Sticky must be on a direct child of this column — a short inner wrapper
              constrains position:sticky and lets the bar (and hamburger) scroll away. */}
          <div ref={bellHostRef} className="sticky top-0 z-20">
            <AppTopBar
              onOpenMobileNav={() => setMobileNavOpen(true)}
              mobileNavOpen={mobileNavOpen}
              profileHref={profileHref}
              notificationSlot={<NotificationBell onOpenChange={setBellOpen} variant="channel" />}
              search={
                isChannelFeed
                  ? {
                      value: searchInput,
                      onChange: setSearchInput,
                      onSubmit: onSearchSubmit,
                      placeholder: "Search posts",
                    }
                  : undefined
              }
            />
          </div>

          <main id={resolvedMainId} className="flex-1">
            {searchReady && !orgId && !pathname.includes("/onboarding") ? (
              <p className="px-4 pt-4 text-sm text-muted-foreground sm:px-6">
                Missing <code>orgId</code> query param — open this page from onboarding or a team
                link that includes <code>?orgId=…</code>.
              </p>
            ) : null}
            {content}
          </main>
        </div>

        {!bellOpen ? (
          <OpenOnYouToast
            onOpenNotifications={() => {
              const button = bellHostRef.current?.querySelector<HTMLButtonElement>(
                "[data-notification-bell]"
              );
              button?.click();
            }}
          />
        ) : null}
      </div>
    </AppShellReactContext.Provider>
  );
}
