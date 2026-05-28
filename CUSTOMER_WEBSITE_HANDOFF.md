# 🌐 Customer Website — Full Handoff (Apply All Recent Changes)

> Copy this entire document into your **Customer Website** chat session.
> It captures every UX/feature change shipped to the Dams Car Rental **mobile app** that should also land on the **customer-facing website**.
> The backend is shared between mobile and web, so backend changes are automatically inherited — you only need frontend updates.

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
| `POST /api/auth/register` | Now **requires** `adult_confirmed: true` in the request body — see Adult Verification section below. |
| `POST /api/admin-panel` 27 fine-grained permissions | Already enforced; if your website has admin pages, the existing tokens still work. |

---

## 🌗 1. Dark Mode

(Already documented in detail in `DARK_MODE_HANDOFF_CUSTOMER_WEBSITE.md` — same color palette, `ThemeProvider`, anti-FOUC inline script. Re-reference that doc.)

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

## 🇩🇴 3. ITBIS / Tax Label Localization

The label MUST switch based on the **pickup location's country**:
- Dominican Republic → **`ITBIS`**
- Everywhere else (USA, etc.) → **`Tax`**

### Shared helper (mirror of mobile)
Create `src/lib/tax.ts`:

```ts
/**
 * Tax label helper — keeps PDF, email, mobile UI and web UI in sync.
 * Dominican Republic = ITBIS (the local VAT)
 * Everywhere else    = Tax
 */
export function taxLabel(country?: string | null): string {
  if (!country) return 'Tax';
  const c = String(country).trim().toLowerCase();
  if (
    c.includes('dominican') ||
    c === 'do' || c === 'dom' ||
    c === 'rd' || c === 'dr'
  ) return 'ITBIS';
  return 'Tax';
}
```

### Apply it everywhere tax appears
| Screen | Example |
|---|---|
| Car detail / Booking summary | `{taxLabel(pickup.country)} ({rate}%) ${amount}` |
| Checkout confirmation | same |
| My Bookings list card | `{taxLabel(booking.pickup_location?.country)} {rate}% ${amount}` |
| Booking receipt page | same |
| Email confirmation HTML (backend already handles this) | n/a |
| Downloaded PDF (backend handles) | n/a |

> ⚠️ Never hardcode `Tax` in customer-facing copy where dynamic tax label applies.

---

## 🛡 4. Anti-Flicker / Anti-Race Tax Display

The mobile app had a race where booking-flow tax briefly showed **0%** until two async calls completed. Don't repeat this on the website.

### Pattern

When the booking page loads:

1. **Prefetch all locations once** into a `locMetaByName` map keyed by lowercased name:
   ```ts
   const [locMetaByName, setLocMetaByName] = useState<Record<string, LocMeta>>({});
   useEffect(() => {
     fetch('/api/locations').then(r => r.json()).then(list => {
       const map: Record<string, LocMeta> = {};
       for (const l of list) {
         const k = (l.name || '').trim().toLowerCase();
         if (k) map[k] = {
           tax_rate: Number(l.tax_rate) || 0,
           country: l.country || '',
           min_booking_days: Number(l.min_booking_days) || 1,
           insurance_included: !!l.insurance_included,
           refuel_amount: Number(l.refuel_amount) || 0,
           unlimited_mileage: l.unlimited_mileage !== false,
           mileage_limit_per_day: Number(l.mileage_limit_per_day) || 0,
           extra_mileage_charge: Number(l.extra_mileage_charge) || 0,
         };
       }
       setLocMetaByName(map);
     });
   }, []);
   ```

2. **When the user picks a pickup location**, hydrate state **synchronously** from the map BEFORE any network call:
   ```ts
   useEffect(() => {
     const name = selectedPickup?.name;
     if (!name) return;
     const key = name.toLowerCase();
     const cached = locMetaByName[key];
     if (cached) {
       setTaxRate(cached.tax_rate);
       setPickupCountry(cached.country);
       // …set the other policy fields
     } else if (Object.keys(locMetaByName).length === 0) {
       // Locations prefetch not done yet — DO NOT reset taxRate to 0.
       // The effect will re-run when the map populates because it's
       // listed as a dependency below.
     } else {
       // Map IS loaded but doesn't contain this name (admin rename
       // or partial name). Fall back to backend tolerant lookup.
       setTaxRate(0);
       setPickupCountry('');
     }
     // Always refresh from /api/locations/tax-by-name in the background
     // in case admin changed something after the prefetch.
     fetch(`/api/locations/tax-by-name?name=${encodeURIComponent(name)}`)
       .then(r => r.ok ? r.json() : null)
       .then(data => {
         if (!data) return;
         setTaxRate(Number(data.tax_rate) || 0);
         setPickupCountry((data.country || '').trim());
         // …apply other policy fields
       });
   }, [selectedPickup?.name, locMetaByName]);
   ```

This gives a **zero-flicker** experience: tax label + rate update in the same render cycle as the chip/dropdown click, with no "Tax (0%)" transient.

---

## 💵 5. "Paid in cash or card at pickup" Copy

Wherever you display the cash payment method explanation, the canonical copy is now:

