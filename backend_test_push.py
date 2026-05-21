"""Backend tests for Push Notification endpoints and booking push triggers.

Tests:
1. POST /api/users/push-token (auth required) - register expo push tokens
2. DELETE /api/users/push-token (auth required) - unregister tokens
3. POST /api/bookings smoke test - booking still saves with push wiring
4. PUT /api/admin/bookings/{id}/status smoke test - admin status update succeeds
"""
import os
import uuid
import sys
import requests
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta, timezone

# Load backend URL from frontend .env
BACKEND_URL = "https://rental-routes.preview.emergentagent.com"
API = f"{BACKEND_URL}/api"

# Load mongo from backend env
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

results = []
def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} {('- ' + detail) if detail else ''}")
    results.append((name, passed, detail))
    return passed

session_admin = requests.Session()
session_user = requests.Session()


def login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        print(f"Login failed for {email}: {r.status_code} {r.text}")
        return None
    return r.json()


def register_random_user():
    suffix = uuid.uuid4().hex[:8]
    email = f"qa.push.{suffix}@damscarrental.com"
    password = "Test@1234"
    name = f"QA Push {suffix}"
    r = session_user.post(f"{API}/auth/register", json={"email": email, "password": password, "name": name}, timeout=20)
    if r.status_code != 200:
        print(f"Register failed: {r.status_code} {r.text}")
        return None
    return r.json()


