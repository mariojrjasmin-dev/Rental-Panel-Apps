# 🍎 App Store Review Notes — DAMS Rent a Car

> **How to use this file:** Copy the **"REVIEW NOTES — COPY THIS BLOCK"** section
> below into the **"App Review Information → Notes"** field in App Store Connect
> when submitting your build. The rest of this document is internal reference.

---

## 📋 REVIEW NOTES — COPY THIS BLOCK ⬇️

```
Hi Apple Review Team,

Thank you for reviewing DAMS Rent a Car — a car rental marketplace serving
the Dominican Republic and the United States.

═══════════════════════════════════════════════════════
🔑 DEMO ACCOUNT
═══════════════════════════════════════════════════════
Email:    reviewer@damscarrental.com
Password: ReviewApp2026!

═══════════════════════════════════════════════════════
💳 TEST PAYMENT (Stripe — no real charge will occur)
═══════════════════════════════════════════════════════
Card number:  4242 4242 4242 4242
Expiration:   12/30 (any future date)
CVC:          123 (any 3 digits)
ZIP/Postal:   10001 (any)

This is a Stripe test card. No real money is charged.

═══════════════════════════════════════════════════════
🧭 RECOMMENDED REVIEW FLOW
═══════════════════════════════════════════════════════
1. Open the app — you may briefly see a Spanish-language splash
   (the app supports EN/ES and auto-detects device locale).
   You can switch to English under Profile → Language.

2. Sign in with the demo account credentials above.

3. Browse cars on the home tab — try filtering by location
   (e.g. "Punta Cana Airport" or "Miami International Airport").

4. Tap any car to see its detail page. The "Locations" section
   shows pickup/drop-off locations — tap any one to open the
   in-app map. This is the primary use of location services.

5. Tap "Book Now" → choose dates → select pickup & drop-off
   locations → review price breakdown → proceed to payment.

6. On the payment screen, use the test card above. Booking
   confirmation will be shown, and a receipt email is sent.

7. Visit Profile → My Bookings to see the booking, then tap
   the booking to view its details / cancel.

8. Profile → Delete Account demonstrates our compliance with
   App Store guideline 5.1.1(v) — full data deletion in-app.

═══════════════════════════════════════════════════════
ℹ️  IMPORTANT NOTES
═══════════════════════════════════════════════════════
• Sign in with Apple / Google were intentionally REMOVED in this
  build. Login is email/password only — guideline 4.8 does not
  apply.

• Location permission is requested only when the user taps a
  location row on a car detail page (to show the route from the
  user's location to the pickup/drop-off). Denying is fine and
  the map still works (it just doesn't draw the user's location).

• Camera permission is used only for uploading optional profile
  photos and admin car listings. The reviewer flow does not
  require granting it.

• Notification permission is requested after a successful booking
  so the user receives reminders. Denying is fine — no critical
  flow depends on it.

• The app is bilingual (English / Spanish). Profile → Language
  switches at runtime.

═══════════════════════════════════════════════════════
📧 SUPPORT
═══════════════════════════════════════════════════════
If anything is unclear or you need additional access:
  info@damsrentacar.com

Thank you!
— DAMS Rent a Car, S.R.L.
```

---

## 🗂️ Internal Reviewer Checklist

### Before clicking "Submit for Review"

