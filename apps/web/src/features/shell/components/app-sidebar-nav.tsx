"use client";

import {
  CaretDown,
  House,
  Lightbulb,
  Plus,
  SquaresFour,
  UserPlus,
  Warning,
} from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { ConveBrandMark } from "@/components/domain/conve-brand-mark";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export interface AppSidebarTeam {
  id: string;
  name: string;
}

interface AppSidebarNavProps {
  locale: string;
  orgId: string | null;
  activeTeamId: string;
  orgTeams: AppSidebarTeam[];
  myTeams: AppSidebarTeam[];
  conflictCount: number;
  suggestionCount: number;
  selectedOrgTeamId: string | null;
  onSelectOrgTeam: (teamId: string | null) => void;
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
  /** Called after a new team is created so the caller can refresh org/my team lists. */
  onTeamCreated?: () => void | Promise<void>;
}

function TeamIconTile({ label }: { label: string }) {
  const initial = label.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[#f5f5f5] text-xs font-semibold text-[#16181d]"
      aria-hidden
    >
      {initial}
    </span>
  );
}

function CountBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  const label = count > 99 ? "99+" : String(count);
  return (
    <span className="ml-auto inline-flex min-w-5 items-center justify-center rounded-full bg-destructive px-1.5 py-0.5 text-[11px] font-semibold text-destructive-foreground">
      {label}
    </span>
  );
}

