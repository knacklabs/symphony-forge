---
name: app-baseline
description: The baseline every Forge client app gets without anyone asking. Use for any frontend or UI work in a Forge client repo, including screens, layout, navigation, forms, tables and prototype demos, before building or changing it.
---

# App baseline

Client apps are business systems of records, often first built as a customer prototype. Every one
gets this baseline, whether or not the story names it. The stack and its rules live in the repo's
conventions (`stack.md`, `frontend.md`) and the standards page; the design craft lives in the
impeccable and emil-design-eng skills. This page lists what must be there and points to them.

## Fixed baseline list

1. Use shadcn's Sidebar with `collapsible="icon"`, grouped sections and an active item.
   Folded icons have tooltips and an `aria-label`. Cmd or Ctrl B folds it, and the app
   remembers its state. At phone width the sidebar becomes a sheet.
2. The top bar holds search (Cmd or Ctrl K), the user menu and breadcrumbs from depth 3.
   It never repeats the title. Show one h1 per page, in the page header.
3. Use the 4-pixel Tailwind spacing scale only, no arbitrary spacing values, and one
   page padding. Use a 24 pixel section gap and a 16 pixel card gap and field gap.
   Data apps use table rows of 32 to 40 pixels.
4. Use the type scale 12, 14, 16, 20, 24 and 30 pixels, at most two font families,
   and hierarchy by weight and colour. Numbers are tabular and right-aligned.
5. Use one accent and semantic tokens only. Status colour needs an icon and a word.
6. Use one primary button per view and a verb on every button. Use one name for one
   action. Give fields visible labels: a placeholder is not a label. Use single-column
   forms and text errors beside each field. An error says the problem and the way out,
   with no apology.
7. Use a select for fewer than 7 options, a search box (combobox) for 7 or more,
   and a radio group for 2 to 4 options when choices need to stay visible.
8. Handle loading, empty (first use, no result, cleared), error, no permission and
   partial data, with a clear next action. Where an app has `libs/shared/ui/src/components/states.tsx`,
   use its `LoadingState`, `EmptyState` and `ErrorState` and build no state markup of your own.
9. At 375 pixels, allow no sideways page scroll. Tables scroll inside their own box.
   The sidebar becomes a sheet.
10. Use plain words and realistic sample data with units. No lorem ipsum or "John Doe".

## Pick the starting theme

Before the first canvas, write a short brief from five facts in the client's notes:

1. The industry.
2. Who uses the app and how often.
3. The screen's job: work, read or persuade.
4. Two or three brand words.
5. Existing brand files.

Map these facts to tokens: font pairing, one accent, radius, density and tone. Explain
each choice from the facts, rather than a stock industry theme. Write the choices into the
client's design system tokens in Claude (the forge skill's "Canvas and app design" says how).
The system's brand guide is then the look that every screen design starts from, and
`docs/design/tokens.json` is the approved copy. With no Claude design tools, write the choices in
the app's theme file and use impeccable's `document` step to record them in DESIGN.md before the
first canvas.
Ask: "Would a different client of this type get the same pick?" If yes, change one choice.
Avoid three common machine looks: cream with a serif font and terracotta; near-black
with a neon accent; thin editorial lines everywhere.
Client brand files win, but must pass contrast.

## Fixed guard rules

- Text contrast is at least 4.5 to 1, or 3 to 1 for large text, including brand colours.
- Body text is 16 pixels, or 14 pixels in dense tables.
- Every control has keyboard access and a visible focus mark. Respect reduced motion: the theme
  file's one rule covers style sheet animation, and animation that a script starts must skip
  movement when `matchMedia('(prefers-reduced-motion: reduce)').matches` is true.
- Buttons and links are at least 24 pixels, or 44 pixels on touch screens.
- Keep empty, loading and error states, one spacing scale and tabular numbers.
- Use one icon library, Lucide, and no emoji icons or decoration.
- App screens and prototypes use impeccable's Operate mode, with restrained effects.

