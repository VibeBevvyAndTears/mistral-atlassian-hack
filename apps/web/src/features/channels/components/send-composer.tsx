"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

interface ChecklistResult {
  ok?: boolean;
  no_unowned_decisions?: boolean;
  unowned_decision_titles?: string[];
  [key: string]: unknown;
}

export function SendComposer({ teamId }: { readonly teamId: string }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [targetTeamId, setTargetTeamId] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [packageId, setPackageId] = useState<string | null>(null);
  const [channelId, setChannelId] = useState<string | null>(null);
  const [checklist, setChecklist] = useState<ChecklistResult | null>(null);
  const [loading, setLoading] = useState(false);

  const blockedByNoOwner = checklist?.no_unowned_decisions === false;
  const canSend = Boolean(packageId) && checklist?.ok === true && !blockedByNoOwner;

  async function createPackage() {
    setLoading(true);
    setStatus(null);
    try {
      const { data } = await apiClient.post<{
        id: string;
        channel_id: string | null;
        checklist: ChecklistResult;
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
      setChecklist(data.checklist);
      if (data.checklist.no_unowned_decisions === false) {
        const titles = data.checklist.unowned_decision_titles ?? [];
        setStatus(
          `Cannot send: every decision needs an owner (receiver). ${
            titles.length
              ? `Unowned: ${titles.join(", ")}`
              : "Assign owners in the Decision register."
          }`
        );
      } else {
        setStatus(
          `Package ${data.status} — checklist ok=${String(data.checklist.ok)}; bypassed=${data.bypassed_checks.join(",") || "none"}`
        );
      }
    } catch {
      setStatus("Create package failed.");
      setChecklist(null);
      setPackageId(null);
    } finally {
      setLoading(false);
    }
  }

  async function send() {
    if (!packageId || !canSend) return;
    setLoading(true);
    try {
      const { data } = await apiClient.post<{ status: string; job_id: string | null }>(
        `/api/packages/${packageId}/send`
      );
      setStatus(`Send enqueued — status=${data.status} job=${data.job_id ?? "—"}`);
    } catch (err: unknown) {
      const detail =
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ===
          "string"
          ? (err as { response: { data: { detail: string } } }).response.data.detail
          : null;
      setStatus(
        detail ??
          "Send failed — Lead role required, and every decision must have an owner before send."
      );
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
          className="min-h-28 w-full rounded-xl border border-border bg-secondary p-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-muted-foreground focus-visible:border-ask-soft focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          placeholder="Message body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          aria-label="Package body"
        />
        <Input
          placeholder="Target team UUID (receiver)"
          value={targetTeamId}
          onChange={(e) => setTargetTeamId(e.target.value)}
          aria-label="Target team id"
          required
        />
        <div className="flex gap-2">
          <Button
            type="button"
            disabled={loading || !title || !body || !targetTeamId}
            onClick={() => void createPackage()}
          >
            Run checklist
          </Button>
          <Button type="button" disabled={loading || !canSend} onClick={() => void send()}>
            Send
          </Button>
        </div>
        {blockedByNoOwner ? (
          <p className="text-sm text-destructive" role="alert">
            NO OWNER - send is blocked. Assign a receiving owner on every decision before sending.
          </p>
        ) : null}
        {channelId ? <p className="text-xs text-muted-foreground">Channel: {channelId}</p> : null}
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
