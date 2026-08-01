"use client";

import { PlusIcon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MyOrgMembership } from "@/features/teams/components/existing-org-picker-form";
import { ExistingOrgPickerForm } from "@/features/teams/components/existing-org-picker-form";
import { OnboardingForm } from "@/features/teams/components/onboarding-form";
import { apiClient } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth/token";

type Mode = "pick" | "create";

export function OnboardingTabs() {
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<Mode>("create");
  const [memberships, setMemberships] = useState<MyOrgMembership[]>([]);

  useEffect(() => {
    if (!getAccessToken()) {
      setMemberships([]);
      setMode("pick");
      setReady(true);
      return;
    }
    apiClient
      .get<MyOrgMembership[]>("/api/orgs")
      .then(({ data }) => {
        setMemberships(data);
        setMode("pick");
      })
      .catch(() => {
        setMemberships([]);
        setMode("pick");
      })
      .finally(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <Card className="w-full max-w-sm" aria-busy="true">
        <CardHeader>
          <div className="h-5 w-40 animate-pulse rounded-md bg-muted" />
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="h-10 animate-pulse rounded-[10px] bg-muted" />
          <div className="h-10 animate-pulse rounded-[10px] bg-muted" />
          <div className="h-10 animate-pulse rounded-[10px] bg-muted" />
        </CardContent>
        <p className="sr-only">Loading workspace options</p>
      </Card>
    );
  }

  const hasOrgs = memberships.length > 0;

  if (mode === "create") {
    return (
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create org &amp; team</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <OnboardingForm />
          <Button type="button" variant="ghost" onClick={() => setMode("pick")}>
            {hasOrgs ? "Use an existing org instead" : "Back"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Choose a workspace</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Button type="button" className="w-full gap-1.5" onClick={() => setMode("create")}>
          <PlusIcon weight="bold" aria-hidden />
          Create org &amp; team
        </Button>

        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="h-px flex-1 bg-border" aria-hidden />
          <span>or use existing</span>
          <span className="h-px flex-1 bg-border" aria-hidden />
        </div>

        {hasOrgs ? (
          <ExistingOrgPickerForm memberships={memberships} />
        ) : (
          <p className="text-sm text-muted-foreground">
            No organizations yet. Create one above to get started.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
