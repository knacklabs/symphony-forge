import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@app/core-web';
import { ThemeProvider } from '@app/shared-ui/components/theme-provider';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>{null}</ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
