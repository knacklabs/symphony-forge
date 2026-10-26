import { useEffect } from 'react';
import { Link, useRouteError } from 'react-router-dom';
import { Button } from '@app/shared-ui/components/ui/button';
import { reportError } from './error-report';

// Each route's errorElement. Try again reloads the whole page, so it also drops the cached bad response.
export function RouteErrorPage() {
  const error = useRouteError();
  useEffect(() => { void reportError(error); }, [error]);
  return (
    <div className="flex flex-col items-center justify-center gap-4 p-6 py-16 text-center">
      <h1 className="text-2xl font-semibold">This page could not load</h1>
      <p className="text-muted-foreground">Something went wrong on this page. Try again, or go to another page.</p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button onClick={() => window.location.reload()}>Try again</Button>
        <Button variant="outline" asChild><Link to="/projects">Go to Projects</Link></Button>
      </div>
    </div>
  );
}
