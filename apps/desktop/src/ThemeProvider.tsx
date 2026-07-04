import { useEffect, useState, type ReactNode } from 'react';
import {
  THEME_STORAGE_KEY,
  ThemeContext,
  applyTheme,
  getInitialThemePreference,
  resolveTheme,
  type ThemePreference,
} from './theme';

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(() => getInitialThemePreference());
  const resolved = resolveTheme(preference);

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
    applyTheme(resolveTheme(preference));

    if (preference !== 'system') {
      return;
    }
    // Follow live OS appearance changes while in system mode.
    const media = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = () => applyTheme(resolveTheme('system'));
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [preference]);

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference }}>
      {children}
    </ThemeContext.Provider>
  );
}
