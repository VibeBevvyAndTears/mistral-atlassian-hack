import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const webSrc = join(import.meta.dirname, "../../..");
const onboardingTabsPath = join(webSrc, "features/teams/components/onboarding-tabs.tsx");
const onboardingPagePath = join(webSrc, "app/[locale]/onboarding/page.tsx");

/**
 * Regression: login redirects to /onboarding, which imports OnboardingTabs.
 * Keep the workspace picker wired so the post-login flow does not 500.
 */
describe("onboarding workspace picker invariant", () => {
  it("ships OnboardingTabs with create-above-orgs flow", () => {
    expect(existsSync(onboardingTabsPath)).toBe(true);
    const source = readFileSync(onboardingTabsPath, "utf8");
    expect(source).toContain("export function OnboardingTabs");
    expect(source).toContain("Create org &amp; team");
    expect(source).toContain("or use existing");
    expect(source).toContain("ExistingOrgPickerForm");
    expect(source).toContain("OnboardingForm");
  });

  it("keeps the onboarding page wired to OnboardingTabs", () => {
    expect(existsSync(onboardingPagePath)).toBe(true);
    const source = readFileSync(onboardingPagePath, "utf8");
    expect(source).toContain('from "@/features/teams/components/onboarding-tabs"');
    expect(source).toContain("OnboardingTabs");
  });
});
