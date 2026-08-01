# Conve Design System

> Direction A - Mockup Faithful. Dark channel workspace for cross-team communication.
> Brand: **Conve**. English UI. WCAG 2.2 AA.

---

## 1. Visual Theme & Atmosphere

Conve is a dense, dark ops workspace - the calm of a focused team channel, not a marketing landing page. Charcoal surfaces stack in clear layers: sidebar, top search, feed. Posts read like work objects (sender, team, priority, action), never like social fluff. Violet appears only for Ask AI and priority alerts. Red is reserved for review-queue urgency. Everything else stays neutral graphite and soft bone text. Motion is quiet (150ms). Density is packed; whitespace is intentional gutters, not empty hero fields.

---

## 2. Color Palette & Roles

### Surfaces
- Ink Black (#0E0F12): app canvas / main background
- Sidebar Charcoal (#16181D): left navigation rail
- Card Graphite (#1E2128): post cards, elevated panels
- Muted Panel (#252830): search field, filter chips at rest
- Hairline (#FFFFFF14): borders, dividers (rgba white 8%)

### Text
- Soft Bone (#E8EAED): primary text, headings
- Quiet Gray (#8B919A): secondary text, timestamps, placeholders
- Dim Gray (#5C6370): disabled / tertiary labels

### Accents (intentional, not decorative)
- Ask Violet (#8B5CF6): AI actions, notification bell active, Ask AI icon only
- Ask Violet Soft (#8B5CF633): AI hover wash / focus ring tint
- Signal Red (#E5484D): review-queue badges, destructive urgency
- Signal Red Soft (#E5484D33): badge glow optional; keep solid badge fill for contrast

### Semantic
- Success (#3DD68C): resolved / sent confirmation
- Warning (#F5A524): non-blocking caution (not primary accent)
- Focus Ring (#E8EAED): keyboard focus outline on dark surfaces

### Consistency locks
- **One accent for product AI/priority chrome:** Ask Violet (#8B5CF6)
- **One urgency accent:** Signal Red (#E5484D)
- **No purple-to-indigo page gradients.** Violet is icon/button accent only.
- **Theme lock:** dark-first for channel workspace pages.

---

## 3. Typography Rules

**Family:** system UI stack only (English-only product).

```
system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif
```

Do not use Inter, Geist, or decorative display fonts.

| Role | Font | Size | Weight | Line Height | Letter Spacing | Features | Notes |
|---|---|---|---|---|---|---|---|
| App title / brand | system-ui | 18px | 600 | 1.3 | -0.01em | none | "Conve" in chrome if shown |
| Section header | system-ui | 12px | 600 | 1.3 | 0.04em | none | Sidebar group labels (Your organisation, My teams, Review Queue) - sentence case preferred; avoid all-caps walls |
| H1 (page) | system-ui | 22px | 600 | 1.3 | -0.01em | none | Rare; feed usually has no large H1 chrome |
| Post title | system-ui | 16px | 600 | 1.4 | -0.01em | none | Card title |
| Body | system-ui | 16px | 400 | 1.55 | 0 | none | >=16px on mobile |
| Meta | system-ui | 13px | 400 | 1.4 | 0 | none | timestamps, team names |
| Badge / chip | system-ui | 11px | 600 | 1.2 | 0.02em | none | tags, counts |
| Button | system-ui | 14px | 500 | 1.2 | 0 | none | Reply, filter labels |

**Principles**
- Body never below 16px on mobile.
- Meta/secondary uses Quiet Gray; never rely on size alone for hierarchy.
- Prefer sentence case for nav and filters.

---

## 4. Component Stylings

### Buttons
- **Primary (rare in feed):** fill Soft Bone (#E8EAED), text Ink Black, radius 10px, h-40px, px-16. Hover: 90% opacity. Focus: 2px Focus Ring offset 2px.
- **Secondary / Reply:** fill Muted Panel, text Soft Bone, border Hairline, radius 10px, h-36-40px. Hover: lighten to #2C3038.
- **Ghost / icon:** transparent, radius 10px, min 40x40 touch. Hover: Muted Panel.
- **AI (Ask AI):** icon Ask Violet; optional soft violet wash on hover. Never gradient fill.
- Transition: 150ms ease-out opacity/background only.

### Cards (post feed)
- Background Card Graphite (#1E2128), radius 12px, border Hairline, padding 16px.
- No nested card-in-card. Reactions / actions sit as inline rows, not inner bordered boxes unless interactive.
- Header: avatar 32px circle (or initials tile) + name + "in {Team}" + date + optional type icon (megaphone = announcement).
- Title: 16px/600 Soft Bone. Body: 16px Quiet-to-Bone.
- Footer: reactions left; Translate / Reply right.
- Hover toolbar (desktop): thumbs, reply, trash, share, bookmark, Ask AI, meatball - icon row top-right; keyboard-accessible via focusable menu, not hover-only.

### Badges & pills
- **Review count:** Signal Red fill, Soft Bone text, circle min 18px, absolute on icon tile.
- **Topic tag:** Muted Panel bg, Quiet Gray or Soft Bone text, radius 999px, px-8 py-2, 11px/600.
- **Type (Announcement):** text + megaphone icon; no rainbow chips.

### Inputs & search
- Top search: full-width max ~560-720px, h-40px, radius 12px, bg Muted Panel, border Hairline, magnifying glass left, placeholder Quiet Gray "Search".
- Focus: border Ask Violet Soft + Focus Ring outline.
- Filter dropdowns (Teams / Type / Sort): same surface language as search; 40px height.

### Onboarding (path picker) - login-aligned card
Auth gate after sign-in. Match login page chrome: centered Conve mark + single `max-w-sm` Card.

```
┌─────────────────────────────────────┐
│ Choose a workspace                  │
│ [ + Create org & team ]  ← always   │
│ ——— or use existing ———             │
│ Organization chips / team rows      │
│ (or empty: create above to start)   │
└─────────────────────────────────────┘
```

- **Create always above orgs:** Soft Bone primary full-width Create button sits above the existing-org section. Empty memberships still show that button, then Quiet Gray empty copy - never hide Create behind a tab.
- **Create mode:** same card pattern as login (`CardHeader` title + stacked inputs + Continue). Ghost link "Use an existing org instead" only when memberships exist.
- **Default mode:** open Create when user has no teams; otherwise open the pick list with Create on top.
- **Preserve:** route `/onboarding`, Organization name / Team name fields, Continue CTA, API flows.
- **Motion:** 150ms ease-out; honor `prefers-reduced-motion`.

### Navigation - sidebar
- Width: 260px desktop; drawer on <1024px.
- Background Sidebar Charcoal.
- **Home:** pill button, icon + label, radius 999px or 12px, selected state = Muted Panel.
- Group headers: Section header type; chevron for collapse.
- Team rows: 40px min height, 8px rounded square icon placeholder + label.
- Bottom **Review Queue:** Conflicts + Suggestions with red count badges; separated by Hairline.
- Active team: Soft Bone text + left accent bar or filled row (Muted Panel).

### Top bar
- Height 56-64px, Ink Black / Sidebar Charcoal blend, sticky.
- Center: search. Right: Ask Violet bell + profile tile (40x40, radius 10px).
- Bell unread: Signal Red dot or count; icon itself stays Ask Violet when highlighting priority / open-on-you alerts.

### Decorative
- No orbs, mesh gradients, or glassmorphism on feed.
- Dividers: Hairline only.
- Icons: Phosphor only (match existing stack).

---

## 5. Layout Principles

### Spacing (8px grid)
4, 8, 12, 16, 24, 32, 48, 64

### Shell
```
┌──────────┬─────────────────────────────┐
│ Sidebar  │ Top: Search | Bell | Profile│
│ 260px    ├─────────────────────────────┤
│          │ Filters: Teams Type | Sort  │
│          │ Feed (date groups)          │
└──────────┴─────────────────────────────┘
```

- Max feed column: ~720-800px centered in remaining space (or full fluid with 24px padding).
- Date group headers: Quiet Gray meta, 12-16px margin above first card of group.
- Gap between cards: 12-16px.

### Radius scale
- sm: 6px
- md: 10px (controls, profile)
- lg: 12px (cards, search)
- full: 999px (Home pill, tags, badges)

**Radius lock:** soft system (10-12px primary). No sharp zero-radius broadsheet look.

### Whitespace
Packed feed; do not stretch first viewport with marketing heroes. Channel page is an app shell, not a landing page.

---

## 6. Depth & Elevation

| Level | Use | Treatment |
|---|---|---|
| 0 | Canvas | Ink Black flat |
| 1 | Sidebar / cards | solid fill + Hairline; no drop shadow required |
| 2 | Dropdowns / menus | Card Graphite + Hairline + shadow `0 8px 24px rgba(0,0,0,0.45)` |
| 3 | Modal / drawer | same as 2 + dim overlay `rgba(0,0,0,0.55)` |
| 4 | Toast | level 2, top or bottom safe area |

**Z-index:** base 0 · sticky bar 20 · sidebar/drawer 30 · dropdown 40 · overlay 50 · modal 60 · toast 70 · tooltip 80

**Glass:** banned on feed and cards. Optional 4px blur only on mobile drawer scrim if needed - prefer solid overlay.

**Light:** top-down implied; no multi-colored glows except Signal Red badge and Ask Violet icon.

---

## 7. Do's and Don'ts

- DO: Use brand name **Conve** in UI chrome (never Cross-Team).
- DON'T: Ship purple-to-blue or violet page gradients.
- DO: Keep Ask Violet for AI/bell/Ask AI only.
- DON'T: Recolor primary nav or whole cards violet.
- DO: Use Signal Red exclusively for review-queue counts and hard urgency.
- DON'T: Nest cards inside cards for filters or posts.
- DO: Sidebar IA = Home, Your organisation (all org teams), My teams, Review Queue.
- DON'T: Replace channel shell with the old horizontal link-soup nav on this page.
- DO: Filters = Teams, Type, Sort (Newest | Priority).
- DON'T: Use Inter / Geist as the UI font.
- DO: Provide keyboard paths for hover-only toolbars (menu button + focus).
- DON'T: Hover-only critical actions without a touch/keyboard alternative.
- DO: Respect `prefers-reduced-motion` (disable non-essential transitions).
- DON'T: Bounce easing or motion > 300ms for UI chrome.
- DO: Em-dash ban in visible copy - use hyphen or rephrase.
- DON'T: Lorem, "John Doe", Acme, or fake-perfect metrics in examples.

---

## 8. Responsive Behavior

| Breakpoint | Range | Behavior |
|---|---|---|
| Mobile | 320-767px | Sidebar as drawer (hamburger / Home opens nav). Search full width under top icons or expands on tap. Filters wrap. Feed single column. Touch targets >= 44px. |
| Tablet | 768-1023px | Optional collapsed icon sidebar (72px) or drawer; feed fluid. |
| Desktop | 1024px+ | Fixed 260px sidebar + sticky top bar + feed. |
| Wide | 1440px+ | Same shell; feed max-width ~800px, left-aligned in content pane (not floating island). |

- Collapsing: sidebar → drawer; filter row wraps; post action toolbar → meatball menu first.
- Safe areas: respect `env(safe-area-inset-*)` for drawer and sticky bar.
- Skip-to-content link to `#channel-feed`.

---

## 9. Agent Prompt Guide

### Quick Color Reference

- Canvas: Ink Black (#0E0F12)
- Sidebar: Sidebar Charcoal (#16181D)
- Card: Card Graphite (#1E2128)
- Panel / search: Muted Panel (#252830)
- Primary text: Soft Bone (#E8EAED)
- Secondary text: Quiet Gray (#8B919A)
- Border: Hairline (#FFFFFF14)
- AI / bell accent: Ask Violet (#8B5CF6)
- Review badge: Signal Red (#E5484D)
- Focus: Focus Ring (#E8EAED)
- Success: #3DD68C
- Warning: #F5A524

### Example Component Prompts

- "Build the Conve channel shell on #0E0F12. Left sidebar 260px #16181D with Home pill, collapsible Your organisation and My teams lists (40px rows, 8px icon tiles), and bottom Review Queue with Conflicts and Suggestions plus red #E5484D count badges. Top sticky bar with centered search #252830 radius 12px, Ask Violet #8B5CF6 bell, and 40x40 profile tile. Main landmark id=channel-feed."
- "Build a post card on #1E2128 radius 12px border #FFFFFF14 padding 16px. Header: 32px avatar, Soft Bone name, Quiet Gray 'in {Team}' and date, optional Announcement megaphone. Title 16px/600 Soft Bone. Body 16px. Footer reactions left; Translate link and Reply button (#252830) right. Desktop hover toolbar must also be available via a meatball menu for keyboard/touch."
- "Build feed filters: Teams and Type dropdowns left; Sort label with Newest | Priority control right. Height 40px, surfaces #252830, text #E8EAED, meta #8B919A. No nested cards."
- "Style NotificationBell icon #8B5CF6; unread uses #E5484D count. Panel #1E2128 border #FFFFFF14 shadow 0 8px 24px rgba(0,0,0,0.45). Highlight top-priority / open-on-you rows without purple gradients."
- "Rename all user-facing Cross-Team strings to Conve. Keep route IA and ?orgId tenant query intact."
- "Build onboarding as one Card Graphite panel on Ink Black. Top: full-width segmented TabsList h-44px on Muted Panel with Use existing (Buildings) and Create new (Plus). Bottom: Create org & team fields or existing org/team picker - never nest a second card. Continue = Soft Bone primary full width. max-w-md centered."

### Token mapping (implement into apps/web)

Map semantic tokens for dark channel workspace (override chartreuse primary on these routes):

```css
:root, .dark, [data-channel-shell] {
  --background: #0E0F12;
  --foreground: #E8EAED;
  --card: #1E2128;
  --card-foreground: #E8EAED;
  --popover: #1E2128;
  --popover-foreground: #E8EAED;
  --primary: #E8EAED; /* Soft Bone - primary CTAs */
  --primary-foreground: #0E0F12;
  --secondary: #252830;
  --secondary-foreground: #E8EAED;
  --muted: #252830;
  --muted-foreground: #8B919A;
  --accent: #252830;
  --accent-foreground: #E8EAED;
  --destructive: #E5484D;
  --destructive-foreground: #E8EAED;
  --border: #FFFFFF14;
  --input: #252830;
  --ring: #E8EAED;
  --sidebar: #16181D;
  --sidebar-foreground: #E8EAED;
  --sidebar-accent: #252830;
  --sidebar-border: #FFFFFF14;
  --ask: #8B5CF6; /* Ask Violet - AI/bell/Ask AI only */
  --ask-soft: #8B5CF633;
  --success: #3DD68C;
  --warning: #F5A524;
  --radius: 0.625rem; /* 10px base; cards use 12px */
  --font-sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
```

### Iteration Guide

1. Structure first (sidebar / top / feed landmarks) before polish.
2. Wire real org teams, my teams, conflict/suggestion counts - no fake badge numbers in production UI.
3. Keep Ask Violet off of primary navigation fills.
4. Verify 375px drawer + 1024px fixed sidebar.
5. Contrast-check Soft Bone and Quiet Gray on Card Graphite and Sidebar Charcoal.
6. After shell lands, restyle post card to Section 4 - do not invent a second visual language.

### Out of scope for this DESIGN.md pass

- Marketing landing redesign (home can stay minimal until a later pass)
- Light-theme parity for channel shell (dark-first lock)
- Custom illustration / 3D

---

## Channel IA (product structure - for implementers)

| Region | Content |
|---|---|
| Left - Home | Navigate to dashboard / home |
| Left - Your organisation | All teams in the active org (org-wide discussion scope) |
| Left - My teams | Teams the signed-in user belongs to |
| Left - Review Queue | Conflicts + Suggestions with live counts |
| Top - Search | Docs, infos, posts |
| Top - Notifications | Top-priority posts that concern the user while they are elsewhere |
| Middle - Feed | Posts the user is concerned about (any team); filter Teams, Type; sort Newest / Priority |
