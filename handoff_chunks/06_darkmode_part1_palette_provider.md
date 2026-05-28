# 🌗 Dark Mode Handoff — Part 1 of 2 (Customer Website)

> **In this part**: Goals & UX requirements · Full color palette (light + dark) · React `ThemeProvider` + anti-FOUC inline script
> _Part 2 covers the toggle button, Tailwind mapping, component cheat sheet, and the full implementation checklist._

---

## 1. Goal & UX Requirements

Build a Dark Mode toggle for the Dams Car Rental **customer website** that:

1. Defaults to **Light** mode on first visit (do not auto-follow system).
2. Persists the user's preference across reloads (use `localStorage`).
3. Exposes a **single toggle** (sun ↔ moon icon) in the header / profile menu.
4. Applies the **same palette** the mobile app uses, so brand color (red `#FF3B30`) and surface tones match across both products.
5. Switches instantly — no flash of wrong theme (FOUC).
6. Works across **all pages**: Home, Car Listing, Car Detail, Booking Flow, Auth, Profile, Bookings, Legal pages.

---

## 2. Color Palette (must match mobile app exactly)

Use **CSS custom properties** on `:root` so any framework (Tailwind, plain CSS, styled-components) can consume them.

```css
/* globals.css — paste at the top */

:root {
  /* Surfaces */
  --bg: #F5F5F7;
  --bg-elevated: #FFFFFF;
  --bg-subtle: #FAFAFA;

  /* Text */
  --text: #0A0A0A;
  --text-muted: #666666;
  --text-subtle: #999999;

  /* Borders */
  --border: #E5E5E5;
  --border-strong: #D1D5DB;

  /* Brand & semantic (same on both themes) */
  --brand: #FF3B30;
  --brand-soft: #FFE9E8;
  --success: #10B981;
  --warning: #F59E0B;
  --danger: #EF4444;
  --info: #3B82F6;
}

:root[data-theme='dark'] {
  --bg: #0B0D12;
  --bg-elevated: #14171D;
  --bg-subtle: #1A1E25;

  --text: #F5F5F7;
  --text-muted: #A4A8B3;
  --text-subtle: #71757F;

  --border: #242932;
  --border-strong: #2F3540;

  --brand: #FF453A;
  --brand-soft: rgba(255, 69, 58, 0.16);
  --success: #34D399;
  --warning: #FBBF24;
  --danger: #F87171;
  --info: #60A5FA;
}

html, body {
  background: var(--bg);
  color: var(--text);
  transition: background-color 200ms ease, color 200ms ease;
}
```

---

## 3. Theme Provider (React Context)

Create `src/contexts/ThemeContext.tsx`:

```tsx
'use client';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

type Theme = 'light' | 'dark';
type Ctx = { theme: Theme; isDark: boolean; toggle: () => void; setTheme: (t: Theme) => void };

const ThemeContext = createContext<Ctx>({
  theme: 'light',
  isDark: false,
  toggle: () => {},
  setTheme: () => {},
});

const STORAGE_KEY = 'app_theme';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('light'); // default light

  // Load persisted preference (client-side only)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Theme | null;
      if (saved === 'dark' || saved === 'light') {
        setThemeState(saved);
        document.documentElement.setAttribute('data-theme', saved);
      }
    } catch { /* ignore */ }
  }, []);

  const apply = useCallback((t: Theme) => {
    setThemeState(t);
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem(STORAGE_KEY, t); } catch { /* ignore */ }
  }, []);

  const toggle = useCallback(() => apply(theme === 'dark' ? 'light' : 'dark'), [theme, apply]);

  const value = useMemo(
    () => ({ theme, isDark: theme === 'dark', toggle, setTheme: apply }),
    [theme, apply, toggle]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
```

### Mount it at the root

**Next.js (App Router)** — `app/layout.tsx`:

```tsx
import { ThemeProvider } from '@/contexts/ThemeContext';
import './globals.css';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Anti-FOUC: apply theme before React hydrates */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var t = localStorage.getItem('app_theme');
                  if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
```

> The inline `<script>` in `<head>` prevents the **flash-of-wrong-theme** on first paint by applying `data-theme` before React mounts.

---

➡️ **Next**: Part 2 — Toggle button component, CSS variable usage pattern, Tailwind integration, component cheat sheet, implementation checklist.
