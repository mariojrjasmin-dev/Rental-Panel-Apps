# 🌗 Dark Mode Implementation — Handoff for Customer Website

> Copy-paste this entire document into your **Customer Website** chat session.
> It mirrors exactly how Dark Mode is implemented in the Dams Car Rental mobile app,
> adapted for a Next.js / React web stack so both products share the same look & UX.

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

## 4. Toggle Button (Header / Profile)

```tsx
'use client';
import { useTheme } from '@/contexts/ThemeContext';
import { Moon, Sun } from 'lucide-react';

export function ThemeToggle() {
  const { isDark, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        width: 40,
        height: 40,
        borderRadius: 999,
        border: '1px solid var(--border)',
        background: 'var(--bg-elevated)',
        color: 'var(--text)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'background 200ms ease, color 200ms ease',
      }}
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
```

Place `<ThemeToggle />` in the navbar (top-right) and optionally on the Profile page.

---

## 5. Styling Pattern — Use CSS Variables Everywhere

### ✅ DO

```tsx
<div style={{ background: 'var(--bg-elevated)', color: 'var(--text)', borderColor: 'var(--border)' }}>
  Car card
</div>
```

```css
.car-card {
  background: var(--bg-elevated);
  color: var(--text);
  border: 1px solid var(--border);
}
```

### ❌ DON'T

- Don't hardcode hex colors (`#fff`, `#000`) in components.
- Don't use Tailwind's default `bg-white text-black` — those won't react to theme. Use the Tailwind mapping below.

---

## 6. Tailwind Integration (if you use Tailwind)

`tailwind.config.ts`:

```ts
import type { Config } from 'tailwindcss';

export default {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        'bg-elevated': 'var(--bg-elevated)',
        'bg-subtle': 'var(--bg-subtle)',
        text: 'var(--text)',
        'text-muted': 'var(--text-muted)',
        'text-subtle': 'var(--text-subtle)',
        border: 'var(--border)',
        'border-strong': 'var(--border-strong)',
        brand: 'var(--brand)',
        'brand-soft': 'var(--brand-soft)',
        success: 'var(--success)',
        warning: 'var(--warning)',
        danger: 'var(--danger)',
        info: 'var(--info)',
      },
    },
  },
} satisfies Config;
```

Now you can write:

```tsx
<div className="bg-bg-elevated text-text border border-border rounded-2xl p-4">
  Car Card
</div>
```

…and it will automatically theme-switch.

---

## 7. Component Cheat Sheet

| Element                  | Light                          | Dark                          | Variable             |
|--------------------------|--------------------------------|-------------------------------|----------------------|
| Page background          | `#F5F5F7`                      | `#0B0D12`                     | `--bg`               |
| Card / Modal             | `#FFFFFF`                      | `#14171D`                     | `--bg-elevated`      |
| Section / Hover          | `#FAFAFA`                      | `#1A1E25`                     | `--bg-subtle`        |
| Primary text             | `#0A0A0A`                      | `#F5F5F7`                     | `--text`             |
| Secondary text           | `#666666`                      | `#A4A8B3`                     | `--text-muted`       |
| Hint / placeholder       | `#999999`                      | `#71757F`                     | `--text-subtle`      |
| Divider / border         | `#E5E5E5`                      | `#242932`                     | `--border`           |
| Brand / CTA              | `#FF3B30`                      | `#FF453A`                     | `--brand`            |
| Brand soft (chip bg)     | `#FFE9E8`                      | `rgba(255,69,58,0.16)`        | `--brand-soft`       |

---

## 8. Implementation Checklist

- [ ] Add CSS variables to `globals.css` (Section 2)
- [ ] Create `ThemeContext.tsx` (Section 3)
- [ ] Wrap `app/layout.tsx` with `<ThemeProvider>` + anti-FOUC inline script
- [ ] Add `<ThemeToggle />` to the navbar
- [ ] (Optional) Configure Tailwind to use the CSS variables (Section 6)
- [ ] Sweep all pages and replace hardcoded colors with variables / Tailwind tokens:
  - [ ] Home / Landing
  - [ ] Car Listing / Search
  - [ ] Car Detail
  - [ ] Booking Flow (steps 1–4)
  - [ ] Auth (Login / Register)
  - [ ] Profile
  - [ ] My Bookings
  - [ ] Legal pages (Terms, Privacy)
  - [ ] Footer / Header
- [ ] Test toggle persistence (refresh page → theme should stick)
- [ ] Test no FOUC (open in incognito with dark saved → no white flash)

---

## 9. Notes

- **Default is Light**, never auto-detect system preference (matches mobile app behavior).
- **Brand red** stays consistent across themes (slightly brighter `#FF453A` in dark for contrast — same as iOS system red dark).
- All transitions are `200ms ease` for a smooth feel.
- The `data-theme` attribute on `<html>` is the single source of truth — CSS variables cascade from there.
- Storage key `app_theme` is identical to the mobile app for consistency.

---

**Source of truth (mobile)**: `/app/frontend/src/theme.tsx` in the Dams Car Rental mobile project.

Ping me if you want a styled-components or CSS Modules variant instead of Tailwind.
