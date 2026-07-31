"use client";

import { useSetAtom } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { extractErrorMessage } from "@/features/teams/utils/extract-error-message";
import { apiClient, setTenantHeaders } from "@/lib/api-client";
import { tenantAtom } from "@/stores/tenant-atoms";

export type MyTeamMembership = {
  team_id: string;
  team_name: string;
  role: string;
};

export type MyOrgMembership = {
  org_id: string;
  org_name: string;
  role: string;
  teams: MyTeamMembership[];
};

type TeamCreateResponse = {
  id: string;
  org_id: string;
  name: string;
};

export function ExistingOrgPickerForm({
  memberships,
}: Readonly<{ memberships: MyOrgMembership[] }>) {
  const params = useParams<{ locale: string }>();
  const router = useRouter();
  const setTenant = useSetAtom(tenantAtom);
  const [localMemberships, setLocalMemberships] = useState(memberships);
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(memberships[0]?.org_id ?? null);
  const [navigating, setNavigating] = useState(false);

  const [creatingTeam, setCreatingTeam] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [createTeamStatus, setCreateTeamStatus] = useState<string | null>(null);
  const [savingTeam, setSavingTeam] = useState(false);

  const [archiveTarget, setArchiveTarget] = useState<
    | { kind: "org"; orgId: string; name: string }
    | { kind: "team"; orgId: string; teamId: string; name: string }
    | null
  >(null);
  const [archiveStatus, setArchiveStatus] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);

  const selectedOrg = localMemberships.find((org) => org.org_id === selectedOrgId) ?? null;

  async function confirmArchive() {
    if (!archiveTarget) return;
    setArchiving(true);
    setArchiveStatus(null);
    try {
      if (archiveTarget.kind === "org") {
        await apiClient.post(`/api/orgs/${archiveTarget.orgId}/archive`, null, {
          headers: { "X-Org-Id": archiveTarget.orgId },
        });
        setLocalMemberships((prev) => prev.filter((org) => org.org_id !== archiveTarget.orgId));
        if (selectedOrgId === archiveTarget.orgId) setSelectedOrgId(null);
      } else {
        await apiClient.post(`/api/teams/${archiveTarget.teamId}/archive`, null, {
          headers: { "X-Org-Id": archiveTarget.orgId, "X-Team-Id": archiveTarget.teamId },
        });
        setLocalMemberships((prev) =>
          prev.map((org) =>
            org.org_id === archiveTarget.orgId
              ? { ...org, teams: org.teams.filter((team) => team.team_id !== archiveTarget.teamId) }
              : org
          )
        );
      }
      setArchiveTarget(null);
    } catch (err) {
      setArchiveStatus(extractErrorMessage(err, "Could not archive."));
    } finally {
      setArchiving(false);
    }
  }

  function selectTeam(orgId: string, teamId: string, role: string) {
    setNavigating(true);
    setTenant({ orgId, teamId });
    setTenantHeaders(orgId, teamId);
    const destination = role === "owner" || role === "lead" ? "profile" : "channels";
    router.push(
      `/${params.locale || "en"}/teams/${teamId}/${destination}?orgId=${encodeURIComponent(orgId)}`
    );
  }

  async function onCreateTeam(orgId: string) {
    const name = newTeamName.trim();
    if (!name) return;
    setSavingTeam(true);
    setCreateTeamStatus(null);
    try {
      const { data } = await apiClient.post<TeamCreateResponse>(
        `/api/orgs/${orgId}/teams`,
        { name },
        { headers: { "X-Org-Id": orgId } }
      );
      setLocalMemberships((prev) =>
        prev.map((org) =>
          org.org_id === orgId
            ? {
                ...org,
                teams: [...org.teams, { team_id: data.id, team_name: data.name, role: "lead" }],
              }
            : org
        )
      );
      setNewTeamName("");
      setCreatingTeam(false);
      selectTeam(orgId, data.id, "lead");
    } catch (err) {
      setCreateTeamStatus(extractErrorMessage(err, "Could not create team."));
    } finally {
      setSavingTeam(false);
    }
  }

  if (localMemberships.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No existing orgs yet</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You don&apos;t belong to any org or team yet — switch to &quot;Create new&quot; to get
            started.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Use an existing org &amp; team</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-medium">Organization</p>
          <div className="flex flex-wrap gap-2">
            {localMemberships.map((org) => (
              <div key={org.org_id} className="flex items-center gap-1">
                <Button
                  type="button"
                  size="sm"
                  variant={org.org_id === selectedOrgId ? "secondary" : "outline"}
                  onClick={() => {
                    setSelectedOrgId(org.org_id);
                    setCreatingTeam(false);
                    setCreateTeamStatus(null);
                  }}
                >
                  {org.org_name}
                </Button>
                {org.role === "owner" ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() =>
                      setArchiveTarget({ kind: "org", orgId: org.org_id, name: org.org_name })
                    }
                  >
                    Archive
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        </div>

        {selectedOrg ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">Team</p>
            {selectedOrg.teams.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selectedOrg.teams.map((team) => (
                  <div key={team.team_id} className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={navigating}
                      onClick={() => selectTeam(selectedOrg.org_id, team.team_id, team.role)}
                    >
                      {team.team_name} ({team.role})
                    </Button>
                    {team.role === "lead" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="text-destructive hover:text-destructive"
                        onClick={() =>
                          setArchiveTarget({
                            kind: "team",
                            orgId: selectedOrg.org_id,
                            teamId: team.team_id,
                            name: team.team_name,
                          })
                        }
                      >
                        Archive
                      </Button>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : selectedOrg.role !== "owner" ? (
              <p className="text-xs text-muted-foreground">
                No teams yet — ask the org owner to create one.
              </p>
            ) : null}

            {selectedOrg.role === "owner" ? (
              creatingTeam ? (
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <Input
                      value={newTeamName}
                      onChange={(e) => setNewTeamName(e.target.value)}
                      placeholder="Team name"
                      aria-label="New team name"
                      disabled={savingTeam}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          void onCreateTeam(selectedOrg.org_id);
                        }
                      }}
                    />
                    <Button
                      type="button"
                      disabled={savingTeam || !newTeamName.trim()}
                      onClick={() => void onCreateTeam(selectedOrg.org_id)}
                    >
                      Create
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={savingTeam}
                      onClick={() => {
                        setCreatingTeam(false);
                        setNewTeamName("");
                        setCreateTeamStatus(null);
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                  {createTeamStatus ? (
                    <p className="text-xs text-destructive">{createTeamStatus}</p>
                  ) : null}
                </div>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="self-start"
                  onClick={() => setCreatingTeam(true)}
                >
                  + Create team
                </Button>
              )
            ) : null}
          </div>
        ) : null}
      </CardContent>

      <Dialog
        open={archiveTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setArchiveTarget(null);
            setArchiveStatus(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Archive {archiveTarget?.kind === "org" ? "organization" : "team"} &quot;
              {archiveTarget?.name}&quot;?
            </DialogTitle>
            <DialogDescription>
              This hides it from the picker — data isn&apos;t deleted and can be restored later.
            </DialogDescription>
          </DialogHeader>
          {archiveStatus ? <p className="text-sm text-destructive">{archiveStatus}</p> : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={archiving}
              onClick={() => {
                setArchiveTarget(null);
                setArchiveStatus(null);
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={archiving}
              onClick={() => void confirmArchive()}
            >
              Archive
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
