"use client";

import { useParams } from "next/navigation";
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
}

export function PostReviewActions({
  postId,
  embedded = false,
}: Readonly<{ postId: string; embedded?: boolean }>) {
  const params = useParams<{ teamId: string }>();
  const teamId = params.teamId;

  const [suggest, setSuggest] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState<SuggestionRow[]>([]);

  const loadPending = useCallback(async () => {
    if (!teamId) return;
    try {
      const { data } = await apiClient.get<SuggestionRow[]>(`/api/teams/${teamId}/suggestions`);
      setPending(
        data.filter(
          (s) =>
            s.post_id === postId &&
            (s.status === "awaiting_approvals" || s.status === "applied" || s.status === "open")
        )
      );
    } catch {
      // non-fatal — review actions still work
    }
  }, [postId, teamId]);

  useEffect(() => {
    void loadPending();
  }, [loadPending]);

  async function review(action: "agree" | "request_changes" | "blocked") {
    try {
      await apiClient.post(`/api/posts/${postId}/review-actions`, { action });
      setStatus(`Recorded ${action}`);
    } catch {
      setStatus("Review action failed.");
    }
  }

  async function propose() {
    try {
      await apiClient.post(`/api/posts/${postId}/suggestions`, { text: suggest });
      setStatus("Suggestion sent — Team A must propose, then both teams approve.");
      setSuggest("");
      await loadPending();
    } catch {
      setStatus("Suggestion failed.");
    }
  }

  async function comment() {
    try {
      await apiClient.post(`/api/posts/${postId}/comments`, { body: suggest });
      setStatus("Comment posted.");
      setSuggest("");
    } catch {
      setStatus("Comment failed.");
    }
  }

  async function approve(id: string) {
    try {
      const { data } = await apiClient.post<SuggestionRow>(`/api/suggestions/${id}/approve`);
      setStatus(
        data.status === "applied"
          ? "Both teams approved — change applied."
          : "Approval recorded — waiting for the other team."
      );
      await loadPending();
    } catch {
      setStatus("Approve failed.");
    }
  }

  async function close(id: string) {
    try {
      await apiClient.post(`/api/suggestions/${id}/close`);
      setStatus("Thread closed.");
      await loadPending();
    } catch {
      setStatus("Close failed.");
    }
  }

  async function cancel(id: string) {
    try {
      await apiClient.post(`/api/suggestions/${id}/cancel`);
      setStatus("Edit request cancelled.");
      await loadPending();
    } catch {
      setStatus("Cancel failed.");
    }
  }

  const body = (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" onClick={() => void review("agree")}>
          Agree
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void review("request_changes")}
        >
          Request changes
        </Button>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          onClick={() => void review("blocked")}
        >
          Blocked
        </Button>
      </div>
      <Input
        placeholder="Suggestion or comment text"
        value={suggest}
        onChange={(e) => setSuggest(e.target.value)}
        aria-label="Suggestion text"
      />
      <div className="flex gap-2">
        <Button type="button" disabled={!suggest} onClick={() => void propose()}>
          Propose change
        </Button>
        <Button type="button" variant="outline" disabled={!suggest} onClick={() => void comment()}>
          Comment
        </Button>
      </div>
      {pending.length > 0 ? (
        <div className="mt-2 flex flex-col gap-2 rounded-md border border-border p-2">
          <p className="text-xs font-medium">Change approvals for this post</p>
          {pending.map((s) => {
            const needsApprove =
              s.status === "awaiting_approvals" && s.awaiting_team_ids.includes(teamId);
            const canCancel =
              s.proposer_team_id === teamId &&
              (s.status === "open" || s.status === "awaiting_approvals");
            return (
              <div key={s.id} className="text-sm">
                <p>{s.proposed_text ?? s.adapted_preview ?? s.original_text}</p>
                <p className="text-xs text-muted-foreground">status={s.status}</p>
                {s.status === "awaiting_approvals" ? (
                  <p className="text-xs text-muted-foreground">
                    Waiting: {s.awaiting_team_ids.join(", ") || "—"}
                  </p>
                ) : null}
                <div className="mt-1 flex gap-2">
                  {needsApprove ? (
                    <Button type="button" size="sm" onClick={() => void approve(s.id)}>
                      Approve change
                    </Button>
                  ) : null}
                  {canCancel ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void cancel(s.id)}
                    >
                      Cancel request
                    </Button>
                  ) : null}
                  {s.status === "applied" && s.proposer_team_id === teamId ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void close(s.id)}
                    >
                      Close thread
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
      {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
    </div>
  );

  if (embedded) {
    return (
      <section className="rounded-xl border border-border bg-secondary/40 p-3">
        <p className="mb-2 text-xs font-medium text-muted-foreground">Post review</p>
        {body}
      </section>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Post review</CardTitle>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
}
