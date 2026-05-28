# 🌐 Customer Website Handoff — Part 3 of 5

> **In this part**: Pickup / Drop-off selection UX · Adult 18+ verification at registration · Booking receipt page
> _Includes a **breaking change**: `POST /api/auth/register` now rejects requests without `adult_confirmed: true`._

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

> ⚠️ **Breaking backend change** — your registration form will start failing once the new backend is deployed unless you add this field.

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

➡️ **Next**: Part 4 — Multi-location vehicle filtering, hide Stripe card UI, design tokens / CSS variables, locations filter default.
