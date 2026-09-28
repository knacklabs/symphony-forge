# Frontend (React with Vite)

How the standards page's frontend rules look in the React app. Read it when your task adds or
changes a screen.

## Layout

```
frontend/src/
  main.tsx
  api.ts            one fetch wrapper: base URL, auth header, unwraps the envelope, throws errors, sends an x-correlation-id
  pages/            one file per screen
  components/ui/    shadcn/ui components (generated; change them through shadcn)
  components/       the app's own components, grouped by domain
```

Error codes and their user messages live in `packages/shared`.

Start with a router (TanStack Router) for the app shell, sign-in, protected routes, and 404/403
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
so Vite's `import.meta.env` cannot decide this. When serving `index.html`, the backend injects a
script setting `window.__APP_ENV__` to `"demo"` only if its validated `APP_ENV` is `demo`, and to
`"production"` otherwise. Replace a fixed placeholder in the served `index.html`, never a value
from the request, and do not cache that response. Keep the dynamic import behind the run-time
check so the toolbar never loads in production. The built assets may contain its lazy chunk.

```tsx
// index.html: <script>window.__APP_ENV__ = "__APP_ENV__";</script>
// backend: replace __APP_ENV__ with APP_ENV === 'demo' ? 'demo' : 'production'
declare global { interface Window { __APP_ENV__?: 'demo' | 'production' } }
const Agentation = lazy(() => import('agentation').then((m) => ({ default: m.Agentation })));

// in App: {window.__APP_ENV__ === 'demo' && <Suspense fallback={null}><Agentation /></Suspense>}
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