> **Paid in cash or card at pickup. Our agent will provide a receipt.**

(Previously was "Paid in cash at pickup..." — the "or card" was missing.)

---

## 📍 6. Pickup / Drop-off Selection UX

### Color tokens (consistent with mobile)
- **Pickup dot/icon**: green `#34C759`
- **Drop-off dot/icon**: red `#FF3B30`
- **Brand red / primary CTA**: `#FF3B30` light, `#FF453A` dark

### Selection summary block (under the chips)
After the user picks pickup and drop-off, render a confirmation block:
```
🟢 Pickup:   Punta Cana Airport
🔴 Drop-off: Santo Domingo Downtown
```
Text colors **must** respect dark mode (use `var(--text-muted)` for "Pickup:" / "Drop-off:" and `var(--text)` for the location name).

### CRITICAL: chip text overflow in horizontal scrollers
On the web you won't hit the React-Native flex-collapse bug we had, but **make sure**:
- Chip text uses `min-width: 0` so long names truncate with ellipsis instead of pushing content off-screen
- Each chip has `max-width: ~280px` and `text-overflow: ellipsis`

---

## 👨‍💼 7. Adult (18+) Verification at Registration

Backend now **rejects** registration requests without `adult_confirmed: true`.

### Form changes

Add a required checkbox to your `/register` page:

```tsx
<label className="flex items-start gap-2 cursor-pointer">
  <input
    type="checkbox"
    checked={adultConfirmed}
    onChange={e => setAdultConfirmed(e.target.checked)}
    required
  />
  <span className="text-sm">
    I confirm that I am <strong>18 years of age or older</strong> and am
    legally able to enter into a rental agreement.
  </span>
</label>
```

### Submit payload

Include both fields in the POST body:

```ts
await fetch('/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email, password, name, phone,
    adult_confirmed: adultConfirmed,
    terms_accepted: termsAccepted,
  }),
});
```

The backend stores `adult_confirmed: true` and `adult_confirmed_at: <timestamp>` on the user record. If `adult_confirmed` is missing or false, you'll get a `400` with detail like `"You must confirm you are 18 years or older"`.

---

## 🧾 8. Booking Receipt Page

Replicate the mobile receipt screen on the website at `/bookings/[id]/receipt`:

### Required sections (in order)
1. **Receipt header card** (always-dark — paper-receipt aesthetic): Receipt #, status pill, issued date
2. **Vehicle card**: image + name
3. **Billed To**: customer name + email
4. **Rental Details**: pickup date, drop-off date, pickup location, drop-off location, duration, payment method, odometer in/out (when set)
5. **Cost Breakdown**:
   - Daily Rate × N
   - Subtotal
   - Promo code discount (if `promo_code`)
   - Extra Mileage (if `extra_mileage_fee > 0`)
   - **`{taxLabel(pickup.country)} ({rate}%)` row** — always show, even when rate is 0
6. **Grand Total card** (always red `#FF3B30` — brand identity)
7. **Refundable Security Deposit card** (always navy blue, when `booking.deposit > 0`) — note that deposit is NOT included in grand total
8. **Download PDF button** → `GET /api/bookings/{id}/receipt.pdf`
9. Footer: "Thank you for choosing DAMS Car Rental." + support@damscarrental.com

### Important
- Use `taxLabel(booking.pickup_location?.country)` for the tax row label
- Read tax data straight from `booking.tax_rate` and `booking.tax_amount` — the backend auto-heals on read, so these are always correct
- The PDF endpoint also auto-heals before rendering — no client-side recomputation needed

---

## 🛠 9. Multi-Location Vehicle Filtering

The cars API filters by location using the **plural `pickup_locations` array** (not the legacy singular `pickup_location`).

### Correct filter

```ts
const url = locationName
  ? `/api/cars?location=${encodeURIComponent(locationName)}`
  : '/api/cars';
```

Backend matches `locationName` against the array of pickup locations per car. So a Mercedes assigned to `[Punta Cana, Santo Domingo, JFK]` will appear when filter is **any of those names**.

### Important UX detail

The filter uses the **location NAME**, not the city. Make sure your "Filter by location" dropdown lists `loc.name` values, not `loc.city`.

---

## 💳 10. Payment Method UI — Hide Card for Now

Per the recent product decision, the **Card / Stripe payment option is hidden** on the mobile app. Apply the same on the website:

- The booking flow should default to **Cash on pickup** (or "Pay at pickup")
- Hide the Stripe Checkout option behind a feature flag: `const SHOW_CARD_PAYMENT = false;`
- When re-enabled in the future, the backend Stripe integration is already wired with the `httpx` fallback for the SDK validation bug — no backend work needed

---

## 🎨 11. Design Tokens to Adopt

These match the mobile app exactly. Add to `globals.css`:

```css
:root {
  --bg: #F5F5F7;
  --bg-elevated: #FFFFFF;
  --bg-subtle: #FAFAFA;
  --text: #0A0A0A;
  --text-muted: #666666;
  --text-subtle: #999999;
  --border: #E5E5E5;
  --border-strong: #D1D5DB;
  --brand: #FF3B30;
  --brand-soft: #FFE9E8;
  --success: #10B981;
  --warning: #F59E0B;
  --danger: #EF4444;
  --info: #3B82F6;
  --radius: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
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
```

