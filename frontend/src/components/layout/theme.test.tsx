import fs from 'node:fs';
import path from 'node:path';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClientProvider } from '@tanstack/react-query';
import { createQueryClient } from '@/services/api/queryClient';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { AppShell } from './AppShell';
import { ThemeProvider } from './ThemeProvider';
import { THEME_STORAGE_KEY } from './themeUtils';

type MatchMediaListener = (event: MediaQueryListEvent) => void;

function installMatchMediaMock(initialDark: boolean) {
  let matches = initialDark;
  const listeners = new Set<MatchMediaListener>();

  const mock = vi.fn().mockImplementation((query: string): MediaQueryList => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      if (typeof listener === 'function') listeners.add(listener as MatchMediaListener);
    },
    removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      if (typeof listener === 'function') listeners.delete(listener as MatchMediaListener);
    },
    addListener: (listener: (ev: MediaQueryListEvent) => void) => {
      listeners.add(listener);
    },
    removeListener: (listener: (ev: MediaQueryListEvent) => void) => {
      listeners.delete(listener);
    },
    dispatchEvent: () => true,
  }));

  window.matchMedia = mock;

  return {
    setDark(nextDark: boolean) {
      matches = nextDark;
      const event = { matches: nextDark, media: '(prefers-color-scheme: dark)' } as MediaQueryListEvent;
      for (const listener of listeners) {
        listener(event);
      }
    },
  };
}

function renderShell(initialRoute = '/overview') {
  const client = createQueryClient();
  return render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[initialRoute]}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/overview" element={<div>Overview body</div>} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe('Theme architecture & permanent dark sidebar', () => {
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.dataset.theme = '';
    document.documentElement.dataset.themePreference = '';
    document.documentElement.classList.remove('dark');
    document.head.innerHTML = '<meta name="theme-color" content="#070b18" />';
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it('defaults to system preference and updates live on OS color-scheme changes', () => {
    const media = installMatchMediaMock(false);
    renderShell();

    expect(document.documentElement.dataset.themePreference).toBe('system');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    act(() => {
      media.setDark(true);
    });

    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(
      document.querySelector('meta[name="theme-color"]')?.getAttribute('content'),
    ).toBe('#070b18');
  });

  it('switches between Light, Dark, and System via Header and persists to localStorage', async () => {
    installMatchMediaMock(true);
    const user = userEvent.setup();
    renderShell();

    const trigger = screen.getByRole('button', { name: /Theme mode:/i });
    await user.click(trigger);

    const group = screen.getByRole('radiogroup', { name: 'Theme mode' });
    await user.click(within(group).getByRole('radio', { name: 'Light' }));

    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.dataset.themePreference).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    await user.click(screen.getByRole('button', { name: /Theme mode:/i }));
    const group2 = screen.getByRole('radiogroup', { name: 'Theme mode' });
    await user.click(within(group2).getByRole('radio', { name: 'Dark' }));

    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    await user.click(screen.getByRole('button', { name: /Theme mode:/i }));
    const group3 = screen.getByRole('radiogroup', { name: 'Theme mode' });
    await user.click(within(group3).getByRole('radio', { name: /System default/i }));

    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('system');
    expect(document.documentElement.dataset.themePreference).toBe('system');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('switches themes via Settings Appearance controls', async () => {
    installMatchMediaMock(false);
    const user = userEvent.setup();
    renderShell('/settings');

    const group = screen.getByRole('radiogroup', { name: 'Theme preference' });
    await user.click(within(group).getByRole('radio', { name: /^Dark/i }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');

    await user.click(within(group).getByRole('radio', { name: /^Light/i }));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  it('keeps desktop, collapsed, and mobile sidebars locked to fixed-dark tokens across all themes', async () => {
    installMatchMediaMock(false);
    const user = userEvent.setup();
    renderShell('/settings');

    const checkDesktopSidebarDark = () => {
      const aside = document.querySelector('aside[data-sidebar-theme="fixed-dark"]');
      expect(aside).toBeInTheDocument();
      expect(aside?.className).toContain('bg-sidebar');
      expect(aside?.className).toContain('border-sidebar-border');
      expect(aside?.className).toContain('text-sidebar-ink');
      expect(aside?.className).not.toContain('bg-surface');
      expect(aside?.className).not.toContain('bg-canvas');
    };

    // Light mode
    checkDesktopSidebarDark();

    // Collapsed mode in light theme
    await user.click(screen.getByRole('button', { name: 'Collapse navigation' }));
    checkDesktopSidebarDark();
    await user.click(screen.getByRole('button', { name: 'Expand navigation' }));

    // Dark mode
    const group = screen.getByRole('radiogroup', { name: 'Theme preference' });
    await user.click(within(group).getByRole('radio', { name: /^Dark/i }));
    checkDesktopSidebarDark();

    // Back to Light + Mobile drawer
    await user.click(within(group).getByRole('radio', { name: /^Light/i }));
    await user.click(screen.getByRole('button', { name: 'Open navigation' }));
    const mobileDrawer = screen.getByRole('dialog', { name: 'Navigation' });
    expect(mobileDrawer).toHaveAttribute('data-sidebar-theme', 'fixed-dark');
    expect(mobileDrawer.className).toContain('bg-sidebar');
    expect(mobileDrawer.className).toContain('border-sidebar-border');
    expect(mobileDrawer.className).toContain('text-sidebar-ink');
  });

  it('keeps [data-theme="light"] CSS block free of any --sidebar variable overrides', () => {
    const cssPath = path.resolve(process.cwd(), 'src/styles/index.css');
    const css = fs.readFileSync(cssPath, 'utf8');
    const lightBlockMatch = css.match(/\[data-theme='light'\]\s*\{([\s\S]*?)\}/);
    expect(lightBlockMatch).not.toBeNull();
    expect(lightBlockMatch?.[1]).not.toMatch(/--sidebar/);
  });
});
