"use client";

import { DotsThree, Info, Megaphone } from "@phosphor-icons/react";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  ChannelPostSourceModal,
  type ChannelSourceDocument,
} from "@/features/channels/components/channel-post-source-modal";
import { PostReviewActions } from "@/features/review/components/post-review-actions";
import { apiClient, setTenantHeaders } from "@/lib/api-client";
import { cn } from "@/lib/utils";

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

function formatPostTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  // Fixed locale avoids SSR/client locale mismatches.
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function dateGroupLabel(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Earlier";
  const today = new Date();
  const utcToday = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const utcThat = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  const diffDays = Math.round((utcToday - utcThat) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

const WHITESPACE = /\s+/;

function initials(name: string): string {
  const parts = name.trim().split(WHITESPACE).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return `${parts[0].slice(0, 1)}${parts[1].slice(0, 1)}`.toUpperCase();
}

function isAnnouncement(post: ChannelPostRow): boolean {
  return post.topic_tags.some((tag) => tag.toLowerCase() === "announcement");
}

function ChannelPostCard({
  post,
  onMarkedRead,
  selected,
  onSelect,
}: Readonly<{
  post: ChannelPostRow;
  onMarkedRead?: (id: string) => void;
  selected?: boolean;
  onSelect?: (id: string | null) => void;
}>) {
  const params = useParams<{ teamId: string }>();
  const search = useSearchParams();
  const teamId = params.teamId;
  const orgId = search.get("orgId");

  const [showOriginal, setShowOriginal] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [panel, setPanel] = useState<"history" | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [sources, setSources] = useState<{
    package_title: string;
    documents: ChannelSourceDocument[];
  } | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const rootRef = useRef<HTMLElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const ensureTenant = useCallback(() => {
    if (orgId && teamId) setTenantHeaders(orgId, teamId);
  }, [orgId, teamId]);

  const senderName = post.sender_name || "Unknown";
  const teamName = post.sender_team_name || "Team";
  const title =
    post.package_title?.trim() || post.adapted_body.split("\n")[0]?.slice(0, 80) || "Update";
  const body = showOriginal ? post.original_body : post.adapted_body;
  const announcement = isAnnouncement(post);

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

  useEffect(() => {
    if (!menuOpen && !selected && panel !== "history") return;
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (menuOpen && !menuRef.current?.contains(target)) {
        setMenuOpen(false);
      }
      if ((selected || panel === "history") && !rootRef.current?.contains(target)) {
        if (selected) onSelect?.(null);
        if (panel === "history") setPanel(null);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMenuOpen(false);
      if (selected) onSelect?.(null);
      if (panel === "history") setPanel(null);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen, onSelect, panel, selected]);

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
        documents: ChannelSourceDocument[];
      }>(`/api/posts/${post.id}/sources`);
      setSources({ package_title: data.package_title, documents: data.documents });
      setSourcesOpen(true);
      setStatus(null);
    } catch {
      setStatus("Could not load source files.");
    }
  }

  return (
    <article
      ref={rootRef}
      className={cn(
        "relative rounded-xl border border-border bg-card p-4 text-sm text-card-foreground transition-colors",
        selected && "ring-1 ring-ring",
        !post.is_read && "border-l-2 border-l-primary"
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold"
          aria-hidden
        >
          {initials(senderName)}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className="font-medium text-foreground">{senderName}</p>
            <p className="text-muted-foreground">in {teamName}</p>
            <p className="text-muted-foreground">{formatPostTimestamp(post.created_at)}</p>
            {announcement ? (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Megaphone className="size-3.5" weight="fill" aria-hidden />
                Announcement
              </span>
            ) : null}
            {post.topic_tags
              .filter((tag) => {
                const lower = tag.toLowerCase();
                return lower !== "announcement" && lower !== "update";
              })
              .slice(0, 2)
              .map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-secondary px-2 py-0.5 text-[11px] font-semibold text-muted-foreground"
                >
                  {tag}
                </span>
              ))}
            {post.ai_priority ? (
              <span
                className="inline-flex items-center gap-0.5 text-xs text-muted-foreground"
                title={post.ai_priority_reason ?? undefined}
              >
                {post.ai_priority}
                {post.ai_priority_reason ? (
                  <Info className="size-3" weight="bold" aria-label={post.ai_priority_reason} />
                ) : null}
              </span>
            ) : null}
          </div>

          <button
            type="button"
            className="mt-2 block w-full text-left"
            onClick={() => onSelect?.(post.id)}
          >
            <h3 className="text-base font-semibold text-foreground">{title}</h3>
            <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-foreground/90">{body}</p>
          </button>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "rounded-md bg-secondary px-2 py-1 text-[11px] font-medium",
                  showOriginal ? "text-muted-foreground" : "text-ask"
                )}
              >
                {showOriginal ? "Original" : "Translated"}
              </span>
              {!post.is_read ? (
                <span className="rounded-md bg-secondary px-2 py-1 text-[11px] font-medium text-ask">
                  Unread
                </span>
              ) : null}
              {post.updated_since_send ? (
                <span className="rounded-md bg-secondary px-2 py-1 text-[11px] text-muted-foreground">
                  Updated
                </span>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                onClick={() => setShowOriginal((v) => !v)}
                aria-pressed={showOriginal}
              >
                {showOriginal ? "See translated" : "See original"}
              </button>
              <Button
                type="button"
                variant={selected ? "default" : "secondary"}
                size="sm"
                className="h-9 rounded-[10px]"
                aria-expanded={selected}
                aria-controls={`post-reply-${post.id}`}
                onClick={() => onSelect?.(selected ? null : post.id)}
              >
                {selected ? "Close reply" : "Reply"}
              </Button>
            </div>
          </div>

          {selected ? (
            <div id={`post-reply-${post.id}`} className="mt-3">
              <PostReviewActions postId={post.id} embedded />
            </div>
          ) : null}

          {panel === "history" ? (
            <aside className="mt-3 rounded-lg border border-border p-3" aria-label="Post history">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h4 className="text-xs font-medium">History log</h4>
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

          {status ? <p className="mt-2 text-xs text-muted-foreground">{status}</p> : null}
        </div>

        <div ref={menuRef} className="relative shrink-0">
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
            <div className="absolute top-full right-0 z-20 mt-1 min-w-[10rem] rounded-md border border-border bg-popover p-1 shadow-[0_8px_24px_rgba(0,0,0,0.45)]">
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
              <button
                type="button"
                className="block w-full rounded px-2 py-1.5 text-left text-xs text-muted-foreground"
                disabled
                title="Ask AI coming soon"
              >
                Ask AI
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <ChannelPostSourceModal
        open={sourcesOpen}
        onOpenChange={setSourcesOpen}
        postId={post.id}
        packageTitle={sources?.package_title ?? post.package_title ?? ""}
        documents={sources?.documents ?? []}
      />
    </article>
  );
}

export { ChannelPostCard as ChannelPostDetailCard, dateGroupLabel, isAnnouncement };
