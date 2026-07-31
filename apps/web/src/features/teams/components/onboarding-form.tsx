"use client";

import { useSetAtom } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient, setTenantHeaders } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth/token";
import { tenantAtom } from "@/stores/tenant-atoms";

export function OnboardingForm() {
  const params = useParams<{ locale: string }>();
  const router = useRouter();
  const setTenant = useSetAtom(tenantAtom);
  const [orgName, setOrgName] = useState("");
  const [teamName, setTeamName] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit() {
    setLoading(true);
    setStatus(null);
    if (!getAccessToken()) {
      setStatus("Sign in first, then create your org and team.");
      setLoading(false);
      router.push(`/${params.locale || "en"}/login`);
      return;
    }
    try {
      const orgRes = await apiClient.post<{ id: string }>("/api/orgs", { name: orgName });
      const orgId = orgRes.data.id;
      const teamRes = await apiClient.post<{ id: string }>(
        `/api/orgs/${orgId}/teams`,
        { name: teamName },
        { headers: { "X-Org-Id": orgId } }
      );
      const teamId = teamRes.data.id;
      setTenant({ orgId, teamId });
      setTenantHeaders(orgId, teamId);
      await apiClient.put(
        `/api/teams/${teamId}/profile`,
        { data: { tone: "neutral" } },
        { headers: { "X-Org-Id": orgId, "X-Team-Id": teamId } }
      );
      setStatus("Org + team ready.");
      router.push(
        `/${params.locale || "en"}/teams/${teamId}/profile?orgId=${encodeURIComponent(orgId)}`
      );
    } catch (error: unknown) {
      const statusCode =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { status?: number } }).response?.status === "number"
          ? (error as { response: { status: number } }).response.status
          : null;
      if (statusCode === 401) {
        setStatus("Session expired — sign in again.");
        router.push(`/${params.locale || "en"}/login`);
      } else {
        setStatus("Onboarding failed. Check the API is running and try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="mx-auto mt-16 w-full max-w-md">
      <CardHeader>
        <CardTitle>Create org & team</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <label className="text-sm" htmlFor="org-name">
          Organization name
        </label>
        <Input
          id="org-name"
          value={orgName}
          onChange={(e) => setOrgName(e.target.value)}
          placeholder="Acme"
        />
        <label className="text-sm" htmlFor="team-name">
          Team name
        </label>
        <Input
          id="team-name"
          value={teamName}
          onChange={(e) => setTeamName(e.target.value)}
          placeholder="Platform"
        />
        <Button
          type="button"
          disabled={loading || !orgName || !teamName}
          onClick={() => void onSubmit()}
        >
          Continue
        </Button>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
