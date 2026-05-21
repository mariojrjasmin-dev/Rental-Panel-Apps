"""Backend tests for Pre-paid Refuel + Rental Terms Acceptance features.

Tests against the live preview backend.
"""
import os
import re
import random
import string
import time
from datetime import datetime, timezone, timedelta

import requests

BASE = "https://rental-routes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

passes = 0
fails = 0
errors = []


def check(cond, label):
    global passes, fails
    if cond:
        passes += 1
        print(f"  ✅ {label}")
    else:
        fails += 1
        errors.append(label)
        print(f"  ❌ {label}")


def rand_suffix(n=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def admin_login():
    r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def register_customer():
    suffix = rand_suffix()
    email = f"maria.gonzalez.{suffix.lower()}@example.com"
    body = {"email": email, "password": "Customer@2026", "name": f"Maria Gonzalez {suffix}"}
    r = requests.post(f"{BASE}/auth/register", json=body, timeout=15)
    r.raise_for_status()
    return r.json()["token"], email


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    admin_token = admin_login()
    print(f"\n[Setup] Admin login OK")

    # ====================== FEATURE A: Location.refuel_amount ======================
    print("\n=== FEATURE A: Location.refuel_amount ===")
    loc_name = f"DAMS Test Refuel Loc {rand_suffix()}"
    create_body = {
        "name": loc_name,
        "address": "Av. España 123",
        "city": "Punta Cana",
        "country": "Dominican Republic",
        "lat": 18.5601,
        "lng": -68.3725,
        "type": "both",
        "tax_rate": 10.0,
        "min_booking_days": 1,
        "insurance_included": False,
        "refuel_amount": 45.50,
    }
    # A1: POST /api/locations creates location with refuel_amount=45.50
    r = requests.post(f"{BASE}/locations", json=create_body, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 200, f"A1: POST /api/locations admin → 200 (got {r.status_code})")
    loc_resp = r.json()
    loc_id = loc_resp.get("id")
    check(loc_resp.get("refuel_amount") == 45.5, f"A1: POST response includes refuel_amount=45.5 (got {loc_resp.get('refuel_amount')})")
    check(loc_resp.get("tax_rate") == 10.0, "A1: POST response includes tax_rate=10")
    # GET /api/locations/{id}
    r = requests.get(f"{BASE}/locations/{loc_id}", timeout=15)
    check(r.status_code == 200, "A1: GET /api/locations/{id} → 200")
    check(r.json().get("refuel_amount") == 45.5, f"A1: GET /api/locations/{{id}} includes refuel_amount=45.5 (got {r.json().get('refuel_amount')})")

    # A2: PUT only {refuel_amount: 0}
    r = requests.put(f"{BASE}/locations/{loc_id}", json={"refuel_amount": 0}, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 200, "A2: PUT /api/locations/{id} {refuel_amount:0} → 200")
    body2 = r.json()
    check(body2.get("refuel_amount") == 0.0, f"A2: response shows refuel_amount=0 (got {body2.get('refuel_amount')})")
    # other fields untouched
    check(body2.get("name") == loc_name, "A2: name field untouched after PUT")
    check(body2.get("tax_rate") == 10.0, "A2: tax_rate untouched (still 10)")
    check(body2.get("city") == "Punta Cana", "A2: city untouched")
    # follow-up GET
    r = requests.get(f"{BASE}/locations/{loc_id}", timeout=15)
    check(r.json().get("refuel_amount") == 0.0, "A2: GET confirms refuel_amount=0 persisted")

    # A3: PUT {refuel_amount: 30}
    r = requests.put(f"{BASE}/locations/{loc_id}", json={"refuel_amount": 30}, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 200, "A3: PUT {refuel_amount:30} → 200")
    check(r.json().get("refuel_amount") == 30.0, f"A3: response shows refuel_amount=30 (got {r.json().get('refuel_amount')})")
    r = requests.get(f"{BASE}/locations/{loc_id}", timeout=15)
    check(r.json().get("refuel_amount") == 30.0, "A3: GET confirms refuel_amount=30 persisted")

    # A4: tax-by-name
    r = requests.get(f"{BASE}/locations/tax-by-name", params={"name": loc_name}, timeout=15)
    check(r.status_code == 200, "A4: GET tax-by-name → 200")
    txr = r.json()
    check(txr.get("refuel_amount") == 30.0, f"A4: tax-by-name includes refuel_amount=30 (got {txr.get('refuel_amount')})")
    check(txr.get("tax_rate") == 10.0, "A4: tax-by-name tax_rate=10")
    # default for non-existent
    nonexistent_name = f"NoSuchPlace_{rand_suffix()}"
    r = requests.get(f"{BASE}/locations/tax-by-name", params={"name": nonexistent_name}, timeout=15)
    check(r.status_code == 200, "A4: tax-by-name non-existent → 200")
    check(r.json().get("refuel_amount") == 0.0, f"A4: non-existent → refuel_amount=0.0 (got {r.json().get('refuel_amount')})")
    # case-insensitive lookup
    r = requests.get(f"{BASE}/locations/tax-by-name", params={"name": loc_name.upper()}, timeout=15)
    check(r.status_code == 200, "A4: case-insensitive tax-by-name → 200")
    check(r.json().get("refuel_amount") == 30.0, f"A4: case-insensitive returns refuel_amount=30 (got {r.json().get('refuel_amount')})")

    # A5: Authorization
    # Register a customer to test non-admin
    cust_token, cust_email = register_customer()
    r = requests.post(f"{BASE}/locations", json=create_body, headers=auth_headers(cust_token), timeout=15)
    check(r.status_code == 403, f"A5: POST /locations non-admin → 403 (got {r.status_code})")
    r = requests.put(f"{BASE}/locations/{loc_id}", json={"refuel_amount": 5}, headers=auth_headers(cust_token), timeout=15)
    check(r.status_code == 403, f"A5: PUT /locations non-admin → 403 (got {r.status_code})")
    r = requests.get(f"{BASE}/locations/tax-by-name", params={"name": loc_name}, timeout=15)
    check(r.status_code == 200, "A5: tax-by-name is public → 200 (no auth)")

    # ====================== FEATURE B: Rental Terms ======================
    print("\n=== FEATURE B: Rental Terms settings ===")
    # B1: GET public
    r = requests.get(f"{BASE}/settings/rental-terms", timeout=15)
    check(r.status_code == 200, f"B1: GET /api/settings/rental-terms public → 200 (got {r.status_code})")
    initial_terms = r.json().get("terms", "")
    check(isinstance(initial_terms, str) and len(initial_terms) >= 10, f"B1: response has terms string len>=10 (got len={len(initial_terms)})")

    # B2: PUT admin valid body
    custom_terms = ("Custom test terms - please read and accept. " * 5).strip()
    while len(custom_terms) < 200:
        custom_terms += " Extra content."
    r = requests.put(
        f"{BASE}/admin/settings/rental-terms",
        json={"terms": custom_terms},
        headers=auth_headers(admin_token),
        timeout=15,
    )
    check(r.status_code == 200, f"B2: PUT admin terms (valid) → 200 (got {r.status_code})")
    pr = r.json()
    check(pr.get("ok") is True, f"B2: response ok=true (got {pr})")
    check(isinstance(pr.get("length"), int) and pr.get("length") == len(custom_terms), f"B2: length=int matches submitted text (got {pr.get('length')} vs expected {len(custom_terms)})")
    # GET returns the custom text
    r = requests.get(f"{BASE}/settings/rental-terms", timeout=15)
    check(r.json().get("terms") == custom_terms, "B2: GET returns exactly the custom text we PUT")

    # B3: Validation
    # short (<10 chars)
    r = requests.put(f"{BASE}/admin/settings/rental-terms", json={"terms": "short"}, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 400, f"B3: PUT empty/short terms (<10) → 400 (got {r.status_code})")
    # empty string
    r = requests.put(f"{BASE}/admin/settings/rental-terms", json={"terms": ""}, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 400, f"B3: PUT empty string → 400 (got {r.status_code})")
    # too long
    big_terms = "A" * 50001
    r = requests.put(f"{BASE}/admin/settings/rental-terms", json={"terms": big_terms}, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 400, f"B3: PUT >50000 chars → 400 (got {r.status_code})")
    # non-admin → 403
    r = requests.put(f"{BASE}/admin/settings/rental-terms", json={"terms": "x" * 200}, headers=auth_headers(cust_token), timeout=15)
    check(r.status_code == 403, f"B3: PUT non-admin → 403 (got {r.status_code})")
    # no auth → 401
    r = requests.put(f"{BASE}/admin/settings/rental-terms", json={"terms": "x" * 200}, timeout=15)
    check(r.status_code == 401, f"B3: PUT no auth → 401 (got {r.status_code})")

    # B4: Restore initial terms
    r = requests.put(
        f"{BASE}/admin/settings/rental-terms",
        json={"terms": initial_terms},
        headers=auth_headers(admin_token),
        timeout=15,
    )
    check(r.status_code == 200, "B4: Restore original terms → 200")

    # ====================== FEATURE C: BookingCreate refuel + terms ======================
    print("\n=== FEATURE C: BookingCreate honors refuel + terms ===")
    # Find a car
    r = requests.get(f"{BASE}/cars", timeout=15)
    cars = r.json()
    check(isinstance(cars, list) and len(cars) > 0, f"C: GET /api/cars returned non-empty list ({len(cars) if isinstance(cars, list) else 0} cars)")
    if not cars:
        return
    # pick the cheapest with both pickup_location set
    cars_with_pickup = [c for c in cars if c.get("pickup_location") and c.get("pickup_location", {}).get("name")]
    if cars_with_pickup:
        car = sorted(cars_with_pickup, key=lambda c: c.get("price_per_day", 1e9))[0]
    else:
        car = sorted(cars, key=lambda c: c.get("price_per_day", 1e9))[0]
    car_id = car["id"]
    price_per_day = float(car["price_per_day"])
    print(f"  Using car: {car.get('name')} @ ${price_per_day}/day, id={car_id}")

    # Identify the car's pickup_location name and find/configure that DAMS location
    car_pickup_name = (car.get("pickup_location") or {}).get("name") or ""
    car_pickup_loc_dict = car.get("pickup_location") or {"name": loc_name, "address": "", "city": "", "country": ""}
    car_dropoff_loc_dict = car.get("dropoff_location") or car_pickup_loc_dict

    # Find the location in /api/locations matching car_pickup_name
    r = requests.get(f"{BASE}/locations", timeout=15)
    all_locs = r.json()
    target_loc = None
    for l in all_locs:
        if (l.get("name") or "").strip().lower() == car_pickup_name.strip().lower():
            target_loc = l
            break
    saved_original = None
    target_loc_id = None
    if target_loc:
        target_loc_id = target_loc.get("id")
        saved_original = {
            "tax_rate": float(target_loc.get("tax_rate") or 0),
            "refuel_amount": float(target_loc.get("refuel_amount") or 0),
        }
        # PATCH it to tax_rate=10 and refuel_amount=50
        r = requests.put(
            f"{BASE}/locations/{target_loc_id}",
            json={"tax_rate": 10.0, "refuel_amount": 50.0},
            headers=auth_headers(admin_token),
            timeout=15,
        )
        check(r.status_code == 200, f"C: PATCH pickup location to refuel=50,tax=10 → 200 (got {r.status_code})")
    else:
        # No matching location — update the car's pickup_location to use our test loc
        print(f"  No matching location for car pickup name {car_pickup_name!r}; updating car to use test loc {loc_name}")
        # First, set our test location to refuel=50, tax=10
        r = requests.put(
            f"{BASE}/locations/{loc_id}",
            json={"refuel_amount": 50.0, "tax_rate": 10.0},
            headers=auth_headers(admin_token),
            timeout=15,
        )
        check(r.status_code == 200, "C: setup test loc with refuel=50,tax=10 → 200")
        # Update the car pickup_location and dropoff_location to our test loc
        new_pickup = {"name": loc_name, "address": "Av. España 123", "city": "Punta Cana", "country": "Dominican Republic"}
        r = requests.put(
            f"{BASE}/cars/{car_id}",
            json={"pickup_location": new_pickup, "dropoff_location": new_pickup},
            headers=auth_headers(admin_token),
            timeout=15,
        )
        check(r.status_code == 200, "C: updated car pickup_location to test loc → 200")
        car_pickup_loc_dict = new_pickup
        car_dropoff_loc_dict = new_pickup

    # tax-by-name confirms current configuration before booking tests
    name_for_check = car_pickup_loc_dict.get("name") if not target_loc else target_loc.get("name")
    r = requests.get(f"{BASE}/locations/tax-by-name", params={"name": name_for_check}, timeout=15)
    cfg = r.json()
    check(cfg.get("refuel_amount") == 50.0 and cfg.get("tax_rate") == 10.0,
          f"C: tax-by-name confirms refuel=50, tax=10 (got refuel={cfg.get('refuel_amount')}, tax={cfg.get('tax_rate')})")

    # Register a fresh customer
    cust2_token, cust2_email = register_customer()
    print(f"  Customer registered: {cust2_email}")

    # Build dates (3 days)
    pickup_date = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat() + "T10:00:00"
    dropoff_date = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat() + "T10:00:00"
    days = 3

    booking_body_base = {
        "car_id": car_id,
        "pickup_date": pickup_date,
        "dropoff_date": dropoff_date,
        "pickup_location": car_pickup_loc_dict if isinstance(car_pickup_loc_dict, dict) else {"name": name_for_check},
        "dropoff_location": car_dropoff_loc_dict if isinstance(car_dropoff_loc_dict, dict) else {"name": name_for_check},
        "payment_method": "cash",
    }

    created_bookings = []

    # C1: terms_accepted=false → 400
    body = {**booking_body_base, "terms_accepted": False, "refuel_opted_in": False}
    r = requests.post(f"{BASE}/bookings", json=body, headers=auth_headers(cust2_token), timeout=20)
    check(r.status_code == 400, f"C1: terms_accepted=false → 400 (got {r.status_code})")
    detail = (r.json().get("detail") if r.status_code == 400 else "") or ""
    check(("term" in detail.lower()) and ("accept" in detail.lower()), f"C1: error mentions terms/accepted (got: {detail!r})")

    # C2: terms_accepted=true, refuel_opted_in=false → success, refuel_amount=0
    body = {**booking_body_base, "terms_accepted": True, "refuel_opted_in": False}
    r = requests.post(f"{BASE}/bookings", json=body, headers=auth_headers(cust2_token), timeout=20)
    check(r.status_code == 200, f"C2: terms_accepted=true, refuel=false → 200 (got {r.status_code}, body={r.text[:200]})")
    if r.status_code == 200:
        b2 = r.json()
        created_bookings.append(b2["id"])
        check(b2.get("refuel_amount") == 0.0, f"C2: booking refuel_amount=0 (got {b2.get('refuel_amount')})")
        check(b2.get("refuel_opted_in") is False, f"C2: booking refuel_opted_in=False (got {b2.get('refuel_opted_in')})")
        expected_subtotal = round(price_per_day * days, 2)
        expected_total = round(expected_subtotal * 1.10, 2)
        check(abs(float(b2.get("total_price", 0)) - expected_total) <= 0.02,
              f"C2: total_price excludes refuel: expected ~{expected_total}, got {b2.get('total_price')}")
        # check terms_accepted_at present? Note the doc has it but serialize_booking returns datetime as isoformat possibly. Let's check it exists.
        tat = b2.get("terms_accepted_at")
        check(tat is not None, f"C2: terms_accepted_at present (got {tat!r})")

    # C3: terms_accepted=true + refuel_opted_in=true → success
    body = {**booking_body_base, "terms_accepted": True, "refuel_opted_in": True}
    r = requests.post(f"{BASE}/bookings", json=body, headers=auth_headers(cust2_token), timeout=20)
    check(r.status_code == 200, f"C3: terms+refuel=true → 200 (got {r.status_code}, body={r.text[:200]})")
    if r.status_code == 200:
        b3 = r.json()
        created_bookings.append(b3["id"])
        check(b3.get("refuel_amount") == 50.0, f"C3: booking refuel_amount=50 (got {b3.get('refuel_amount')})")
        check(b3.get("refuel_opted_in") is True, f"C3: booking refuel_opted_in=True (got {b3.get('refuel_opted_in')})")
        expected_subtotal = round(price_per_day * days, 2)
        expected_taxable = round(expected_subtotal + 50.0, 2)
        expected_total = round(expected_taxable * 1.10, 2)
        actual_total = float(b3.get("total_price", 0))
        check(abs(actual_total - expected_total) <= 0.02,
              f"C3: total = (subtotal+refuel)*(1+tax/100): expected ~{expected_total}, got {actual_total} (subtotal={expected_subtotal}, taxable={expected_taxable})")
        tat = b3.get("terms_accepted_at")
        check(tat is not None, f"C3: terms_accepted_at present (got {tat!r})")
        # Confirm it's a recent ISO datetime (parse it)
        if tat:
            try:
                if isinstance(tat, str):
                    dt = datetime.fromisoformat(tat.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - dt).total_seconds()
                    check(0 <= age <= 300, f"C3: terms_accepted_at is recent (<5min old, age={age:.1f}s)")
                else:
                    check(True, "C3: terms_accepted_at present (non-string)")
            except Exception as ex:
                check(False, f"C3: terms_accepted_at parseable as ISO (parse err: {ex})")

    # C4: refuel_opted_in=true but location has refuel_amount=0
    # Create another fresh location with refuel_amount=0 and tax_rate=10
    loc2_name = f"DAMS Zero Refuel Loc {rand_suffix()}"
    zero_loc_body = {**create_body, "name": loc2_name, "refuel_amount": 0.0, "tax_rate": 10.0}
    r = requests.post(f"{BASE}/locations", json=zero_loc_body, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 200, "C4: create zero-refuel location → 200")
    zero_loc = r.json()
    zero_loc_id = zero_loc.get("id")
    # Update the car to use this location
    new_pickup2 = {"name": loc2_name, "address": "Av. España 123", "city": "Punta Cana", "country": "Dominican Republic"}
    r = requests.put(
        f"{BASE}/cars/{car_id}",
        json={"pickup_location": new_pickup2, "dropoff_location": new_pickup2},
        headers=auth_headers(admin_token),
        timeout=15,
    )
    check(r.status_code == 200, "C4: update car to zero-refuel location → 200")
    body = {
        **booking_body_base,
        "pickup_location": new_pickup2,
        "dropoff_location": new_pickup2,
        "terms_accepted": True,
        "refuel_opted_in": True,
    }
    r = requests.post(f"{BASE}/bookings", json=body, headers=auth_headers(cust2_token), timeout=20)
    check(r.status_code == 200, f"C4: booking at zero-refuel loc → 200 (got {r.status_code})")
    if r.status_code == 200:
        b4 = r.json()
        created_bookings.append(b4["id"])
        check(b4.get("refuel_amount") == 0.0, f"C4: booking refuel_amount=0 (got {b4.get('refuel_amount')})")
        check(b4.get("refuel_opted_in") is False, f"C4: refuel_opted_in coerced to False when amount=0 (got {b4.get('refuel_opted_in')})")
        expected_subtotal = round(price_per_day * days, 2)
        expected_total = round(expected_subtotal * 1.10, 2)
        check(abs(float(b4.get("total_price", 0)) - expected_total) <= 0.02,
              f"C4: total unchanged (no refuel charge): expected ~{expected_total}, got {b4.get('total_price')}")

    # C5: Promo + refuel combo. Use the loc with refuel=50, tax=10.
    # Restore car to the refuel-loc first.
    if target_loc_id:
        r = requests.put(
            f"{BASE}/cars/{car_id}",
            json={"pickup_location": car.get("pickup_location"), "dropoff_location": car.get("dropoff_location") or car.get("pickup_location")},
            headers=auth_headers(admin_token),
            timeout=15,
        )
    else:
        r = requests.put(
            f"{BASE}/cars/{car_id}",
            json={"pickup_location": {"name": loc_name, "address": "Av. España 123", "city": "Punta Cana", "country": "Dominican Republic"},
                  "dropoff_location": {"name": loc_name, "address": "Av. España 123", "city": "Punta Cana", "country": "Dominican Republic"}},
            headers=auth_headers(admin_token),
            timeout=15,
        )
    check(r.status_code == 200, "C5: restore car to refuel-50 location → 200")
    # Create a 10% promo
    promo_code = f"REFUELTEST{rand_suffix()}"
    promo_body = {
        "code": promo_code,
        "discount_type": "percent",
        "discount_value": 10.0,
        "max_uses": 5,
        "min_amount": 0.0,
        "active": True,
    }
    r = requests.post(f"{BASE}/admin/promo-codes", json=promo_body, headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 200, f"C5: create promo {promo_code} → 200 (got {r.status_code})")
    created_promo_id = r.json().get("id") if r.status_code == 200 else None

    pickup_loc_for_book5 = car.get("pickup_location") or {"name": loc_name, "address": "Av. España 123", "city": "Punta Cana", "country": "Dominican Republic"}
    dropoff_loc_for_book5 = car.get("dropoff_location") or pickup_loc_for_book5
    body = {
        "car_id": car_id,
        "pickup_date": pickup_date,
        "dropoff_date": dropoff_date,
        "pickup_location": pickup_loc_for_book5,
        "dropoff_location": dropoff_loc_for_book5,
        "payment_method": "cash",
        "terms_accepted": True,
        "refuel_opted_in": True,
        "promo_code": promo_code,
    }
    r = requests.post(f"{BASE}/bookings", json=body, headers=auth_headers(cust2_token), timeout=20)
    check(r.status_code == 200, f"C5: promo + refuel booking → 200 (got {r.status_code}, body={r.text[:300]})")
    if r.status_code == 200:
        b5 = r.json()
        created_bookings.append(b5["id"])
        subtotal = round(price_per_day * days, 2)
        discount = round(subtotal * 0.10, 2)
        discounted = round(subtotal - discount, 2)
        taxable = round(discounted + 50.0, 2)
        expected_total = round(taxable * 1.10, 2)
        actual_total = float(b5.get("total_price", 0))
        check(b5.get("refuel_amount") == 50.0, f"C5: booking refuel_amount=50 (got {b5.get('refuel_amount')})")
        check(abs(float(b5.get("discount_amount", 0)) - discount) <= 0.02,
              f"C5: discount_amount={discount} (got {b5.get('discount_amount')})")
        check(abs(actual_total - expected_total) <= 0.02,
              f"C5: total = (sub-disc+refuel)*(1+tax/100): expected ~{expected_total}, got {actual_total} (subtotal={subtotal}, discount={discount}, taxable={taxable})")

    # ====================== CLEANUP ======================
    print("\n=== CLEANUP ===")
    # Delete test locations
    r = requests.delete(f"{BASE}/locations/{loc_id}", headers=auth_headers(admin_token), timeout=15)
    check(r.status_code == 200, f"Cleanup: DELETE test loc {loc_id} → 200 (got {r.status_code})")
    try:
        r = requests.delete(f"{BASE}/locations/{zero_loc_id}", headers=auth_headers(admin_token), timeout=15)
        check(r.status_code == 200, f"Cleanup: DELETE zero-refuel loc → 200 (got {r.status_code})")
    except Exception:
        pass

    # Restore target_loc refuel/tax if we modified it
    if target_loc and saved_original is not None:
        r = requests.put(
            f"{BASE}/locations/{target_loc_id}",
            json={"refuel_amount": saved_original["refuel_amount"], "tax_rate": saved_original["tax_rate"]},
            headers=auth_headers(admin_token),
            timeout=15,
        )
        check(r.status_code == 200, f"Cleanup: restore original loc {target_loc_id} tax/refuel → 200")

    # Restore car pickup_location if we changed it (use original car)
    try:
        r = requests.put(
            f"{BASE}/cars/{car_id}",
            json={"pickup_location": car.get("pickup_location"), "dropoff_location": car.get("dropoff_location")},
            headers=auth_headers(admin_token),
            timeout=15,
        )
        # don't fail test on this
    except Exception:
        pass

    # Delete promo
    if created_promo_id:
        r = requests.delete(f"{BASE}/admin/promo-codes/{created_promo_id}", headers=auth_headers(admin_token), timeout=15)
        check(r.status_code == 200, "Cleanup: DELETE promo → 200")

    # Delete created bookings (if admin endpoint exists) - we leave them; just print
    print(f"  Created bookings (left in DB for audit): {created_bookings}")

    # Restore rental terms to initial
    r = requests.put(
        f"{BASE}/admin/settings/rental-terms",
        json={"terms": initial_terms},
        headers=auth_headers(admin_token),
        timeout=15,
    )
    check(r.status_code == 200, "Cleanup: restored original rental terms")

    print(f"\n========================= RESULTS =========================")
    print(f"PASSED: {passes}")
    print(f"FAILED: {fails}")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
