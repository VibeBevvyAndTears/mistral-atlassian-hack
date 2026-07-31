/**
 * Supabase Realtime browser client (T1-E / M1-12).
 * When NEXT_PUBLIC_SUPABASE_* is unset, helpers return null and callers
 * fall back to REST polling.
 */
import { createClient, type RealtimeChannel, type SupabaseClient } from "@supabase/supabase-js";
import { env } from "@/config/env";

let client: SupabaseClient | null | undefined;

export function getSupabaseBrowserClient(): SupabaseClient | null {
  if (client !== undefined) return client;
  const url = env.NEXT_PUBLIC_SUPABASE_URL?.trim() ?? "";
  const key = env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ?? "";
  if (!url || !key) {
    client = null;
    return null;
  }
  client = createClient(url, key, {
    realtime: { params: { eventsPerSecond: 5 } },
  });
  return client;
}

export function isRealtimeConfigured(): boolean {
  return getSupabaseBrowserClient() !== null;
}

/** Subscribe to notification INSERTs for a user (filter on user_id). */
export function subscribeNotifications(
  userId: string,
  onInsert: (row: Record<string, unknown>) => void
): (() => void) | null {
  const sb = getSupabaseBrowserClient();
  if (!sb) return null;
  const channel: RealtimeChannel = sb
    .channel(`notifications:${userId}`)
    .on(
      "postgres_changes",
      {
        event: "INSERT",
        schema: "public",
        table: "notifications",
        filter: `user_id=eq.${userId}`,
      },
      (payload) => {
        onInsert((payload.new ?? {}) as Record<string, unknown>);
      }
    )
    .subscribe();
  return () => {
    void sb.removeChannel(channel);
  };
}

/** Subscribe to job_queue UPDATEs for a specific job id. */
export function subscribeJob(
  jobId: string,
  onUpdate: (row: Record<string, unknown>) => void
): (() => void) | null {
  const sb = getSupabaseBrowserClient();
  if (!sb) return null;
  const channel: RealtimeChannel = sb
    .channel(`jobs:${jobId}`)
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "job_queue",
        filter: `id=eq.${jobId}`,
      },
      (payload) => {
        onUpdate((payload.new ?? {}) as Record<string, unknown>);
      }
    )
    .subscribe();
  return () => {
    void sb.removeChannel(channel);
  };
}
