"use client";

import { CaretDown, Megaphone, Paperclip, Plus, X } from "@phosphor-icons/react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient, setTenantHeaders } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export interface ChannelComposerTeam {
  id: string;
  name: string;
}

interface ChannelFeedComposerProps {
  orgId: string;
  activeTeamId: string;
  myTeams: ChannelComposerTeam[];
  orgTeams: ChannelComposerTeam[];
  /** Opposite / peer team ids for the current chat — pre-selected as receivers. */
  defaultReceiverIds?: string[];
  onPublished: () => void;
}

type PostType = "announcement" | "update";

interface AttachedDoc {
  id: string;
  filename: string;
}

function uniqueIds(ids: string[]): string[] {
  return [...new Set(ids.filter(Boolean))];
}

export function ChannelFeedComposer({
  orgId,
  activeTeamId,
  myTeams,
  orgTeams,
  defaultReceiverIds = [],
  onPublished,
}: ChannelFeedComposerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLElement>(null);
  const composerId = useId();
  const [expanded, setExpanded] = useState(false);
  const [publisherTeamId, setPublisherTeamId] = useState(activeTeamId);
  const [receiverIds, setReceiverIds] = useState<string[]>(() =>
    uniqueIds(defaultReceiverIds.filter((id) => id !== activeTeamId))
  );
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [postType, setPostType] = useState<PostType>("announcement");
  const [docs, setDocs] = useState<AttachedDoc[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [addReceiverOpen, setAddReceiverOpen] = useState(false);

  useEffect(() => {
    setPublisherTeamId(activeTeamId);
  }, [activeTeamId]);

  useEffect(() => {
    const peers = uniqueIds(defaultReceiverIds.filter((id) => id !== publisherTeamId));
    setReceiverIds((current) => {
      if (current.length === 0 && peers.length > 0) return peers;
      return current.filter((id) => id !== publisherTeamId);
    });
  }, [defaultReceiverIds, publisherTeamId]);

  useEffect(() => {
    if (!expanded) return;
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setExpanded(false);
        setAddReceiverOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setExpanded(false);
        setAddReceiverOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [expanded]);

  const publisher =
    myTeams.find((t) => t.id === publisherTeamId) ??
    myTeams.find((t) => t.id === activeTeamId) ??
    myTeams[0] ??
    null;

  const receiverOptions = orgTeams.filter((t) => t.id !== (publisher?.id ?? publisherTeamId));
  const selectedReceivers = receiverOptions.filter((t) => receiverIds.includes(t.id));

  const canPublish =
    Boolean(publisher) &&
    receiverIds.length > 0 &&
    title.trim().length > 0 &&
    body.trim().length > 0 &&
    !loading;

  function expand() {
    setExpanded(true);
  }

  function toggleReceiver(id: string) {
    setReceiverIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id]
    );
    setAddReceiverOpen(false);
  }

  async function onPickFiles(files: FileList | null) {
    if (!files?.length || !publisher) return;
    setTenantHeaders(orgId, publisher.id);
    setStatus(null);
    const uploaded: AttachedDoc[] = [];
    for (const file of Array.from(files)) {
      try {
        const form = new FormData();
        form.append("file", file);
        const { data } = await apiClient.post<AttachedDoc>(
          `/api/teams/${publisher.id}/documents`,
          form,
          { headers: { "Content-Type": "multipart/form-data" } }
        );
        uploaded.push({ id: data.id, filename: data.filename });
      } catch {
        setStatus(`Could not upload ${file.name}.`);
      }
    }
    if (uploaded.length) {
      setDocs((current) => [...current, ...uploaded]);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function waitUntilSent(packageId: string) {
    for (let i = 0; i < 40; i += 1) {
      const { data } = await apiClient.get<{ status: string }>(`/api/packages/${packageId}`);
      if (data.status === "sent") return;
      if (data.status === "failed" || data.status === "error") {
        throw new Error("Send failed");
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    throw new Error("Send timed out");
  }

  async function publish() {
    if (!canPublish || !publisher) return;
    setLoading(true);
    setStatus(null);
    setTenantHeaders(orgId, publisher.id);
    const tags = postType === "announcement" ? ["Announcement"] : ["Update"];
    const targets = [...receiverIds];
    try {
      for (const targetId of targets) {
        const { data: pkg } = await apiClient.post<{ id: string }>(
          `/api/teams/${publisher.id}/packages`,
          {
            title: title.trim(),
            body: body.trim(),
            target_team_id: targetId,
            bypass_incomplete_pipeline: true,
            included_node_ids: [],
            topic_tags: tags,
            attached_document_ids: docs.map((d) => d.id),
          }
        );
        await apiClient.post(`/api/packages/${pkg.id}/send`, {
          acknowledge_conflicts: true,
        });
        await waitUntilSent(pkg.id);
      }
      setTitle("");
      setBody("");
      setDocs([]);
      setPostType("announcement");
      setAddReceiverOpen(false);
      setReceiverIds(uniqueIds(defaultReceiverIds.filter((id) => id !== publisher.id)));
      setStatus(
        `Published to ${targets.length} team${targets.length === 1 ? "" : "s"} as ${publisher.name}.`
      );
      setExpanded(false);
      onPublished();
    } catch {
      setStatus("Publish failed. Check that you can send from the selected team.");
    } finally {
      setLoading(false);
    }
  }

  if (myTeams.length === 0) {
    return (
      <section className="mb-4 rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
        Join a team before publishing. Select one of your teams in the sidebar first.
      </section>
    );
  }

  if (!expanded) {
    return (
      <section ref={rootRef} className="mb-4" aria-label="Publish a post">
        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left text-sm text-muted-foreground shadow-[0_8px_24px_rgba(0,0,0,0.25)] transition-colors hover:bg-secondary/40"
          onClick={expand}
          aria-expanded={false}
          aria-controls={composerId}
        >
          <span
            className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-foreground"
            aria-hidden
          >
            +
          </span>
          <span>Write a post to {selectedReceivers[0]?.name ?? "the other team"}…</span>
        </button>
        {status ? <p className="mt-2 text-xs text-muted-foreground">{status}</p> : null}
      </section>
    );
  }

  return (
    <section
      ref={rootRef}
      id={composerId}
      className="mb-4 rounded-xl border border-border bg-card p-4 text-card-foreground shadow-[0_8px_24px_rgba(0,0,0,0.25)]"
      aria-label="Publish a post"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="composer-publisher">
          Publishing team
        </label>
        <select
          id="composer-publisher"
          className="h-9 rounded-full border border-border bg-secondary px-3 text-sm font-medium"
          value={publisher?.id ?? ""}
          onChange={(event) => {
            const next = event.target.value;
            setPublisherTeamId(next);
            setReceiverIds((ids) => {
              const withoutSelf = ids.filter((id) => id !== next);
              if (withoutSelf.length > 0) return withoutSelf;
              return uniqueIds(defaultReceiverIds.filter((id) => id !== next));
            });
            setTenantHeaders(orgId, next);
          }}
        >
          {myTeams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>

        {selectedReceivers.map((team) => (
          <button
            key={team.id}
            type="button"
            className="inline-flex h-9 items-center gap-1.5 rounded-full bg-secondary px-3 text-sm"
            onClick={() => toggleReceiver(team.id)}
            aria-label={`Remove receiver ${team.name}`}
          >
            {team.name}
            <X className="size-3.5" aria-hidden />
          </button>
        ))}

        <div className="relative">
          <Button
            type="button"
            variant="secondary"
            size="icon-sm"
            className="rounded-full"
            aria-label="Add receiver team"
            aria-expanded={addReceiverOpen}
            onClick={() => setAddReceiverOpen((v) => !v)}
          >
            <Plus className="size-4" />
          </Button>
          {addReceiverOpen ? (
            <div className="absolute top-full left-0 z-20 mt-1 min-w-[12rem] rounded-md border border-border bg-popover p-1 shadow-[0_8px_24px_rgba(0,0,0,0.45)]">
              {receiverOptions.length === 0 ? (
                <p className="px-2 py-1.5 text-xs text-muted-foreground">No other teams</p>
              ) : (
                receiverOptions.map((team) => {
                  const selected = receiverIds.includes(team.id);
                  return (
                    <button
                      key={team.id}
                      type="button"
                      className={cn(
                        "block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-muted",
                        selected && "bg-muted"
                      )}
                      onClick={() => toggleReceiver(team.id)}
                    >
                      {selected ? "✓ " : ""}
                      {team.name}
                    </button>
                  );
                })
              )}
            </div>
          ) : null}
        </div>
      </div>

      <Input
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Title"
        aria-label="Post title"
        autoFocus
        className="mb-2 h-10 border-0 bg-transparent px-0 text-base font-semibold shadow-none focus-visible:ring-0"
      />
      <textarea
        value={body}
        onChange={(event) => setBody(event.target.value)}
        placeholder="Text"
        aria-label="Post body"
        rows={5}
        className="mb-3 min-h-[7.5rem] w-full resize-y rounded-md border-0 bg-transparent px-0 text-sm text-foreground outline-none placeholder:text-muted-foreground"
      />

      {docs.length > 0 ? (
        <ul className="mb-3 flex flex-wrap gap-2">
          {docs.map((doc) => (
            <li
              key={doc.id}
              className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 text-xs"
            >
              <Paperclip className="size-3" aria-hidden />
              <span className="max-w-[10rem] truncate">{doc.filename}</span>
              <button
                type="button"
                aria-label={`Remove ${doc.filename}`}
                onClick={() => setDocs((current) => current.filter((d) => d.id !== doc.id))}
              >
                <X className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <label className="relative inline-flex h-9 items-center gap-1.5 rounded-full bg-secondary px-3 text-sm">
          <Megaphone className="size-3.5 text-destructive" weight="fill" aria-hidden />
          <span className="sr-only">Post type</span>
          <select
            className="appearance-none bg-transparent pr-4 text-sm outline-none"
            value={postType}
            onChange={(event) => setPostType(event.target.value as PostType)}
            aria-label="Post type"
          >
            <option value="announcement">Announcement</option>
            <option value="update">Update</option>
          </select>
          <CaretDown className="pointer-events-none absolute right-2 size-3" aria-hidden />
        </label>

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          multiple
          onChange={(event) => void onPickFiles(event.target.files)}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Attach documents"
          onClick={() => fileInputRef.current?.click()}
          disabled={!publisher}
        >
          <Paperclip className="size-4" />
        </Button>

        <div className="ml-auto flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setTitle("");
              setBody("");
              setDocs([]);
              setAddReceiverOpen(false);
              setExpanded(false);
            }}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!canPublish}
            onClick={() => void publish()}
            className="rounded-full px-4"
          >
            {loading ? "Posting…" : "Post"}
          </Button>
        </div>
      </div>

      <p className="mt-3 text-sm text-muted-foreground">
        {publisher
          ? selectedReceivers.length > 0
            ? `Posting as ${publisher.name} → ${selectedReceivers.map((t) => t.name).join(", ")}`
            : `Posting as ${publisher.name}. Add a receiver team.`
          : "Select one of your teams to publish."}
      </p>
      {status ? <p className="mt-1 text-xs text-muted-foreground">{status}</p> : null}
    </section>
  );
}
