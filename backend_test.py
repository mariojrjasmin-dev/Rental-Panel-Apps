"""
Backend tests for DAMS Car Rental - Booking Management and Receipt endpoints.

Tests:
1) GET /api/admin/bookings (admin-only) with filters status/q
2) PUT /api/admin/bookings/{id}/status (admin-only)
3) GET /api/bookings/{id}/receipt.pdf (authenticated, owner or admin)
"""
import os
import sys
import uuid
import json
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = "https://rental-routes.preview.emergentagent.com/api"

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

results = []


def log(ok, name, detail=""):
    results.append((ok, name, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" :: {detail}" if detail else ""))


def login(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["token"], data


def register(name, email, password):
    r = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password, "name": name}, timeout=30)
    if r.status_code == 400 and "already" in r.text.lower():
        # Already exists, login instead
        return login(email, password)
    r.raise_for_status()
    data = r.json()
    return data["token"], data


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_booking(token, car_id, pickup_loc, dropoff_loc):
    pickup = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    dropoff = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    body = {
        "car_id": car_id,
        "pickup_date": pickup,
        "dropoff_date": dropoff,
        "pickup_location": pickup_loc,
        "dropoff_location": dropoff_loc,
        "payment_method": "cash",
    }
    r = requests.post(f"{BASE_URL}/bookings", json=body, headers=auth_headers(token), timeout=30)
    return r


