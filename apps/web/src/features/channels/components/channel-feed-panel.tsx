"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { AiPriorityInfoButton } from "@/features/channels/components/ai-priority-info-button";
import { ChannelFeedComposer } from "@/features/channels/components/channel-feed-composer";
import {
  ChannelPostDetailCard,
  type ChannelPostRow,
  dateGroupLabel,
  isAnnouncement,
} from "@/features/channels/components/channel-post-detail-card";
import { useAppShell } from "@/features/shell/components/app-shell";
import { apiClient, setTenantHeaders } from "@/lib/api-client";

interface ChannelOption {
  id: string;
  peer_team_id: string | null;
  peer_team_name: string | null;
  team_a_name: string | null;
  team_b_name: string | null;
}

interface ChannelPostsPage {
  items: ChannelPostRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  q: string | null;
}

const PAGE_SIZE = 20;

export function ChannelFeedPanel() {
  const { orgId, teamId, orgTeams, myTeams, selectedOrgTeamId, reloadNav, channelSearchQuery } =
    useAppShell();

  const [channels, setChannels] = useState<ChannelOption[]>([]);
  const [posts, setPosts] = useState<ChannelPostRow[]>([]);
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [sort, setSort] = useState<"priority" | "newest">("newest");
  const [teamFilter, setTeamFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<"all" | "announcement" | "update">("all");
  const [loading, setLoading] = useState(false);

  const loadFeed = useCallback(async () => {
    if (!teamId || !orgId) return;
    setTenantHeaders(orgId, teamId);
    setLoading(true);
    try {
      const { data: channelRows } = await apiClient.get<ChannelOption[]>(
        `/api/teams/${teamId}/channels`
      );
      setChannels(channelRows);

      if (channelRows.length === 0) {
        setPosts([]);
        setStatus("No channels yet - send a package first.");
        setSelectedPostId(null);
        return;
      }

      const pages = await Promise.all(
        channelRows.map((ch) =>
          apiClient.get<ChannelPostsPage>(`/api/channels/${ch.id}/posts`, {
            params: {
              sort,
              q: channelSearchQuery || undefined,
              page: 1,
              page_size: PAGE_SIZE,
            },
          })
        )
      );

      const merged = pages.flatMap((page) => page.data.items);
      const byId = new Map<string, ChannelPostRow>();
      for (const post of merged) byId.set(post.id, post);
      const items = [...byId.values()];

      if (sort === "newest") {
        items.sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
      } else {
        const rank = (p: string | null) => {
          if (!p) return 99;
          const n = Number(p.replace(/\D/g, ""));
          return Number.isFinite(n) ? n : 50;
        };
        items.sort((a, b) => {
          const d = rank(a.ai_priority) - rank(b.ai_priority);
          if (d !== 0) return d;
          return +new Date(b.created_at) - +new Date(a.created_at);
        });
      }

      setPosts(items);
      setStatus(
        items.length === 0
          ? channelSearchQuery
            ? `No posts match "${channelSearchQuery}".`
            : "No posts yet."
          : null
      );
      setSelectedPostId((current) =>
        current && items.some((p) => p.id === current) ? current : null
      );
    } catch {
      setStatus("Could not load feed.");
    } finally {
      setLoading(false);
    }
  }, [channelSearchQuery, orgId, sort, teamId]);

  const peerTeamIds = useMemo(
    () => [
      ...new Set(
        channels
          .map((ch) => ch.peer_team_id)
          .filter((id): id is string => Boolean(id) && id !== teamId)
      ),
    ],
    [channels, teamId]
  );

  useEffect(() => {
    void loadFeed();
  }, [loadFeed]);

  const teamNames = useMemo(() => {
    const names = new Set<string>();
    for (const post of posts) {
      if (post.sender_team_name) names.add(post.sender_team_name);
    }
    for (const ch of channels) {
      if (ch.peer_team_name) names.add(ch.peer_team_name);
      if (ch.team_a_name) names.add(ch.team_a_name);
      if (ch.team_b_name) names.add(ch.team_b_name);
    }
    return [...names].sort((a, b) => a.localeCompare(b));
  }, [channels, posts]);

  const filtered = useMemo(() => {
    let rows = posts;
    const orgTeamName = selectedOrgTeamId
      ? orgTeams.find((t) => t.id === selectedOrgTeamId)?.name
      : null;
    if (orgTeamName) {
      rows = rows.filter(
        (p) =>
          p.sender_team_name === orgTeamName ||
          (p.package_title?.toLowerCase().includes(orgTeamName.toLowerCase()) ?? false)
      );
    }
    if (teamFilter !== "all") {
      rows = rows.filter((p) => p.sender_team_name === teamFilter);
    }
    if (typeFilter === "announcement") {
      rows = rows.filter((p) => isAnnouncement(p));
    } else if (typeFilter === "update") {
      rows = rows.filter((p) => !isAnnouncement(p));
    }
    return rows;
  }, [orgTeams, posts, selectedOrgTeamId, teamFilter, typeFilter]);

  const grouped = useMemo(() => {
    const map = new Map<string, ChannelPostRow[]>();
    for (const post of filtered) {
      const key = dateGroupLabel(post.created_at);
      const list = map.get(key) ?? [];
      list.push(post);
      map.set(key, list);
    }
    return map;
  }, [filtered]);

  if (!orgId) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        Missing orgId in the URL. Open Channels from a team link that includes <code>?orgId=…</code>
        .
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[800px] px-4 py-4 sm:px-6">
      <ChannelFeedComposer
        orgId={orgId}
        activeTeamId={teamId}
        myTeams={myTeams}
        orgTeams={orgTeams}
        defaultReceiverIds={peerTeamIds}
        onPublished={() => {
          void reloadNav();
          void loadFeed();
        }}
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="sr-only">Teams</span>
            <select
              className="h-10 rounded-[10px] border border-border bg-secondary px-3 text-sm text-foreground"
              value={teamFilter}
              onChange={(event) => setTeamFilter(event.target.value)}
              aria-label="Filter by team"
            >
              <option value="all">Teams</option>
              {teamNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="sr-only">Type</span>
            <select
              className="h-10 rounded-[10px] border border-border bg-secondary px-3 text-sm text-foreground"
              value={typeFilter}
              onChange={(event) =>
                setTypeFilter(event.target.value as "all" | "announcement" | "update")
              }
              aria-label="Filter by type"
            >
              <option value="all">Type</option>
              <option value="announcement">Announcement</option>
              <option value="update">Update</option>
            </select>
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">Sort:</span>
          <select
            className="h-10 rounded-[10px] border border-border bg-secondary px-3 text-foreground"
            value={sort}
            onChange={(event) => setSort(event.target.value as "priority" | "newest")}
            aria-label="Sort posts"
          >
            <option value="newest">Newest</option>
            <option value="priority">Priority</option>
          </select>
          <AiPriorityInfoButton />
          <Button type="button" variant="ghost" size="sm" onClick={() => void loadFeed()}>
            Refresh
          </Button>
        </div>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading feed…</p> : null}
      {status ? <p className="mb-3 text-sm text-muted-foreground">{status}</p> : null}

      <div className="flex flex-col gap-6">
        {[...grouped.entries()].map(([label, rows]) => (
          <section key={label} aria-label={label}>
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">{label}</h2>
            <ul className="flex flex-col gap-3">
              {rows.map((post) => (
                <li key={post.id}>
                  <ChannelPostDetailCard
                    post={post}
                    selected={selectedPostId === post.id}
                    onSelect={setSelectedPostId}
                    onMarkedRead={(id) =>
                      setPosts((current) =>
                        current.map((row) => (row.id === id ? { ...row, is_read: true } : row))
                      )
                    }
                  />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
