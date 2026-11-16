'use client';

import { Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';

type Theme = 'dark' | 'light';
const STORAGE_KEY = 'cartiq.theme';

/** Dark is the default: the console is an operations surface. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    const stored = document.documentElement.dataset.theme;
    if (stored === 'light' || stored === 'dark') setTheme(stored);
  }, []);

  function apply(next: Theme) {
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private browsing: the toggle still works for this page view.
    }
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      onClick={() => apply(theme === 'dark' ? 'light' : 'dark')}
    >
      {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

/** Applied before paint so a stored light theme does not flash dark. */
export const themeScript = `
(function(){try{var t=localStorage.getItem('${STORAGE_KEY}');document.documentElement.dataset.theme=(t==='light'||t==='dark')?t:'dark';}catch(e){document.documentElement.dataset.theme='dark';}})();
`;
