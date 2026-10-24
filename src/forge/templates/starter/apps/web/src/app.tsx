import { Navigate, Outlet, Route, createBrowserRouter, createRoutesFromElements, useLocation } from 'react-router-dom';
import { AppShell } from '@/components/app-shell';
import { RouteErrorPage } from '@/components/route-error-page';
import { ForgotPasswordPage } from '@/features/auth/pages/forgot-password-page';
import { ResetPasswordPage } from '@/features/auth/pages/reset-password-page';
import { SignInPage } from '@/features/auth/pages/sign-in-page';
import { SignUpPage } from '@/features/auth/pages/sign-up-page';
import { useAccount } from '@/features/auth/hooks/auth-hooks';
import { NotFoundPage } from '@/features/not-found/pages/not-found-page';
import { ProjectsPage } from '@/features/projects/pages/projects-page';
import { SettingsPage } from '@/features/settings/pages/settings-page';
import { Button } from '@/components/ui/button';

function ProtectedLayout() {
  const account = useAccount();
  const location = useLocation();

  if (account.isPending) {
    return <main id="main-content" className="flex min-h-screen items-center justify-center p-6"><p role="status">Loading your account…</p></main>;
  }
  if (account.isError) {
    return (
      <main id="main-content" className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
        <h1 className="text-xl font-semibold">We could not load your account.</h1>
        <p className="text-sm text-muted-foreground">Check your connection and try again.</p>
        <Button variant="outline" onClick={() => void account.refetch()}>Try again</Button>
      </main>
    );
  }
  if (!account.data) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;

  return <AppShell account={account.data} />;
}

export function App() {
  const location = useLocation();
  const title = ({
    '/': 'Projects',
    '/sign-in': 'Sign in',
    '/sign-up': 'Create account',
    '/forgot-password': 'Forgot password',
    '/reset-password': 'Reset password',
    '/projects': 'Projects',
    '/settings': 'Settings',
  } as Record<string, string>)[location.pathname] ?? 'Page not found';
  return (
    <>
      <title>{`${title} | Starter app`}</title>
      <a className="sr-only fixed left-4 top-4 z-50 rounded-md bg-background p-3 text-foreground focus:not-sr-only focus:ring-2 focus:ring-ring" href="#main-content">
        Skip to content
      </a>
      <Outlet />
    </>
  );
}

export const router = createBrowserRouter(createRoutesFromElements(
  <Route element={<App />} errorElement={<RouteErrorPage />}>
    <Route path="/" element={<Navigate to="/projects" replace />} errorElement={<RouteErrorPage />} />
    <Route path="/sign-in" element={<SignInPage />} errorElement={<RouteErrorPage />} />
    <Route path="/sign-up" element={<SignUpPage />} errorElement={<RouteErrorPage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} errorElement={<RouteErrorPage />} />
    <Route path="/reset-password" element={<ResetPasswordPage />} errorElement={<RouteErrorPage />} />
    <Route element={<ProtectedLayout />} errorElement={<RouteErrorPage />}>
      <Route path="/projects" element={<ProjectsPage />} errorElement={<RouteErrorPage />} />
      <Route path="/settings" element={<SettingsPage />} errorElement={<RouteErrorPage />} />
    </Route>
    <Route path="*" element={<NotFoundPage />} errorElement={<RouteErrorPage />} />
  </Route>,
));
