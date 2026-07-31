"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { extractErrorMessage } from "@/features/teams/utils/extract-error-message";
import { apiClient } from "@/lib/api-client";
import { useSession } from "@/lib/auth/auth-client";
import { isRealtimeConfigured, subscribeJob } from "@/lib/realtime/supabase";

/** PRD D-9 / wireframe W1 team profile schema. */
export type TeamProfileFields = {
  identity_label: string;
  identity_description: string;
  translation_style: string;
  expertise_level: string;
  detail_depth_default: string;
  preferred_language: string;
  responsibilities: string[];
  jargon_known: string[];
  jargon_must_explain: string[];
};

const EMPTY_PROFILE: TeamProfileFields = {
  identity_label: "",
  identity_description: "",
  translation_style: "",
  expertise_level: "",
  detail_depth_default: "",
  preferred_language: "",
  responsibilities: [],
  jargon_known: [],
  jargon_must_explain: [],
};

const EXPERTISE_OPTIONS = ["novice", "familiar", "practitioner", "expert"] as const;
const DETAIL_OPTIONS = ["brief", "balanced", "deep"] as const;
const TRANSLATION_STYLE_OPTIONS = ["Technical", "Business", "Simple", "High-level scope"] as const;

const teamProfileSchema = z.object({
  identity_label: z.string().trim().min(1, "Identity label is required."),
  identity_description: z.string().trim().min(1, "Function & responsibilities is required."),
  responsibilities: z.array(z.string()).min(1, "Add at least one responsibility tag."),
  expertise_level: z.string().trim().min(1, "Select an expertise level."),
  preferred_language: z.string().trim().min(1, "Preferred language is required."),
  detail_depth_default: z.string().trim().min(1, "Select a detail depth."),
  translation_style: z.string().trim().min(1, "Select a translation style."),
});

type ValidationErrors = Partial<Record<keyof z.infer<typeof teamProfileSchema>, string>>;

type ProfileApi = {
  version: number;
  data: Record<string, unknown>;
};

type DraftApi = {
  data: {
    purpose?: string;
    audiences?: string[];
    communication_preferences?: string[];
    known_terms?: string[];
  };
};

type DocRow = {
  id: string;
  filename: string;
  status: string;
  job_id: string | null;
};

type MemberRow = {
  user_id: string;
  role: string;
};

type ProfileVersionSummary = {
  version: number;
  created_at: string;
  created_by: string;
};

type DraftPhase = "idle" | "uploading" | "ingesting" | "drafting" | "error";

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function parseProfileData(data: Record<string, unknown> | undefined): TeamProfileFields {
  const raw = data ?? {};
  return {
    identity_label: asString(raw.identity_label),
    identity_description: asString(raw.identity_description),
    translation_style: asString(raw.translation_style),
    expertise_level: asString(raw.expertise_level),
    detail_depth_default: asString(raw.detail_depth_default),
    preferred_language: asString(raw.preferred_language),
    responsibilities: asStringList(raw.responsibilities),
    jargon_known: asStringList(raw.jargon_known),
    jargon_must_explain: asStringList(raw.jargon_must_explain),
  };
}

function RequiredMark() {
  return (
    <span className="text-destructive" aria-hidden="true">
      {" *"}
    </span>
  );
}

function FieldError({ id, message }: Readonly<{ id: string; message?: string }>) {
  if (!message) return null;
  return (
    <p id={id} className="text-xs text-destructive">
      {message}
    </p>
  );
}

function ChipField({
  label,
  hint,
  values,
  onChange,
  variant = "known",
  required = false,
  error,
}: Readonly<{
  label: string;
  hint?: string;
  values: string[];
  onChange: (next: string[]) => void;
  variant?: "known" | "explain";
  required?: boolean;
  error?: string;
}>) {
  const [draft, setDraft] = useState("");

  function addChip() {
    const next = draft
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    if (next.length === 0) return;
    const merged = [...values];
    for (const term of next) {
      if (!merged.includes(term)) merged.push(term);
    }
    onChange(merged);
    setDraft("");
  }

  return (
    <div className="space-y-2">
      <div>
        <p className="text-sm font-medium">
          {label}
          {required ? <RequiredMark /> : null}
        </p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {values.length === 0 ? (
          <span className="text-xs text-muted-foreground">No terms yet</span>
        ) : (
          values.map((term) => (
            <button
              key={term}
              type="button"
              className={
                variant === "explain"
                  ? "rounded-md border border-destructive/40 bg-destructive/10 px-2 py-0.5 text-xs text-destructive"
                  : "rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs"
              }
              onClick={() => onChange(values.filter((item) => item !== term))}
              title="Remove"
            >
              {term} ×
            </button>
          ))
        )}
      </div>
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add term, or comma-separated list"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addChip();
            }
          }}
        />
        <Button type="button" variant="outline" onClick={addChip}>
          Add
        </Button>
      </div>
      <FieldError id={`${label}-error`} message={error} />
    </div>
  );
}

