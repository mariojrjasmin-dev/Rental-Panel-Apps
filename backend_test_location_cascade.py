"""
Backend tests for the Location rename cascade + orphan reference repair feature.

Targets:
  PUT  /api/locations/{id}           (now cascades name/country to cars + bookings)
  POST /api/admin/locations/repair-references  (new admin-only endpoint)

Run: python /app/backend_test_location_cascade.py
"""
import os
import sys
import time
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

BASE = os.environ.get("BACKEND_URL", "http://localhost:8001/api")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

mc = AsyncIOMotorClient(MONGO_URL)
db = mc[DB_NAME]

# Track results
PASS = 0
FAIL = 0
FAILURES = []
CLEANUP_LOC_IDS: list = []
CLEANUP_CAR_IDS: list = []
CLEANUP_BOOKING_IDS: list = []
CLEANUP_USER_IDS: list = []


def expect(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  ❌ {label}")


def admin_token() -> str:
    r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def register_customer() -> tuple[str, str, str]:
    """Returns (email, password, token)"""
    rand = uuid.uuid4().hex[:8]
    email = f"laura.cascade.{rand}@example.com"
    pwd = "Test#1234"
    r = requests.post(
        f"{BASE}/auth/register",
        json={
            "email": email,
            "password": pwd,
            "name": "Laura Cascade",
            "phone": "+18095550111",
            "terms_accepted": True,
            "adult_confirmed": True,
        },
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    return email, pwd, body["token"]


async def find_user_id(email: str) -> str | None:
    u = await db.users.find_one({"email": email.lower().strip()})
    return str(u["_id"]) if u else None


async def seed_location(name: str, country: str = "Dominican Republic", city: str = "Test City",
                        tax_rate: float = 18.0, active: bool = True) -> str:
    doc = {
        "name": name,
        "address": "Test address 123",
        "city": city,
        "country": country,
        "lat": 0.0,
        "lng": 0.0,
        "type": "both",
        "tax_rate": tax_rate,
        "min_booking_days": 1,
        "insurance_included": False,
        "refuel_amount": 0.0,
        "unlimited_mileage": True,
        "mileage_limit_per_day": 0,
        "extra_mileage_charge": 0.0,
        "active": active,
        "created_at": datetime.now(timezone.utc),
        "_test_marker": True,
    }
    res = await db.locations.insert_one(doc)
    CLEANUP_LOC_IDS.append(res.inserted_id)
    return str(res.inserted_id)


async def seed_car_with_loc(loc_name: str, country: str) -> str:
    doc = {
        "name": "Test Cascade Car",
        "brand": "Toyota",
        "model": "Yaris",
        "year": 2024,
        "category": "Economy",
        "transmission": "automatic",
        "fuel_type": "gasoline",
        "seats": 5,
        "price_per_day": 50.0,
        "deposit": 250.0,
        "available": True,
        "images": [],
        "image": "",
        "features": [],
        "stock": {loc_name: 3},
        "pickup_locations": [{"name": loc_name, "country": country}],
        "dropoff_locations": [{"name": loc_name, "country": country}],
        "pickup_location": {"name": loc_name, "country": country},
        "dropoff_location": {"name": loc_name, "country": country},
        "created_at": datetime.now(timezone.utc),
        "_test_marker": True,
    }
    res = await db.cars.insert_one(doc)
    CLEANUP_CAR_IDS.append(res.inserted_id)
    return str(res.inserted_id)


async def seed_booking_with_loc(user_id: str, car_id: str, loc_name: str, country: str) -> str:
    doc = {
        "user_id": user_id,
        "user_email": "seed@example.com",
        "car_id": car_id,
        "car_name": "Test Cascade Car",
        "pickup_date": "2026-06-01T10:00:00",
        "dropoff_date": "2026-06-04T10:00:00",
        "pickup_location": {"name": loc_name, "country": country},
        "dropoff_location": {"name": loc_name, "country": country},
        "status": "pending_payment",
        "payment_status": "pending",
        "payment_method": "cash",
        "subtotal": 150.0,
        "tax_rate": 18.0,
        "tax_amount": 27.0,
        "total_price": 177.0,
        "created_at": datetime.now(timezone.utc),
        "_test_marker": True,
    }
    res = await db.bookings.insert_one(doc)
    CLEANUP_BOOKING_IDS.append(res.inserted_id)
    return str(res.inserted_id)


async def cleanup():
    print("\n--- CLEANUP ---")
    if CLEANUP_BOOKING_IDS:
        r = await db.bookings.delete_many({"_id": {"$in": CLEANUP_BOOKING_IDS}})
        print(f"  bookings deleted: {r.deleted_count}")
    # Defensive: delete any booking with _test_marker:true (includes any we created via POST /bookings)
    r = await db.bookings.delete_many({"_test_marker": True})
    print(f"  marker bookings: {r.deleted_count}")
    if CLEANUP_CAR_IDS:
        r = await db.cars.delete_many({"_id": {"$in": CLEANUP_CAR_IDS}})
        print(f"  cars deleted: {r.deleted_count}")
    if CLEANUP_LOC_IDS:
        r = await db.locations.delete_many({"_id": {"$in": CLEANUP_LOC_IDS}})
        print(f"  locations deleted: {r.deleted_count}")
    if CLEANUP_USER_IDS:
        r = await db.users.delete_many({"_id": {"$in": CLEANUP_USER_IDS}})
        print(f"  users deleted: {r.deleted_count}")


def auth_hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_cascade_full_rename():
    print("\n=== TEST 1: PUT /locations/{id} full cascade on rename ===")
    tok = admin_token()
    rand = uuid.uuid4().hex[:6]
    old_name = f"Cascade Test Loc {rand}"
    new_name = f"Cascade Renamed Loc {rand}"

    loc_id = await seed_location(old_name, country="Dominican Republic", city="Cascade City")
    email, _, _ = register_customer()
    uid = await find_user_id(email)
    if uid:
        CLEANUP_USER_IDS.append(ObjectId(uid))
    car_id = await seed_car_with_loc(old_name, "Dominican Republic")
    booking_id = await seed_booking_with_loc(uid, car_id, old_name, "Dominican Republic")

    # Rename via PUT
    r = requests.put(
        f"{BASE}/locations/{loc_id}",
        headers=auth_hdr(tok),
        json={"name": new_name},
        timeout=15,
    )
    expect(r.status_code == 200, f"PUT rename returns 200 (got {r.status_code} body={r.text[:200]})")
    body = r.json() if r.status_code == 200 else {}
    expect(body.get("name") == new_name, f"response.name == new_name (got {body.get('name')})")
    cascade = body.get("_cascade") or {}
    expect(isinstance(cascade, dict), "_cascade is dict")
    expected_paths = [
        "cars.pickup_locations.name",
        "cars.dropoff_locations.name",
        "cars.pickup_location.name",
        "cars.dropoff_location.name",
        "bookings.pickup_location.name",
        "bookings.dropoff_location.name",
    ]
    for path in expected_paths:
        expect(cascade.get(path, 0) >= 1, f"_cascade has {path} >= 1 (got {cascade.get(path)})")

    # Verify DB state
    car = await db.cars.find_one({"_id": ObjectId(car_id)})
    expect(car["pickup_locations"][0]["name"] == new_name, "cars.pickup_locations[0].name updated")
    expect(car["dropoff_locations"][0]["name"] == new_name, "cars.dropoff_locations[0].name updated")
    expect(car["pickup_location"]["name"] == new_name, "cars.pickup_location.name updated")
    expect(car["dropoff_location"]["name"] == new_name, "cars.dropoff_location.name updated")

    bk = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    expect(bk["pickup_location"]["name"] == new_name, "bookings.pickup_location.name updated")
    expect(bk["dropoff_location"]["name"] == new_name, "bookings.dropoff_location.name updated")

    return loc_id, car_id, booking_id, new_name


async def test_country_only_cascade(loc_id: str, car_id: str, booking_id: str, current_name: str):
    print("\n=== TEST 2: country-only cascade (no rename) ===")
    tok = admin_token()
    new_country = "USA"

    r = requests.put(
        f"{BASE}/locations/{loc_id}",
        headers=auth_hdr(tok),
        json={"country": new_country},
        timeout=15,
    )
    expect(r.status_code == 200, f"PUT country change returns 200 (got {r.status_code})")
    body = r.json() if r.status_code == 200 else {}
    cascade = body.get("_cascade") or {}
    expect(isinstance(cascade, dict), "_cascade dict present on country change")
    # Should NOT include any *.name paths
    name_paths = [k for k in cascade.keys() if k.endswith(".name")]
    expect(len(name_paths) == 0, f"no *.name keys when only country changes (got {name_paths})")
    # Should include country paths
    expected_country_paths = [
        "cars.pickup_locations.country",
        "cars.dropoff_locations.country",
        "cars.pickup_location.country",
        "cars.dropoff_location.country",
        "bookings.pickup_location.country",
        "bookings.dropoff_location.country",
    ]
    for p in expected_country_paths:
        expect(cascade.get(p, 0) >= 1, f"_cascade has {p}>=1 (got {cascade.get(p)})")

    # Verify DB
    car = await db.cars.find_one({"_id": ObjectId(car_id)})
    expect(car["pickup_locations"][0].get("country") == new_country, "cars.pickup_locations[0].country=USA")
    expect(car["dropoff_locations"][0].get("country") == new_country, "cars.dropoff_locations[0].country=USA")
    expect(car["pickup_location"].get("country") == new_country, "cars.pickup_location.country=USA")
    expect(car["dropoff_location"].get("country") == new_country, "cars.dropoff_location.country=USA")
    bk = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    expect(bk["pickup_location"].get("country") == new_country, "bookings.pickup_location.country=USA")
    expect(bk["dropoff_location"].get("country") == new_country, "bookings.dropoff_location.country=USA")

    # Revert country back so the e2e booking test works in same country
    requests.put(
        f"{BASE}/locations/{loc_id}",
        headers=auth_hdr(tok),
        json={"country": "Dominican Republic"},
        timeout=15,
    )


async def test_noop_cascade(loc_id: str):
    print("\n=== TEST 3: no-op cascade for tax_rate/active/refuel_amount-only updates ===")
    tok = admin_token()
    # tax_rate change only
    r = requests.put(
        f"{BASE}/locations/{loc_id}",
        headers=auth_hdr(tok),
        json={"tax_rate": 18.5},
        timeout=10,
    )
    expect(r.status_code == 200, "PUT tax_rate-only returns 200")
    cascade = (r.json() or {}).get("_cascade") or {}
    expect(cascade == {} or "_cascade" not in r.json(), f"tax_rate-only → _cascade empty or absent (got {cascade})")

    # active flag only
    r = requests.put(f"{BASE}/locations/{loc_id}", headers=auth_hdr(tok), json={"active": True}, timeout=10)
    expect(r.status_code == 200, "PUT active-only returns 200")
    cascade2 = (r.json() or {}).get("_cascade") or {}
    expect(cascade2 == {}, f"active-only → no cascade (got {cascade2})")

    # refuel_amount only
    r = requests.put(f"{BASE}/locations/{loc_id}", headers=auth_hdr(tok), json={"refuel_amount": 25.0}, timeout=10)
    expect(r.status_code == 200, "PUT refuel-only returns 200")
    cascade3 = (r.json() or {}).get("_cascade") or {}
    expect(cascade3 == {}, f"refuel-only → no cascade (got {cascade3})")

    # Reset tax_rate back to 18.0 for end-to-end booking test (correct ITBIS)
    requests.put(f"{BASE}/locations/{loc_id}", headers=auth_hdr(tok), json={"tax_rate": 18.0}, timeout=10)


async def test_e2e_booking_after_rename():
    print("\n=== TEST 4: end-to-end booking after rename (the bug fix) ===")
    tok = admin_token()
    rand = uuid.uuid4().hex[:6]
    initial_name = f"E2E Initial Loc {rand}"
    renamed = f"E2E Renamed Loc {rand}"

    loc_id = await seed_location(initial_name, country="Dominican Republic", city="E2E City", tax_rate=18.0)
    car_id = await seed_car_with_loc(initial_name, "Dominican Republic")
    # Make car visible to API
    email, pwd, ctok = register_customer()
    uid = await find_user_id(email)
    if uid:
        CLEANUP_USER_IDS.append(ObjectId(uid))

    # Rename location
    r = requests.put(f"{BASE}/locations/{loc_id}", headers=auth_hdr(tok), json={"name": renamed}, timeout=15)
    expect(r.status_code == 200, "rename PUT 200")
    cascade = (r.json() or {}).get("_cascade") or {}
    expect(cascade.get("cars.pickup_locations.name", 0) >= 1, "cascade hit cars.pickup_locations.name")
    expect(cascade.get("cars.dropoff_locations.name", 0) >= 1, "cascade hit cars.dropoff_locations.name")

    # Verify car was actually updated
    car = await db.cars.find_one({"_id": ObjectId(car_id)})
    expect(car["pickup_locations"][0]["name"] == renamed, "car.pickup_locations[0].name = renamed")

    # NOTE: cars.stock is keyed by location name. The cascade spec does NOT
    # include stock re-keying. To isolate this test from that unrelated
    # concern (which would block POST /bookings with "out of stock"), we
    # manually re-key stock here. This is OUTSIDE the cascade contract.
    await db.cars.update_one(
        {"_id": ObjectId(car_id)},
        {"$set": {f"stock.{renamed}": 3}, "$unset": {f"stock.{initial_name}": ""}},
    )

    # GET tax-by-name with NEW name → tax_rate > 0
    r = requests.get(f"{BASE}/locations/tax-by-name", params={"name": renamed}, timeout=10)
    expect(r.status_code == 200, "tax-by-name 200")
    j = r.json()
    expect(float(j.get("tax_rate") or 0) > 0, f"tax-by-name(new) tax_rate > 0 (got {j.get('tax_rate')})")
    expect(float(j.get("tax_rate") or 0) == 18.0, f"tax-by-name(new) tax_rate==18.0 (got {j.get('tax_rate')})")

    # POST /api/bookings with car referencing the renamed location
    pickup_dt = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    dropoff_dt = (datetime.now(timezone.utc) + timedelta(days=13)).isoformat()
    r = requests.post(
        f"{BASE}/bookings",
        headers=auth_hdr(ctok),
        json={
            "car_id": car_id,
            "pickup_date": pickup_dt,
            "dropoff_date": dropoff_dt,
            "pickup_location": {"name": renamed, "country": "Dominican Republic"},
            "dropoff_location": {"name": renamed, "country": "Dominican Republic"},
            "payment_method": "cash",
            "terms_accepted": True,
        },
        timeout=15,
    )
    expect(r.status_code == 200, f"POST /bookings after rename 200 (got {r.status_code} body={r.text[:300]})")
    if r.status_code == 200:
        bj = r.json()
        bid = bj.get("id")
        if bid:
            try:
                CLEANUP_BOOKING_IDS.append(ObjectId(bid))
            except Exception:
                pass
        # Tag it for cleanup
        if bid:
            await db.bookings.update_one({"_id": ObjectId(bid)}, {"$set": {"_test_marker": True}})
        expect(float(bj.get("tax_rate") or 0) > 0, f"booking.tax_rate > 0 (got {bj.get('tax_rate')})")
        expect(float(bj.get("tax_amount") or 0) > 0, f"booking.tax_amount > 0 (got {bj.get('tax_amount')})")
        # Confirm DB persists tax_rate>0 (this is THE bug fix)
        if bid:
            bk = await db.bookings.find_one({"_id": ObjectId(bid)})
            expect(float(bk.get("tax_rate") or 0) > 0, f"DB booking.tax_rate > 0 (got {bk.get('tax_rate')})")


async def test_repair_endpoint_auth():
    print("\n=== TEST 5: repair-references endpoint auth shape ===")
    r = requests.post(f"{BASE}/admin/locations/repair-references", timeout=10)
    expect(r.status_code == 401, f"no auth → 401 (got {r.status_code})")

    # Non-admin
    email, _, ctok = register_customer()
    uid = await find_user_id(email)
    if uid:
        CLEANUP_USER_IDS.append(ObjectId(uid))
    r = requests.post(f"{BASE}/admin/locations/repair-references", headers=auth_hdr(ctok), timeout=10)
    expect(r.status_code == 403, f"non-admin → 403 (got {r.status_code})")

    # Admin
    tok = admin_token()
    r = requests.post(f"{BASE}/admin/locations/repair-references", headers=auth_hdr(tok), timeout=30)
    expect(r.status_code == 200, f"admin → 200 (got {r.status_code} body={r.text[:200]})")
    body = r.json() if r.status_code == 200 else {}
    for k in ("orphans_found", "repaired", "still_orphaned", "details"):
        expect(k in body, f"response has '{k}' key")


async def test_repair_resolvable_orphan():
    print("\n=== TEST 6: repair-references repairs resolvable orphan + idempotent ===")
    tok = admin_token()

    # Seed a car with an orphan name 'Punta Cana' (prefix-matches 'Punta Cana Airport')
    car_doc = {
        "name": "Orphan Test Car",
        "brand": "Honda",
        "model": "Civic",
        "year": 2024,
        "category": "Economy",
        "transmission": "automatic",
        "fuel_type": "gasoline",
        "seats": 5,
        "price_per_day": 60.0,
        "deposit": 250.0,
        "available": True,
        "images": [],
        "image": "",
        "features": [],
        "stock": {"Punta Cana": 1},
        # ORPHAN — 'Punta Cana' is NOT a current location name, but it prefix-matches 'Punta Cana Airport'
        "pickup_locations": [{"name": "Punta Cana", "country": ""}],
        "dropoff_locations": [{"name": "Punta Cana Airport", "country": "Dominican Republic"}],
        "created_at": datetime.now(timezone.utc),
        "_test_marker": True,
    }
    res = await db.cars.insert_one(car_doc)
    CLEANUP_CAR_IDS.append(res.inserted_id)
    car_id = res.inserted_id

    r = requests.post(f"{BASE}/admin/locations/repair-references", headers=auth_hdr(tok), timeout=30)
    expect(r.status_code == 200, "repair returns 200")
    body = r.json()
    print(f"  orphans_found={body.get('orphans_found')} repaired={body.get('repaired')} still_orphaned={len(body.get('still_orphaned') or [])} details={len(body.get('details') or [])}")
    expect(body.get("orphans_found", 0) >= 1, f"orphans_found >= 1 (got {body.get('orphans_found')})")
    expect(body.get("repaired", 0) >= 1, f"repaired >= 1 (got {body.get('repaired')})")

    # Find the details entry for OUR test car
    details_for_us = [
        d for d in (body.get("details") or [])
        if d.get("collection") == "cars" and d.get("id") == str(car_id)
    ]
    expect(len(details_for_us) >= 1, f"details has entry for our car (got {len(details_for_us)})")
    if details_for_us:
        d = details_for_us[0]
        expect(d.get("from") == "Punta Cana", f"detail.from='Punta Cana' (got {d.get('from')})")
        expect(d.get("to") == "Punta Cana Airport", f"detail.to='Punta Cana Airport' (got {d.get('to')})")

    # Verify DB: car.pickup_locations[0] now has name 'Punta Cana Airport' AND country populated
    car = await db.cars.find_one({"_id": car_id})
    expect(car["pickup_locations"][0]["name"] == "Punta Cana Airport", f"DB pickup_locations[0].name='Punta Cana Airport' (got {car['pickup_locations'][0].get('name')})")
    expect(car["pickup_locations"][0].get("country") == "Dominican Republic", f"DB pickup_locations[0].country='Dominican Republic' (got {car['pickup_locations'][0].get('country')})")

    # Idempotency
    r2 = requests.post(f"{BASE}/admin/locations/repair-references", headers=auth_hdr(tok), timeout=30)
    expect(r2.status_code == 200, "second repair 200")
    body2 = r2.json()
    # Our specific car should no longer appear in details
    details_for_us2 = [
        d for d in (body2.get("details") or [])
        if d.get("collection") == "cars" and d.get("id") == str(car_id)
    ]
    expect(len(details_for_us2) == 0, f"second call: our car not in details (got {len(details_for_us2)})")


async def test_repair_unresolvable_orphan():
    print("\n=== TEST 7: repair-references reports unresolvable orphan ===")
    tok = admin_token()

    # Seed a car with truly unresolvable name 'Mars Colony Spaceport'
    car_doc = {
        "name": "Unresolvable Orphan Car",
        "brand": "Honda",
        "model": "Civic",
        "year": 2024,
        "category": "Economy",
        "transmission": "automatic",
        "fuel_type": "gasoline",
        "seats": 5,
        "price_per_day": 60.0,
        "deposit": 250.0,
        "available": True,
        "images": [],
        "image": "",
        "features": [],
        "stock": {},
        "pickup_locations": [{"name": "Mars Colony Spaceport", "country": ""}],
        "dropoff_locations": [],
        "created_at": datetime.now(timezone.utc),
        "_test_marker": True,
    }
    res = await db.cars.insert_one(car_doc)
    CLEANUP_CAR_IDS.append(res.inserted_id)
    car_id = res.inserted_id

    r = requests.post(f"{BASE}/admin/locations/repair-references", headers=auth_hdr(tok), timeout=30)
    expect(r.status_code == 200, "repair returns 200")
    body = r.json()
    print(f"  orphans_found={body.get('orphans_found')} repaired={body.get('repaired')} still_orphaned={len(body.get('still_orphaned') or [])}")

    # Find OUR entry in still_orphaned
    so = body.get("still_orphaned") or []
    ours = [s for s in so if s.get("collection") == "cars" and s.get("id") == str(car_id)]
    expect(len(ours) >= 1, f"still_orphaned has our car (got {len(ours)})")
    if ours:
        s = ours[0]
        expect(s.get("name") == "Mars Colony Spaceport", f"still_orphaned.name='Mars Colony Spaceport' (got {s.get('name')})")
        # Field path should be array-style
        expect("pickup_locations" in str(s.get("field")), f"still_orphaned.field contains 'pickup_locations' (got {s.get('field')})")

    # Verify DB still untouched
    car = await db.cars.find_one({"_id": car_id})
    expect(car["pickup_locations"][0]["name"] == "Mars Colony Spaceport", "DB orphan name unchanged")


async def test_real_db_unchanged():
    print("\n=== POST-RUN CHECK: real-data locations unchanged ===")
    expected_names = {
        "Punta Cana Airport",
        "Bavaro Beach Hub",
        "Santo Domingo Downtown",
        "Las Americas Airport SDQ",
        "Miami International Airport",
        "Miami Beach Rental Center",
        "JFK Airport New York",
        "Manhattan Midtown Hub",
    }
    cur = set()
    async for l in db.locations.find({}, {"_id": 0, "name": 1}):
        cur.add(l.get("name"))
    missing = expected_names - cur
    expect(len(missing) == 0, f"All real-data location names present (missing: {missing})")


async def main():
    print(f"\nBackend Tests — Location Rename Cascade + Orphan Repair")
    print(f"Base: {BASE}")
    print(f"DB:   {DB_NAME}\n")

    try:
        # Test 1: Full cascade on rename
        loc_id, car_id, booking_id, new_name = await test_cascade_full_rename()

        # Test 2: Country-only cascade
        await test_country_only_cascade(loc_id, car_id, booking_id, new_name)

        # Test 3: No-op cascade
        await test_noop_cascade(loc_id)

        # Test 4: E2E booking after rename (the actual bug fix)
        await test_e2e_booking_after_rename()

        # Test 5: Repair endpoint auth
        await test_repair_endpoint_auth()

        # Test 6: Repair resolvable orphan + idempotency
        await test_repair_resolvable_orphan()

        # Test 7: Repair unresolvable orphan
        await test_repair_unresolvable_orphan()
    finally:
        await cleanup()
        await test_real_db_unchanged()

    print(f"\n=========================================")
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:")
        for f in FAILURES:
            print(f"  - {f}")
    print(f"=========================================\n")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
