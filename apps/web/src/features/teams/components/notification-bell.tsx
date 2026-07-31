"use client";

import { Bell } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { isRealtimeConfigured, subscribeNotifications } from "@/lib/realtime/supabase";

interface NotificationRow {
  id: string;
  user_id: string;
  kind: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

const OPEN_ON_YOU_KINDS = new Set([
  "suggestion_received",
  "suggestion_response",
  "node_changed",
  "post_updated",
]);

function formatKind(kind: string): string {
  switch (kind) {
    case "suggestion_received":
      return "Suggestion on your graph";
    case "suggestion_response":
      return "Reply to your suggestion";
    case "node_changed":
      return "Source node updated";
    case "post_updated":
      return "Post updated since send";
    default:
      return kind.replaceAll("_", " ");
  }
}

function formatPayload(payload: Record<string, unknown>): string {
  const title =
    (typeof payload.title === "string" && payload.title) ||
    (typeof payload.post_title === "string" && payload.post_title) ||
    (typeof payload.summary === "string" && payload.summary) ||
    null;
  if (title) return title;
  const keys = Object.keys(payload);
  if (keys.length === 0) return "Open to review";
  return keys
    .slice(0, 3)
    .map((key) => `${key}: ${String(payload[key])}`)
    .join(" · ");
}

export function NotificationBell({ onOpenChange }: { onOpenChange?: (open: boolean) => void }) {
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get<NotificationRow[]>("/api/notifications", {
        params: { unread_only: false, limit: 20 },
      });
      setItems(data);
      if (data[0]?.user_id) setUserId(data[0].user_id);
      setStatus(null);
    } catch {
      setStatus("Could not load notifications.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (isRealtimeConfigured() && userId) {
      return (
        subscribeNotifications(userId, () => {
          void load();
        }) ?? undefined
      );
    }
    const id = window.setInterval(() => {
      void load();
    }, 15_000);
    return () => window.clearInterval(id);
  }, [load, userId]);

  const unread = items.filter((n) => !n.read_at);
  const openOnYou = items.filter((n) => !n.read_at && OPEN_ON_YOU_KINDS.has(n.kind));

  function toggleOpen() {
    setOpen((prev) => {
      const next = !prev;
      onOpenChange?.(next);
      return next;
    });
    void load();
  }

  return (
    <div className="relative ml-auto">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label={unread.length > 0 ? `Notifications, ${unread.length} unread` : "Notifications"}
        aria-expanded={open}
        onClick={toggleOpen}
        className="gap-1.5"
      >
        <Bell className="size-4" weight={unread.length > 0 ? "fill" : "regular"} />
        {unread.length > 0 ? (
          <span className="rounded-full bg-destructive px-1.5 text-[10px] font-medium text-destructive-foreground">
            {unread.length}
          </span>
        ) : null}
      </Button>
      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-80 rounded-md border border-border bg-background p-2 text-sm shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Open on you
            </p>
            <span className="text-[10px] text-muted-foreground">{openOnYou.length} awaiting</span>
          </div>
          {status ? <p className="px-1 text-muted-foreground">{status}</p> : null}
          {items.length === 0 && !status ? (
            <p className="px-1 text-muted-foreground">No notifications</p>
          ) : null}
          <ul className="flex max-h-72 flex-col gap-2 overflow-auto">
            {items.map((n) => {
              const isOpenOnYou = OPEN_ON_YOU_KINDS.has(n.kind);
              return (
                <li
                  key={n.id}
                  className={`rounded border px-2 py-1.5 ${
                    isOpenOnYou && !n.read_at
                      ? "border-destructive/40 border-l-2 border-l-destructive"
                      : "border-border"
                  } ${n.read_at ? "opacity-60" : ""}`}
                >
                  <p className="font-medium">{formatKind(n.kind)}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {formatPayload(n.payload)}
                  </p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    {new Date(n.created_at).toLocaleString()}
                    {!n.read_at ? " · unread" : ""}
                  </p>
                </li>
              );
            })}
          </ul>
          <p className="mt-2 px-1 text-[10px] text-muted-foreground">
            {isRealtimeConfigured() ? "Realtime enabled" : "Polling fallback (no Supabase keys)"}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export type { NotificationRow };
export { OPEN_ON_YOU_KINDS };
