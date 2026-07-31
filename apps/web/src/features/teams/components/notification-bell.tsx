"use client";

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

export function NotificationBell() {
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

  const unread = items.filter((n) => !n.read_at).length;

  return (
    <div className="relative ml-auto">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label="Notifications"
        onClick={() => {
          setOpen((v) => !v);
          void load();
        }}
      >
        Alerts{unread > 0 ? ` (${unread})` : ""}
      </Button>
      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-md border border-border bg-background p-2 text-sm shadow-sm">
          {status ? <p className="text-muted-foreground">{status}</p> : null}
          {items.length === 0 && !status ? (
            <p className="text-muted-foreground">No notifications</p>
          ) : null}
          <ul className="flex max-h-64 flex-col gap-2 overflow-auto">
            {items.map((n) => (
              <li key={n.id} className="rounded border border-border px-2 py-1">
                <p className="font-medium">{n.kind}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {JSON.stringify(n.payload)}
                </p>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] text-muted-foreground">
            {isRealtimeConfigured() ? "Realtime enabled" : "Polling fallback (no Supabase keys)"}
          </p>
        </div>
      ) : null}
    </div>
  );
}
