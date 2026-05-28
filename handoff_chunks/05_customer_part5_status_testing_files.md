# 🌐 Customer Website Handoff — Part 5 of 5

> **In this part**: Booking status & payment-status lifecycle · Pre-ship testing checklist · Known anti-patterns · File mirror map · Priority order

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
3. **Don't reset tax/rate to 0 on a cold load** — wait for the locations prefetch (see Part 2 §4)
4. **Don't keep "Tax" hardcoded** — always use `taxLabel(country)`
5. **Don't use `flex: 1` inside narrow horizontal scrollers** (RN bug; not a web issue but the same instinct applies — use `min-width: 0` if you do)

---

## 📎 Files to Mirror from Mobile

| Mobile path | Suggested web path |
|---|---|
| `/app/frontend/src/tax.ts` | `src/lib/tax.ts` |
| `/app/frontend/src/theme.tsx` | `src/contexts/ThemeContext.tsx` (web version — see Parts 6 & 7) |
| `/app/frontend/components/BrandLogo.tsx` | `src/components/BrandLogo.tsx` (web version in Part 1) |
| `/app/frontend/assets/images/dams-logo.png` | `public/logo/dams-logo.png` |
| `/app/frontend/assets/images/dams-logo-dark.png` | `public/logo/dams-logo-dark.png` |

---

## ✅ Done

After implementing all 15 sections across Parts 1–5, the customer website will be fully in sync with the v1.1.0 mobile app — same look, same UX, same rules, same fixes.

### If you implement piece by piece, do these first:

1. **Part 2 — ITBIS/Tax label + anti-flicker** (fixes the most-reported bug)
2. **Part 3 — Adult verification** (otherwise registration will start failing once you deploy the new backend)
3. **Parts 6 & 7 — Dark mode** + **Part 1 — Logo** (brand consistency)
4. The rest are polish.

---

➡️ **Next (optional deep dive)**: Parts 6 & 7 — Full Dark Mode implementation (palette, ThemeProvider, anti-FOUC script, toggle button, Tailwind mapping).

— DAMS mobile team
