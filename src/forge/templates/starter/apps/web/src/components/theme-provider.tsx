import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';

const ThemeContext = createContext<{ theme: ThemeMode; setTheme: (theme: ThemeMode) => void } | null>(null);

function getSavedTheme(): ThemeMode {
  const theme = localStorage.getItem('theme');
  return theme === 'light' || theme === 'dark' ? theme : 'system';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeMode>(getSavedTheme);

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const applyTheme = () => {
      const dark = theme === 'dark' || (theme === 'system' && media.matches);
      document.documentElement.classList.toggle('dark', dark);
      document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
    };
    applyTheme();
    media.addEventListener('change', applyTheme);
    return () => media.removeEventListener('change', applyTheme);
  }, [theme]);

  const updateTheme = (nextTheme: ThemeMode) => {
    localStorage.setItem('theme', nextTheme);
    setTheme(nextTheme);
  };

  return <ThemeContext.Provider value={{ theme, setTheme: updateTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used inside ThemeProvider.');
  return context;
}
