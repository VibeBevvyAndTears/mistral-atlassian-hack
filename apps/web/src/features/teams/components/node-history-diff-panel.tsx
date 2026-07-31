"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

export function NodeHistoryDiffPanel() {
  const [nodeId, setNodeId] = useState("");
  const [fromVersion, setFromVersion] = useState("1");
  const [toVersion, setToVersion] = useState("2");
  const [diff, setDiff] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function loadDiff() {
    try {
      const { data } = await apiClient.get<{ diff: string }>(`/api/nodes/${nodeId}/diff`, {
        params: { from_version: fromVersion, to_version: toVersion },
      });
      setDiff(data.diff || "No text changes.");
      setStatus(null);
    } catch {
      setStatus("Could not load consecutive node versions.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Node history diff</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Input
          value={nodeId}
          onChange={(event) => setNodeId(event.target.value)}
          placeholder="Node UUID"
        />
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            min="1"
            value={fromVersion}
            onChange={(event) => setFromVersion(event.target.value)}
            aria-label="From version"
          />
          <Input
            type="number"
            min="2"
            value={toVersion}
            onChange={(event) => setToVersion(event.target.value)}
            aria-label="To version"
          />
        </div>
        <Button type="button" disabled={!nodeId} onClick={loadDiff}>
          Compare versions
        </Button>
        {diff ? (
          <section aria-label="Node diff">
            <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{diff}</pre>
          </section>
        ) : null}
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