export function AppSidebarNav({
  locale,
  orgId,
  activeTeamId,
  orgTeams,
  myTeams,
  conflictCount,
  suggestionCount,
  selectedOrgTeamId,
  onSelectOrgTeam,
  mobileOpen,
  onMobileOpenChange,
  onTeamCreated,
}: AppSidebarNavProps) {
  const [orgOpen, setOrgOpen] = useState(true);
  const [myOpen, setMyOpen] = useState(true);
  // Avoid SSR/client mismatch: team lists load after mount via AppShell.fetch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const q = orgId ? `?orgId=${encodeURIComponent(orgId)}` : "";

  const newTeamInputId = useId();
  const [creatingTeam, setCreatingTeam] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [creatingTeamLoading, setCreatingTeamLoading] = useState(false);
  const [createTeamError, setCreateTeamError] = useState<string | null>(null);

  const inviteInputId = useId();
  const [invitingMember, setInvitingMember] = useState(false);
  const [inviteIdentifier, setInviteIdentifier] = useState("");
  const [invitingMemberLoading, setInvitingMemberLoading] = useState(false);
  const [inviteStatus, setInviteStatus] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);

  function startCreateTeam() {
    setOrgOpen(true);
    setInvitingMember(false);
    setCreatingTeam(true);
    setCreateTeamError(null);
  }

  function cancelCreateTeam() {
    setCreatingTeam(false);
    setNewTeamName("");
    setCreateTeamError(null);
  }

  async function submitCreateTeam() {
    const name = newTeamName.trim();
    if (!name || !orgId) return;
    setCreatingTeamLoading(true);
    setCreateTeamError(null);
    try {
      await apiClient.post(`/api/orgs/${orgId}/teams`, { name });
      setNewTeamName("");
      setCreatingTeam(false);
      await onTeamCreated?.();
    } catch {
      setCreateTeamError("Could not create team.");
    } finally {
      setCreatingTeamLoading(false);
    }
  }

  function startInviteMember() {
    setOrgOpen(true);
    setCreatingTeam(false);
    setInvitingMember(true);
    setInviteStatus(null);
  }

  function cancelInviteMember() {
    setInvitingMember(false);
    setInviteIdentifier("");
    setInviteStatus(null);
  }

  async function submitInviteMember() {
    const trimmed = inviteIdentifier.trim();
    if (!trimmed || !activeTeamId) return;
    setInvitingMemberLoading(true);
    setInviteStatus(null);
    const body = trimmed.includes("@")
      ? { email: trimmed, role: "member" }
      : { username: trimmed.toLowerCase(), role: "member" };
    try {
      const { data } = await apiClient.post<{ added_immediately?: boolean; email: string }>(
        `/api/teams/${activeTeamId}/invites`,
        body
      );
      setInviteIdentifier("");
      setInviteStatus({
        kind: "success",
        message: data.added_immediately
          ? `Added ${data.email} to the team.`
          : `Invite created for ${data.email}.`,
      });
    } catch {
      setInviteStatus({
        kind: "error",
        message: "Could not invite - use a known username or email (Lead/Owner required).",
      });
    } finally {
      setInvitingMemberLoading(false);
    }
  }

  function renderNav() {
    return (
      <nav
        className="flex h-full w-[260px] flex-col bg-[var(--sidebar)] text-[var(--sidebar-foreground)]"
        aria-label="Workspace navigation"
      >
        <div className="flex flex-col gap-3 p-3">
          <Link
            href={`/${locale}/teams/${activeTeamId}/channels${q}`}
            className="inline-flex items-center rounded-[10px] px-1 py-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            onClick={() => onMobileOpenChange(false)}
            aria-label="Conve home"
          >
            <ConveBrandMark size="sm" />
          </Link>
          <Link
            href={`/${locale}/teams/${activeTeamId}/channels${q}`}
            className="inline-flex h-10 items-center gap-2 rounded-full bg-[var(--sidebar-accent)] px-4 text-sm font-medium text-foreground transition-colors hover:bg-[#2c3038] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            onClick={() => onMobileOpenChange(false)}
          >
            <House className="size-4" weight="fill" aria-hidden />
            Home
          </Link>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-3 pb-3">
          <section>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="flex flex-1 items-center gap-1 py-1 text-left text-xs font-semibold tracking-wide text-muted-foreground"
                aria-expanded={orgOpen}
                onClick={() => setOrgOpen((v) => !v)}
              >
                <CaretDown
                  className={cn("size-3 transition-transform", !orgOpen && "-rotate-90")}
                  weight="bold"
                  aria-hidden
                />
                Your organisation
              </button>
              <button
                type="button"
                className="flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-[var(--sidebar-accent)] hover:text-foreground"
                aria-label="Invite member"
                aria-expanded={invitingMember}
                onClick={() => (invitingMember ? cancelInviteMember() : startInviteMember())}
                disabled={!orgId || !activeTeamId}
              >
                <UserPlus className="size-3.5" weight="bold" aria-hidden />
              </button>
              <button
                type="button"
                className="flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-[var(--sidebar-accent)] hover:text-foreground"
                aria-label="Create team"
                aria-expanded={creatingTeam}
                onClick={() => (creatingTeam ? cancelCreateTeam() : startCreateTeam())}
                disabled={!orgId}
              >
                <Plus className="size-3.5" weight="bold" aria-hidden />
              </button>
            </div>
            {invitingMember ? (
              <div className="mt-1 flex flex-col gap-1.5 rounded-lg border border-[var(--sidebar-border)] bg-[var(--sidebar-accent)]/40 p-2">
                <label className="sr-only" htmlFor={inviteInputId}>
                  Username or email
                </label>
                <input
                  id={inviteInputId}
                  type="text"
                  value={inviteIdentifier}
                  onChange={(event) => setInviteIdentifier(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void submitInviteMember();
                    } else if (event.key === "Escape") {
                      cancelInviteMember();
                    }
                  }}
                  placeholder="Username or email"
                  disabled={invitingMemberLoading}
                  className="h-9 rounded-md border border-[var(--sidebar-border)] bg-[var(--sidebar)] px-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                />
                {inviteStatus ? (
                  <p
                    className={cn(
                      "text-xs",
                      inviteStatus.kind === "error" ? "text-destructive" : "text-muted-foreground"
                    )}
                  >
                    {inviteStatus.message}
                  </p>
                ) : null}
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    className="h-7 flex-1 rounded-md bg-foreground px-2 text-xs font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
                    disabled={invitingMemberLoading || !inviteIdentifier.trim()}
                    onClick={() => void submitInviteMember()}
                  >
                    {invitingMemberLoading ? "Inviting…" : "Invite"}
                  </button>
                  <button
                    type="button"
                    className="h-7 rounded-md px-2 text-xs text-muted-foreground hover:bg-[var(--sidebar-accent)] hover:text-foreground"
                    disabled={invitingMemberLoading}
                    onClick={cancelInviteMember}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : null}
            {creatingTeam ? (
              <div className="mt-1 flex flex-col gap-1.5 rounded-lg border border-[var(--sidebar-border)] bg-[var(--sidebar-accent)]/40 p-2">
                <label className="sr-only" htmlFor={newTeamInputId}>
                  New team name
                </label>
                <input
                  id={newTeamInputId}
                  type="text"
                  value={newTeamName}
                  onChange={(event) => setNewTeamName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void submitCreateTeam();
                    } else if (event.key === "Escape") {
                      cancelCreateTeam();
                    }
                  }}
                  placeholder="Team name"
                  disabled={creatingTeamLoading}
                  className="h-9 rounded-md border border-[var(--sidebar-border)] bg-[var(--sidebar)] px-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                />
                {createTeamError ? (
                  <p className="text-xs text-destructive">{createTeamError}</p>
                ) : null}
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    className="h-7 flex-1 rounded-md bg-foreground px-2 text-xs font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
                    disabled={creatingTeamLoading || !newTeamName.trim()}
                    onClick={() => void submitCreateTeam()}
                  >
                    {creatingTeamLoading ? "Creating…" : "Create"}
                  </button>
                  <button
                    type="button"
                    className="h-7 rounded-md px-2 text-xs text-muted-foreground hover:bg-[var(--sidebar-accent)] hover:text-foreground"
                    disabled={creatingTeamLoading}
                    onClick={cancelCreateTeam}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : null}
            {orgOpen ? (
              <ul className="mt-1 flex flex-col gap-0.5">
                {!mounted ? (
                  <li className="h-10 px-2 py-2 text-xs text-muted-foreground" aria-hidden>
                    &nbsp;
                  </li>
                ) : orgTeams.length === 0 ? (
                  <li className="px-2 py-2 text-xs text-muted-foreground">No teams yet</li>
                ) : (
                  orgTeams.map((team) => {
                    const selected = selectedOrgTeamId === team.id;
                    return (
                      <li key={team.id}>
                        <button
                          type="button"
                          className={cn(
                            "flex h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-sm transition-colors",
                            selected
                              ? "bg-[var(--sidebar-accent)] text-foreground"
                              : "hover:bg-[var(--sidebar-accent)]/70"
                          )}
                          aria-pressed={selected}
                          onClick={() => {
                            onSelectOrgTeam(selected ? null : team.id);
                            onMobileOpenChange(false);
                          }}
                        >
                          <TeamIconTile label={team.name} />
                          <span className="truncate">{team.name}</span>
                        </button>
                      </li>
                    );
                  })
                )}
              </ul>
            ) : null}
          </section>

          <section>
            <button
              type="button"
              className="flex w-full items-center gap-1 py-1 text-left text-xs font-semibold tracking-wide text-muted-foreground"
              aria-expanded={myOpen}
              onClick={() => setMyOpen((v) => !v)}
            >
              <CaretDown
                className={cn("size-3 transition-transform", !myOpen && "-rotate-90")}
                weight="bold"
                aria-hidden
              />
              My teams
            </button>
            {myOpen ? (
              <ul className="mt-1 flex flex-col gap-0.5">
                {!mounted ? (
                  <li className="h-10 px-2 py-2 text-xs text-muted-foreground" aria-hidden>
                    &nbsp;
                  </li>
                ) : myTeams.length === 0 ? (
                  <li className="px-2 py-2 text-xs text-muted-foreground">No memberships</li>
                ) : (
                  myTeams.map((team) => {
                    const active = team.id === activeTeamId;
                    return (
                      <li key={team.id}>
                        <Link
                          href={`/${locale}/teams/${team.id}/channels${q}`}
                          className={cn(
                            "flex h-10 items-center gap-2 rounded-lg px-2 text-sm transition-colors",
                            active
                              ? "bg-[var(--sidebar-accent)] text-foreground"
                              : "hover:bg-[var(--sidebar-accent)]/70"
                          )}
                          aria-current={active ? "page" : undefined}
                          onClick={() => onMobileOpenChange(false)}
                        >
                          <TeamIconTile label={team.name} />
                          <span className="truncate">{team.name}</span>
                        </Link>
                      </li>
                    );
                  })
                )}
              </ul>
            ) : null}
          </section>
        </div>

        <div className="mt-auto border-t border-[var(--sidebar-border)] p-3">
          <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground">
            Review Queue
          </p>
          <ul className="flex flex-col gap-0.5">
            <li>
              <Link
                href={`/${locale}/teams/${activeTeamId}/review-items${q}`}
                className="flex h-10 items-center gap-2 rounded-lg px-2 text-sm hover:bg-[var(--sidebar-accent)]"
                onClick={() => onMobileOpenChange(false)}
              >
                <span className="flex size-8 items-center justify-center rounded-lg bg-[#f5f5f5] text-[#16181d]">
                  <Warning className="size-4" weight="fill" aria-hidden />
                </span>
                Conflicts
                <CountBadge count={conflictCount} />
              </Link>
            </li>
            <li>
              <Link
                href={`/${locale}/teams/${activeTeamId}/suggestions${q}`}
                className="flex h-10 items-center gap-2 rounded-lg px-2 text-sm hover:bg-[var(--sidebar-accent)]"
                onClick={() => onMobileOpenChange(false)}
              >
                <span className="flex size-8 items-center justify-center rounded-lg bg-[#f5f5f5] text-[#16181d]">
                  <Lightbulb className="size-4" weight="fill" aria-hidden />
                </span>
                Suggestions
                <CountBadge count={suggestionCount} />
              </Link>
            </li>
            <li>
              <Link
                href={`/${locale}/teams/${activeTeamId}/compose${q}`}
                className="mt-1 flex h-9 items-center gap-2 rounded-lg px-2 text-xs text-muted-foreground hover:bg-[var(--sidebar-accent)] hover:text-foreground"
                onClick={() => onMobileOpenChange(false)}
              >
                <SquaresFour className="size-4" aria-hidden />
                More team tools
              </Link>
            </li>
          </ul>
        </div>
      </nav>
    );
  }

  return (
    <>
      {/* Desktop */}
      <aside className="sticky top-0 hidden h-svh shrink-0 lg:block">{renderNav()}</aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/55"
            aria-label="Close navigation"
            onClick={() => onMobileOpenChange(false)}
          />
          <div className="absolute inset-y-0 left-0 z-[51] shadow-lg">{renderNav()}</div>
        </div>
      ) : null}
    </>
  );
}
