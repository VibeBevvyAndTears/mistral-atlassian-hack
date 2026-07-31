import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const webSrc = join(import.meta.dirname, "../../..");
const teamRoute = join(webSrc, "app/[locale]/teams/[teamId]");

const LOADING_CONVE_RE = /Loading Conve/;
const SUSPENSE_IMPORT_RE = /import\s*\{[^}]*Suspense/;
const USE_APP_SHELL_IMPORT_RE = /import\s*\{\s*useAppShell\s*\}/;
const APP_SHELL_JSX_RE = /<\s*AppShell\b/;
const STICKY_CHROME_RE = /className="sticky top-0 z-20"/;
const FLEX_COLUMN_CHILD_RE = /flex min-w-0 flex-1 flex-col/;

/**
 * Regression: Suspense + useSearchParams around AppShell streamed chrome as
 * static HTML that never hydrated — navbar clicks no-op on team profile.
 * Shell must mount without a loading-only Suspense and without useSearchParams.
 */
describe("team route shell hydration invariant", () => {
  it("mounts TeamRouteShell in the team layout without Suspense", () => {
    const layout = readFileSync(join(teamRoute, "layout.tsx"), "utf8");
    expect(layout).toContain("TeamRouteShell");
    expect(layout).not.toContain("<Suspense");
    expect(layout).not.toMatch(LOADING_CONVE_RE);
  });

  it("does not re-wrap team tool pages in Suspense", () => {
    const pageDirs = readdirSync(teamRoute, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name);

    for (const dir of pageDirs) {
      const pagePath = join(teamRoute, dir, "page.tsx");
      const source = readFileSync(pagePath, "utf8");
      expect(source, `${dir}/page.tsx must not import Suspense`).not.toMatch(SUSPENSE_IMPORT_RE);
      expect(source, `${dir}/page.tsx must not render Suspense`).not.toContain("<Suspense");
    }
  });

  it("keeps ChannelFeedPanel as content-only inside the shared shell", () => {
    const panel = readFileSync(
      join(webSrc, "features/channels/components/channel-feed-panel.tsx"),
      "utf8"
    );
    expect(panel).toMatch(USE_APP_SHELL_IMPORT_RE);
    expect(panel).not.toMatch(APP_SHELL_JSX_RE);
  });

  it("keeps sticky chrome on a direct flex-column child in AppShell", () => {
    const shell = readFileSync(join(webSrc, "features/shell/components/app-shell.tsx"), "utf8");
    expect(shell).toMatch(STICKY_CHROME_RE);
    expect(shell).toMatch(FLEX_COLUMN_CHILD_RE);
  });

  it("avoids useSearchParams so the shell never suspends", () => {
    const shell = readFileSync(join(webSrc, "features/shell/components/app-shell.tsx"), "utf8");
    const importLine = shell.split("\n").find((line) => line.includes('from "next/navigation"'));
    expect(importLine).toBeTruthy();
    expect(importLine).not.toContain("useSearchParams");
    expect(shell).toContain("readSearch");
    expect(shell).toContain("onOpenMobileNav={() => setMobileNavOpen(true)}");
    // Query params applied after mount to keep SSR/client markup aligned.
    expect(shell).toContain("setSearchReady(true)");
  });
});