## Screens for the API

A new starter has no screens. The design comes first. Before any screen, use the app's existing
design. If it has none, use the look method above before a design canvas. Every API a person
uses gets its screen in the client's design, built by the agent when it builds the API, with no
need to ask. Webhooks, endpoints only agents or other systems call, and background jobs get no
screen. Build the basic screens first, then the business screens. The demo opens on the client's
business task, and the basic screens are shown last.

## Basic screens

The sign-in, forgot password, reset password and accept invite specs below are the default for
email and password. The app's approved sign-in answer, spec or decision decides which basic
screens exist and what they hold. For another method, such as one-time codes or company sign-in,
follow that choice and do not build the password screens.

Build these screens first in every prototype, in the client's design: sign-in, forgot password,
reset password, accept invite, members and settings.

- Sign-in has `Email`, `Password`, a `Sign in` button and a `Forgot password?` link. It shows the
  API message in an alert for a wrong password, an unknown email or a lock. A signed-out visit
  to a protected page goes to sign-in.
- Forgot password has `Email` and a `Send reset link` button. It gives the same neutral message for
  known and unknown emails, and says the admin can give a link when no email arrives.
- Reset password has `New password` and a `Reset password` button. An expired or used link shows
  the API message. Success tells the person to sign in.
- Accept invite has `Email`, `Password` and a `Join` button. An expired or used link shows the API
  message.
- Members lists people and roles. An admin can use `Invite` to open a link with a `Copy` button,
  change a role, use `Remove` with a confirm step, add an agent account with a key shown once, and
  use `Reset link` to show a link once with a `Copy` button. The admin has no `Remove` button on
  their own row; members see none of these actions.
- Settings shows the signed-in email, the theme choice and `Sign out`.
- Every screen refetches the account on each page change, so a removed member returns to sign-in.
  Writes send the CSRF header. Screens show the API's `message` and handle loading, empty and error
  states. Confirm destructive actions and warn before leaving unsaved forms.

## 1. Components

- shadcn/ui only, installed with its pinned CLI (`npx shadcn@4.21.4 add <component>`, with `--cwd libs/shared/ui` when the app has that library). One set of
  accessible components you own as code.
- Never hand-roll something shadcn already has (dialog, menu, select, tabs, table). A second
  version drifts in look and accessibility.
- Tailwind theme tokens only (`bg-primary`, `text-muted-foreground`), never an ad-hoc colour. The
  look and dark mode change in one place.
- Icons from lucide-react. It is what shadcn uses, so icons match.

## 2. App shell

- shadcn's Sidebar block: collapsible, grouped sections, icon plus label, a clear active item, and
  a sheet on mobile. People always know where they are and can get anywhere.
- Top bar with breadcrumbs from depth 3, search and the user menu, never the page title.
- ⌘K / Ctrl+K command palette (shadcn Command) for search and navigation. Power users skip the
  menu.
- User menu with profile and sign out, and a theme switch (light, dark, system). Every app is
  expected to have them.

## 3. Pages

- Each page has a header: title, one-line description, and one primary action. One obvious next
  step per page.
- Protected routes send signed-out visitors to the sign-in screen. A records app is never open to
  anyone.
- 404 and 403 pages that say what happened and link home. A dead end is never a blank screen.

## 4. Lists

- shadcn's data table (TanStack Table) with sorting, filters, pagination, column visibility, row
  actions and bulk select. Records are worked in lists.
- Page, sort, filters and search live in the URL. A shared link or a refresh shows the same view.

## 5. Forms

- shadcn Form with react-hook-form and zod, reusing the shared package's validators. The client
  and the API agree on what is valid.
- Inline messages next to the field that say how to fix it ("Enter a date after the start date").
  The user fixes it without guessing.
- Submit is disabled while saving. No double submits.
- Warn before leaving with unsaved changes. Nobody loses work to a stray click.

## 6. Feedback

