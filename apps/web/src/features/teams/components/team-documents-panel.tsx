"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";
import { isRealtimeConfigured, subscribeJob } from "@/lib/realtime/supabase";

interface DocRow {
  id: string;
  filename: string;
  status: string;
  job_id: string | null;
}

export function TeamDocumentsPanel({ teamId }: { teamId: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [latest, setLatest] = useState<DocRow | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [liveMode, setLiveMode] = useState<"realtime" | "poll" | "idle">("idle");

  const refresh = useCallback(async (docId: string) => {
    const { data } = await apiClient.get<DocRow>(`/api/documents/${docId}`);
    setLatest(data);
    return data;
  }, []);

  useEffect(() => {
    if (!latest?.job_id || !latest.id) return;

    if (isRealtimeConfigured()) {
      setLiveMode("realtime");
      const unsub = subscribeJob(latest.job_id, () => {
        void refresh(latest.id);
      });
      return () => {
        unsub?.();
      };
    }

    setLiveMode("poll");
    const id = window.setInterval(() => {
      void refresh(latest.id);
    }, 5_000);
    return () => window.clearInterval(id);
  }, [latest?.id, latest?.job_id, refresh]);

  async function onUpload() {
    if (!file) return;
    setLoading(true);
    setStatus(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const { data } = await apiClient.post<DocRow>(`/api/teams/${teamId}/documents`, body, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setLatest(data);
      setStatus(`Uploaded — status ${data.status}`);
    } catch {
      setStatus("Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  async function onPaste() {
    const text = pasteText.trim();
    if (!text) return;
    setLoading(true);
    setStatus(null);
    try {
      const { data } = await apiClient.post<DocRow>(`/api/teams/${teamId}/documents/paste`, {
        text,
        filename: "paste.txt",
      });
      setLatest(data);
      setPasteText("");
      setStatus(`Pasted — status ${data.status}`);
    } catch {
      setStatus("Paste failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Team documents</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          aria-label="Document file"
        />
        <Button type="button" disabled={loading || !file} onClick={() => void onUpload()}>
          Upload
        </Button>
        <textarea
          className="min-h-[6rem] w-full rounded-xl border border-border bg-secondary px-3 py-2 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-muted-foreground focus-visible:border-ask-soft focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          placeholder="Paste text to ingest…"
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          aria-label="Paste document text"
        />
        <Button
          type="button"
          variant="outline"
          disabled={loading || !pasteText.trim()}
          onClick={() => void onPaste()}
        >
          Paste text
        </Button>
        {latest ? (
          <div className="rounded-md border border-border p-3 text-sm">
            <p>
              <span className="text-muted-foreground">File:</span> {latest.filename}
            </p>
            <p>
              <span className="text-muted-foreground">Status:</span> {latest.status}
            </p>
            <p>
              <span className="text-muted-foreground">Job:</span> {latest.job_id ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              Live updates:{" "}
              {liveMode === "realtime"
                ? "Realtime (job_queue)"
                : liveMode === "poll"
                  ? "poll fallback every 5s"
                  : "idle"}
            </p>
            <Button
              type="button"
              variant="outline"
              className="mt-2"
              onClick={() => void refresh(latest.id)}
            >
              Refresh status
            </Button>
          </div>
        ) : null}
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
