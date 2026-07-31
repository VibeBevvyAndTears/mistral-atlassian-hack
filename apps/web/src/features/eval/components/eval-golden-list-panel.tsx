"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient, setTenantHeaders } from "@/lib/api-client";

interface GoldenExample {
  id: string;
  kind: "conflict" | "judge" | "fidelity";
  notes: string | null;
}

interface EvalRun {
  status: "passed" | "failed" | "skipped";
  warning: string | null;
  total_goldens: number;
}

export function EvalGoldenListPanel() {
  const orgId = useSearchParams().get("orgId");
  const [goldens, setGoldens] = useState<GoldenExample[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    if (!orgId) return;
    setTenantHeaders(orgId, null);
    try {
      const { data } = await apiClient.get<GoldenExample[]>(`/api/orgs/${orgId}/eval/goldens`);
      setGoldens(data);
      setMessage(null);
    } catch {
      setMessage("Could not load evaluation goldens.");
    }
  }, [orgId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runGate() {
    if (!orgId) return;
    setRunning(true);
    try {
      const { data } = await apiClient.post<EvalRun>(`/api/orgs/${orgId}/eval/run`);
      setMessage(data.warning ?? `Gate ${data.status}: ${data.total_goldens} goldens evaluated.`);
    } catch {
      setMessage("Could not run the evaluation gate.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle>Evaluation goldens</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => void runGate()} disabled={!orgId || running}>
              {running ? "Running…" : "Run gate"}
            </Button>
            <Button type="button" variant="outline" onClick={() => void load()} disabled={!orgId}>
              Reload
            </Button>
          </div>
          {!orgId ? (
            <p className="text-sm text-muted-foreground">
              Add an <code>orgId</code> query parameter to manage evaluation goldens.
            </p>
          ) : null}
          {goldens.length === 0 && orgId ? (
            <p className="text-sm text-muted-foreground">No goldens yet.</p>
          ) : null}
          <ul className="flex flex-col gap-2">
            {goldens.map((golden) => (
              <li key={golden.id} className="rounded-md border border-border px-3 py-2">
                <p className="font-medium capitalize">{golden.kind}</p>
                <p className="text-sm text-muted-foreground">{golden.notes ?? "No notes"}</p>
              </li>
            ))}
          </ul>
          {message ? <output className="text-sm text-muted-foreground">{message}</output> : null}
        </CardContent>
      </Card>
    </main>
  );
}
