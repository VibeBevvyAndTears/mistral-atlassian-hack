"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";
import { setAccessToken, setRefreshToken } from "@/lib/auth/token";

type Mode = "signin" | "signup";

export function LoginForm() {
  const params = useParams<{ locale: string }>();
  const router = useRouter();
  const locale = params.locale || "en";
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canSubmit = Boolean(email && password) && (mode === "signin" || Boolean(username));

  async function onSubmit() {
    setLoading(true);
    setStatus(null);
    try {
      if (mode === "signup") {
        const { data } = await apiClient.post<{
          access_token: string;
          refresh_token: string;
        }>("/api/auth/register", {
          email,
          password,
          username,
          name: username,
        });
        setAccessToken(data.access_token);
        setRefreshToken(data.refresh_token);
        router.push(`/${locale}/onboarding`);
        return;
      }

      const { data } = await apiClient.post<{
        access_token: string;
        refresh_token: string;
      }>("/api/auth/login", { email, password });
      setAccessToken(data.access_token);
      setRefreshToken(data.refresh_token);
      router.push(`/${locale}/onboarding`);
    } catch (error: unknown) {
      const detail =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ===
          "string"
          ? (error as { response: { data: { detail: string } } }).response.data.detail
          : null;
      setStatus(detail || (mode === "signup" ? "Sign up failed." : "Sign in failed."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>{mode === "signup" ? "Create account" : "Sign in"}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {mode === "signup" ? (
          <Input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            aria-label="Username"
            autoComplete="username"
          />
        ) : null}
        <Input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-label="Email"
          autoComplete="email"
        />
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-label="Password"
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
        />
        <Button type="button" disabled={loading || !canSubmit} onClick={() => void onSubmit()}>
          {mode === "signup" ? "Sign up" : "Sign in"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={loading}
          onClick={() => {
            setMode(mode === "signup" ? "signin" : "signup");
            setStatus(null);
          }}
        >
          {mode === "signup" ? "Already have an account? Sign in" : "Need an account? Sign up"}
        </Button>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