- Sonner toasts for success and errors. Every save gets an answer.
- A confirm dialog (shadcn AlertDialog) before anything destructive, naming what will be lost. A
  mistake costs a click, not data.

## 7. States

- Loading skeletons shaped like the content. The page doesn't jump when data arrives. Use
  `LoadingState`, `EmptyState` and `ErrorState` from `@app/shared-ui/components/states`
  wherever an app has them.
- Empty states that say what the screen is for and offer the next action as a button. A new user
  knows what to do first.
- Errors that say what happened, in plain words, and offer retry. The client can recover alone.

## 8. Everywhere

- Keyboard access and visible focus on every control; a label on every control; contrast as
  impeccable's audit checks it. Accessibility is never simplified away.
- Dates, numbers and currency formatted with `Intl` in the user's locale and time zone; stored in
  UTC. People read their own formats.
- A page title per route and a favicon. Tabs and bookmarks stay readable.
- Every record shows who created it or last changed it, and when (from the audit fields in the
  data rules). A system of records answers "who did this?".

## 9. Design ownership

impeccable owns visual design and the checking pass: shape before building, then audit and polish
before a demo. emil-design-eng owns interaction feel; invoke it with a specific task. Where they
disagree, the frontend conventions settle it:

- Stagger only when a list appears as a list.
- App motion stays under 300 ms.
- Content is visible by default; enter with `@starting-style` or transitions.
- One ease-out token: `cubic-bezier(0.23, 1, 0.32, 1)`.
- CSS and the Web Animations API first; Motion only for springs or drag.
- impeccable's bounded checking: one batched inspection, at most one more round.
- App screens and prototypes use impeccable's Operate mode: Emil's restraint wins over bold effects.
- Popovers scale from their trigger via Radix's transform-origin variable.
- No animation on keyboard-driven or very frequent actions.

## 10. Prototype demos

- The demo opens on the customer's business task, and the basic screens are shown last.
- Demo data and the feedback toolbar follow the stack conventions when the repo has them.

## 11. Dashboard and charts

- Charts use shadcn's Chart components (built on Recharts, themed from the same tokens); no other
  chart library. Charts match the app and follow light and dark.
- Home after sign-in is a dashboard from shadcn's dashboard block: 3-4 KPI cards, each with its
  trend against the previous period; one main chart over time; a recent-activity table. People
  see how things stand before they go looking.
- The KPIs are the numbers from the customer's problem card (hours spent, orders delayed), so the
  dashboard shows the saving; in a prototype they come from the demo data. The customer watches
  the problem they paid to fix shrink.
- Numbers come from real queries, never hard-coded. A dashboard that lies once is never trusted.
- The date range lives in the URL, with presets (7 days, 30 days, quarter, custom). A shared link
  shows the same period.
- Numbers use tabular figures and the user's locale. Columns line up and read naturally.
- Charts never rely on colour alone, have axis labels, and offer a readable table view for screen
  readers. Everyone can read the numbers.
- Loading skeletons and empty states match the rest of the app. The dashboard is no exception.

## 12. Done means

Run this before calling any UI change finished:

- [ ] Only shadcn components and theme tokens; no hand-rolled copies, no raw colours.
- [ ] The screen sits in the shell with a sidebar item, breadcrumbs and a page header.
- [ ] Lists keep their state in the URL; forms validate inline, block double submits and warn on
      unsaved changes.
- [ ] Loading, empty and error states render, each with its next action.
- [ ] Destructive actions confirm; saves and failures toast.
- [ ] Keyboard-only walk-through works with visible focus; every control has a label.
- [ ] Dates, numbers and money use the user's locale and time zone.
- [ ] Records show who created or changed them and when.
- [ ] Home is the dashboard: problem-card KPIs with trends, one chart over time, recent activity,
      all from real queries, with the date range in the URL.
- [ ] Charts are shadcn Chart only, with axis labels, more than colour, and a table view.
- [ ] Light and dark themes and the mobile width both look right.
- [ ] impeccable's audit and polish pass ran, with emil-design-eng's checklist inside it.
