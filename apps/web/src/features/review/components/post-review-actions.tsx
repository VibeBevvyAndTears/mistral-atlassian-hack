"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

export function PostReviewActions({ postId }: { postId: string }) {
  const [suggest, setSuggest] = useState("");
  const [status, setStatus] = useState<string | null>(null);

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
      setStatus("Suggestion sent (reverse-adapted preview on server).");
      setSuggest("");
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Post review</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
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
          <Button
            type="button"
            variant="outline"
            disabled={!suggest}
            onClick={() => void comment()}
          >
            Comment
          </Button>
        </div>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
