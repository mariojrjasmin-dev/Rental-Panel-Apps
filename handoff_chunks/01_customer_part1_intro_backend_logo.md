# 🌐 Customer Website Handoff — Part 1 of 5

> **Source mobile project**: Dams Car Rental v1.1.0
> **In this part**: Backend changes overview · Dark mode pointer · New transparent logo
> _Subsequent parts cover tax/ITBIS, pickup/adult/receipt, multi-loc/payment/tokens, status/testing/file-map._

---

## Intro

This document captures every UX/feature change shipped to the Dams Car Rental **mobile app** that should also land on the **customer-facing website**.
The backend is shared between mobile and web, so backend changes are automatically inherited — you only need frontend updates.

---

## ✅ Backend Changes (Automatically Available — Just Use Them)

The website's FastAPI backend already includes (no work needed):

| Endpoint / Feature | What it gives you |
|---|---|
| `GET /api/locations` | Returns each location with `tax_rate`, `country`, `min_booking_days`, `insurance_included`, `refuel_amount`, `unlimited_mileage`, `mileage_limit_per_day`, `extra_mileage_charge`, `active` |
| `GET /api/locations/tax-by-name?name=X` | **Tolerant matching** — exact → prefix → city → contains. So `?name=Santo Domingo` resolves to `Santo Domingo Downtown` and returns its full tax/country data. |
| `POST /api/bookings` | Server-side tolerant lookup; enriches booking with `pickup_location.country` and stores correct `tax_rate`/`tax_amount`/`subtotal`/`total_price`. **You only need to send `{name, lat, lng}` — server takes care of the rest.** |
| `GET /api/bookings/{id}` and `GET /api/bookings` | **Auto-heals** any booking with `tax_rate=0` or missing country — recomputes and persists the correct values on every read. So legacy bookings self-correct as users browse. |
| `GET /api/bookings/{id}/receipt.pdf` | Auto-healed before PDF rendering. ITBIS for DR locations, Tax for US. |
| `POST /api/auth/register` | Now **requires** `adult_confirmed: true` in the request body — see Adult Verification (Part 3). |
| `POST /api/admin-panel` 27 fine-grained permissions | Already enforced; if your website has admin pages, the existing tokens still work. |

---

## 🌗 1. Dark Mode

Dark mode has its own deep-dive doc — see **Part 6** and **Part 7** of this handoff series for the full implementation (palette, `ThemeProvider`, anti-FOUC inline script, Tailwind mapping, toggle button).

**Key reminder**: storage key is `app_theme`, `data-theme` attribute on `<html>`, default **light**.

---

## 🎨 2. New Professional Logo

The brand logo was upgraded to a transparent-background PNG with both light and dark variants.

### Files to add
Place these in `/public/logo/` (or `/assets/`):
- `dams-logo.png` — light variant (dark text, transparent bg, 934×278 PNG)
- `dams-logo-dark.png` — dark variant (light text, transparent bg)

Or download them straight from your shared backend:
```
GET https://<api-host>/api/assets/logo.png
```
(this returns the light variant; the backend file is `/app/frontend/assets/images/dams-logo.png` in the mobile project — copy both `dams-logo.png` and `dams-logo-dark.png` from there)

### `<BrandLogo>` component for the web
```tsx
'use client';
import Image from 'next/image';
import { useTheme } from '@/contexts/ThemeContext';

type Props = { size?: 'small' | 'medium' | 'large'; className?: string };

const DIMENSIONS = {
  small:  { width: 120, height: 38 },
  medium: { width: 160, height: 50 },
  large:  { width: 260, height: 80 },
};

export default function BrandLogo({ size = 'medium', className }: Props) {
  const { isDark } = useTheme();
  const dim = DIMENSIONS[size];
  const src = isDark ? '/logo/dams-logo-dark.png' : '/logo/dams-logo.png';
  return (
    <Image
      src={src}
      alt="DAMS Rent A Car"
      width={dim.width}
      height={dim.height}
      className={className}
      priority
    />
  );
}
```

### Usage tips
- Header: `<BrandLogo size="medium" />`
- Hero / landing: `<BrandLogo size="large" />`
- Footer: `<BrandLogo size="small" />`
- Forced-light variant (e.g. on a white login page): wrap with `<div data-theme="light">` so `useTheme()` returns light.

---

➡️ **Next**: Part 2 — ITBIS/Tax label localization + anti-flicker tax display + cash-payment copy.