### Status pill classes (carry over from admin panel)
```css
.pill { display:inline-flex; padding:3px 9px; border-radius:50px;
        font-size:10.5px; font-weight:800; letter-spacing:0.4px;
        text-transform:uppercase; }
.pill-green { background: rgba(16,185,129,0.16); color: #047857; }
.pill-amber { background: rgba(245,158,11,0.18); color: #92400e; }
.pill-red   { background: rgba(239,68,68,0.16);  color: #991b1b; }
.pill-blue  { background: rgba(59,130,246,0.16); color: #1e3a8a; }
.pill-purple{ background: rgba(139,92,246,0.16); color: #5b21b6; }
.pill-gray  { background: var(--bg-hover, var(--bg-subtle)); color: var(--text-muted); }
[data-theme='dark'] .pill-green  { color: #6ee7b7; }
[data-theme='dark'] .pill-amber  { color: #fcd34d; }
[data-theme='dark'] .pill-red    { color: #fca5a5; }
[data-theme='dark'] .pill-blue   { color: #93c5fd; }
[data-theme='dark'] .pill-purple { color: #c4b5fd; }
```

Use for booking status (`pending_payment` → amber, `confirmed` → blue, `active` → green, `completed` → purple, `cancelled` → red) and payment status.

---

## 🔎 12. Locations Filter & "All Locations" Default

When the user is on **"All Locations"** (no specific filter), the home/car-listing page should:
- Show every active car
- When the user proceeds to book a specific car, the booking page picks the **first available** pickup location automatically
- The cost summary then displays based on that auto-selected pickup (with the anti-flicker logic in section 4)

---

## 📋 13. Booking Status Lifecycle (UI Reference)

Status values to recognize on the website:
| Status | Label | Pill color |
|---|---|---|
| `pending_payment` | Pending Payment | amber |
| `pending` | Pending | amber |
| `confirmed` | Confirmed | blue |
| `active` | Active (Picked up) | green |
| `completed` | Completed | purple |
| `cancelled` | Cancelled | red |

Payment status:
| Status | Label | Pill color |
|---|---|---|
| `paid` / `succeeded` / `cash_paid` | PAID | green |
| `pending` / `unpaid` | UNPAID | amber |
| `refunded` | REFUNDED | gray |
| `failed` | FAILED | red |

---

## 🧪 14. Testing Checklist Before Shipping

- [ ] Dark mode toggle works on all pages
- [ ] Logo renders with transparent bg on both themes
- [ ] Tax label says **ITBIS** for any DR pickup, **Tax** for US pickups — verified on at least two of each country
- [ ] No "Tax (0%) $0.00" transient on slow networks during car selection
- [ ] Adult 18+ checkbox is required at registration
- [ ] Booking submitted with only `{name, lat, lng}` (no country/city) — backend enriches and tax is correctly applied
- [ ] PDF download from receipt page returns correct ITBIS/Tax label
- [ ] Cash-only UI by default (Stripe hidden behind flag)
- [ ] Multi-location vehicles appear under all their pickup locations
- [ ] Status pills use consistent colors
- [ ] Location filter uses `name`, not `city`
- [ ] Receipt page displays correct grand total (auto-healing means historical broken bookings now show correctly)

---

## 🚧 15. Known Issues to Not Repeat

1. **Don't hardcode location names** for tax rules — derive label from `country` field
2. **Don't filter cars by `pickup_location.city`** — use `pickup_locations` array name match
3. **Don't reset tax/rate to 0 on a cold load** — wait for the locations prefetch (see section 4)
4. **Don't keep "Tax" hardcoded** — always use `taxLabel(country)`
5. **Don't use `flex: 1` inside narrow horizontal scrollers** (RN bug; not a web issue but the same instinct applies — use `min-width: 0` if you do)

---

## 📎 Files to Mirror from Mobile

| Mobile path | Suggested web path |
|---|---|
| `/app/frontend/src/tax.ts` | `src/lib/tax.ts` |
| `/app/frontend/src/theme.tsx` | `src/contexts/ThemeContext.tsx` (web version — already in earlier handoff) |
| `/app/frontend/components/BrandLogo.tsx` | `src/components/BrandLogo.tsx` (web version above) |
| `/app/frontend/assets/images/dams-logo.png` | `public/logo/dams-logo.png` |
| `/app/frontend/assets/images/dams-logo-dark.png` | `public/logo/dams-logo-dark.png` |

---

**Done.** After implementing all 15 sections above, the customer website will be fully in sync with the v1.1.0 mobile app — same look, same UX, same rules, same fixes.

If you implement piece by piece, the highest-impact ones first are:
1. **§3 ITBIS/Tax label** + **§4 anti-flicker** (fixes the most-reported bug)
2. **§7 Adult verification** (otherwise registration will start failing once you deploy the new backend)
3. **§1 Dark mode** + **§2 logo** (brand consistency)
4. The rest are polish.

— DAMS mobile team
