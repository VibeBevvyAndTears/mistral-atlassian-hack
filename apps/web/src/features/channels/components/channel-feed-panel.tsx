"use client";

import { Info } from "@phosphor-icons/react";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { AiPriorityInfoButton } from "@/features/channels/components/ai-priority-info-button";
import { PostReviewActions } from "@/features/review/components/post-review-actions";
import { apiClient } from "@/lib/api-client";

interface PostRow {
  id: string;
  adapted_body: string;
  original_body: string;
  ai_priority: string | null;
  ai_priority_reason: string | null;
  topic_tags: string[];
  is_read: boolean;
  what_was_done: string;
  updated_since_send?: boolean;
  judge: { fidelity: string | null; fit: string | null; badge: string | null } | null;
  created_at: string;
}

interface HistoryEntry {
  kind: string;
  summary: string;
  source: string;
  created_at: string;
  node_id: string | null;
}

export function ChannelFeedPanel() {
  const [channelId, setChannelId] = useState("");
  const [posts, setPosts] = useState<PostRow[]>([]);
  const [selected, setSelected] = useState<PostRow | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [sort, setSort] = useState<"priority" | "newest" | "oldest">("newest");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [topicTags, setTopicTags] = useState<string[]>([]);
  const [topicTagInput, setTopicTagInput] = useState("");

  const load = useCallback(async () => {
    if (!channelId) return;
    try {
      const { data } = await apiClient.get<PostRow[]>(`/api/channels/${channelId}/posts`, {
        params: {
          sort,
          unread_only: unreadOnly,
          topic_tags: topicTags.join(",") || undefined,
        },
      });
      setPosts(data);
      setStatus(null);
    } catch {
      setStatus("Could not load feed.");
    }
  }, [channelId, sort, topicTags, unreadOnly]);

  async function openPost(id: string) {
    try {
      const { data } = await apiClient.get<PostRow>(`/api/posts/${id}`);
      setSelected(data);
      setShowOriginal(false);
      setHistoryOpen(false);
      setHistory([]);
      if (!data.is_read) {
        await apiClient.post(`/api/posts/${id}/read`);
        setPosts((rows) => rows.map((row) => (row.id === id ? { ...row, is_read: true } : row)));
      }
    } catch {
      setStatus("Could not load post.");
    }
  }

  async function openHistory(postId: string) {
    try {
      const { data } = await apiClient.get<HistoryEntry[]>(`/api/posts/${postId}/history`);
      setHistory(data);
      setHistoryOpen(true);
      setStatus(null);
    } catch {
      setStatus("Could not load post history.");
    }
  }

  async function openSources(postId: string) {
    try {
      const { data } = await apiClient.get<{
        package_id: string;
        package_title: string;
        documents: { id: string; filename: string; status: string }[];
      }>(`/api/posts/${postId}/sources`);
      const docs =
        data.documents.length === 0
          ? "no linked documents"
          : data.documents.map((d) => d.filename).join(", ");
      setStatus(`Source: ${data.package_title} · ${docs}`);
    } catch {
      setStatus("Could not load post sources.");
    }
  }

  function addTopicTag() {
    const tag = topicTagInput.trim();
    if (tag && !topicTags.includes(tag)) setTopicTags((tags) => [...tags, tag]);
    setTopicTagInput("");
  }

  function removeTopicTag(tag: string) {
    setTopicTags((tags) => tags.filter((value) => value !== tag));
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Channel feed</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Input
            placeholder="Channel UUID"
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
            aria-label="Channel id"
          />
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <span>Sort</span>
              <select
                className="rounded-md border border-border bg-background px-2 py-1"
                value={sort}
                onChange={(event) =>
                  setSort(event.target.value as "priority" | "newest" | "oldest")
                }
              >
                <option value="priority">Priority</option>
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
              </select>
            </label>
            <AiPriorityInfoButton />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={(event) => setUnreadOnly(event.target.checked)}
              />
              <span>Unread only</span>
            </label>
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Topic tag"
              value={topicTagInput}
              onChange={(event) => setTopicTagInput(event.target.value)}
              aria-label="Topic tag"
            />
            <Button type="button" variant="outline" onClick={addTopicTag}>
              Add tag
            </Button>
          </div>
          {topicTags.length ? (
            <fieldset className="flex flex-wrap gap-2">
              <legend className="sr-only">Active topic filters</legend>
              {topicTags.map((tag) => (
                <button
                  type="button"
                  key={tag}
                  className="rounded-full border border-border px-2 py-1 text-xs"
                  onClick={() => removeTopicTag(tag)}
                  title="Remove filter"
                >
                  {tag} ×
                </button>
              ))}
            </fieldset>
          ) : null}
          <Button type="button" onClick={() => void load()}>
            Load feed
          </Button>
          <ul className="flex flex-col gap-2">
            {posts.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className="w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-muted/40"
                  onClick={() => void openPost(p.id)}
                >
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <span
                      title={p.ai_priority_reason ?? "No AI priority explanation"}
                      className="inline-flex items-center gap-0.5"
                    >
                      {p.ai_priority ?? "unprioritized"}
                      {p.ai_priority_reason ? (
                        <Info
                          className="size-3 shrink-0"
                          weight="bold"
                          aria-label={p.ai_priority_reason}
                        />
                      ) : null}
                    </span>
                    <span>
                      · {p.created_at}
                      {!p.is_read ? " · Unread" : ""}
                      {p.updated_since_send ? " · Updated" : ""}
                    </span>
                  </span>
                  {p.topic_tags.length ? (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {p.topic_tags.map((tag) => `#${tag}`).join(" ")}
                    </span>
                  ) : null}
                  <p className="line-clamp-2">{p.adapted_body}</p>
                </button>
              </li>
            ))}
          </ul>
          {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
        </CardContent>
      </Card>
      {selected ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
          <Card>
            <CardHeader>
              <CardTitle>Post detail</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowOriginal((v) => !v)}
                >
                  {showOriginal ? "Show adapted" : "Toggle original"}
                </Button>
                <details className="relative">
                  <summary className="cursor-pointer list-none rounded-md border border-border px-2 py-1 text-xs">
                    •••
                  </summary>
                  <div className="absolute z-10 mt-1 flex min-w-[10rem] flex-col rounded-md border border-border bg-background p-1 shadow-sm">
                    <button
                      type="button"
                      className="rounded px-2 py-1 text-left text-xs hover:bg-muted"
                      onClick={() => void openSources(selected.id)}
                    >
                      View source
                    </button>
                    <button
                      type="button"
                      className="rounded px-2 py-1 text-left text-xs hover:bg-muted"
                      onClick={() => void openHistory(selected.id)}
                    >
                      History
                    </button>
                  </div>
                </details>
              </div>
              <p>{showOriginal ? selected.original_body : selected.adapted_body}</p>
              <p className="text-xs text-muted-foreground">{selected.what_was_done}</p>
              {selected.judge ? (
                <p className="text-xs">
                  Judge: fidelity={selected.judge.fidelity ?? "—"} fit={selected.judge.fit ?? "—"}{" "}
                  badge={selected.judge.badge ?? "—"}
                </p>
              ) : null}
            </CardContent>
          </Card>
          {historyOpen ? (
            <aside
              className="rounded-md border border-border bg-background p-3"
              aria-label="Post history"
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-sm font-medium">History</h3>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setHistoryOpen(false)}
                >
                  Close
                </Button>
              </div>
              {history.length === 0 ? (
                <p className="text-xs text-muted-foreground">No history yet.</p>
              ) : (
                <ol className="flex flex-col gap-2">
                  {history.map((entry) => (
                    <li
                      key={`${entry.kind}-${entry.created_at}-${entry.source}-${entry.summary}`}
                      className="border-b border-border pb-2 text-xs last:border-0"
                    >
                      <p className="text-muted-foreground">
                        {entry.kind} · {entry.source} · {entry.created_at}
                      </p>
                      <p>{entry.summary}</p>
                    </li>
                  ))}
                </ol>
              )}
            </aside>
          ) : null}
        </div>
      ) : null}
      {selected ? <PostReviewActions postId={selected.id} /> : null}
    </div>
  );
}
