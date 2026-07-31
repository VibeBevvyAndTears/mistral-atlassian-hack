"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

export function SendComposer({ teamId }: { teamId: string }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [targetTeamId, setTargetTeamId] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [packageId, setPackageId] = useState<string | null>(null);
  const [channelId, setChannelId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function createPackage() {
    setLoading(true);
    setStatus(null);
    try {
      const { data } = await apiClient.post<{
        id: string;
        channel_id: string | null;
        checklist: Record<string, unknown>;
        bypassed_checks: string[];
        status: string;
      }>(`/api/teams/${teamId}/packages`, {
        title,
        body,
        target_team_id: targetTeamId,
        bypass_incomplete_pipeline: true,
      });
      setPackageId(data.id);
      setChannelId(data.channel_id);
      setStatus(
        `Package ${data.status} — checklist ok=${String(data.checklist.ok)}; bypassed=${data.bypassed_checks.join(",") || "none"}`
      );
    } catch {
      setStatus("Create package failed.");
    } finally {
      setLoading(false);
    }
  }

  async function send() {
    if (!packageId) return;
    setLoading(true);
    try {
      const { data } = await apiClient.post<{ status: string; job_id: string | null }>(
        `/api/packages/${packageId}/send`
      );
      setStatus(`Send enqueued — status=${data.status} job=${data.job_id ?? "—"}`);
    } catch {
      setStatus("Send failed — Lead role + checklist required.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Send composer</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Input
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          aria-label="Package title"
        />
        <textarea
          className="min-h-28 rounded-md border border-border bg-background p-2 text-sm"
          placeholder="Message body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          aria-label="Package body"
        />
        <Input
          placeholder="Target team UUID"
          value={targetTeamId}
          onChange={(e) => setTargetTeamId(e.target.value)}
          aria-label="Target team id"
        />
        <div className="flex gap-2">
          <Button
            type="button"
            disabled={loading || !title || !body || !targetTeamId}
            onClick={() => void createPackage()}
          >
            Run checklist
          </Button>
          <Button type="button" disabled={loading || !packageId} onClick={() => void send()}>
            Send
          </Button>
        </div>
        {channelId ? <p className="text-xs text-muted-foreground">Channel: {channelId}</p> : null}
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
