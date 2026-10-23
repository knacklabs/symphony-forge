import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <main id="main-content" className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-muted-foreground">That address does not match a page. Check it and try again.</p>
      <Link className="underline underline-offset-4" to="/projects">Go to Projects</Link>
    </main>
  );
}
