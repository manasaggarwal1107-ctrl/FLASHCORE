import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  applyResolvedTheme,
  getSystemTheme,
  readStoredThemePreference,
  resolveTheme,
  THEME_STORAGE_KEY,
} from './themeUtils';
import type { ResolvedTheme, Theme, ThemePreference } from './themeUtils';

export type { ResolvedTheme, Theme, ThemePreference };

interface ThemeContextValue {
  /** Active effective workspace theme after resolving 'system'. */
  theme: ResolvedTheme;
  /** User-selected mode ('light', 'dark', or 'system'). */
  preference: ThemePreference;
  /** Current OS preference observed via prefers-color-scheme. */
  systemTheme: ResolvedTheme;
  setTheme: (next: ThemePreference) => void;
  toggleTheme: () => void;
  cycleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const existing = useContext(ThemeContext);
  const [preference, setPreference] = useState<ThemePreference>(readStoredThemePreference);
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme);

  const resolved = resolveTheme(preference, systemTheme);

  useEffect(() => {
    if (existing) return;
    if (typeof window.matchMedia !== 'function') return;

    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const sync = (matches: boolean) => {
      setSystemTheme(matches ? 'dark' : 'light');
    };
    sync(media.matches);

    const onChange = (event: MediaQueryListEvent) => sync(event.matches);
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onChange);
      return () => media.removeEventListener('change', onChange);
    }
    media.addListener(onChange);
    return () => media.removeListener(onChange);
  }, [existing]);

  useEffect(() => {
    if (existing) return;
    applyResolvedTheme(resolved, preference);

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, preference);
    } catch {
      // Theme still applies for the active session.
    }
  }, [existing, preference, resolved]);

  const setTheme = useCallback((next: ThemePreference) => {
    setPreference(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setPreference((currentPref) => {
      const currentResolved = resolveTheme(currentPref, getSystemTheme());
      return currentResolved === 'dark' ? 'light' : 'dark';
    });
  }, []);

  const cycleTheme = useCallback(() => {
    setPreference((current) =>
      current === 'light' ? 'dark' : current === 'dark' ? 'system' : 'light',
    );
  }, []);

  // Avoid duplicate listeners/mutations when AppShell renders under root Providers.
  if (existing) {
    return <>{children}</>;
  }

  return (
    <ThemeContext.Provider
      value={{
        theme: resolved,
        preference,
        systemTheme,
        setTheme,
        toggleTheme,
        cycleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useOptionalTheme() {
  return useContext(ThemeContext);
}
