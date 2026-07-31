"use client";

import { useSetAtom } from "jotai";
import { useEffect } from "react";
import { tenantAtom } from "@/stores/tenant-atoms";

/** Syncs route teamId + orgId (search param or prop) into tenantAtom for API headers. */
export function useTeamTenant(orgId: string | null, teamId: string | null) {
  const setTenant = useSetAtom(tenantAtom);
  useEffect(() => {
    setTenant({ orgId, teamId });
  }, [orgId, teamId, setTenant]);
}
