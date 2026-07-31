"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

interface DecisionRow {
  id: string;
  claim_id: string;
  title: string;
  body: string;
  source: string;
  status: string;
  owner_team_id: string | null;
  owner_team_name: string | null;
  channel_id: string | null;
  superseded_by: string | null;
  created_at: string;
}

interface ChannelRow {
  id: string;
  team_a_id: string;
  team_b_id: string;
  team_a_name: string | null;
  team_b_name: string | null;
  peer_team_id: string | null;
  peer_team_name: string | null;
}

type StatusFilter = "all" | "open" | "contested";

function displayStatus(
  status: string
): "contested" | "agreed" | "proposed" | "superseded" | "open" {
  if (status === "open") return "proposed";
  if (
    status === "contested" ||
    status === "agreed" ||
    status === "superseded" ||
    status === "proposed"
  ) {
    return status;
  }
  return "open";
}

function statusBadgeClass(status: string): string {
  const s = displayStatus(status);
  switch (s) {
    case "contested":
      return "bg-destructive/20 text-destructive";
    case "agreed":
      return "bg-success/15 text-success";
    case "superseded":
      return "bg-muted text-muted-foreground";
    default:
      return "bg-secondary text-muted-foreground";
  }
}

function cardAccentClass(status: string, hasOwner: boolean): string {
  if (!hasOwner) return "border-l-destructive";
  const s = displayStatus(status);
  switch (s) {
    case "contested":
      return "border-l-destructive";
    case "agreed":
      return "border-l-success";
    case "superseded":
      return "border-l-border opacity-60";
    default:
      return "border-l-border";
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
    });
  } catch {
    return iso;
  }
}

