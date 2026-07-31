"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

interface SuggestionRow {
  id: string;
  original_text: string;
  adapted_preview: string | null;
  proposed_text: string | null;
  status: string;
  post_id: string;
  proposer_team_id: string;
  target_team_id: string;
  approved_team_ids: string[];
  awaiting_team_ids: string[];
  response: string | null;
}

export function SuggestionQueuePanel({ teamId }: Readonly<{ teamId: string }>) {
  const [rows, setRows] = useState<SuggestionRow[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [editText, setEditText] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get<SuggestionRow[]>(`/api/teams/${teamId}/suggestions`);
      setRows(data);
      setStatus(null);
    } catch {
      setStatus("Could not load suggestions.");
    }
  }, [teamId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function respond(id: string, response: "accept" | "edit" | "reject") {
    try {
      await apiClient.post(`/api/suggestions/${id}/respond`, {
        response,
        reason: response === "reject" ? rejectReason || "No" : null,
        edited_text: response === "edit" ? editText[id] || null : null,
      });
      setStatus(
        response === "reject"
          ? "Rejected."
          : "Proposed — waiting for the other team to approve before apply."
      );
      await load();
    } catch {
      setStatus("Respond failed — Lead required / stale target.");
    }
  }

  async function approve(id: string) {
    try {
      const { data } = await apiClient.post<SuggestionRow>(`/api/suggestions/${id}/approve`);
      setStatus(
        data.status === "applied"
          ? "Both teams approved — change applied."
          : "Your approval recorded — waiting for the other team."
      );
      await load();
    } catch {
      setStatus("Approve failed.");
    }
  }

  async function close(id: string) {
    try {
      await apiClient.post(`/api/suggestions/${id}/close`);
      setStatus("Thread closed.");
      await load();
    } catch {
      setStatus("Close failed — apply/reject first.");
    }
  }

  async function cancel(id: string) {
    try {
      await apiClient.post(`/api/suggestions/${id}/cancel`);
      setStatus("Edit request cancelled.");
      await load();
    } catch {
      setStatus("Cancel failed — already applied or not your suggestion.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Suggestion queue</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Accept/Edit proposes a change. Both teams must approve before the graph edit is applied.
          The requesting team can cancel before apply.
        </p>
        <Input
          placeholder="Reject reason"
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          aria-label="Reject reason"
        />
        <Button type="button" variant="outline" onClick={() => void load()}>
          Reload
        </Button>
        <ul className="flex flex-col gap-2">
          {rows.map((s) => {
            const isTarget = s.target_team_id === teamId;
            const isProposer = s.proposer_team_id === teamId;
            const needsMyApprove =
              s.status === "awaiting_approvals" && s.awaiting_team_ids.includes(teamId);
            const canCancel =
              isProposer && (s.status === "open" || s.status === "awaiting_approvals");
            return (
              <li key={s.id} className="rounded-md border border-border p-3 text-sm">
                <p>{s.adapted_preview ?? s.original_text}</p>
                {s.proposed_text ? (
                  <p className="mt-1 text-xs">
                    Proposed text: <span className="font-medium">{s.proposed_text}</span>
                  </p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  status={s.status}
                  {s.response ? ` · response=${s.response}` : ""} · post={s.post_id}
                </p>
                {s.status === "awaiting_approvals" ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Approved: {s.approved_team_ids.join(", ") || "none"} · Waiting:{" "}
                    {s.awaiting_team_ids.join(", ") || "none"}
                  </p>
                ) : null}
                {s.status === "open" && isTarget ? (
                  <div className="mt-2 flex flex-col gap-2">
                    <Input
                      placeholder="Optional edited text (Edit)"
                      value={editText[s.id] ?? ""}
                      onChange={(e) => setEditText((prev) => ({ ...prev, [s.id]: e.target.value }))}
                      aria-label="Edited suggestion text"
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" size="sm" onClick={() => void respond(s.id, "accept")}>
                        Accept (propose)
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!editText[s.id]?.trim()}
                        onClick={() => void respond(s.id, "edit")}
                      >
                        Edit & propose
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="destructive"
                        onClick={() => void respond(s.id, "reject")}
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                ) : null}
                {needsMyApprove ? (
                  <div className="mt-2">
                    <Button type="button" size="sm" onClick={() => void approve(s.id)}>
                      Approve change
                    </Button>
                  </div>
                ) : null}
                {canCancel ? (
                  <div className="mt-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void cancel(s.id)}
                    >
                      Cancel request
                    </Button>
                  </div>
                ) : null}
                {s.status === "applied" && isProposer ? (
                  <div className="mt-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void close(s.id)}
                    >
                      Close thread
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
