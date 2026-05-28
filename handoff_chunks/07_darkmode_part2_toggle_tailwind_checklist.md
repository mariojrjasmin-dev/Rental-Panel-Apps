# 🌗 Dark Mode Handoff — Part 2 of 2 (Customer Website)

> **In this part**: Toggle button · CSS variable styling pattern · Tailwind integration · Component cheat sheet · Full implementation checklist
> _If you haven't pasted Part 1 yet, do that first — it sets up the palette and ThemeProvider._

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

- [ ] Add CSS variables to `globals.css` (Part 1 §2)
- [ ] Create `ThemeContext.tsx` (Part 1 §3)
- [ ] Wrap `app/layout.tsx` with `<ThemeProvider>` + anti-FOUC inline script (Part 1 §3)
- [ ] Add `<ThemeToggle />` to the navbar (§4 above)
- [ ] (Optional) Configure Tailwind to use the CSS variables (§6 above)
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

---

✅ **End of handoff series.** You've now received all 7 chunks (5 customer-website + 2 dark-mode). Ship the priority order from Part 5 of the customer-website series.
