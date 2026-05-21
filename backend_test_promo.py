#!/usr/bin/env python3
"""
End-to-end backend tests for the new Promo Codes system.

Coverage:
  1. Admin CRUD: POST/GET/PUT/DELETE /api/admin/promo-codes
  2. Validation endpoint: POST /api/promo-codes/validate
  3. Booking flow with promo: POST /api/bookings (+ uses count increment)
  4. Authorization (admin-only on CRUD; auth-required on validate)
"""

import os
import sys
import time
import json
import random
import string
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = "https://rental-routes.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"


# --------- tiny test framework ---------
PASSES = 0
FAILS = 0
FAIL_DETAILS = []

def _label(msg):
    print(f"\n=== {msg} ===")

def check(cond, msg, extra=""):
    global PASSES, FAILS
    if cond:
        PASSES += 1
        print(f"  ✅ {msg}")
    else:
        FAILS += 1
        FAIL_DETAILS.append(f"{msg} :: {extra}")
        print(f"  ❌ {msg}  --> {extra}")


def rand_suffix(n=5):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def register(name, email, password):
    r = requests.post(f"{API}/auth/register", json={"name": name, "email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return r.json()["token"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    print(f"Base URL: {BASE_URL}")

    # ---------- Auth ----------
    _label("Authenticate as admin")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    check(bool(admin_token), "admin login returned token")

    # Register a fresh customer (real-looking data)
    cust_email = f"luisa.fernandez+{int(time.time())}@example.com"
    cust_token = register("Luisa Fernandez", cust_email, "Customer@123")
    check(bool(cust_token), "customer registered + token issued")

    # Fetch a car and location for the booking flow (use a location with min_booking_days small)
    cars = requests.get(f"{API}/cars", timeout=20).json()
    locs = requests.get(f"{API}/locations", timeout=20).json()
    pickup_loc = next(
        (l for l in locs if int(l.get("min_booking_days") or 1) == 1),
        locs[0],
    )
    # Pick the cheapest car so the math is easy to reason about
    car = min(cars, key=lambda c: c.get("price_per_day", 999999))
    print(f"Using car {car['name'].strip()} @ ${car['price_per_day']}/day")
    print(f"Using pickup location: {pickup_loc['name']} (tax_rate={pickup_loc.get('tax_rate')}, min_days={pickup_loc.get('min_booking_days', 1)})")

    # ===========================================================
    # 1. Admin CRUD
    # ===========================================================
    _label("1. Admin CRUD")

    test10_code = f"TEST10{rand_suffix(4)}"
    # Create a valid percent code
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={
            "code": test10_code,
            "discount_type": "percent",
            "discount_value": 10,
            "max_uses": 5,
            "min_amount": 20,
            "active": True,
        },
        timeout=20,
    )
    check(r.status_code == 200, "POST percent promo code returns 200", f"got {r.status_code} {r.text}")
    created = r.json() if r.status_code == 200 else {}
    test10_id = created.get("id")
    check(bool(test10_id), "created promo has id")
    check(created.get("code") == test10_code.upper(), "code stored uppercase")
    check(created.get("discount_type") == "percent", "discount_type=percent")
    check(float(created.get("discount_value", 0)) == 10.0, "discount_value=10")
    check(int(created.get("used_count", -1)) == 0, "used_count initialized to 0")

    # Duplicate code
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": test10_code, "discount_type": "percent", "discount_value": 10},
        timeout=20,
    )
    check(r.status_code == 400, "duplicate code returns 400", f"got {r.status_code} {r.text}")
    check("already exists" in r.text.lower(), "duplicate error mentions 'already exists'")

    # discount_value=0
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": f"ZERO{rand_suffix(4)}", "discount_type": "percent", "discount_value": 0},
        timeout=20,
    )
    check(r.status_code == 400, "discount_value=0 returns 400", f"got {r.status_code} {r.text}")

    # percent > 100
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": f"OVER{rand_suffix(4)}", "discount_type": "percent", "discount_value": 150},
        timeout=20,
    )
    check(r.status_code == 400, "percent>100 returns 400", f"got {r.status_code} {r.text}")
    check("100" in r.text, "error mentions 100", r.text)

    # invalid discount_type
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": f"BAD{rand_suffix(4)}", "discount_type": "invalid", "discount_value": 5},
        timeout=20,
    )
    check(r.status_code == 400, "invalid discount_type returns 400", f"got {r.status_code} {r.text}")

    # 1-char code
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": "X", "discount_type": "percent", "discount_value": 5},
        timeout=20,
    )
    check(r.status_code == 400, "1-char code returns 400", f"got {r.status_code} {r.text}")
    check("at least 2" in r.text.lower(), "error mentions 'at least 2'", r.text)

    # GET list includes our new code
    r = requests.get(f"{API}/admin/promo-codes", headers=H(admin_token), timeout=20)
    check(r.status_code == 200, "GET list returns 200", f"got {r.status_code}")
    codes_seen = [p.get("code") for p in (r.json() or [])]
    check(test10_code in codes_seen, f"list contains {test10_code}", f"codes_seen sample: {codes_seen[:10]}")

    # PUT update with {active: false}
    r = requests.put(
        f"{API}/admin/promo-codes/{test10_id}",
        headers=H(admin_token),
        json={"active": False},
        timeout=20,
    )
    check(r.status_code == 200, "PUT active=false returns 200", f"got {r.status_code} {r.text}")
    check(r.json().get("active") is False, "active flipped to false on response")

    # Re-activate to use it later
    r = requests.put(
        f"{API}/admin/promo-codes/{test10_id}",
        headers=H(admin_token),
        json={"active": True},
        timeout=20,
    )
    check(r.status_code == 200, "PUT active=true (re-activate) returns 200", f"got {r.status_code} {r.text}")

    # PUT invalid id (non-hex / bad ObjectId)
    r = requests.put(
        f"{API}/admin/promo-codes/not-a-valid-id",
        headers=H(admin_token),
        json={"active": False},
        timeout=20,
    )
    check(r.status_code == 400, "PUT invalid id returns 400", f"got {r.status_code} {r.text}")

    # PUT non-existent id
    r = requests.put(
        f"{API}/admin/promo-codes/000000000000000000000000",
        headers=H(admin_token),
        json={"active": False},
        timeout=20,
    )
    check(r.status_code == 404, "PUT non-existent id returns 404", f"got {r.status_code} {r.text}")

    # DELETE
    r = requests.delete(f"{API}/admin/promo-codes/{test10_id}", headers=H(admin_token), timeout=20)
    check(r.status_code == 200, "DELETE returns 200", f"got {r.status_code} {r.text}")
    check(r.json().get("ok") is True, "DELETE body has ok:true")

    # DELETE again -> 404
    r = requests.delete(f"{API}/admin/promo-codes/{test10_id}", headers=H(admin_token), timeout=20)
    check(r.status_code == 404, "DELETE again returns 404", f"got {r.status_code} {r.text}")

    # ===========================================================
    # 2. Validation endpoint
    # ===========================================================
    _label("2. Validation endpoint")

    suffix = rand_suffix(5)
    PERCENT = f"TESTPERCENT{suffix}"
    FIXED = f"TESTFIXED{suffix}"
    INACTIVE = f"TESTINACTIVE{suffix}"
    EXPIRED = f"TESTEXPIRED{suffix}"
    MAXED = f"TESTMAXED{suffix}"

    created_ids = []

    # Create TESTPERCENT
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": PERCENT, "discount_type": "percent", "discount_value": 20, "min_amount": 50, "active": True},
        timeout=20,
    )
    check(r.status_code == 200, f"create {PERCENT}")
    percent_id = r.json().get("id")
    created_ids.append(percent_id)

    # Create TESTFIXED
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": FIXED, "discount_type": "fixed", "discount_value": 15, "min_amount": 10, "active": True},
        timeout=20,
    )
    check(r.status_code == 200, f"create {FIXED}")
    fixed_id = r.json().get("id")
    created_ids.append(fixed_id)

    # Validate TESTPERCENT with subtotal=200 -> valid, discount=40
    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": PERCENT, "subtotal": 200},
        timeout=20,
    )
    check(r.status_code == 200, f"validate {PERCENT} (200 subtotal) returns 200", f"got {r.status_code} {r.text}")
    data = r.json() if r.status_code == 200 else {}
    check(data.get("valid") is True, "valid=true")
    check(abs(float(data.get("discount", 0)) - 40.0) < 0.01, "discount=40", str(data))

    # Validate TESTPERCENT with subtotal=30 -> invalid (below min_amount=50)
    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": PERCENT, "subtotal": 30},
        timeout=20,
    )
    check(r.status_code == 200, "validate below min returns 200 envelope")
    data = r.json()
    check(data.get("valid") is False, "valid=false when subtotal < min_amount")
    check("minimum" in (data.get("message", "").lower()), "message indicates minimum required", str(data))

    # Validate TESTFIXED with subtotal=100 -> valid, discount=15
    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": FIXED, "subtotal": 100},
        timeout=20,
    )
    data = r.json()
    check(r.status_code == 200 and data.get("valid") is True, f"validate {FIXED} valid")
    check(abs(float(data.get("discount", 0)) - 15.0) < 0.01, "fixed discount=15")

    # Validate TESTFIXED with subtotal=5 -> below min_amount=10 -> invalid
    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": FIXED, "subtotal": 5},
        timeout=20,
    )
    data = r.json()
    check(r.status_code == 200, "validate fixed subtotal=5 returns 200")
    check(data.get("valid") is False, "valid=false (below min_amount=10)")

    # INVALID code -> {valid:false, message:"Invalid promo code", discount:0} 200
    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": "INVALID_CODE_XYZ", "subtotal": 100},
        timeout=20,
    )
    check(r.status_code == 200, "validate unknown code returns 200 (not 400)", f"got {r.status_code} {r.text}")
    data = r.json()
    check(data.get("valid") is False, "unknown code: valid=false")
    check(data.get("message") == "Invalid promo code", f"message='Invalid promo code', got {data.get('message')!r}")
    check(float(data.get("discount", -1)) == 0, "unknown code: discount=0")

    # Case-insensitive: lowercase code
    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": PERCENT.lower(), "subtotal": 200},
        timeout=20,
    )
    data = r.json()
    check(r.status_code == 200 and data.get("valid") is True, "lowercase code is case-insensitive")
    check(data.get("code") == PERCENT.upper(), "returned code normalized to UPPER")

    # Inactive code -> invalid
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": INACTIVE, "discount_type": "percent", "discount_value": 10, "active": False},
        timeout=20,
    )
    check(r.status_code == 200, f"create {INACTIVE} (inactive)")
    inactive_id = r.json().get("id")
    created_ids.append(inactive_id)

    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": INACTIVE, "subtotal": 100},
        timeout=20,
    )
    data = r.json()
    check(r.status_code == 200 and data.get("valid") is False, "inactive code -> invalid")
    check("inactive" in data.get("message", "").lower(), "message mentions inactive", str(data))

    # Expired code: create with expires_at in the past
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={
            "code": EXPIRED,
            "discount_type": "percent",
            "discount_value": 10,
            "expires_at": "2020-01-01T00:00:00Z",
            "active": True,
        },
        timeout=20,
    )
    check(r.status_code == 200, f"create {EXPIRED}", f"{r.status_code} {r.text}")
    expired_id = r.json().get("id")
    created_ids.append(expired_id)

    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": EXPIRED, "subtotal": 100},
        timeout=20,
    )
    data = r.json()
    check(r.status_code == 200 and data.get("valid") is False, "expired code -> invalid")
    check("expired" in data.get("message", "").lower(), "message mentions expired", str(data))

    # Maxed code: max_uses=1, then bump used_count via PUT or via a booking
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(admin_token),
        json={"code": MAXED, "discount_type": "percent", "discount_value": 10, "max_uses": 1, "active": True},
        timeout=20,
    )
    check(r.status_code == 200, f"create {MAXED}", f"{r.status_code} {r.text}")
    maxed_id = r.json().get("id")
    created_ids.append(maxed_id)

    # Use Mongo update via the admin PUT? `used_count` is not in PromoCodeUpdate.
    # So we'll instead create a booking that consumes it, OR directly hit DB. The
    # PromoCodeUpdate model doesn't include used_count, so PUT can't bump it.
    # Easiest path: make a booking using MAXED via the customer (subtotal must be >= 0 min_amount).
    # We'll do this with the cheapest car for 2 days to keep totals simple.
    pickup = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00")
    dropoff = (datetime.now(timezone.utc) + timedelta(days=4)).strftime("%Y-%m-%dT10:00:00")
    booking_payload = {
        "car_id": car["id"],
        "pickup_date": pickup,
        "dropoff_date": dropoff,
        "pickup_location": {"name": pickup_loc["name"], "city": pickup_loc.get("city", "")},
        "dropoff_location": {"name": pickup_loc["name"], "city": pickup_loc.get("city", "")},
        "payment_method": "cash",
        "promo_code": MAXED,
    }
    r = requests.post(f"{API}/bookings", headers=H(cust_token), json=booking_payload, timeout=30)
    check(r.status_code == 200, f"booking with MAXED first time returns 200", f"{r.status_code} {r.text}")
    maxed_booking_1 = r.json() if r.status_code == 200 else {}

    # Re-validate MAXED -> invalid (limit reached)
    r = requests.post(
        f"{API}/promo-codes/validate",
        headers=H(cust_token),
        json={"code": MAXED, "subtotal": 100},
        timeout=20,
    )
    data = r.json()
    check(r.status_code == 200 and data.get("valid") is False, "maxed code -> invalid")
    check("usage limit" in data.get("message", "").lower() or "limit" in data.get("message", "").lower(),
          "message mentions usage limit", str(data))

    # Without auth -> 401
    r = requests.post(
        f"{API}/promo-codes/validate",
        json={"code": PERCENT, "subtotal": 200},
        timeout=20,
    )
    check(r.status_code == 401, "validate without auth returns 401", f"got {r.status_code} {r.text}")

    # ===========================================================
    # 3. Booking flow with promo
    # ===========================================================
    _label("3. Booking flow with promo")

    # Read current used_count for PERCENT (for delta check later)
    r = requests.get(f"{API}/admin/promo-codes", headers=H(admin_token), timeout=20)
    all_promos = r.json()
    percent_before = next((p for p in all_promos if p.get("id") == percent_id), None)
    used_before = int(percent_before.get("used_count", 0)) if percent_before else 0

    # Booking with TESTPERCENT (subtotal must be >= 50 due to min_amount; cheapest car 5-day rental should be enough)
    # Pick 5 days so subtotal is meaningful even for cheaper cars
    pickup = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00")
    dropoff = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT10:00:00")
    days = 5
    expected_subtotal = round(days * float(car["price_per_day"]), 2)
    expected_discount = round(expected_subtotal * 0.20, 2)
    expected_discounted = round(max(expected_subtotal - expected_discount, 0.0), 2)
    expected_tax = round(expected_discounted * (float(pickup_loc.get("tax_rate") or 0) / 100), 2)
    expected_total = round(expected_discounted + expected_tax, 2)

    booking_payload = {
        "car_id": car["id"],
        "pickup_date": pickup,
        "dropoff_date": dropoff,
        "pickup_location": {"name": pickup_loc["name"], "city": pickup_loc.get("city", "")},
        "dropoff_location": {"name": pickup_loc["name"], "city": pickup_loc.get("city", "")},
        "payment_method": "cash",
        "promo_code": PERCENT,
    }
    r = requests.post(f"{API}/bookings", headers=H(cust_token), json=booking_payload, timeout=30)
    check(r.status_code == 200, "booking with PERCENT promo returns 200", f"{r.status_code} {r.text}")
    b = r.json() if r.status_code == 200 else {}
    check(b.get("promo_code") == PERCENT.upper(), f"booking.promo_code == {PERCENT}", str(b.get("promo_code")))
    check(float(b.get("discount_amount", 0)) > 0, f"booking.discount_amount > 0 (got {b.get('discount_amount')})")
    check(abs(float(b.get("subtotal", 0)) - expected_subtotal) < 0.01,
          f"booking.subtotal == {expected_subtotal} (no discount)", f"got {b.get('subtotal')}")
    check(abs(float(b.get("discount_amount", 0)) - expected_discount) < 0.01,
          f"booking.discount_amount == {expected_discount}", f"got {b.get('discount_amount')}")
    check(abs(float(b.get("tax_amount", 0)) - expected_tax) < 0.01,
          f"booking.tax_amount == {expected_tax} (computed on DISCOUNTED subtotal)",
          f"got {b.get('tax_amount')}")
    check(abs(float(b.get("total_price", 0)) - expected_total) < 0.01,
          f"booking.total_price == (subtotal-discount) + tax == {expected_total}",
          f"got {b.get('total_price')}")

    # Verify used_count incremented by 1
    r = requests.get(f"{API}/admin/promo-codes", headers=H(admin_token), timeout=20)
    percent_after = next((p for p in r.json() if p.get("id") == percent_id), None)
    used_after = int(percent_after.get("used_count", 0)) if percent_after else -1
    check(used_after == used_before + 1, f"used_count incremented (before={used_before}, after={used_after})")

    # Booking with INVALID promo -> 400
    bad_payload = dict(booking_payload)
    bad_payload["promo_code"] = "INVALID_NOEXIST"
    r = requests.post(f"{API}/bookings", headers=H(cust_token), json=bad_payload, timeout=30)
    check(r.status_code == 400, "booking with INVALID promo returns 400", f"{r.status_code} {r.text}")
    check("invalid promo" in r.text.lower(), "error mentions 'Invalid promo code'", r.text)

    # Booking with no promo_code -> 200, promo_code=None, discount_amount=0
    nopromo_payload = dict(booking_payload)
    nopromo_payload.pop("promo_code", None)
    r = requests.post(f"{API}/bookings", headers=H(cust_token), json=nopromo_payload, timeout=30)
    check(r.status_code == 200, "booking with NO promo returns 200", f"{r.status_code} {r.text}")
    b = r.json() if r.status_code == 200 else {}
    check(b.get("promo_code") in (None, ""), f"promo_code is None (got {b.get('promo_code')!r})")
    check(float(b.get("discount_amount", -1)) == 0, f"discount_amount=0 (got {b.get('discount_amount')})")
    # And tax computed on full subtotal
    expected_tax_full = round(expected_subtotal * (float(pickup_loc.get("tax_rate") or 0) / 100), 2)
    check(abs(float(b.get("tax_amount", 0)) - expected_tax_full) < 0.01,
          "no-promo booking tax computed on full subtotal", f"got {b.get('tax_amount')} expected {expected_tax_full}")

    # Booking with inactive promo -> 400
    inactive_payload = dict(booking_payload)
    inactive_payload["promo_code"] = INACTIVE
    r = requests.post(f"{API}/bookings", headers=H(cust_token), json=inactive_payload, timeout=30)
    check(r.status_code == 400, "booking with INACTIVE promo returns 400", f"{r.status_code} {r.text}")
    check("inactive" in r.text.lower(), "error mentions 'inactive'", r.text)

    # ===========================================================
    # 4. Authorization
    # ===========================================================
    _label("4. Authorization")

    # Non-admin can call /promo-codes/validate (already covered) -> 200
    r = requests.post(f"{API}/promo-codes/validate",
                      headers=H(cust_token),
                      json={"code": PERCENT, "subtotal": 200}, timeout=20)
    check(r.status_code == 200, "non-admin can call /promo-codes/validate", f"{r.status_code} {r.text}")

    # Non-admin cannot list
    r = requests.get(f"{API}/admin/promo-codes", headers=H(cust_token), timeout=20)
    check(r.status_code == 403, "non-admin GET /admin/promo-codes returns 403", f"{r.status_code} {r.text}")

    # Non-admin cannot create
    r = requests.post(
        f"{API}/admin/promo-codes",
        headers=H(cust_token),
        json={"code": f"NA{rand_suffix(3)}", "discount_type": "percent", "discount_value": 5},
        timeout=20,
    )
    check(r.status_code == 403, "non-admin POST /admin/promo-codes returns 403", f"{r.status_code} {r.text}")

    # Non-admin cannot update
    r = requests.put(
        f"{API}/admin/promo-codes/{percent_id}",
        headers=H(cust_token),
        json={"active": False},
        timeout=20,
    )
    check(r.status_code == 403, "non-admin PUT /admin/promo-codes/{id} returns 403", f"{r.status_code} {r.text}")

    # Non-admin cannot delete
    r = requests.delete(f"{API}/admin/promo-codes/{percent_id}", headers=H(cust_token), timeout=20)
    check(r.status_code == 403, "non-admin DELETE /admin/promo-codes/{id} returns 403", f"{r.status_code} {r.text}")

    # ---------- cleanup ----------
    _label("Cleanup")
    for pid in created_ids:
        if pid:
            try:
                requests.delete(f"{API}/admin/promo-codes/{pid}", headers=H(admin_token), timeout=15)
            except Exception:
                pass
    print(f"\nResults: {PASSES} passed, {FAILS} failed")
    if FAILS:
        print("\n--- FAILURE DETAILS ---")
        for f in FAIL_DETAILS:
            print(" *", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
