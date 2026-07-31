"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";

interface DecisionRow {
  id: string;
  claim_id: string;
  title: string;
  body: string;
  source: string;
  status: string;
  owner_team_id: string | null;
  created_at: string;
}

type Filter = "all" | "open" | "contested";

export function DecisionRegisterPanel({ teamId }: { teamId: string }) {
  const [rows, setRows] = useState<DecisionRow[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get<DecisionRow[]>(`/api/teams/${teamId}/decisions`, {
        params: { status: filter },
      });
      setRows(data);
      setStatus(null);
    } catch {
      setStatus("Could not load decisions.");
    }
  }, [teamId, filter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Decision register</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <fieldset className="flex flex-wrap gap-2 border-0 p-0">
          <legend className="sr-only">Decision filters</legend>
          {(["all", "open", "contested"] as const).map((f) => (
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
          <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
            Reload
          </Button>
        </fieldset>
        {rows.length === 0 && !status ? (
          <p className="text-sm text-muted-foreground">No decisions yet.</p>
        ) : null}
        <ul className="flex flex-col gap-2">
          {rows.map((d) => (
            <li key={d.id} className="rounded-md border border-border px-3 py-2 text-sm">
              <p className="font-medium">{d.title}</p>
              <p className="text-xs text-muted-foreground">
                {d.source} · {d.status}
                {d.owner_team_id ? "" : " · unowned"}
              </p>
            </li>
          ))}
        </ul>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