| ✅ | Item | Where in App Store Connect |
|---|------|-----|
| ☐ | Build uploaded via EAS / Xcode | TestFlight → Builds |
| ☐ | App Information complete | App Information |
| ☐ | Privacy Policy URL is **publicly reachable** | App Privacy → URL |
| ☐ | Privacy Nutrition Label completed | App Privacy → Data Types |
| ☐ | Screenshots uploaded (6.7" + 6.5" + iPad 12.9") | App Store → Screenshots |
| ☐ | App description, keywords, support URL | App Store metadata |
| ☐ | Age rating set (recommend 17+ for vehicle rental) | Age Rating |
| ☐ | App category: **Travel** (primary) | App Information |
| ☐ | Review Notes block above pasted | App Review → Notes |
| ☐ | Demo account email + password in Review Notes | App Review → Sign-In |
| ☐ | Build selected for review | App Store → Build |
| ☐ | Export Compliance (likely "No, app does not use encryption beyond exempt") | App Information |

### Privacy Nutrition Label Recommendations

DAMS collects the following — declare these in **App Privacy**:

| Data Type | Used For | Linked to User? | Tracking? |
|---|---|---|---|
| **Email** | Account, support, receipts | Yes | No |
| **Name** | Account, booking confirmation | Yes | No |
| **Phone** | Booking confirmation, reminders | Yes | No |
| **Payment info** (handled by Stripe) | Payment processing | Yes | No |
| **Coarse/Precise location** | Show distance to pickup point | No (used only at runtime) | No |
| **Photos (optional)** | Profile / car listing photos | Yes | No |
| **Identifiers — User ID** | Auth, booking history | Yes | No |
| **Usage Data (crash logs only)** | Diagnostics | No | No |

---

## 🐛 Known Behaviors (Pre-empting Reviewer Questions)

| Reviewer might say… | Reality |
|---|---|
| "Stripe payment fails" | They must use test card `4242 4242 4242 4242`. Live cards in TestFlight will be rejected by Stripe-test endpoint. |
| "Camera permission requested without explanation" | The `NSCameraUsageDescription` is `"Take photos of cars for listings"`. Only triggered when admin or user taps "Upload photo". |
| "Why is the bundle ID `app.emergent.rentalroutes8c25bea5`?" | This is the auto-assigned bundle ID from the Emergent EAS pipeline used in TestFlight. The final production build (post-review) will use `com.damsrentacar.app` once provisioned with the developer's own account. (If reviewing this TestFlight build, no further action required.) |
| "App requires sign-in to view content" | Yes — this is intentional, because rental laws require verified customer identity. Stated in the Description and Notes. |
| "Account deletion missing" | It's in **Profile → Delete Account** (visible after sign-in). |

---

## 🛠️ If Apple Rejects

Most common rejection reasons for rental/marketplace apps and quick fixes:

1. **"Guideline 5.1.1 — Privacy"** → Update the in-app Privacy Policy link and the App Privacy questionnaire to match. They must align.

2. **"Guideline 4.0 — Design"** → Usually about missing loading states or broken flows. Run the full reviewer flow above end-to-end before resubmitting.

3. **"Guideline 2.1 — Performance: Crashes"** → Apple tests on multiple devices, including iPad. Make sure `supportsTablet: true` actually renders well on iPad (use Xcode simulator).

4. **"Guideline 4.8 — Sign in with Apple"** → Won't apply since we removed Google SSO. If they push back, point out you only use email/password.

5. **"Guideline 5.1.1(v) — Account Deletion"** → Demonstrate Profile → Delete Account. It permanently removes user PII (bookings are anonymized to retain financial integrity per local tax law — disclose this).

---

## 📝 Suggested App Store Description (Optional Starting Point)

> **DAMS Rent a Car** — Rent the perfect car, drive your trip.
>
> From SUVs to luxury sedans, DAMS makes renting a car simple,
> fast and secure across the Dominican Republic and the United
> States.
>
> ✓ Browse and book in minutes
> ✓ Multiple pickup and drop-off locations
> ✓ Built-in maps for easy navigation
> ✓ Secure card payments via Stripe
> ✓ Email confirmations and digital receipts
> ✓ Bilingual: English & Spanish
> ✓ Biometric sign-in (Face ID / Touch ID)
> ✓ Manage bookings on the go
>
> Whether you're landing at Punta Cana Airport, exploring
> Santo Domingo, or driving Miami Beach, DAMS has your wheels.
>
> Powered by DAMS Rent a Car, S.R.L.

**Keywords (App Store search):** car rental, rent a car, alquiler de
carros, dominican republic, miami rental, suv rental, airport rental,
punta cana, santo domingo, dams

---

*Last updated: 2026-05-30 — generated post-SSO removal*
