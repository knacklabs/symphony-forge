# Frontend (React with Vite)

How the standards page's frontend rules look in the React app. Read it when your task adds or
changes a screen.

## Layout

```
apps/web/src/
  main.tsx
  api.ts            one fetch wrapper: base URL, auth header, unwraps the envelope, throws errors
  pages/            one file per screen
  components/ui/    shadcn/ui components (generated; change them through shadcn)
  components/       the app's own components, grouped by domain
```

Add a router (TanStack Router) when the app gets a second page.

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
- Forms use native inputs with `<label>`, `required`, `type="email"` and the like before any form
  library, and show the API's field errors next to their fields.
- Style with Tailwind and the theme's tokens (`bg-primary`, not a raw colour), so the look changes
  in one place.

## Design and accessibility

- impeccable is the one UI skill: use it to shape and critique screens, and run its `distill`
  before a demo. Use motion skills only when a Done-when item needs motion.
- Every control works with the keyboard and shows visible focus, every input has a label, every
  image has alt text, contrast meets WCAG AA, and anything clickable is a `<button>` or a link.
  shadcn/ui components handle most of this; don't override their accessibility attributes.