export function TeamProfileForm({ teamId }: Readonly<{ teamId: string }>) {
  const [fields, setFields] = useState<TeamProfileFields>(EMPTY_PROFILE);
  const [fieldErrors, setFieldErrors] = useState<ValidationErrors>({});
  const [version, setVersion] = useState<number | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [draftPhase, setDraftPhase] = useState<DraftPhase>("idle");
  const [draftMessage, setDraftMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const draftCleanupRef = useRef<(() => void) | null>(null);

  const { data: session } = useSession();
  const [canEdit, setCanEdit] = useState<boolean | null>(null);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [versions, setVersions] = useState<ProfileVersionSummary[] | null>(null);
  const [previewVersion, setPreviewVersion] = useState<{
    version: number;
    fields: TeamProfileFields;
  } | null>(null);
  const [historyStatus, setHistoryStatus] = useState<string | null>(null);

  useEffect(() => {
    return () => draftCleanupRef.current?.();
  }, []);

  useEffect(() => {
    const userId = session?.user?.id;
    if (!userId) return;
    let cancelled = false;
    apiClient
      .get<MemberRow[]>(`/api/teams/${teamId}/members`)
      .then(({ data }) => {
        if (cancelled) return;
        const me = data.find((member) => member.user_id === userId);
        setCanEdit(me != null && (me.role === "owner" || me.role === "lead"));
      })
      .catch(() => {
        if (!cancelled) setCanEdit(false);
      });
    return () => {
      cancelled = true;
    };
  }, [teamId, session?.user?.id]);

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const { data } = await apiClient.get<ProfileApi>(`/api/teams/${teamId}/profile`);
      setVersion(data.version);
      setFields(parseProfileData(data.data));
    } catch {
      setVersion(null);
      setFields(EMPTY_PROFILE);
      setStatus("No profile yet — fill the fields and save to create v1.");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void load();
  }, [load]);

  function updateField<K extends keyof TeamProfileFields>(key: K, value: TeamProfileFields[K]) {
    setFields((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key as keyof ValidationErrors];
      return next;
    });
  }

  async function onSave() {
    const payload: TeamProfileFields = {
      ...fields,
      identity_label: fields.identity_label.trim(),
      identity_description: fields.identity_description.trim(),
      translation_style: fields.translation_style.trim(),
      expertise_level: fields.expertise_level.trim(),
      detail_depth_default: fields.detail_depth_default.trim(),
      preferred_language: fields.preferred_language.trim(),
      responsibilities: fields.responsibilities.map((item) => item.trim()).filter(Boolean),
      jargon_known: fields.jargon_known.map((item) => item.trim()).filter(Boolean),
      jargon_must_explain: fields.jargon_must_explain.map((item) => item.trim()).filter(Boolean),
    };

    const result = teamProfileSchema.safeParse(payload);
    if (!result.success) {
      const flat = result.error.flatten().fieldErrors;
      const nextErrors: ValidationErrors = {};
      for (const key of Object.keys(flat) as (keyof ValidationErrors)[]) {
        nextErrors[key] = flat[key]?.[0];
      }
      setFieldErrors(nextErrors);
      setStatus("Fix the highlighted fields before saving.");
      return;
    }
    setFieldErrors({});

    setLoading(true);
    setStatus(null);
    try {
      const { data } = await apiClient.put<ProfileApi>(`/api/teams/${teamId}/profile`, {
        data: payload,
      });
      setVersion(data.version);
      setFields(parseProfileData(data.data));
      setStatus(`Saved profile v${data.version}`);
      setVersions(null);
    } catch (err) {
      setStatus(extractErrorMessage(err, "Save failed"));
    } finally {
      setLoading(false);
    }
  }

  function applyDraft(draft: DraftApi["data"]) {
    setFields((prev) => ({
      ...prev,
      identity_label: draft.purpose?.trim() || prev.identity_label,
      identity_description: draft.purpose?.trim() || prev.identity_description,
      responsibilities:
        draft.audiences && draft.audiences.length > 0 ? draft.audiences : prev.responsibilities,
      jargon_known:
        draft.known_terms && draft.known_terms.length > 0 ? draft.known_terms : prev.jargon_known,
    }));
  }

  async function fetchDocument(documentId: string): Promise<DocRow> {
    const { data } = await apiClient.get<DocRow>(`/api/documents/${documentId}`);
    return data;
  }

  async function runDraftFromDocument(documentIds: string[]) {
    setDraftPhase("drafting");
    setDraftMessage(
      documentIds.length > 1
        ? "Drafting profile from documents…"
        : "Drafting profile from document…"
    );
    try {
      const { data } = await apiClient.post<DraftApi>(
        `/api/teams/${teamId}/profile/draft-from-document`,
        { document_ids: documentIds }
      );
      applyDraft(data.data);
      setDraftPhase("idle");
      setDraftMessage(null);
      setStatus("Draft applied from document(s) — review and save to version it.");
    } catch (err) {
      setDraftPhase("error");
      setDraftMessage(extractErrorMessage(err, "Draft failed."));
    }
  }

  function pollUntilReady(documentIds: string[], jobIds: (string | null)[]) {
    setDraftPhase("ingesting");
    setDraftMessage(
      documentIds.length > 1 ? `Ingesting ${documentIds.length} documents…` : "Ingesting document…"
    );

    const cleanup = () => {
      draftCleanupRef.current?.();
      draftCleanupRef.current = null;
    };

    const evaluate = async () => {
      const docs = await Promise.all(documentIds.map(fetchDocument));
      const stuck = docs.find(
        (doc) => doc.status === "failed" || doc.status === "needs_manual_review"
      );
      if (stuck) {
        cleanup();
        setDraftPhase("error");
        setDraftMessage("Ingestion needs attention on the Documents page — then browse again.");
        return;
      }
      const readyCount = docs.filter((doc) => doc.status === "ready").length;
      if (readyCount === docs.length) {
        cleanup();
        await runDraftFromDocument(documentIds);
        return;
      }
      if (docs.length > 1) {
        setDraftMessage(`Ingesting… ${readyCount} of ${docs.length} ready`);
      }
    };

    void evaluate();

    const jobsToWatch = jobIds.filter((id): id is string => Boolean(id));
    if (jobsToWatch.length > 0 && isRealtimeConfigured()) {
      const unsubs = jobsToWatch.map((jobId) => subscribeJob(jobId, () => void evaluate()));
      draftCleanupRef.current = () => {
        for (const unsub of unsubs) unsub?.();
      };
      return;
    }

    const interval = window.setInterval(() => void evaluate(), 5_000);
    draftCleanupRef.current = () => window.clearInterval(interval);
  }

  async function onFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (selected.length === 0) return;
    const files = selected.slice(0, 3);
    const truncated = selected.length > 3;

    draftCleanupRef.current?.();
    draftCleanupRef.current = null;
    setDraftPhase("uploading");
    setDraftMessage(
      truncated
        ? "Only the first 3 documents are used — uploading…"
        : files.length > 1
          ? `Uploading ${files.length} documents…`
          : "Uploading document…"
    );
    try {
      const uploads = await Promise.all(
        files.map(async (file) => {
          const body = new FormData();
          body.append("file", file);
          const { data } = await apiClient.post<DocRow>(`/api/teams/${teamId}/documents`, body, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          return data;
        })
      );
      pollUntilReady(
        uploads.map((doc) => doc.id),
        uploads.map((doc) => doc.job_id)
      );
    } catch (err) {
      setDraftPhase("error");
      setDraftMessage(extractErrorMessage(err, "Upload failed."));
    }
  }

  const draftBusy =
    draftPhase === "uploading" || draftPhase === "ingesting" || draftPhase === "drafting";

  async function toggleHistory() {
    if (historyOpen) {
      setHistoryOpen(false);
      return;
    }
    setHistoryOpen(true);
    setPreviewVersion(null);
    if (versions !== null) return;
    setHistoryStatus(null);
    try {
      const { data } = await apiClient.get<ProfileVersionSummary[]>(
        `/api/teams/${teamId}/profile/versions`
      );
      setVersions(data);
    } catch (err) {
      setHistoryStatus(extractErrorMessage(err, "Could not load version history."));
    }
  }

  async function previewVersionAt(targetVersion: number) {
    setHistoryStatus(null);
    try {
      const { data } = await apiClient.get<ProfileApi>(
        `/api/teams/${teamId}/profile/versions/${targetVersion}`
      );
      setPreviewVersion({ version: targetVersion, fields: parseProfileData(data.data) });
    } catch (err) {
      setHistoryStatus(extractErrorMessage(err, "Could not load that version."));
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>Team profile</CardTitle>
        <div className="flex items-center gap-2">
          {version != null ? (
            <span className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground">
              v{version}
            </span>
          ) : null}
          <Button type="button" variant="ghost" size="sm" onClick={() => void toggleHistory()}>
            {historyOpen ? "Hide history" : "History"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {historyOpen ? (
          <div className="space-y-3 rounded-md border border-border p-3">
            <p className="text-sm font-medium">Version history</p>
            {versions === null ? (
              <p className="text-xs text-muted-foreground">Loading…</p>
            ) : versions.length === 0 ? (
              <p className="text-xs text-muted-foreground">No versions yet.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {versions.map((v) => (
                  <button
                    key={v.version}
                    type="button"
                    className={
                      previewVersion?.version === v.version
                        ? "rounded-md border border-ring bg-muted px-2 py-1 text-xs"
                        : "rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
                    }
                    onClick={() => void previewVersionAt(v.version)}
                  >
                    v{v.version} · {new Date(v.created_at).toLocaleDateString()}
                  </button>
                ))}
              </div>
            )}
            {previewVersion ? (
              <div className="space-y-1 rounded-md border border-border bg-muted/30 p-3 text-xs">
                <p className="text-sm font-medium">Viewing v{previewVersion.version} (read-only)</p>
                <dl className="grid grid-cols-[10rem_1fr] gap-x-2 gap-y-1">
                  <dt className="text-muted-foreground">Identity label</dt>
                  <dd>{previewVersion.fields.identity_label || "—"}</dd>
                  <dt className="text-muted-foreground">Function &amp; responsibilities</dt>
                  <dd>{previewVersion.fields.identity_description || "—"}</dd>
                  <dt className="text-muted-foreground">Responsibility tags</dt>
                  <dd>{previewVersion.fields.responsibilities.join(", ") || "—"}</dd>
                  <dt className="text-muted-foreground">Expertise level</dt>
                  <dd>{previewVersion.fields.expertise_level || "—"}</dd>
                  <dt className="text-muted-foreground">Preferred language</dt>
                  <dd>{previewVersion.fields.preferred_language || "—"}</dd>
                  <dt className="text-muted-foreground">Detail depth</dt>
                  <dd>{previewVersion.fields.detail_depth_default || "—"}</dd>
                  <dt className="text-muted-foreground">Translation style</dt>
                  <dd>{previewVersion.fields.translation_style || "—"}</dd>
                  <dt className="text-muted-foreground">Known jargon</dt>
                  <dd>{previewVersion.fields.jargon_known.join(", ") || "—"}</dd>
                  <dt className="text-muted-foreground">Must explain</dt>
                  <dd>{previewVersion.fields.jargon_must_explain.join(", ") || "—"}</dd>
                </dl>
              </div>
            ) : null}
            {historyStatus ? <p className="text-xs text-destructive">{historyStatus}</p> : null}
          </div>
        ) : null}

        {canEdit === false ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            Only a Team Lead can edit this profile. You can still browse the fields below.
          </p>
        ) : null}

        <fieldset disabled={canEdit !== true} className="space-y-5">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="identity_label">
              Identity label
              <RequiredMark />
            </label>
            <Input
              id="identity_label"
              value={fields.identity_label}
              onChange={(e) => updateField("identity_label", e.target.value)}
              placeholder="e.g. Marketing"
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.identity_label)}
              aria-describedby={fieldErrors.identity_label ? "identity_label-error" : undefined}
            />
            <FieldError id="identity_label-error" message={fieldErrors.identity_label} />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="identity_description">
              Function &amp; responsibilities
              <RequiredMark />
            </label>
            <textarea
              id="identity_description"
              className="min-h-24 w-full rounded-md border border-input bg-transparent px-2.5 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              value={fields.identity_description}
              onChange={(e) => updateField("identity_description", e.target.value)}
              placeholder="What this team owns and who they serve"
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.identity_description)}
              aria-describedby={
                fieldErrors.identity_description ? "identity_description-error" : undefined
              }
            />
            <FieldError
              id="identity_description-error"
              message={fieldErrors.identity_description}
            />
            <ChipField
              label="Responsibility tags"
              hint="Short tags for adaptation context (responsibilities[])"
              values={fields.responsibilities}
              onChange={(next) => updateField("responsibilities", next)}
              required
              error={fieldErrors.responsibilities}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="expertise_level">
                Expertise level
                <RequiredMark />
              </label>
              <select
                id="expertise_level"
                className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
                value={fields.expertise_level}
                onChange={(e) => updateField("expertise_level", e.target.value)}
                aria-required="true"
                aria-invalid={Boolean(fieldErrors.expertise_level)}
                aria-describedby={fieldErrors.expertise_level ? "expertise_level-error" : undefined}
              >
                <option value="">Select…</option>
                {EXPERTISE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <FieldError id="expertise_level-error" message={fieldErrors.expertise_level} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="preferred_language">
                Preferred language
                <RequiredMark />
              </label>
              <Input
                id="preferred_language"
                value={fields.preferred_language}
                onChange={(e) => updateField("preferred_language", e.target.value)}
                placeholder="e.g. en, th, ja"
                aria-required="true"
                aria-invalid={Boolean(fieldErrors.preferred_language)}
                aria-describedby={
                  fieldErrors.preferred_language ? "preferred_language-error" : undefined
                }
              />
              <FieldError id="preferred_language-error" message={fieldErrors.preferred_language} />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="detail_depth_default">
                Detail depth
                <RequiredMark />
              </label>
              <select
                id="detail_depth_default"
                className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
                value={fields.detail_depth_default}
                onChange={(e) => updateField("detail_depth_default", e.target.value)}
                aria-required="true"
                aria-invalid={Boolean(fieldErrors.detail_depth_default)}
                aria-describedby={
                  fieldErrors.detail_depth_default ? "detail_depth_default-error" : undefined
                }
              >
                <option value="">Select…</option>
                {DETAIL_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <FieldError
                id="detail_depth_default-error"
                message={fieldErrors.detail_depth_default}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="translation_style">
                Translation style
                <RequiredMark />
              </label>
              <select
                id="translation_style"
                className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
                value={fields.translation_style}
                onChange={(e) => updateField("translation_style", e.target.value)}
                aria-required="true"
                aria-invalid={Boolean(fieldErrors.translation_style)}
                aria-describedby={
                  fieldErrors.translation_style ? "translation_style-error" : undefined
                }
              >
                <option value="">Select…</option>
                {TRANSLATION_STYLE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <FieldError id="translation_style-error" message={fieldErrors.translation_style} />
            </div>
          </div>

          <div className="space-y-4 rounded-md border border-border p-3">
            <p className="text-sm font-medium">Jargon they know / must have explained</p>
            <ChipField
              label="Known jargon"
              hint="Safe to use without explanation"
              values={fields.jargon_known}
              onChange={(next) => updateField("jargon_known", next)}
              variant="known"
            />
            <ChipField
              label="Must explain"
              hint="Blocking terms for the judge fit rubric"
              values={fields.jargon_must_explain}
              onChange={(next) => updateField("jargon_must_explain", next)}
              variant="explain"
            />
          </div>

          <div className="space-y-2 rounded-md border border-dashed border-border p-3">
            <p className="text-sm font-medium">Draft from a document</p>
            <p className="text-xs text-muted-foreground">
              Browse for up to 3 files — once they finish processing, their content drafts the
              fields above. Review before saving.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => void onFileSelected(e)}
              aria-label="Browse for up to 3 documents to draft the profile from"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={draftBusy}
                onClick={() => fileInputRef.current?.click()}
              >
                Browse…
              </Button>
              {draftMessage ? (
                <p
                  className={
                    draftPhase === "error"
                      ? "text-sm text-destructive"
                      : "text-sm text-muted-foreground"
                  }
                >
                  {draftMessage}
                </p>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="button" disabled={loading} onClick={() => void onSave()}>
              Save profile
            </Button>
          </div>
        </fieldset>

        <div>
          <Button type="button" variant="outline" disabled={loading} onClick={() => void load()}>
            Reload
          </Button>
        </div>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
