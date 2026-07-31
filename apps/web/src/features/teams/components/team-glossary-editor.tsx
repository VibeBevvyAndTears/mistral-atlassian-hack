"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

interface GlossaryTerm {
  id: string;
  term: string;
  definition: string;
  kind: "known" | "must_explain";
}

interface TeamGlossaryEditorProps {
  readonly teamId: string;
}

export function TeamGlossaryEditor({ teamId }: TeamGlossaryEditorProps) {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [term, setTerm] = useState("");
  const [definition, setDefinition] = useState("");
  const [kind, setKind] = useState<GlossaryTerm["kind"]>("known");
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get<GlossaryTerm[]>(`/api/teams/${teamId}/glossary`);
      setTerms(data);
      setStatus(null);
    } catch {
      setStatus("Could not load glossary.");
    }
  }, [teamId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function addTerm() {
    try {
      await apiClient.post(`/api/teams/${teamId}/glossary`, { term, definition, kind });
      setTerm("");
      setDefinition("");
      await load();
    } catch {
      setStatus("Could not add term. Lead role is required.");
    }
  }

  async function removeTerm(id: string) {
    try {
      await apiClient.delete(`/api/teams/${teamId}/glossary/${id}`);
      await load();
    } catch {
      setStatus("Could not delete term. Lead role is required.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Team glossary</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Term" />
        <Input
          value={definition}
          onChange={(event) => setDefinition(event.target.value)}
          placeholder="Definition"
        />
        <select
          className="h-10 rounded-xl border border-border bg-secondary px-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 focus-visible:border-ask-soft focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          value={kind}
          onChange={(event) => setKind(event.target.value as GlossaryTerm["kind"])}
          aria-label="Glossary term kind"
        >
          <option value="known">Known</option>
          <option value="must_explain">Must explain</option>
        </select>
        <Button type="button" disabled={!term.trim() || !definition.trim()} onClick={addTerm}>
          Add term
        </Button>
        <ul className="flex flex-col gap-2">
          {terms.map((item) => (
            <li
              className="flex items-start justify-between gap-3 rounded-xl border border-border bg-card p-3"
              key={item.id}
            >
              <div>
                <p className="font-medium">{item.term}</p>
                <p className="text-sm">{item.definition}</p>
                <p className="text-xs text-muted-foreground">{item.kind.replace("_", " ")}</p>
              </div>
              <Button type="button" size="sm" variant="outline" onClick={() => removeTerm(item.id)}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