def main():
    print("=" * 60)
    print("Backend Push Notification Tests")
    print("=" * 60)

    # ---- Login admin ----
    admin = login(session_admin, ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin:
        record("Admin login", False, "Cannot proceed without admin auth")
        sys.exit(1)
    record("Admin login", True, f"id={admin.get('id')}")

    # ---- Create test user ----
    user = register_random_user()
    if not user:
        record("Register test user", False)
        sys.exit(1)
    user_id = user["id"]
    record("Register test user", True, f"id={user_id}")

    # ============================================================
    # TEST 1: POST /api/users/push-token
    # ============================================================
    print("\n--- POST /api/users/push-token ---")

    # 1a) Without auth - should be 401
    r = requests.post(f"{API}/users/push-token", json={"token": "ExponentPushToken[abc123def456]"}, timeout=20)
    record("POST push-token without auth -> 401", r.status_code == 401, f"got {r.status_code}")

    # 1b) Valid ExponentPushToken[...] - 200, {ok: true}
    valid_token_1 = "ExponentPushToken[abc123def456]"
    r = session_user.post(f"{API}/users/push-token", json={"token": valid_token_1}, timeout=20)
    ok = r.status_code == 200 and r.json().get("ok") is True
    record("POST valid ExponentPushToken[..] -> 200 {ok:true}", ok, f"status={r.status_code} body={r.text[:120]}")

    # Verify persisted in Mongo
    udoc = db.users.find_one({"_id": ObjectId(user_id)})
    tokens = (udoc or {}).get("push_tokens") or []
    record("Token persisted in user.push_tokens", valid_token_1 in tokens, f"push_tokens={tokens}")

    # 1c) Register same token again - $addToSet should not duplicate
    r = session_user.post(f"{API}/users/push-token", json={"token": valid_token_1}, timeout=20)
    udoc = db.users.find_one({"_id": ObjectId(user_id)})
    tokens = (udoc or {}).get("push_tokens") or []
    count_same = tokens.count(valid_token_1)
    record("Re-registering same token is idempotent (no duplicates)", r.status_code == 200 and count_same == 1, f"count={count_same} tokens={tokens}")

    # 1d) Valid ExpoPushToken[...] prefix - 200
    valid_token_2 = "ExpoPushToken[xyz]"
    r = session_user.post(f"{API}/users/push-token", json={"token": valid_token_2}, timeout=20)
    ok = r.status_code == 200 and r.json().get("ok") is True
    record("POST ExpoPushToken[xyz] -> 200 {ok:true}", ok, f"status={r.status_code} body={r.text[:120]}")

    udoc = db.users.find_one({"_id": ObjectId(user_id)})
    tokens = (udoc or {}).get("push_tokens") or []
    record("Both tokens stored", valid_token_1 in tokens and valid_token_2 in tokens, f"tokens={tokens}")

    # 1e) Invalid format "garbage" - 400
    r = session_user.post(f"{API}/users/push-token", json={"token": "garbage"}, timeout=20)
    ok = r.status_code == 400 and "Invalid Expo push token format" in r.text
    record("POST 'garbage' -> 400 invalid format", ok, f"status={r.status_code} body={r.text[:200]}")

    # 1f) Empty token - 400 missing
    r = session_user.post(f"{API}/users/push-token", json={"token": ""}, timeout=20)
    ok = r.status_code == 400 and "Missing token" in r.text
    record("POST empty token -> 400 missing", ok, f"status={r.status_code} body={r.text[:200]}")

    # ============================================================
    # TEST 2: DELETE /api/users/push-token
    # ============================================================
    print("\n--- DELETE /api/users/push-token ---")

    # 2a) Without auth - 401
    r = requests.delete(f"{API}/users/push-token", json={"token": valid_token_1}, timeout=20)
    record("DELETE push-token without auth -> 401", r.status_code == 401, f"got {r.status_code}")

    # 2b) Delete existing token - 200 {ok:true}
    r = session_user.delete(f"{API}/users/push-token", json={"token": valid_token_1}, timeout=20)
    ok = r.status_code == 200 and r.json().get("ok") is True
    record("DELETE existing token -> 200 {ok:true}", ok, f"status={r.status_code} body={r.text[:120]}")

    udoc = db.users.find_one({"_id": ObjectId(user_id)})
    tokens = (udoc or {}).get("push_tokens") or []
    record("Deleted token removed from array", valid_token_1 not in tokens, f"tokens={tokens}")

    # 2c) Delete same token again - 200 (idempotent)
    r = session_user.delete(f"{API}/users/push-token", json={"token": valid_token_1}, timeout=20)
    ok = r.status_code == 200 and r.json().get("ok") is True
    record("DELETE already-removed token -> 200 (idempotent)", ok, f"status={r.status_code} body={r.text[:120]}")

    # ============================================================
    # TEST 3: POST /api/bookings smoke test (push wired)
    # ============================================================
    print("\n--- POST /api/bookings smoke test ---")

    # Find a car
    car_doc = db.cars.find_one({"available": True})
    if not car_doc:
        record("Find a car for booking", False, "No available car in DB")
    else:
        car_id = str(car_doc["_id"])
        # Determine pickup location: use car's pickup_location if present, else default
        pickup_loc = car_doc.get("pickup_location") or {"name": "Punta Cana Airport", "address": "Punta Cana", "city": "Punta Cana"}
        dropoff_loc = car_doc.get("dropoff_location") or pickup_loc
        # Use a duration that satisfies min_booking_days (check location)
        loc_doc = db.locations.find_one({"name": pickup_loc.get("name")})
        min_days = (loc_doc or {}).get("min_booking_days", 1)
        days = max(7, min_days)  # generous
        pickup_dt = datetime.now(timezone.utc) + timedelta(days=3)
        dropoff_dt = pickup_dt + timedelta(days=days)
        payload = {
            "car_id": car_id,
            "pickup_date": pickup_dt.isoformat(),
            "dropoff_date": dropoff_dt.isoformat(),
            "pickup_location": pickup_loc,
            "dropoff_location": dropoff_loc,
            "payment_method": "cash",
        }

        # IMPORTANT: User has zero push_tokens now (we deleted valid_token_1 above and only valid_token_2 remains).
        # Actually valid_token_2 still exists. Test states "even when user has zero push tokens" - let's remove all first.
        db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"push_tokens": []}})

        r = session_user.post(f"{API}/bookings", json=payload, timeout=30)
        if r.status_code != 200:
            record("POST /api/bookings (cash, user with zero push tokens) -> 200", False, f"status={r.status_code} body={r.text[:300]}")
            booking = None
        else:
            booking = r.json()
            required_keys = {"id", "user_id", "car_id", "status", "payment_status", "total_price", "subtotal", "tax_amount"}
            missing = required_keys - set(booking.keys())
            shape_ok = (
                len(missing) == 0
                and booking["status"] == "pending_payment"
                and booking["payment_status"] == "pending"
                and booking["payment_method"] == "cash"
            )
            record(
                "POST /api/bookings (cash) -> 200 with correct shape",
                shape_ok,
                f"status={booking.get('status')} pay={booking.get('payment_status')} missing={missing}",
            )

        # ============================================================
        # TEST 4: PUT /api/admin/bookings/{id}/status smoke test
        # ============================================================
        print("\n--- PUT /api/admin/bookings/{id}/status smoke test ---")
        if booking:
            bid = booking["id"]
            r = session_admin.put(
                f"{API}/admin/bookings/{bid}/status",
                json={"status": "confirmed", "payment_status": "paid"},
                timeout=20,
            )
            if r.status_code != 200:
                record("PUT admin status update -> 200", False, f"status={r.status_code} body={r.text[:300]}")
            else:
                upd = r.json()
                ok = (
                    upd.get("id") == bid
                    and upd.get("status") == "confirmed"
                    and upd.get("payment_status") == "paid"
                )
                record(
                    "PUT admin status update -> 200 (booking returned & push doesn't block)",
                    ok,
                    f"status={upd.get('status')} pay={upd.get('payment_status')}",
                )

    # ============================================================
    # Cleanup test user
    # ============================================================
    print("\n--- Cleanup ---")
    try:
        # Delete bookings for test user
        db.bookings.delete_many({"user_id": user_id})
        db.users.delete_one({"_id": ObjectId(user_id)})
        print(f"Cleaned up test user {user_id}")
    except Exception as e:
        print(f"Cleanup error (non-fatal): {e}")

    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "=" * 60)
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"RESULT: {passed}/{total} assertions passed")
    print("=" * 60)
    failed = [(n, d) for n, p, d in results if not p]
    if failed:
        print("FAILED:")
        for n, d in failed:
            print(f"  - {n}: {d}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