export function DecisionRegisterPanel({ teamId }: { readonly teamId: string }) {
  const search = useSearchParams();
  const orgId = search.get("orgId");
  const [channels, setChannels] = useState<ChannelRow[]>([]);
  const [channelId, setChannelId] = useState<string>("");
  const [peerTeamId, setPeerTeamId] = useState("");
  const [rows, setRows] = useState<DecisionRow[]>([]);
  const [summaryRows, setSummaryRows] = useState<DecisionRow[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [loading, setLoading] = useState(false);

  const selected = useMemo(
    () => channels.find((c) => c.id === channelId) ?? null,
    [channels, channelId]
  );

  const pairLabel = useMemo(() => {
    if (!selected) return "Select an interaction";
    const selfName = selected.team_a_id === teamId ? selected.team_a_name : selected.team_b_name;
    const peerName = selected.peer_team_name ?? "Peer";
    return `${selfName ?? "This team"} ↔ ${peerName}`;
  }, [selected, teamId]);

  const summary = useMemo(() => {
    let agreed = 0;
    let contested = 0;
    let proposed = 0;
    for (const d of summaryRows) {
      const s = displayStatus(d.status);
      if (s === "agreed") agreed += 1;
      else if (s === "contested") contested += 1;
      else if (s === "proposed" || s === "open") proposed += 1;
    }
    return { agreed, contested, proposed };
  }, [summaryRows]);

  const loadChannels = useCallback(async () => {
    try {
      const { data } = await apiClient.get<ChannelRow[]>(`/api/teams/${teamId}/channels`);
      setChannels(data);
      setChannelId((prev) => prev || data[0]?.id || "");
      setStatus(null);
    } catch {
      setStatus("Could not load interactions.");
    }
  }, [teamId]);

  const loadDecisions = useCallback(async () => {
    if (!channelId) {
      setRows([]);
      setSummaryRows([]);
      return;
    }
    setLoading(true);
    try {
      const [filtered, all] = await Promise.all([
        apiClient.get<DecisionRow[]>(`/api/channels/${channelId}/decisions`, {
          params: { status: filter },
        }),
        apiClient.get<DecisionRow[]>(`/api/channels/${channelId}/decisions`, {
          params: { status: "all" },
        }),
      ]);
      setRows(filtered.data);
      setSummaryRows(all.data);
      setStatus(null);
    } catch {
      setStatus("Could not load decisions.");
    } finally {
      setLoading(false);
    }
  }, [channelId, filter]);

  useEffect(() => {
    void loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    void loadDecisions();
  }, [loadDecisions]);

  async function openInteraction() {
    if (!orgId || !peerTeamId.trim()) {
      setStatus("Provide orgId and a peer team id to open an interaction.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await apiClient.post<ChannelRow>(`/api/orgs/${orgId}/channels`, {
        team_a_id: teamId,
        team_b_id: peerTeamId.trim(),
      });
      await loadChannels();
      setChannelId(data.id);
      setPeerTeamId("");
      setStatus(null);
    } catch {
      setStatus("Could not open that interaction.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="text-xl font-semibold tracking-tight">Decisions - {pairLabel}</h1>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Interaction
              <select
                className="h-10 min-w-[14rem] rounded-xl border border-border bg-secondary px-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 focus-visible:border-ask-soft focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                aria-label="Filter by team interaction"
              >
                <option value="">Select interaction…</option>
                {channels.map((c) => (
                  <option key={c.id} value={c.id}>
                    {(c.team_a_id === teamId ? c.team_a_name : c.team_b_name) ?? "This team"} ↔{" "}
                    {c.peer_team_name ?? "Peer"}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <fieldset className="flex flex-wrap gap-2 border-0 p-0">
            <legend className="sr-only">Decision status filters</legend>
            {(["all", "contested", "open"] as const).map((f) => (
              <Button
                key={f}
                type="button"
                size="sm"
                variant={filter === f ? "default" : "outline"}
                onClick={() => setFilter(f)}
              >
                {f === "all" ? "All" : f === "open" ? "Open" : "Contested"}
              </Button>
            ))}
          </fieldset>
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <label
            htmlFor="peer-team-id"
            className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-muted-foreground"
          >
            Open another interaction (peer team id)
            <Input
              id="peer-team-id"
              value={peerTeamId}
              onChange={(e) => setPeerTeamId(e.target.value)}
              placeholder="Peer team UUID"
            />
          </label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading || !peerTeamId.trim() || !orgId}
            onClick={() => void openInteraction()}
          >
            Open interaction
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading || !channelId}
            onClick={() => void loadDecisions()}
          >
            Reload
          </Button>
        </div>
      </div>

      {!channelId ? (
        <p className="text-sm text-muted-foreground">
          Choose or open an interaction (e.g. Engineering ↔ Marketing) to view its decision
          register.
        </p>
      ) : null}

      <ul className="flex flex-col gap-3">
        {rows.map((d) => {
          const hasOwner = Boolean(d.owner_team_id);
          const label = displayStatus(d.status);
          return (
            <li
              key={d.id}
              className={`rounded-xl border border-border border-l-4 bg-card px-4 py-3 ${cardAccentClass(d.status, hasOwner)}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${statusBadgeClass(d.status)}`}
                  >
                    {label}
                  </span>
                  <p className="font-medium">{d.title}</p>
                </div>
                <p className="text-xs text-muted-foreground">
                  owner: {hasOwner ? (d.owner_team_name ?? "team") : "unassigned"}
                </p>
              </div>
              {d.body ? (
                <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{d.body}</p>
              ) : (
                <div className="mt-2 h-2 w-4/5 rounded bg-muted" aria-hidden />
              )}
              <p className="mt-2 text-xs text-muted-foreground">
                {d.source}
                {d.created_at ? ` · ${formatDate(d.created_at)}` : ""}
                {d.superseded_by ? " · replaced" : ""}
              </p>
              {!hasOwner ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="rounded bg-destructive/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-destructive">
                    No owner
                  </span>
                  <span className="text-xs text-destructive">
                    flagged by the pre-send checklist - send is blocked until a receiver is assigned
                  </span>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

      {channelId && rows.length === 0 && !status && !loading ? (
        <p className="text-sm text-muted-foreground">No decisions for this interaction yet.</p>
      ) : null}
      {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}

      {channelId ? (
        <footer className="mt-2 flex flex-col gap-4 border-t border-border pt-4">
          <section aria-labelledby="decision-summary-heading">
            <h2
              id="decision-summary-heading"
              className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground"
            >
              Summary
            </h2>
            <div className="flex flex-wrap gap-2">
              <span className="rounded bg-success/15 px-2 py-1 text-xs font-medium text-success">
                {summary.agreed} agreed
              </span>
              <span className="rounded bg-destructive/20 px-2 py-1 text-xs font-medium text-destructive">
                {summary.contested} contested
              </span>
              <span className="rounded bg-secondary px-2 py-1 text-xs font-medium text-muted-foreground">
                {summary.proposed} proposed
              </span>
            </div>
          </section>
          <section aria-labelledby="decision-source-heading">
            <h2
              id="decision-source-heading"
              className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground"
            >
              Source
            </h2>
            <p className="text-sm text-muted-foreground">
              Every row traces to a claim of type{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">decision</code> and its
              document span.
            </p>
          </section>
        </footer>
      ) : null}
    </div>
  );
}
