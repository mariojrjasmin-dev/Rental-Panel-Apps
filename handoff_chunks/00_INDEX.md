# 📑 Dams Car Rental — Customer Website Handoff (Chunked Index)

The original handoff docs were too big to comfortably paste into a single chat message.
They've been split into **7 copy-paste-friendly chunks**.

## Paste order

**Highest impact first** — paste in the order shown below. The Customer Website agent can implement each part incrementally and ship.

| # | File | Topic | ~Size |
|---|------|-------|-------|
| 1 | `01_customer_part1_intro_backend_logo.md` | Backend overview + Dark mode pointer + New Logo | ~3 KB |
| 2 | `02_customer_part2_tax_itbis_antiflicker.md` | **ITBIS/Tax label + anti-flicker race fix** ⭐ | ~5 KB |
| 3 | `03_customer_part3_pickup_adult_receipt.md` | Pickup/Dropoff UX + Adult 18+ + Receipt page | ~4 KB |
| 4 | `04_customer_part4_multiloc_payment_tokens.md` | Multi-location filter + Cash UI + Design tokens | ~4 KB |
| 5 | `05_customer_part5_status_testing_files.md` | Booking status lifecycle + Testing checklist + File map | ~3 KB |
| 6 | `06_darkmode_part1_palette_provider.md` | Dark Mode: palette + ThemeProvider + anti-FOUC | ~5 KB |
| 7 | `07_darkmode_part2_toggle_tailwind_checklist.md` | Dark Mode: toggle button + Tailwind + checklist | ~5 KB |

## How to use

1. Open your **Customer Website** Emergent chat session.
2. For each chunk above (1 → 7):
   - Open the file with `cat` or your editor.
   - Copy its full contents.
   - Paste as a single message into the Customer Website chat.
   - Wait for the agent to finish that part before pasting the next one.
3. Chunks 1–5 cover the **CUSTOMER_WEBSITE_HANDOFF.md**.
4. Chunks 6–7 cover the **DARK_MODE_HANDOFF_CUSTOMER_WEBSITE.md** (deeper dive — only needed if §1 of Part 1 wasn't enough).

## Originals (untouched)

The full original files remain at:
- `/app/CUSTOMER_WEBSITE_HANDOFF.md`
- `/app/DARK_MODE_HANDOFF_CUSTOMER_WEBSITE.md`

## Priority shortlist (if the website team is time-boxed)

If they can only ship a subset, recommend this order:

1. **Part 2** — ITBIS/Tax + anti-flicker (fixes the most-reported bug)
2. **Part 3** — Adult 18+ (otherwise `/api/auth/register` will start returning `400`)
3. **Parts 6 + 7** — Dark mode (brand consistency)
4. **Part 1** — New logo
5. **Parts 4, 5** — Polish & QA
