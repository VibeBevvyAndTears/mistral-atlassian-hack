"use client";

import { DownloadSimple, FileText } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export interface ChannelSourceDocument {
  id: string;
  filename: string;
  status: string;
  content_type?: string | null;
}

interface ChannelPostSourceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  postId: string;
  packageTitle: string;
  documents: ChannelSourceDocument[];
}

function isTextLike(filename: string, contentType: string | null | undefined): boolean {
  const lower = filename.toLowerCase();
  if (
    lower.endsWith(".txt") ||
    lower.endsWith(".md") ||
    lower.endsWith(".csv") ||
    lower.endsWith(".json") ||
    lower.endsWith(".log")
  ) {
    return true;
  }
  return Boolean(contentType?.startsWith("text/"));
}

function isPdf(filename: string, contentType: string | null | undefined): boolean {
  return filename.toLowerCase().endsWith(".pdf") || contentType === "application/pdf";
}

export function ChannelPostSourceModal({
  open,
  onOpenChange,
  postId,
  packageTitle,
  documents,
}: ChannelPostSourceModalProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = documents.find((d) => d.id === selectedId) ?? null;

  const clearPreview = useCallback(() => {
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
    setPreviewText(null);
  }, []);

  useEffect(() => {
    if (!open) {
      setSelectedId(null);
      clearPreview();
      setError(null);
      setLoading(false);
      return;
    }
    if (documents.length === 1) {
      setSelectedId(documents[0].id);
    }
  }, [clearPreview, documents, open]);

  useEffect(() => {
    if (!open || !selectedId || !selected) {
      clearPreview();
      return;
    }

    let cancelled = false;
    clearPreview();
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const { data } = await apiClient.get<Blob>(
          `/api/posts/${postId}/sources/${selectedId}/content`,
          {
            params: { disposition: "inline" },
            responseType: "blob",
          }
        );
        if (cancelled) return;
        const type = selected.content_type || data.type || "application/octet-stream";
        const blob = data.type ? data : new Blob([data], { type });
        if (isTextLike(selected.filename, type)) {
          setPreviewText(await blob.text());
        } else {
          setPreviewUrl(URL.createObjectURL(blob));
        }
      } catch {
        if (!cancelled) setError("Could not load this source file.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [clearPreview, open, postId, selected, selectedId]);

  async function downloadSelected() {
    if (!selected) return;
    setError(null);
    try {
      const { data } = await apiClient.get<Blob>(
        `/api/posts/${postId}/sources/${selected.id}/content`,
        {
          params: { disposition: "attachment" },
          responseType: "blob",
        }
      );
      const type = selected.content_type || data.type || "application/octet-stream";
      const blob = data.type ? data : new Blob([data], { type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = selected.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not download this source file.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-hidden sm:max-w-2xl" showCloseButton>
        <DialogHeader>
          <DialogTitle>Source files</DialogTitle>
          <DialogDescription>
            Package: {packageTitle || "—"}. Open a file to preview, or download it.
          </DialogDescription>
        </DialogHeader>

        {documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No linked documents.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-[12rem_1fr]">
            <ul className="flex max-h-64 flex-col gap-1 overflow-auto md:max-h-[50vh]">
              {documents.map((doc) => (
                <li key={doc.id}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm hover:bg-muted",
                      selectedId === doc.id && "bg-muted"
                    )}
                    onClick={() => setSelectedId(doc.id)}
                  >
                    <FileText
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                      aria-hidden
                    />
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{doc.filename}</span>
                      <span className="block text-xs text-muted-foreground">{doc.status}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>

            <div className="flex min-h-48 flex-col rounded-lg border border-border bg-background">
              <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
                <p className="truncate text-sm font-medium">
                  {selected?.filename ?? "Select a file"}
                </p>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="shrink-0 gap-1.5"
                  disabled={!selected || loading}
                  onClick={() => void downloadSelected()}
                >
                  <DownloadSimple className="size-4" aria-hidden />
                  Download
                </Button>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-3">
                {loading ? <p className="text-sm text-muted-foreground">Loading preview…</p> : null}
                {error ? <p className="text-sm text-destructive">{error}</p> : null}
                {!loading && !error && previewText !== null ? (
                  <pre className="whitespace-pre-wrap break-words font-mono text-xs text-foreground">
                    {previewText}
                  </pre>
                ) : null}
                {!loading &&
                !error &&
                previewUrl &&
                selected &&
                isPdf(selected.filename, selected.content_type) ? (
                  <iframe
                    title={selected.filename}
                    src={previewUrl}
                    className="h-[50vh] w-full rounded-md border border-border bg-card"
                  />
                ) : null}
                {!loading &&
                !error &&
                previewUrl &&
                selected &&
                !isPdf(selected.filename, selected.content_type) &&
                !isTextLike(selected.filename, selected.content_type) ? (
                  <p className="text-sm text-muted-foreground">
                    Preview is not available for this file type. Use Download to save it.
                  </p>
                ) : null}
                {!loading && !error && !selected ? (
                  <p className="text-sm text-muted-foreground">Choose a file from the list.</p>
                ) : null}
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
