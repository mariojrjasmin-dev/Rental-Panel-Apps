# 🚗 DAMS Car Rental — API Integration Doc for damsrentacar.com

This document describes everything the damsrentacar.com website needs to consume the **unified DAMS Car Rental backend** so customers can browse cars, register, login, book, pay, and view bookings — using the **same production database** as the mobile app.

---

## 🔗 Base URLs

| Environment | URL |
|-------------|-----|
| Production  | `https://rental-routes.emergent.host` |
| Preview     | `https://rental-routes.preview.emergentagent.com` |

All API endpoints below are prefixed with `/api`.

**CORS is already configured** to allow `https://damsrentacar.com` (and `https://www.damsrentacar.com`) with `credentials: 'include'`. No special headers needed beyond `Content-Type: application/json` and the JWT bearer token after login.

---

## 🔐 Authentication

JWT-based. After login/register, store the returned `token` in `localStorage` and send it on every authenticated request:

```js
const token = localStorage.getItem('auth_token');
fetch(`${BASE_URL}/api/cars`, { headers: { 'Authorization': `Bearer ${token}` } });
```

### Endpoints
| Method | Path | Auth | Body | Notes |
|--------|------|------|------|-------|
| `POST` | `/api/auth/register` | No | `{ name, email, password, phone?, terms_accepted: true }` | `terms_accepted` is **required**. Min password 6 chars. Returns `{ id, email, name, role, token }`. |
| `POST` | `/api/auth/login` | No | `{ email, password }` | Returns `{ token, user: {...} }` |
| `POST` | `/api/auth/logout` | Yes | – | Invalidates token |
| `GET`  | `/api/auth/me` | Yes | – | Returns current user |
| `POST` | `/api/auth/forgot-password` | No | `{ email }` | Sends 6-digit code via email. Always returns 200 (anti-enumeration). |
| `POST` | `/api/auth/reset-password` | No | `{ email, code, new_password }` | Code expires 15 min, max 5 attempts. |

---

## 🚙 Cars (public)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET`  | `/api/cars` | No | List all available cars. Optional `?city=Punta+Cana&category=SUV&min_price=&max_price=&seats=` |
| `GET`  | `/api/cars/{car_id}` | No | Single car detail |
| `GET`  | `/api/cars/{car_id}/reviews` | No | All reviews for this car |

Each car object contains: `id, name, brand, model, year, category, price_per_day, seats, image (base64 or URL), pickup_location {name,lat,lng}, dropoff_location {name,lat,lng}, transmission, fuel_type, ...`.

---

## 📍 Locations (public)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET`  | `/api/locations` | No | All locations: name, city, country, lat, lng, tax_rate, min_booking_days, insurance_included, refuel_amount |
| `GET`  | `/api/locations/tax-by-name?name=<name>` | No | Returns `{ tax_rate, min_booking_days, insurance_included, refuel_amount }` for a specific pickup location |

---

## 🎟️ Promo Codes (public validation)

| Method | Path | Auth | Body | Notes |
|--------|------|------|------|-------|
| `POST` | `/api/promo-codes/validate` | No | `{ code, amount }` | Returns `{ valid, discount, type, value, code }` |

---

## 📜 Legal (public HTML — for your website footer)

Both render styled HTML pages you can link to directly from your footer or embed in an iframe:

- `GET /api/legal/terms`   → live rental Terms & Conditions
- `GET /api/legal/privacy` → live Privacy Policy

Also available as JSON if you'd rather render in-page:
- `GET /api/settings/rental-terms`   → `{ terms }`
- `GET /api/settings/privacy-policy` → `{ text, updated_at }`

---

## 📅 Bookings (authenticated)

| Method | Path | Auth | Body | Notes |
|--------|------|------|------|-------|
| `GET`  | `/api/bookings` | Yes | – | Returns the logged-in user's bookings |
| `POST` | `/api/bookings` | Yes | see below | Create a booking |
| `GET`  | `/api/bookings/{id}` | Yes | – | Booking detail |
| `POST` | `/api/bookings/{id}/cancel` | Yes | – | Cancel a booking |

### Booking creation payload
```json
{
  "car_id": "<car id>",
  "pickup_date": "2026-06-01",
  "dropoff_date": "2026-06-05",
  "pickup_location": { "name": "Punta Cana Airport", "lat": 18.567, "lng": -68.363 },
  "dropoff_location": { "name": "Punta Cana Airport", "lat": 18.567, "lng": -68.363 },
  "payment_method": "stripe",   // or "cash"
  "promo_code": "SUMMER10",      // optional
  "refuel_opted_in": true,       // optional, adds the location's refuel_amount
  "terms_accepted": true         // REQUIRED, otherwise 400
}
```

Returns `{ id, total_price, tax_amount, refuel_amount, discount_amount, payment_status, status, ... }` plus a `stripe_checkout_url` when `payment_method === "stripe"`.

---

## 💳 Stripe Checkout (web)

After a `POST /api/bookings` with `payment_method: "stripe"`, the response includes `stripe_checkout_url`. Redirect the browser there.

Success / cancel return URLs are already configured to come back to your domain:
- Success: `https://damsrentacar.com/booking-success?session_id=...`
- Cancel:  `https://damsrentacar.com/booking-cancelled?session_id=...`

(You can change these via the admin panel or by overriding the `STRIPE_SUCCESS_URL`/`STRIPE_CANCEL_URL` env vars. Tell me if you want the URLs to point elsewhere.)

You can also poll status:
- `GET /api/checkout/status/{session_id}` → `{ status, payment_status, amount_total, currency }`.

---

## 📧 Email notifications

The backend automatically sends transactional emails via **SMTP2GO** (already configured) for:
- New booking confirmation
- Booking status change (paid / cancelled / completed)
- Password reset code

No work needed on the website side — emails fire when the API endpoints above are hit.

---

## ✅ Implementation checklist for the damsrentacar.com agent

1. **Auth pages** — sign up, login, forgot password (2-step: email → code + new password). Sign-up form MUST include a required "Accept Terms" checkbox (link to `/api/legal/terms`).
2. **Home / Cars listing** — fetch `GET /api/cars`. Filter by city via `GET /api/cars?city=...`.
3. **Car detail page** — `GET /api/cars/{id}` + `GET /api/cars/{id}/reviews`.
4. **Booking form** — date picker, pickup/drop-off dropdowns (from `GET /api/locations`), promo code field, refuel toggle (only when location's `refuel_amount > 0`), required Terms checkbox.
5. **Checkout** — call `POST /api/bookings`. On Stripe, redirect to `stripe_checkout_url`. On cash, show confirmation.
6. **My Bookings page** — `GET /api/bookings`. Allow cancel.
7. **Footer** — replace existing Terms/Privacy links with `/api/legal/terms` and `/api/legal/privacy` (or embed the JSON versions in branded pages).
8. **Environment var** — store the `BASE_URL` (production) in a `NEXT_PUBLIC_API_URL` (or equivalent) env var. **Do not hardcode.**

---

## 🧪 Test account

Use these credentials for testing on the website without touching real customer data:
- Customer: `customer@damscarrental.com` / `Customer@123`

---

## ❓ Questions / extensions

If the damsrentacar.com agent needs:
- Additional API endpoints
- Webhook receivers
- Different Stripe redirect URLs
- Additional CORS origins (staging/preview subdomains)

…just reply in the DAMS Car Rental app chat and I'll add them.
