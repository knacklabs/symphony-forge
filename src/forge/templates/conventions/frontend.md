# Frontend (React with Vite)

How the standards page's frontend rules look in the React app. Read it when your task adds or
changes a screen.

## Layout

```
apps/web/src/
  app.tsx           React Router routes
  main.tsx
  features/
    <feature>/
      hooks/
      pages/        screens for the feature
  components/ui/    shadcn/ui components (generated; change them through shadcn)
  components/       shared app components
  lib/              API client and utilities
```

Error codes and their user messages live in `libs/shared`, imported through `@app/shared`.
Use one fetch wrapper for the base URL and auth header. It unwraps the response envelope,
throws errors, and sends an `x-correlation-id` header.

Start with React Router for the app shell, sign-in, protected routes, and 404/403
pages.

## Server data

Each resource gets small hooks over TanStack Query, next to the screens that use them:

```tsx
export const useOrders = (page: number) =>
  useQuery({ queryKey: ['orders', { page }], queryFn: () => api.get(`/orders?page=${page}`) });

export const useCancelOrder = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/orders/${id}/cancel`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['orders'] }),
  });
};
```

Never fetch in `useEffect`, and never copy server data into component state: TanStack Query
already caches it and tracks loading and errors.

## Components

- React Compiler is on (`babel-plugin-react-compiler` in the Vite config) and memoizes. Do not add
  `useMemo`, `useCallback` or `React.memo`. The shadcn/ui copies in `components/ui/` keep theirs.
- Pass layout content as `children`.
- Build parts that share state as a compound component: one parent holds the state in a context,
  and its parts (`<Filters>`, `<Filters.Status>`) read it.
- Put logic that renders no markup in a custom hook.
- Do not add a boolean prop that switches a component between modes (`<Card compact>`,
  `isEditing`). Make two components, or a compound component.

## Web address

Keep filters, tabs, sort order and the page number of a list in the web address. Read them through
React Router's `useSearchParams`, and update the query parameters when the view changes. Reloading
the page or sharing its link must show the same view. Keep local state only for values a shared
link does not need to reproduce.

## Route error pages

Use React Router's data router (`createBrowserRouter` and `RouterProvider`). Give each route its
own `errorElement`, so a crash on one screen shows that route's error page and the other screens
keep working. The error page says what happened and how to try again or open another screen.
Keep each screen's data-loading error state too.

## Screens

- Each screen that loads data renders its loading, error and empty states. The error message comes
  from the API's `message`, which already says what to do next; the empty state says what the
  screen is for and offers its first action.
- Forms use shadcn Form with react-hook-form and zod, reusing shared validators, and show the API's
  field errors next to their fields.
- Style with Tailwind and the theme's tokens (`bg-primary`, not a raw colour), so the look changes
  in one place.

## Pointing at the screen in a demo

A demo build adds the Agentation feedback toolbar, so a salesperson can click an element, write
what's wrong and paste the output to the agent, which then knows exactly which element was meant.
Show it only when `APP_ENV=demo` at run time. The Dockerfile builds the frontend without `APP_ENV`,
so Vite's `import.meta.env` cannot decide this. The served `index.html` carries
`<meta name="app-env" content="%APP_ENV%">`, and the backend replaces the placeholder with `demo`
only if its validated `APP_ENV` is `demo`, and with `production` otherwise. A meta tag, not an
inline script, because Helmet's default content security policy (`script-src 'self'`) blocks inline
scripts. Replace a fixed placeholder, never a value from the request, and do not cache that
response. Keep the dynamic import behind the run-time check so the toolbar never loads in
production. The built assets may contain its lazy chunk.

```tsx
// index.html: <meta name="app-env" content="%APP_ENV%">
// backend: replace %APP_ENV% with APP_ENV === 'demo' ? 'demo' : 'production'
const isDemo = document.querySelector<HTMLMetaElement>('meta[name=app-env]')?.content === 'demo';
const Agentation = lazy(() => import('agentation').then((m) => ({ default: m.Agentation })));

// in App: {isDemo && <Suspense fallback={null}><Agentation /></Suspense>}
```

## Design and accessibility

- impeccable and emil-design-eng are required for every UI, prototypes included. impeccable owns
  visual design: layout, type, colour, states and copy. Shape the screen before building, then use
  one batched inspection to audit and polish before a demo, with at most one more round. Run
  emil-design-eng's review checklist inside that inspection. Invoke emil-design-eng with a
  specific task, never bare. It owns interaction feel: press feedback, easing, durations,
  popovers, tooltips, drag and when not to animate.
- Stagger only when a list appears as a list. Routine app-screen motion stays under 300 ms; a
  longer duration is only for one authored moment on a landing page. Content is visible by
  default; enter with `@starting-style` or transitions, never hide content until a script runs.
  Use one shared ease-out token, `cubic-bezier(0.23, 1, 0.32, 1)`. Use CSS and the Web Animations
  API first; use Motion only when a Done-when item needs springs or drag. Prototypes are app UI in
  impeccable's Operate mode, so Emil's restraint wins over bold effects. Scale popovers from their
  trigger with shadcn/Radix's transform-origin variable. Do not animate keyboard-driven or very
  frequent actions.
- Every control works with the keyboard and shows visible focus, every input has a label, every
  image has alt text, contrast meets WCAG AA, and anything clickable is a `<button>` or a link.
  shadcn/ui components handle most of this; don't override their accessibility attributes.

## In an app set up before this release

These rules apply to code that a change adds. The app's current code stays as it is, and the
review does not flag it. An app without React Compiler keeps its own memoization, and an app on
<BrowserRouter> keeps it.
