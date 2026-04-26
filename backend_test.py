"""
Backend tests for Dams Car Rental - min_booking_days per location feature.

Tests:
1) POST /api/locations persists min_booking_days
2) PUT /api/locations/{id} updates min_booking_days
3) GET /api/locations/tax-by-name returns min_booking_days correctly
   - existing with value
   - existing missing field -> default 1
   - non-existent name -> default 1
   - case-insensitive lookup
4) Authorization on POST/PUT vs public GET tax-by-name
"""

import os
import sys
import uuid
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = "https://rental-routes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

session_admin = requests.Session()
session_user = requests.Session()
created_location_ids = []
created_user_email = None

results = []


def record(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}{(' - ' + detail) if detail else ''}")
    results.append((name, ok, detail))


def login_admin():
    r = session_admin.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("role") == "admin", "logged-in user is not admin"
    return data


def register_regular_user():
    global created_user_email
    suffix = uuid.uuid4().hex[:8]
    email = f"customer_{suffix}@damstest.com"
    password = "Customer@123"
    r = session_user.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "name": f"Test Customer {suffix}"},
        timeout=15,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    created_user_email = email
    return email, password


# ---------- 1. POST /api/locations with min_booking_days=5 ----------
def test_create_location_with_min_booking_days():
    name = f"DamsTest Pickup {uuid.uuid4().hex[:6]}"
    payload = {
        "name": name,
        "address": "123 Test Blvd",
        "city": "Test City",
        "country": "Testland",
        "lat": 18.5,
        "lng": -68.5,
        "type": "both",
        "tax_rate": 12.5,
        "min_booking_days": 5,
    }
    r = session_admin.post(f"{BASE_URL}/locations", json=payload, timeout=15)
    record("POST /api/locations returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    if r.status_code != 200:
        return None, None
    body = r.json()
    loc_id = body.get("id")
    if loc_id:
        created_location_ids.append(loc_id)
    record(
        "POST /api/locations persists min_booking_days=5",
        body.get("min_booking_days") == 5,
        f"got {body.get('min_booking_days')!r}",
    )
    record(
        "POST /api/locations returns full doc with name+id",
        bool(body.get("name") == name and loc_id),
        f"name={body.get('name')!r} id={loc_id!r}",
    )
    return loc_id, name


# ---------- 2. PUT /api/locations/{id} updates only min_booking_days ----------
def test_update_min_booking_days(loc_id):
    if not loc_id:
        record("PUT /api/locations updates min_booking_days", False, "no location id")
        return
    r = session_admin.put(
        f"{BASE_URL}/locations/{loc_id}",
        json={"min_booking_days": 3},
        timeout=15,
    )
    record(
        "PUT /api/locations/{id} returns 200",
        r.status_code == 200,
        f"status={r.status_code} body={r.text[:200]}",
    )
    if r.status_code != 200:
        return
    body = r.json()
    record(
        "PUT response reflects min_booking_days=3",
        body.get("min_booking_days") == 3,
        f"got {body.get('min_booking_days')!r}",
    )
    # Verify GET reflects the change
    r2 = session_admin.get(f"{BASE_URL}/locations/{loc_id}", timeout=15)
    ok = r2.status_code == 200 and r2.json().get("min_booking_days") == 3
    record(
        "GET /api/locations/{id} reflects updated min_booking_days=3",
        ok,
        f"status={r2.status_code} body={r2.text[:200]}",
    )


# ---------- 3. GET /api/locations/tax-by-name ----------
def test_tax_by_name_with_value(name):
    # Set min_booking_days=5 on the test location for this check
    r_put = session_admin.put(
        f"{BASE_URL}/locations/{created_location_ids[0]}",
        json={"min_booking_days": 5, "tax_rate": 12.5},
        timeout=15,
    )
    assert r_put.status_code == 200, f"setup PUT failed {r_put.status_code} {r_put.text}"

    # Public access (no auth)
    pub = requests.Session()
    r = pub.get(f"{BASE_URL}/locations/tax-by-name", params={"name": name}, timeout=15)
    record("GET tax-by-name (public, exists) returns 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code != 200:
        return
    body = r.json()
    expected_keys = {"tax_rate", "name", "city", "min_booking_days"}
    record(
        "tax-by-name response has expected keys",
        expected_keys.issubset(body.keys()),
        f"keys={list(body.keys())}",
    )
    record(
        "tax-by-name returns min_booking_days=5 when set",
        body.get("min_booking_days") == 5,
        f"got {body.get('min_booking_days')!r}",
    )
    record(
        "tax-by-name returns matching name + non-empty city",
        body.get("name") == name and body.get("city") == "Test City",
        f"name={body.get('name')!r} city={body.get('city')!r}",
    )

    # Case-insensitive lookup
    r2 = pub.get(f"{BASE_URL}/locations/tax-by-name", params={"name": name.lower()}, timeout=15)
    body2 = r2.json() if r2.status_code == 200 else {}
    ok2 = (
        r2.status_code == 200
        and body2.get("min_booking_days") == 5
        and (body2.get("name") or "").lower() == name.lower()
    )
    record(
        "tax-by-name lookup is case-insensitive",
        ok2,
        f"status={r2.status_code} body={r2.text[:200]}",
    )


def test_tax_by_name_missing_field():
    """Insert a location directly via Mongo without min_booking_days to verify default."""
    try:
        mc = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        db = mc[DB_NAME]
        unique_name = f"DamsLegacyLoc_{uuid.uuid4().hex[:6]}"
        doc = {
            "name": unique_name,
            "address": "Legacy Rd",
            "city": "Legacy City",
            "country": "Testland",
            "lat": 1.0,
            "lng": 2.0,
            "type": "both",
            "tax_rate": 7.5,
            # NOTE: no min_booking_days field
        }
        ins = db.locations.insert_one(doc)
        try:
            r = requests.get(
                f"{BASE_URL}/locations/tax-by-name",
                params={"name": unique_name},
                timeout=15,
            )
            body = r.json() if r.status_code == 200 else {}
            ok = (
                r.status_code == 200
                and body.get("min_booking_days") == 1
                and body.get("name") == unique_name
            )
            record(
                "tax-by-name returns default 1 when min_booking_days missing in DB",
                ok,
                f"status={r.status_code} body={r.text[:200]}",
            )
        finally:
            db.locations.delete_one({"_id": ins.inserted_id})
        mc.close()
    except Exception as e:
        record(
            "tax-by-name returns default 1 when min_booking_days missing in DB",
            False,
            f"setup error: {e}",
        )


def test_tax_by_name_nonexistent():
    pub = requests.Session()
    bogus = f"NoSuchLocation_{uuid.uuid4().hex[:8]}"
    r = pub.get(f"{BASE_URL}/locations/tax-by-name", params={"name": bogus}, timeout=15)
    ok_status = r.status_code == 200
    record("tax-by-name (nonexistent) returns 200", ok_status, f"status={r.status_code}")
    if not ok_status:
        return
    body = r.json()
    record(
        "tax-by-name (nonexistent) returns tax_rate=0.0",
        body.get("tax_rate") == 0.0,
        f"got {body.get('tax_rate')!r}",
    )
    record(
        "tax-by-name (nonexistent) returns min_booking_days=1",
        body.get("min_booking_days") == 1,
        f"got {body.get('min_booking_days')!r}",
    )
    record(
        "tax-by-name (nonexistent) echoes name and empty city",
        body.get("name") == bogus and body.get("city") == "",
        f"name={body.get('name')!r} city={body.get('city')!r}",
    )


# ---------- 4. Authorization ----------
def test_authorization():
    pub = requests.Session()
    r = pub.get(
        f"{BASE_URL}/locations/tax-by-name",
        params={"name": "Punta Cana Airport"},
        timeout=15,
    )
    record(
        "GET tax-by-name is public (no auth)",
        r.status_code == 200,
        f"status={r.status_code} body={r.text[:200]}",
    )

    payload = {
        "name": f"Unauthorized_{uuid.uuid4().hex[:6]}",
        "address": "x",
        "city": "x",
        "country": "x",
        "lat": 0.0,
        "lng": 0.0,
        "type": "both",
        "tax_rate": 0.0,
        "min_booking_days": 1,
    }
    r = session_user.post(f"{BASE_URL}/locations", json=payload, timeout=15)
    record(
        "POST /api/locations as non-admin returns 403",
        r.status_code == 403,
        f"status={r.status_code} body={r.text[:200]}",
    )

    if created_location_ids:
        r = session_user.put(
            f"{BASE_URL}/locations/{created_location_ids[0]}",
            json={"min_booking_days": 9},
            timeout=15,
        )
        record(
            "PUT /api/locations/{id} as non-admin returns 403",
            r.status_code == 403,
            f"status={r.status_code} body={r.text[:200]}",
        )


def cleanup():
    for loc_id in list(created_location_ids):
        try:
            r = session_admin.delete(f"{BASE_URL}/locations/{loc_id}", timeout=15)
            print(f"Cleanup DELETE /locations/{loc_id} -> {r.status_code}")
        except Exception as e:
            print(f"Cleanup error for {loc_id}: {e}")
    if created_user_email:
        try:
            mc = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            db = mc[DB_NAME]
            db.users.delete_one({"email": created_user_email})
            mc.close()
            print(f"Cleanup deleted user {created_user_email}")
        except Exception as e:
            print(f"Cleanup user error: {e}")


def main():
    print(f"Backend URL: {BASE_URL}")
    print(f"Mongo: {MONGO_URL} db={DB_NAME}")
    login_admin()
    register_regular_user()
    loc_id, name = test_create_location_with_min_booking_days()
    test_update_min_booking_days(loc_id)
    if name:
        test_tax_by_name_with_value(name)
    test_tax_by_name_missing_field()
    test_tax_by_name_nonexistent()
    test_authorization()
    cleanup()

    passed = sum(1 for _, ok, _ in results if ok)
    failed = [n for n, ok, _ in results if not ok]
    print("\n" + "=" * 70)
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {len(failed)}")
    if failed:
        print("Failed tests:")
        for n in failed:
            print(f"  - {n}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
