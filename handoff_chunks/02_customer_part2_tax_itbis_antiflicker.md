# 🌐 Customer Website Handoff — Part 2 of 5

> **In this part**: ⭐ ITBIS / Tax label localization · Anti-flicker tax display race fix · "Paid in cash or card" copy
> _These three fixes resolve the most-reported customer-facing bugs._

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

➡️ **Next**: Part 3 — Pickup/Drop-off UX, Adult 18+ verification at registration, Booking Receipt page.
