"use client";

import { useAtomValue } from "jotai";
import { type ReactNode, useEffect } from "react";
import { setTenantHeaders } from "@/lib/api-client";
import { tenantAtom } from "@/stores/tenant-atoms";

/**
 * Mounts inside the app Jotai Provider, above suspense-consuming subtrees (T2-M).
 * Syncs the active tenant into the Axios client as X-Org-Id / X-Team-Id.
 */
export function TenantProvider({ children }: { children: ReactNode }) {
  return (
    <>
      <TenantHeaderSync />
      {children}
    </>
  );
}

function TenantHeaderSync() {
  const tenant = useAtomValue(tenantAtom);
  useEffect(() => {
    setTenantHeaders(tenant.orgId, tenant.teamId);
  }, [tenant.orgId, tenant.teamId]);
  return null;
}
