"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";

interface AdminMetrics {
  trace_count: number;
  total_cost_usd: number;
  average_latency_ms: number | null;
  job_count: number;
  job_pass_rate: number | null;
  post_count: number;
  package_count: number;
  suggestion_count: number;
}

interface OrgAdminMetricsPanelProps {
  readonly orgId?: string;
}

export function OrgAdminMetricsPanel({ orgId }: OrgAdminMetricsPanelProps) {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      const { data } = await apiClient.get<AdminMetrics>(`/api/orgs/${orgId}/admin/metrics`);
      setMetrics(data);
      setStatus(null);
    } catch {
      setStatus("Could not load metrics. Organization owner role is required.");
    }
  }, [orgId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization metrics</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {metrics ? (
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-muted-foreground">AI cost</dt>
              <dd>${metrics.total_cost_usd.toFixed(4)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Average latency</dt>
              <dd>{metrics.average_latency_ms?.toFixed(0) ?? "—"} ms</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Job pass rate</dt>
              <dd>
                {metrics.job_pass_rate == null
                  ? "—"
                  : `${(metrics.job_pass_rate * 100).toFixed(1)}%`}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">AI traces / jobs</dt>
              <dd>
                {metrics.trace_count} / {metrics.job_count}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Posts / packages</dt>
              <dd>
                {metrics.post_count} / {metrics.package_count}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Suggestions</dt>
              <dd>{metrics.suggestion_count}</dd>
            </div>
          </dl>
        ) : null}
        <Button type="button" variant="outline" disabled={!orgId} onClick={load}>
          Refresh metrics
        </Button>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
