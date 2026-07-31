"use client";

import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { MyOrgMembership } from "@/features/teams/components/existing-org-picker-form";
import { ExistingOrgPickerForm } from "@/features/teams/components/existing-org-picker-form";
import { OnboardingForm } from "@/features/teams/components/onboarding-form";
import { apiClient } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth/token";

export function OnboardingTabs() {
  const [defaultTab, setDefaultTab] = useState<"existing" | "create" | null>(null);
  const [memberships, setMemberships] = useState<MyOrgMembership[]>([]);

  useEffect(() => {
    if (!getAccessToken()) {
      setDefaultTab("create");
      return;
    }
    apiClient
      .get<MyOrgMembership[]>("/api/orgs")
      .then(({ data }) => {
        setMemberships(data);
        setDefaultTab(data.some((org) => org.teams.length > 0) ? "existing" : "create");
      })
      .catch(() => setDefaultTab("create"));
  }, []);

  if (defaultTab === null) {
    return <p className="mx-auto mt-16 text-center text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <Tabs defaultValue={defaultTab} className="mx-auto mt-16 w-full max-w-md">
      <TabsList className="w-full">
        <TabsTrigger value="existing">Use existing</TabsTrigger>
        <TabsTrigger value="create">Create new</TabsTrigger>
      </TabsList>
      <TabsContent value="existing">
        <ExistingOrgPickerForm memberships={memberships} />
      </TabsContent>
      <TabsContent value="create">
        <OnboardingForm />
      </TabsContent>
    </Tabs>
  );
}
