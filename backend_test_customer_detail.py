"""
Test GET /api/admin/customers/{customer_id} — N+1 optimization verification.

Focus: confirm the endpoint batches cars lookup into a single db.cars.find() call
and returns the correct response shape including the deleted-car fallback for
missing/invalid car_ids.
"""
import os
import time
import secrets
import requests
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import MongoClient


BASE = "http://localhost:8001/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

PASS = 0
FAIL = 0
FAILURES = []


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {msg}")
    else:
        FAIL += 1
        FAILURES.append(msg)
        print(f"  ❌ {msg}")


def login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"Login failed {email}: {r.status_code} {r.text}")
    return r.json()["token"]


def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    print("\n=== (1) AUTH ===")
    # Pick any existing user oid for path
    any_user = db.users.find_one({})
    any_uid = str(any_user["_id"])

    r = requests.get(f"{BASE}/admin/customers/{any_uid}")
    check(r.status_code == 401, f"Unauth → 401 (got {r.status_code})")

    # Register temp customer
    tag = secrets.token_hex(3)
    temp_email = f"ndtest.cust.{tag}@example.com"
    temp_pwd = "TempPass#123"
    rr = requests.post(f"{BASE}/auth/register", json={
        "name": "Temp NonAdmin",
        "email": temp_email,
        "password": temp_pwd,
        "phone": "+18095551234",
        "terms_accepted": True,
    })
    check(rr.status_code == 200, f"Register temp customer → 200 (got {rr.status_code} {rr.text[:100]})")
    cust_token = rr.json()["token"]
    cust_id = rr.json()["id"]
    cust_h = {"Authorization": f"Bearer {cust_token}"}

    r = requests.get(f"{BASE}/admin/customers/{any_uid}", headers=cust_h)
    check(r.status_code == 403, f"Non-admin → 403 (got {r.status_code})")

    r = requests.get(f"{BASE}/admin/customers/{any_uid}", headers=admin_h)
    check(r.status_code == 200, f"Admin → 200 (got {r.status_code})")

    print("\n=== (6) BAD ID ===")
    r = requests.get(f"{BASE}/admin/customers/abc", headers=admin_h)
    check(r.status_code == 400, f"customer_id='abc' → 400 (got {r.status_code})")
    check("Invalid customer id" in r.text, f"Detail mentions 'Invalid customer id'")

    r = requests.get(f"{BASE}/admin/customers/000000000000000000000000", headers=admin_h)
    check(r.status_code == 404, f"Unknown OID → 404 (got {r.status_code})")
    check("Customer not found" in r.text, f"Detail mentions 'Customer not found'")

    print("\n=== (5) NO BOOKINGS ===")
    # Use newly-registered temp customer (has 0 bookings)
    r = requests.get(f"{BASE}/admin/customers/{cust_id}", headers=admin_h)
    check(r.status_code == 200, f"GET customer with 0 bookings → 200")
    body = r.json()
    expected_top_keys = {"id", "name", "email", "phone", "role", "created_at",
                        "terms_accepted_at", "password_updated_at", "bookings",
                        "bookings_count", "total_spent"}
    check(set(body.keys()) == expected_top_keys,
          f"Top-level keys match exactly (got {sorted(body.keys())})")
    check(body["bookings"] == [], f"bookings = []")
    check(body["bookings_count"] == 0, f"bookings_count = 0")
    check(body["total_spent"] == 0.0, f"total_spent = 0.0 (got {body['total_spent']})")
    check(body["id"] == cust_id, "id matches")
    check(body["email"] == temp_email, "email matches")
    check(body["role"] == "user", "role = user")

    print("\n=== Setup: pick a real car for happy-path ===")
    real_car = db.cars.find_one({})
    if not real_car:
        print("  ⚠️ No car in db.cars; skipping happy path tests")
        real_car_id = None
        real_car_name = None
        real_car_brand = None
    else:
        real_car_id = str(real_car["_id"])
        real_car_name = real_car.get("name", "")
        real_car_brand = real_car.get("brand", "")
        print(f"  Picked car: {real_car_id} name='{real_car_name}' brand='{real_car_brand}'")

    print("\n=== (2) HAPPY PATH: seed 3 fake bookings for temp customer ===")
    now = datetime.now(timezone.utc)
    seeded_booking_ids = []
    if real_car_id:
        for i in range(3):
            doc = {
                "user_id": cust_id,
                "user_email": temp_email,
                "user_name": "Temp NonAdmin",
                "car_id": real_car_id,
                "car_name": real_car_name,
                "car_brand": real_car_brand,
                "pickup_date": datetime(2026, 5, 10 + i, 10, 0, tzinfo=timezone.utc),
                "dropoff_date": datetime(2026, 5, 15 + i, 10, 0, tzinfo=timezone.utc),
                "status": "confirmed",
                "payment_status": "paid",
                "payment_method": "cash",
                "total_price": 100.0 * (i + 1),
                "created_at": now,
                "pickup_location": {"name": "Test Loc"},
                "dropoff_location": {"name": "Test Loc"},
                "_test_marker": True,
            }
            res = db.bookings.insert_one(doc)
            seeded_booking_ids.append(res.inserted_id)
        print(f"  Inserted {len(seeded_booking_ids)} bookings")

    r = requests.get(f"{BASE}/admin/customers/{cust_id}", headers=admin_h)
    check(r.status_code == 200, "GET customer w/ bookings → 200")
    body = r.json()
    check(body["bookings_count"] == 3, f"bookings_count == 3 (got {body['bookings_count']})")
    check(abs(body["total_spent"] - 600.0) < 0.01, f"total_spent = 600.0 (got {body['total_spent']})")
    check(len(body["bookings"]) == 3, "bookings list len = 3")
    expected_b_keys = {"id", "car_name", "car_brand", "pickup_date", "dropoff_date",
                      "status", "payment_status", "payment_method", "total_price",
                      "created_at"}
    if body["bookings"]:
        b0 = body["bookings"][0]
        check(set(b0.keys()) == expected_b_keys,
              f"Booking keys match exactly (got {sorted(b0.keys())})")
        check(b0["car_name"] == real_car_name,
              f"car_name='{real_car_name}' (got '{b0['car_name']}')")
        check(b0["car_brand"] == real_car_brand,
              f"car_brand='{real_car_brand}' (got '{b0['car_brand']}')")
        check(isinstance(b0["pickup_date"], str) and "T" in b0["pickup_date"],
              f"pickup_date is ISO (got {b0['pickup_date']})")
        check(isinstance(b0["dropoff_date"], str) and "T" in b0["dropoff_date"],
              "dropoff_date is ISO")
        check(b0["car_name"] != "(deleted car)", "car_name != '(deleted car)' for real car")

    print("\n=== (3) DELETED-CAR HANDLING ===")
    fake_oid = ObjectId()  # valid format, doesn't exist in db.cars
    while db.cars.find_one({"_id": fake_oid}):
        fake_oid = ObjectId()
    del_booking = {
        "user_id": cust_id,
        "user_email": temp_email,
        "user_name": "Temp NonAdmin",
        "car_id": str(fake_oid),
        "pickup_date": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "dropoff_date": datetime(2026, 6, 5, tzinfo=timezone.utc),
        "status": "pending",
        "payment_status": "pending",
        "payment_method": "cash",
        "total_price": 50.0,
        "created_at": now,
        "_test_marker": True,
    }
    del_id = db.bookings.insert_one(del_booking).inserted_id
    seeded_booking_ids.append(del_id)

    r = requests.get(f"{BASE}/admin/customers/{cust_id}", headers=admin_h)
    check(r.status_code == 200, "GET w/ deleted-car booking → 200")
    body = r.json()
    del_b = next((x for x in body["bookings"] if x["id"] == str(del_id)), None)
    check(del_b is not None, "Deleted-car booking present in response")
    if del_b:
        check(del_b["car_name"] == "(deleted car)",
              f"car_name='(deleted car)' (got '{del_b['car_name']}')")
        check(del_b["car_brand"] == "",
              f"car_brand='' (got '{del_b['car_brand']}')")

    print("\n=== (4) INVALID car_id FORMAT ===")
    bad_id_booking = {
        "user_id": cust_id,
        "user_email": temp_email,
        "user_name": "Temp NonAdmin",
        "car_id": "not-an-objectid-at-all",
        "pickup_date": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "dropoff_date": datetime(2026, 7, 5, tzinfo=timezone.utc),
        "status": "pending",
        "payment_status": "pending",
        "payment_method": "cash",
        "total_price": 75.0,
        "created_at": now,
        "_test_marker": True,
    }
    bad_id = db.bookings.insert_one(bad_id_booking).inserted_id
    seeded_booking_ids.append(bad_id)

    r = requests.get(f"{BASE}/admin/customers/{cust_id}", headers=admin_h)
    check(r.status_code == 200, "GET w/ invalid-format car_id → 200 (try/except handled)")
    body = r.json()
    bad_b = next((x for x in body["bookings"] if x["id"] == str(bad_id)), None)
    check(bad_b is not None, "Bad-id booking present in response")
    if bad_b:
        check(bad_b["car_name"] == "(deleted car)",
              f"car_name='(deleted car)' for invalid car_id (got '{bad_b['car_name']}')")
        check(bad_b["car_brand"] == "",
              f"car_brand='' for invalid car_id (got '{bad_b['car_brand']}')")

    print("\n=== (7) PERFORMANCE / QUERY COUNT (Mongo profiler) ===")
    # Seed 10 more bookings each referencing a distinct EXISTING car.
    # If db.cars has fewer than 10 cars, reuse but vary car_ids by picking up to N.
    cars_sample = list(db.cars.find({}, {"_id": 1}).limit(10))
    seeded_perf_ids = []
    if len(cars_sample) == 0:
        print("  ⚠️ No cars to use for perf test; skipping")
    else:
        # Clear any pre-existing _test_marker bookings for this customer to keep test clean
        for c in cars_sample:
            doc = {
                "user_id": cust_id,
                "user_email": temp_email,
                "user_name": "Temp NonAdmin",
                "car_id": str(c["_id"]),
                "pickup_date": datetime(2026, 8, 1, tzinfo=timezone.utc),
                "dropoff_date": datetime(2026, 8, 5, tzinfo=timezone.utc),
                "status": "pending",
                "payment_status": "pending",
                "payment_method": "cash",
                "total_price": 10.0,
                "created_at": now,
                "_test_marker": True,
            }
            res = db.bookings.insert_one(doc)
            seeded_perf_ids.append(res.inserted_id)
        seeded_booking_ids.extend(seeded_perf_ids)
        print(f"  Seeded {len(seeded_perf_ids)} bookings across {len(cars_sample)} distinct cars")

        # Enable profiling at level 2 on the test database
        db.command({"profile": 0})
        # Drop existing system.profile to start fresh (must lower profile before drop)
        try:
            db.system.profile.drop()
        except Exception:
            pass
        db.command({"profile": 2, "slowms": 0})

        # Time delimiter
        time.sleep(0.05)
        t_start = datetime.now(timezone.utc)

        # Make the request
        r = requests.get(f"{BASE}/admin/customers/{cust_id}", headers=admin_h)
        check(r.status_code == 200, "GET (perf run) → 200")
        body = r.json()
        check(body["bookings_count"] >= len(seeded_perf_ids),
              f"bookings_count >= {len(seeded_perf_ids)} (got {body['bookings_count']})")

        # Wait a moment for profile records to flush
        time.sleep(0.2)
        t_end = datetime.now(timezone.utc)

        # Disable profiling
        db.command({"profile": 0})

        # Inspect profiler entries during the window for db.cars
        # Filter by ns and ts range; look at op (query/command) and command.find
        profile_entries = list(db.system.profile.find({
            "ns": f"{DB_NAME}.cars",
            "ts": {"$gte": t_start, "$lte": t_end},
        }))
        # Count find vs findOne (motor's find_one issues a find with limit:1 in modern drivers,
        # but the helper find_one shows up as op="query" with "command.singleBatch":true or
        # with "limit":1; safer: count any op that targets db.cars and inspect details).
        find_count = 0
        find_one_count = 0
        for e in profile_entries:
            cmd = e.get("command", {}) or {}
            op = e.get("op", "")
            # Newer Mongo: op="command" with command.find=collection
            if op == "command" and "find" in cmd:
                # Distinguish find() vs find_one() — find_one sets limit:1 + singleBatch:true
                if cmd.get("limit") == 1 and cmd.get("singleBatch") is True:
                    find_one_count += 1
                else:
                    find_count += 1
            elif op == "query":
                # Legacy OP_QUERY (unlikely on Mongo 4+)
                if cmd.get("limit") == 1:
                    find_one_count += 1
                else:
                    find_count += 1

        print(f"  Profile entries against {DB_NAME}.cars during request: {len(profile_entries)}")
        print(f"  find() count = {find_count}, find_one() count = {find_one_count}")
        # If profile entries present but classification unclear, print one sample for diagnostics
        if profile_entries and find_count == 0 and find_one_count == 0:
            print(f"  Sample entry: {profile_entries[0]}")

        check(find_count == 1,
              f"Exactly ONE db.cars find() during request (got {find_count})")
        check(find_one_count == 0,
              f"ZERO db.cars find_one() during request (got {find_one_count})")

        # Drop the test profile collection for cleanup
        try:
            db.system.profile.drop()
        except Exception:
            pass

    print("\n=== (8) CLEANUP ===")
    # Delete all seeded _test_marker bookings
    del_res = db.bookings.delete_many({"_test_marker": True, "user_id": cust_id})
    print(f"  Deleted {del_res.deleted_count} bookings (_test_marker:true, user_id={cust_id})")
    check(del_res.deleted_count >= len(seeded_booking_ids),
          f"Cleaned up >= {len(seeded_booking_ids)} bookings (deleted {del_res.deleted_count})")

    # Delete temp user
    user_del = db.users.delete_one({"_id": ObjectId(cust_id)})
    check(user_del.deleted_count == 1, "Deleted temp customer user")

    # Verify no residuals
    leftover = db.bookings.count_documents({"_test_marker": True})
    check(leftover == 0, f"No _test_marker bookings remain (count={leftover})")

    print(f"\n=== RESULT: {PASS} passed, {FAIL} failed ===")
    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
