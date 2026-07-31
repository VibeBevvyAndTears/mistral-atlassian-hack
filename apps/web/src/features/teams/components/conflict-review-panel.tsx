"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";

interface ReviewItem {
  id: string;
  claim_a_id: string;
  claim_b_id: string;
  conflict_class: string;
  severity: string;
  rationale: string;
  status: string;
  proposed_resolution: string | null;
  resolved_resolution: string | null;
}

const RESOLUTIONS = ["keep_a", "keep_b", "keep_both", "not_a_conflict"] as const;

export function ConflictReviewPanel({ teamId }: { teamId: string }) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.get<ReviewItem[]>(`/api/teams/${teamId}/review-items`);
      setItems(data);
      setStatus(null);
    } catch {
      setStatus("Could not load review items.");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function propose(id: string, resolution: string) {
    setLoading(true);
    try {
      await apiClient.post(`/api/review-items/${id}/propose`, { resolution });
      await load();
    } catch {
      setStatus("Propose failed.");
      setLoading(false);
    }
  }

  async function resolve(id: string, resolution: string) {
    setLoading(true);
    try {
      await apiClient.post(`/api/review-items/${id}/resolve`, { resolution });
      setStatus("Resolved.");
      await load();
    } catch {
      setStatus("Resolve failed — Lead role required.");
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Conflict review</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Button type="button" variant="outline" disabled={loading} onClick={() => void load()}>
          Reload
        </Button>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No review items.</p>
        ) : null}
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <li key={item.id} className="rounded-md border border-border p-3 text-sm">
              <p>
                <span className="text-muted-foreground">Class:</span> {item.conflict_class} ·{" "}
                {item.severity}
              </p>
              <p className="mt-1">{item.rationale}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {item.claim_a_id} vs {item.claim_b_id} · status={item.status}
              </p>
              {item.status !== "resolved" ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {RESOLUTIONS.map((r) => (
                    <Button
                      key={`p-${r}`}
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={loading}
                      onClick={() => void propose(item.id, r)}
                    >
                      Propose {r}
                    </Button>
                  ))}
                  {RESOLUTIONS.map((r) => (
                    <Button
                      key={`r-${r}`}
                      type="button"
                      size="sm"
                      disabled={loading}
                      onClick={() => void resolve(item.id, r)}
                    >
                      Resolve {r}
                    </Button>
                  ))}
                </div>
              ) : (
                <p className="mt-1 text-xs">Resolved: {item.resolved_resolution}</p>
              )}
            </li>
          ))}
        </ul>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
