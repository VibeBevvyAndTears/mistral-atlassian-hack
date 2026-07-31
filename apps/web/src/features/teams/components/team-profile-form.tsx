"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

/** PRD D-9 / wireframe W1 team profile schema. */
export type TeamProfileFields = {
  identity_label: string;
  identity_description: string;
  translation_style: string;
  expertise_level: string;
  tone: string;
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
  tone: "",
  detail_depth_default: "",
  preferred_language: "",
  responsibilities: [],
  jargon_known: [],
  jargon_must_explain: [],
};

const EXPERTISE_OPTIONS = ["novice", "familiar", "practitioner", "expert"] as const;
const DETAIL_OPTIONS = ["brief", "balanced", "deep"] as const;
const TONE_OPTIONS = ["plain", "professional", "technical", "warm"] as const;

type ProfileApi = {
  version: number;
  data: Record<string, unknown>;
};

type DraftApi = {
  data: {
    purpose?: string;
    audiences?: string[];
    tone?: string;
    communication_preferences?: string[];
    known_terms?: string[];
  };
};

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
    tone: asString(raw.tone),
    detail_depth_default: asString(raw.detail_depth_default),
    preferred_language: asString(raw.preferred_language),
    responsibilities: asStringList(raw.responsibilities),
    jargon_known: asStringList(raw.jargon_known),
    jargon_must_explain: asStringList(raw.jargon_must_explain),
  };
}

function ChipField({
  label,
  hint,
  values,
  onChange,
  variant = "known",
}: Readonly<{
  label: string;
  hint?: string;
  values: string[];
  onChange: (next: string[]) => void;
  variant?: "known" | "explain";
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
        <p className="text-sm font-medium">{label}</p>
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
    </div>
  );
}

export function TeamProfileForm({ teamId }: Readonly<{ teamId: string }>) {
  const [fields, setFields] = useState<TeamProfileFields>(EMPTY_PROFILE);
  const [version, setVersion] = useState<number | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
  }

  async function onSave() {
    setLoading(true);
    setStatus(null);
    try {
      const payload: TeamProfileFields = {
        ...fields,
        identity_label: fields.identity_label.trim(),
        identity_description: fields.identity_description.trim(),
        translation_style: fields.translation_style.trim(),
        expertise_level: fields.expertise_level.trim(),
        tone: fields.tone.trim(),
        detail_depth_default: fields.detail_depth_default.trim(),
        preferred_language: fields.preferred_language.trim(),
        responsibilities: fields.responsibilities.map((item) => item.trim()).filter(Boolean),
        jargon_known: fields.jargon_known.map((item) => item.trim()).filter(Boolean),
        jargon_must_explain: fields.jargon_must_explain.map((item) => item.trim()).filter(Boolean),
      };
      const { data } = await apiClient.put<ProfileApi>(`/api/teams/${teamId}/profile`, {
        data: payload,
      });
      setVersion(data.version);
      setFields(parseProfileData(data.data));
      setStatus(`Saved profile v${data.version}`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed");
    } finally {
      setLoading(false);
    }
  }

  async function onDraftFromDocument() {
    const id = documentId.trim();
    if (!id) {
      setStatus("Paste a document id from the Documents page first.");
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const { data } = await apiClient.post<DraftApi>(
        `/api/teams/${teamId}/profile/draft-from-document`,
        { document_id: id }
      );
      const draft = data.data;
      setFields((prev) => ({
        ...prev,
        identity_label: draft.purpose?.trim() || prev.identity_label,
        identity_description: draft.purpose?.trim() || prev.identity_description,
        tone: draft.tone?.trim() || prev.tone,
        translation_style: draft.communication_preferences?.join("; ") || prev.translation_style,
        responsibilities:
          draft.audiences && draft.audiences.length > 0 ? draft.audiences : prev.responsibilities,
        jargon_known:
          draft.known_terms && draft.known_terms.length > 0 ? draft.known_terms : prev.jargon_known,
      }));
      setStatus("Draft applied from document — review and save to version it.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Draft failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>Team profile</CardTitle>
        {version != null ? (
          <span className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground">
            v{version}
          </span>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="identity_label">
            Identity label
          </label>
          <Input
            id="identity_label"
            value={fields.identity_label}
            onChange={(e) => updateField("identity_label", e.target.value)}
            placeholder="e.g. Marketing"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="identity_description">
            Function &amp; responsibilities
          </label>
          <textarea
            id="identity_description"
            className="min-h-24 w-full rounded-md border border-input bg-transparent px-2.5 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            value={fields.identity_description}
            onChange={(e) => updateField("identity_description", e.target.value)}
            placeholder="What this team owns and who they serve"
          />
          <ChipField
            label="Responsibility tags"
            hint="Short tags for adaptation context (responsibilities[])"
            values={fields.responsibilities}
            onChange={(next) => updateField("responsibilities", next)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="expertise_level">
              Expertise level
            </label>
            <select
              id="expertise_level"
              className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
              value={fields.expertise_level}
              onChange={(e) => updateField("expertise_level", e.target.value)}
            >
              <option value="">Select…</option>
              {EXPERTISE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="preferred_language">
              Preferred language
            </label>
            <Input
              id="preferred_language"
              value={fields.preferred_language}
              onChange={(e) => updateField("preferred_language", e.target.value)}
              placeholder="e.g. en, th, ja"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="detail_depth_default">
              Detail depth
            </label>
            <select
              id="detail_depth_default"
              className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
              value={fields.detail_depth_default}
              onChange={(e) => updateField("detail_depth_default", e.target.value)}
            >
              <option value="">Select…</option>
              {DETAIL_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="tone">
              Tone
            </label>
            <select
              id="tone"
              className="h-9 w-full rounded-md border border-input bg-transparent px-2.5 text-sm"
              value={fields.tone}
              onChange={(e) => updateField("tone", e.target.value)}
            >
              <option value="">Select…</option>
              {TONE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="translation_style">
            Translation style
          </label>
          <Input
            id="translation_style"
            value={fields.translation_style}
            onChange={(e) => updateField("translation_style", e.target.value)}
            placeholder="How claims should be rephrased for this team"
          />
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
          <p className="text-sm font-medium">Draft from a sample document</p>
          <p className="text-xs text-muted-foreground">
            Upload a doc on Documents, copy its id, then draft. Review fields before saving a new
            version.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="Document UUID"
            />
            <Button
              type="button"
              variant="secondary"
              disabled={loading}
              onClick={() => void onDraftFromDocument()}
            >
              Draft from document
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" disabled={loading} onClick={() => void onSave()}>
            Save profile
          </Button>
          <Button type="button" variant="outline" disabled={loading} onClick={() => void load()}>
            Reload
          </Button>
        </div>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
