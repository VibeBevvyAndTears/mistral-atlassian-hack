"use client";

import { useParams, useSearchParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { AiPriorityInfoButton } from "@/features/channels/components/ai-priority-info-button";
import {
  ChannelPostDetailCard,
  type ChannelPostRow,
} from "@/features/channels/components/channel-post-detail-card";
import { PostReviewActions } from "@/features/review/components/post-review-actions";
import { apiClient, setTenantHeaders } from "@/lib/api-client";

interface ChannelOption {
  id: string;
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

const PAGE_SIZE = 10;

export function ChannelFeedPanel() {
  const params = useParams<{ teamId: string }>();
  const search = useSearchParams();
  const teamId = params.teamId;
  const orgId = search.get("orgId");

  const [channels, setChannels] = useState<ChannelOption[]>([]);
  const [channelId, setChannelId] = useState("");
  const [posts, setPosts] = useState<ChannelPostRow[]>([]);
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [sort, setSort] = useState<"priority" | "newest" | "oldest">("priority");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [topicTags, setTopicTags] = useState<string[]>([]);
  const [topicTagInput, setTopicTagInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    if (orgId && teamId) setTenantHeaders(orgId, teamId);
  }, [orgId, teamId]);

  const loadChannels = useCallback(async () => {
    if (!teamId || !orgId) return;
    setTenantHeaders(orgId, teamId);
    try {
      const { data } = await apiClient.get<ChannelOption[]>(`/api/teams/${teamId}/channels`);
      setChannels(data);
      setChannelId((current) => current || data[0]?.id || "");
      setStatus(data.length ? null : "No channels yet — send a package first.");
    } catch {
      setStatus("Could not load channels.");
    }
  }, [orgId, teamId]);

  const loadPosts = useCallback(async () => {
    if (!channelId || !orgId || !teamId) return;
    setTenantHeaders(orgId, teamId);
    try {
      const { data } = await apiClient.get<ChannelPostsPage>(`/api/channels/${channelId}/posts`, {
        params: {
          sort,
          unread_only: unreadOnly,
          topic_tags: topicTags.join(",") || undefined,
          q: searchQuery || undefined,
          page,
          page_size: PAGE_SIZE,
        },
      });
      setPosts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      if (data.page !== page) setPage(data.page);
      if (data.total === 0) {
        setStatus(
          searchQuery ? `No posts match “${searchQuery}”.` : "No posts in this channel yet."
        );
      } else {
        setStatus(null);
      }
      setSelectedPostId((current) => {
        if (current && data.items.some((p) => p.id === current)) return current;
        return data.items[0]?.id ?? null;
      });
    } catch {
      setStatus("Could not load feed.");
    }
  }, [channelId, orgId, page, searchQuery, sort, teamId, topicTags, unreadOnly]);

  useEffect(() => {
    void loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    if (!channelId) return;
    void loadPosts();
  }, [channelId, loadPosts]);

  function resetToFirstPage() {
    setPage(1);
    setSelectedPostId(null);
  }

  function addTopicTag() {
    const tag = topicTagInput.trim();
    if (tag && !topicTags.includes(tag)) {
      setTopicTags((tags) => [...tags, tag]);
      resetToFirstPage();
    }
    setTopicTagInput("");
  }

  function removeTopicTag(tag: string) {
    setTopicTags((tags) => tags.filter((value) => value !== tag));
    resetToFirstPage();
  }

  function submitSearch(event?: FormEvent) {
    event?.preventDefault();
    setSearchQuery(searchInput.trim());
    resetToFirstPage();
  }

  function clearSearch() {
    setSearchInput("");
    setSearchQuery("");
    resetToFirstPage();
  }

  function markRead(id: string) {
    setPosts((rows) => rows.map((row) => (row.id === id ? { ...row, is_read: true } : row)));
  }

  if (!orgId) {
    return (
      <Card>
        <CardContent className="pt-4 text-sm text-muted-foreground">
          Missing orgId in the URL. Open Channels from a team link that includes{" "}
          <code>?orgId=…</code>.
        </CardContent>
      </Card>
    );
  }

  const rangeStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, total);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Channel feed</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span>Channel</span>
            <select
              className="rounded-md border border-border bg-background px-2 py-2"
              value={channelId}
              onChange={(event) => {
                setChannelId(event.target.value);
                setSelectedPostId(null);
                setPosts([]);
                setPage(1);
                setSearchInput("");
                setSearchQuery("");
              }}
              aria-label="Channel"
            >
              {channels.length === 0 ? <option value="">No channels</option> : null}
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.peer_team_name
                    ? `With ${ch.peer_team_name}`
                    : `${ch.team_a_name ?? "Team A"} ↔ ${ch.team_b_name ?? "Team B"}`}
                </option>
              ))}
            </select>
          </label>

          <form className="flex flex-col gap-1" onSubmit={submitSearch}>
            <label className="text-sm" htmlFor="channel-post-search">
              Search posts in this channel
            </label>
            <div className="flex gap-2">
              <Input
                id="channel-post-search"
                placeholder="Title, tags, body, sender…"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                aria-label="Search posts in this channel"
              />
              <Button type="submit" variant="secondary">
                Search
              </Button>
              {searchQuery ? (
                <Button type="button" variant="ghost" onClick={clearSearch}>
                  Clear
                </Button>
              ) : null}
            </div>
            <p className="text-xs text-muted-foreground">
              Weighted lexical search: all words must match; title and tags rank higher than body.
              Results stay scoped to this channel.
            </p>
          </form>

          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <span>Sort</span>
              <select
                className="rounded-md border border-border bg-background px-2 py-1"
                value={sort}
                onChange={(event) => {
                  setSort(event.target.value as "priority" | "newest" | "oldest");
                  resetToFirstPage();
                }}
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
                onChange={(event) => {
                  setUnreadOnly(event.target.checked);
                  resetToFirstPage();
                }}
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
          <Button type="button" variant="outline" onClick={() => void loadPosts()}>
            Refresh feed
          </Button>
          {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
        </CardContent>
      </Card>

      <ul className="flex flex-col gap-4">
        {posts.map((post) => (
          <li key={post.id}>
            <button
              type="button"
              className="mb-2 text-xs text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setSelectedPostId(post.id)}
            >
              {selectedPostId === post.id ? "Selected for review" : "Select for review actions"}
            </button>
            <ChannelPostDetailCard post={post} onMarkedRead={markRead} />
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className="text-muted-foreground">
          {total === 0
            ? "0 posts"
            : `Showing ${rangeStart}–${rangeEnd} of ${total} · page ${page} of ${totalPages}`}
        </p>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={page >= totalPages || total === 0}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>

      {selectedPostId ? <PostReviewActions postId={selectedPostId} /> : null}
    </div>
  );
}