def main():
    print(f"Testing against: {BASE_URL}")

    # 1. Admin login
    try:
        admin_token, admin_user = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        log(admin_user.get("role") == "admin", "Admin login", f"role={admin_user.get('role')}")
    except Exception as e:
        log(False, "Admin login", str(e))
        return

    # 2. Regular user 1 (owner of new booking)
    u1_email = f"diana.ramos+{uuid.uuid4().hex[:8]}@example.com"
    u1_token, u1 = register("Diana Ramos", u1_email, "Passw0rd!Secure")
    log(True, "Register regular user 1", u1_email)

    # 3. Regular user 2 (non-owner)
    u2_email = f"marco.silva+{uuid.uuid4().hex[:8]}@example.com"
    u2_token, u2 = register("Marco Silva", u2_email, "Passw0rd!Secure")
    log(True, "Register regular user 2", u2_email)

    # 4. Get a car to book
    r = requests.get(f"{BASE_URL}/cars", timeout=30)
    cars = r.json()
    if not cars:
        log(False, "Fetch cars for booking", "No cars available")
        return
    car = cars[0]
    car_id = car["id"]
    pickup_loc = car.get("pickup_location") or {"name": "Punta Cana Airport"}
    dropoff_loc = car.get("dropoff_location") or {"name": "Bavaro Beach Hub"}
    log(True, "Fetch cars for booking", f"car_id={car_id}, name={car.get('name')}")

    # 5. User 1 creates a fresh booking
    r = create_booking(u1_token, car_id, pickup_loc, dropoff_loc)
    if r.status_code != 200:
        log(False, "User 1 creates booking", f"{r.status_code} {r.text}")
        return
    new_booking = r.json()
    booking_id = new_booking["id"]
    log(True, "User 1 creates booking", f"id={booking_id}, status={new_booking.get('status')}")

    # ============================================================
    # TEST 1: GET /api/admin/bookings
    # ============================================================
    print("\n--- GET /api/admin/bookings ---")

    # 1a. Admin: list all bookings
    r = requests.get(f"{BASE_URL}/admin/bookings", headers=auth_headers(admin_token), timeout=30)
    if r.status_code == 200 and isinstance(r.json(), list):
        log(True, "Admin list bookings (no filter)", f"count={len(r.json())}")
        assert any(b["id"] == booking_id for b in r.json()), "New booking should be in list"
    else:
        log(False, "Admin list bookings (no filter)", f"{r.status_code} {r.text[:200]}")

    # 1b. Non-admin: should get 403
    r = requests.get(f"{BASE_URL}/admin/bookings", headers=auth_headers(u1_token), timeout=30)
    log(r.status_code == 403, "Non-admin GET /admin/bookings returns 403", f"status={r.status_code}")

    # 1c. Unauthenticated: should get 401
    r = requests.get(f"{BASE_URL}/admin/bookings", timeout=30)
    log(r.status_code == 401, "Unauthenticated GET /admin/bookings returns 401", f"status={r.status_code}")

    # 1d. Status filter: ?status=confirmed (cash bookings are confirmed)
    r = requests.get(f"{BASE_URL}/admin/bookings?status=confirmed", headers=auth_headers(admin_token), timeout=30)
    if r.status_code == 200:
        items = r.json()
        all_confirmed = all(b.get("status") == "confirmed" for b in items)
        log(all_confirmed, "Status filter ?status=confirmed", f"count={len(items)}, all_confirmed={all_confirmed}")
    else:
        log(False, "Status filter ?status=confirmed", f"{r.status_code}")

    # 1e. Search filter ?q=<text> by user email
    # Take part of the u1 email local-part
    q_term = u1_email.split("@")[0][:10]
    r = requests.get(f"{BASE_URL}/admin/bookings?q={q_term}", headers=auth_headers(admin_token), timeout=30)
    if r.status_code == 200:
        items = r.json()
        matches = [b for b in items if q_term in (b.get("user_email", "") or "").lower() or q_term in (b.get("user_name", "") or "").lower() or q_term in (b.get("car_name", "") or "").lower()]
        log(len(items) >= 1 and len(matches) == len(items), "Search filter ?q=<email fragment>", f"count={len(items)}")
    else:
        log(False, "Search filter ?q=<email fragment>", f"{r.status_code}")

    # 1f. Combined filter
    r = requests.get(f"{BASE_URL}/admin/bookings?status=confirmed&q={q_term}", headers=auth_headers(admin_token), timeout=30)
    if r.status_code == 200:
        items = r.json()
        ok = all(b.get("status") == "confirmed" for b in items)
        log(ok, "Combined ?status=confirmed&q=...", f"count={len(items)}")
    else:
        log(False, "Combined ?status=confirmed&q=...", f"{r.status_code}")

    # ============================================================
    # TEST 2: PUT /api/admin/bookings/{id}/status
    # ============================================================
    print("\n--- PUT /api/admin/bookings/{id}/status ---")

    # 2a. Non-admin: 403
    r = requests.put(f"{BASE_URL}/admin/bookings/{booking_id}/status", json={"status": "active"}, headers=auth_headers(u1_token), timeout=30)
    log(r.status_code == 403, "Non-admin update booking status returns 403", f"status={r.status_code}")

    # 2b. Invalid status: 400
    r = requests.put(f"{BASE_URL}/admin/bookings/{booking_id}/status", json={"status": "foo"}, headers=auth_headers(admin_token), timeout=30)
    log(r.status_code == 400, "Invalid status returns 400", f"status={r.status_code} body={r.text[:120]}")

    # 2c. Non-existent booking: 404
    fake_id = "000000000000000000000000"
    r = requests.put(f"{BASE_URL}/admin/bookings/{fake_id}/status", json={"status": "confirmed"}, headers=auth_headers(admin_token), timeout=30)
    log(r.status_code == 404, "Non-existent booking returns 404", f"status={r.status_code}")

    # 2d. Valid update: change to "active"
    r = requests.put(f"{BASE_URL}/admin/bookings/{booking_id}/status", json={"status": "active"}, headers=auth_headers(admin_token), timeout=30)
    if r.status_code == 200:
        body = r.json()
        log(body.get("status") == "active", "Admin valid status update to 'active'", f"new_status={body.get('status')}")
    else:
        log(False, "Admin valid status update to 'active'", f"{r.status_code} {r.text[:200]}")

    # 2e. Verify persistence via GET
    r = requests.get(f"{BASE_URL}/bookings/{booking_id}", headers=auth_headers(u1_token), timeout=30)
    if r.status_code == 200:
        log(r.json().get("status") == "active", "Status change persisted (GET booking)", f"status={r.json().get('status')}")
    else:
        log(False, "Status change persisted (GET booking)", f"{r.status_code}")

    # 2f. Change to completed
    r = requests.put(f"{BASE_URL}/admin/bookings/{booking_id}/status", json={"status": "completed"}, headers=auth_headers(admin_token), timeout=30)
    log(r.status_code == 200 and r.json().get("status") == "completed", "Update status to 'completed'", f"status={r.status_code}")

    # ============================================================
    # TEST 3: GET /api/bookings/{id}/receipt.pdf
    # ============================================================
    print("\n--- GET /api/bookings/{id}/receipt.pdf ---")

    # 3a. Owner gets PDF
    r = requests.get(f"{BASE_URL}/bookings/{booking_id}/receipt.pdf", headers=auth_headers(u1_token), timeout=30)
    ok = (r.status_code == 200
          and r.headers.get("content-type", "").startswith("application/pdf")
          and r.content[:5] == b"%PDF-")
    log(ok, "Owner downloads receipt PDF", f"status={r.status_code}, ct={r.headers.get('content-type')}, bytes={len(r.content)}, starts={r.content[:8]!r}")

    # 3b. Admin gets PDF for any booking
    r = requests.get(f"{BASE_URL}/bookings/{booking_id}/receipt.pdf", headers=auth_headers(admin_token), timeout=30)
    ok = (r.status_code == 200
          and r.headers.get("content-type", "").startswith("application/pdf")
          and r.content[:5] == b"%PDF-")
    log(ok, "Admin downloads receipt PDF", f"status={r.status_code}, bytes={len(r.content)}")

    # 3c. Non-owner, non-admin user: 403
    r = requests.get(f"{BASE_URL}/bookings/{booking_id}/receipt.pdf", headers=auth_headers(u2_token), timeout=30)
    log(r.status_code == 403, "Non-owner user gets 403 on receipt", f"status={r.status_code}")

    # 3d. Unauthenticated: 401
    r = requests.get(f"{BASE_URL}/bookings/{booking_id}/receipt.pdf", timeout=30)
    log(r.status_code == 401, "Unauthenticated gets 401 on receipt", f"status={r.status_code}")

    # 3e. Invalid booking_id (non-existent): should be 404 or 400
    fake_id = "000000000000000000000000"
    r = requests.get(f"{BASE_URL}/bookings/{fake_id}/receipt.pdf", headers=auth_headers(admin_token), timeout=30)
    log(r.status_code in (400, 404), "Non-existent booking receipt returns 404/400", f"status={r.status_code}")

    # 3f. Malformed booking id (not 24-hex)
    r = requests.get(f"{BASE_URL}/bookings/not-a-real-id/receipt.pdf", headers=auth_headers(admin_token), timeout=30)
    log(r.status_code in (400, 404, 422, 500), "Malformed booking id returns error", f"status={r.status_code}")

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r[0])
    failed = sum(1 for r in results if not r[0])
    print(f"TOTAL: {len(results)}  PASS: {passed}  FAIL: {failed}")
    if failed:
        print("\nFailures:")
        for ok, name, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
