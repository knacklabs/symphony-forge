import type { ReactNode } from 'react';

export function AuthPageFrame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main id="main-content" className="flex min-h-screen items-center justify-center p-6">
      <section className="w-full max-w-sm space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        </div>
        {children}
      </section>
    </main>
  );
}
