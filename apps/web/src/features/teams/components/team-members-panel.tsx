"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";

interface MemberRow {
  user_id: string;
  role: string;
  email?: string;
  username?: string;
}

function looksLikeEmail(value: string): boolean {
  return value.includes("@");
}

export function TeamMembersPanel({ teamId }: { teamId: string }) {
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [identifier, setIdentifier] = useState("");
  const [acceptToken, setAcceptToken] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.get<MemberRow[]>(`/api/teams/${teamId}/members`);
      setMembers(data);
    } catch {
      setStatus("Could not load members.");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onInvite() {
    setLoading(true);
    setStatus(null);
    setInviteToken(null);
    const trimmed = identifier.trim();
    const body = looksLikeEmail(trimmed)
      ? { email: trimmed, role: "member" }
      : { username: trimmed.toLowerCase(), role: "member" };
    try {
      const { data } = await apiClient.post<{
        token: string;
        added_immediately?: boolean;
        email: string;
      }>(`/api/teams/${teamId}/invites`, body);
      setInviteToken(data.token);
      setStatus(
        data.added_immediately
          ? `Added ${data.email} to the team.`
          : `Invite created for ${data.email}. Share the token so they can accept after signup.`
      );
      setIdentifier("");
      await load();
    } catch {
      setStatus("Invite failed — use a known username or email (Lead/Owner required).");
    } finally {
      setLoading(false);
    }
  }

  async function onAcceptInvite() {
    setLoading(true);
    setStatus(null);
    try {
      await apiClient.post("/api/invites/accept", { token: acceptToken.trim() });
      setStatus("Invite accepted.");
      setAcceptToken("");
      await load();
    } catch {
      setStatus("Accept failed — token must match your account email.");
    } finally {
      setLoading(false);
    }
  }

  async function onRemove(userId: string) {
    setLoading(true);
    setStatus(null);
    try {
      await apiClient.post(`/api/teams/${teamId}/members/${userId}/remove`);
      setStatus("Member removed (tokens revoked).");
      await load();
    } catch {
      setStatus("Remove failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Members</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm" htmlFor="invite-identifier">
            Invite by username or email
          </label>
          <Input
            id="invite-identifier"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="alice or alice@example.com"
          />
          <Button type="button" disabled={loading || !identifier} onClick={() => void onInvite()}>
            Send invite
          </Button>
          {inviteToken ? (
            <p className="break-all text-xs text-muted-foreground">Invite token: {inviteToken}</p>
          ) : null}
        </div>

        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <label className="text-sm" htmlFor="accept-token">
            Accept invite token
          </label>
          <Input
            id="accept-token"
            value={acceptToken}
            onChange={(e) => setAcceptToken(e.target.value)}
            placeholder="Paste invite token"
          />
          <Button
            type="button"
            variant="outline"
            disabled={loading || !acceptToken}
            onClick={() => void onAcceptInvite()}
          >
            Accept invite
          </Button>
        </div>

        <ul className="flex flex-col gap-2">
          {members.map((m) => (
            <li
              key={m.user_id}
              className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm"
            >
              <span>
                {m.username ? `@${m.username}` : m.user_id}
                {m.email ? <span className="text-muted-foreground"> · {m.email}</span> : null}{" "}
                <span className="text-muted-foreground">({m.role})</span>
              </span>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={loading}
                onClick={() => void onRemove(m.user_id)}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
