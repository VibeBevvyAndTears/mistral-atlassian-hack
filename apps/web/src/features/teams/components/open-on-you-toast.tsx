"use client";

import { X } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  type NotificationRow,
  OPEN_ON_YOU_KINDS,
} from "@/features/teams/components/notification-bell";
import { apiClient } from "@/lib/api-client";

const DISMISS_KEY = "open-on-you-toast-dismissed-at";

function summarize(items: NotificationRow[]): string {
  const suggestions = items.filter(
    (n) => n.kind === "suggestion_received" || n.kind === "suggestion_response"
  ).length;
  if (suggestions === 1) return "1 suggestion awaiting your reply";
  if (suggestions > 1) return `${suggestions} suggestions awaiting your reply`;
  if (items.length === 1) return "1 item needs your attention";
  return `${items.length} items need your attention`;
}

export function OpenOnYouToast({ onOpenNotifications }: { onOpenNotifications?: () => void }) {
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [visible, setVisible] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get<NotificationRow[]>("/api/notifications", {
        params: { unread_only: true, limit: 20 },
      });
      const openItems = data.filter((n) => OPEN_ON_YOU_KINDS.has(n.kind));
      setItems(openItems);

      const dismissedAt = sessionStorage.getItem(DISMISS_KEY);
      const newest = openItems[0]?.created_at;
      const shouldShow =
        openItems.length > 0 && (!dismissedAt || (newest !== undefined && newest > dismissedAt));
      setVisible(shouldShow);
    } catch {
      setVisible(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => {
      void load();
    }, 30_000);
    return () => window.clearInterval(id);
  }, [load]);

  if (!visible || items.length === 0) return null;

  return (
    <aside
      className="fixed right-4 bottom-4 z-40 w-72 rounded-md border border-border border-l-2 border-l-destructive bg-background p-3 shadow-lg"
      aria-label="Open on you"
      role="status"
    >
      <div className="mb-1.5 flex items-start justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-destructive uppercase">Open on you</p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          aria-label="Dismiss"
          onClick={() => {
            sessionStorage.setItem(DISMISS_KEY, new Date().toISOString());
            setVisible(false);
          }}
        >
          <X className="size-3.5" />
        </Button>
      </div>
      <p className="text-sm">{summarize(items)}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Open the notification bell for the latest posts that need you.
      </p>
      {onOpenNotifications ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => {
            onOpenNotifications();
            setVisible(false);
          }}
        >
          Open notifications
        </Button>
      ) : null}
    </aside>
  );
}
