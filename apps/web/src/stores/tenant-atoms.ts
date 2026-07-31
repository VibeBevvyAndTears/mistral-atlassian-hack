import { atom } from "jotai";

export interface TenantContext {
  orgId: string | null;
  teamId: string | null;
}

/** Active org/team for API tenancy headers (X-Org-Id / X-Team-Id). */
export const tenantAtom = atom<TenantContext>({
  orgId: null,
  teamId: null,
});

tenantAtom.debugLabel = "tenant";
