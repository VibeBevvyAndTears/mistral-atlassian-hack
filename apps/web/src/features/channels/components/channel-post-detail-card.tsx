"use client";

import { DotsThree, Info } from "@phosphor-icons/react";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient, setTenantHeaders } from "@/lib/api-client";

export interface ChannelPostRow {
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
  package_title?: string | null;
  sender_team_name?: string | null;
  sender_name?: string | null;
  created_at: string;
}

interface HistoryEntry {
  kind: string;
  summary: string;
  source: string;
  created_at: string;
  node_id: string | null;
}

interface SourceDocument {
  id: string;
  filename: string;
  status: string;
}

function formatPostTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function ChannelPostCard({
  post,
  onMarkedRead,
}: Readonly<{
  post: ChannelPostRow;
  onMarkedRead?: (id: string) => void;
}>) {
  const params = useParams<{ teamId: string }>();
  const search = useSearchParams();
  const teamId = params.teamId;
  const orgId = search.get("orgId");

  const [showOriginal, setShowOriginal] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [panel, setPanel] = useState<"history" | "sources" | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [sources, setSources] = useState<{
    package_title: string;
    documents: SourceDocument[];
  } | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const ensureTenant = useCallback(() => {
    if (orgId && teamId) setTenantHeaders(orgId, teamId);
  }, [orgId, teamId]);

  const senderLabel =
    post.sender_name && post.sender_team_name
      ? `${post.sender_name} · ${post.sender_team_name}`
      : post.sender_team_name || post.sender_name || "Unknown sender";

  useEffect(() => {
    if (post.is_read) return;
    ensureTenant();
    void (async () => {
      try {
        await apiClient.post(`/api/posts/${post.id}/read`);
        onMarkedRead?.(post.id);
      } catch {
        // non-fatal
      }
    })();
  }, [ensureTenant, onMarkedRead, post.id, post.is_read]);

  async function openHistory() {
    setMenuOpen(false);
    ensureTenant();
    try {
      const { data } = await apiClient.get<HistoryEntry[]>(`/api/posts/${post.id}/history`);
      setHistory(data);
      setPanel("history");
      setStatus(null);
    } catch {
      setStatus("Could not load post history.");
    }
  }

  async function openSources() {
    setMenuOpen(false);
    ensureTenant();
    try {
      const { data } = await apiClient.get<{
        package_id: string;
        package_title: string;
        documents: SourceDocument[];
      }>(`/api/posts/${post.id}/sources`);
      setSources({ package_title: data.package_title, documents: data.documents });
      setPanel("sources");
      setStatus(null);
    } catch {
      setStatus("Could not load source files.");
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-4 text-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-medium">{senderLabel}</p>
            <p className="text-xs text-muted-foreground">
              {formatPostTimestamp(post.created_at)}
              {post.package_title ? ` · ${post.package_title}` : ""}
              {!post.is_read ? " · Unread" : ""}
              {post.updated_since_send ? " · Updated" : ""}
            </p>
            <p className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
              <span
                title={post.ai_priority_reason ?? "No AI priority explanation"}
                className="inline-flex items-center gap-0.5"
              >
                {post.ai_priority ?? "unprioritized"}
                {post.ai_priority_reason ? (
                  <Info
                    className="size-3 shrink-0"
                    weight="bold"
                    aria-label={post.ai_priority_reason}
                  />
                ) : null}
              </span>
              <button
                type="button"
                className="underline-offset-2 hover:underline"
                onClick={() => setShowOriginal((v) => !v)}
              >
                {showOriginal ? "Show adapted" : "Show original"}
              </button>
            </p>
          </div>

          <div className="relative shrink-0">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Post actions"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <DotsThree className="size-5" weight="bold" />
            </Button>
            {menuOpen ? (
              <div className="absolute top-full right-0 z-20 mt-1 min-w-[10rem] rounded-md border border-border bg-background p-1 shadow-md">
                <button
                  type="button"
                  className="block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-muted"
                  onClick={() => void openSources()}
                >
                  View source
                </button>
                <button
                  type="button"
                  className="block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-muted"
                  onClick={() => void openHistory()}
                >
                  History
                </button>
              </div>
            ) : null}
          </div>
        </div>

        <div className="rounded-md border border-border/60 bg-muted/20 p-3">
          <p className="whitespace-pre-wrap">
            {showOriginal ? post.original_body : post.adapted_body}
          </p>
        </div>

        {post.what_was_done ? (
          <p className="text-xs text-muted-foreground">{post.what_was_done}</p>
        ) : null}

        {panel === "history" ? (
          <aside className="rounded-md border border-border p-3" aria-label="Post history">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-medium">History log</h3>
              <Button type="button" variant="ghost" size="xs" onClick={() => setPanel(null)}>
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
                      {entry.kind} · {entry.source} · {formatPostTimestamp(entry.created_at)}
                    </p>
                    <p>{entry.summary}</p>
                  </li>
                ))}
              </ol>
            )}
          </aside>
        ) : null}

        {panel === "sources" ? (
          <aside className="rounded-md border border-border p-3" aria-label="Source files">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-medium">Source files</h3>
              <Button type="button" variant="ghost" size="xs" onClick={() => setPanel(null)}>
                Close
              </Button>
            </div>
            <p className="mb-2 text-xs text-muted-foreground">
              Package: {sources?.package_title ?? "—"}
            </p>
            {!sources?.documents.length ? (
              <p className="text-xs text-muted-foreground">No linked documents.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {sources.documents.map((doc) => (
                  <li key={doc.id} className="text-xs">
                    <p className="font-medium">{doc.filename}</p>
                    <p className="text-muted-foreground">status={doc.status}</p>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        ) : null}

        <div className="mt-auto border-t border-border pt-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Topics from sender nodes</p>
          {post.topic_tags.length > 0 ? (
            <ul className="flex flex-wrap gap-2">
              {post.topic_tags.map((tag) => (
                <li
                  key={tag}
                  className="rounded-full border border-border bg-background px-2.5 py-0.5 text-xs"
                >
                  {tag}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground">No node labels on this package.</p>
          )}
        </div>

        {status ? <p className="text-xs text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}

export { ChannelPostCard as ChannelPostDetailCard };
