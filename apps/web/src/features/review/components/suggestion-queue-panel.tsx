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
  status: string;
  post_id: string;
}

export function SuggestionQueuePanel({ teamId }: { teamId: string }) {
  const [rows, setRows] = useState<SuggestionRow[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

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

  async function respond(id: string, response: "accept" | "reject") {
    try {
      await apiClient.post(`/api/suggestions/${id}/respond`, {
        response,
        reason: response === "reject" ? rejectReason || "No" : null,
      });
      await load();
    } catch {
      setStatus("Respond failed — Lead required / stale target.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Suggestion queue</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
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
          {rows.map((s) => (
            <li key={s.id} className="rounded-md border border-border p-3 text-sm">
              <p>{s.adapted_preview ?? s.original_text}</p>
              <p className="text-xs text-muted-foreground">
                status={s.status} post={s.post_id}
              </p>
              {s.status === "open" ? (
                <div className="mt-2 flex gap-2">
                  <Button type="button" size="sm" onClick={() => void respond(s.id, "accept")}>
                    Accept
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
              ) : null}
            </li>
          ))}
        </ul>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
