# 🌐 Customer Website Handoff — Part 4 of 5

> **In this part**: Multi-location vehicle filtering · Hide Card/Stripe UI · Design tokens (CSS variables + pills) · "All Locations" default filter

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
- The cost summary then displays based on that auto-selected pickup (with the anti-flicker logic in Part 2 §4)

---

➡️ **Next**: Part 5 — Booking status lifecycle, full testing checklist, known anti-patterns, file mirror map, priority order.
