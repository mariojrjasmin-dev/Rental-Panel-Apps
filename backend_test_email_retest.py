"""Retest after fix for serialize_booking double-mutation bug.

Goal:
1) End-to-end booking status update flow (cash booking -> confirmed+paid -> active -> completed -> cancelled).
2) Email test endpoint sanity recheck.
"""
import sys
import time
import requests

BASE = "https://rental-routes.preview.emergentagent.com/api"

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

passed = 0
failed = 0
failures = []


def check(cond, label):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        failures.append(label)
        print(f"  FAIL {label}")


def login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


def main():
    print("== Login admin ==")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    H_admin = {"Authorization": f"Bearer {admin_token}"}

    print("\n== Test 1: Email test endpoint sanity recheck ==")
    r = requests.post(f"{BASE}/admin/email/test", json={"to": "info@damsrentacar.com"}, headers=H_admin, timeout=30)
    print(f"  Valid -> {r.status_code}: {r.text[:200]}")
    check(r.status_code == 200, "Email test valid -> 200")
    try:
        check(r.json().get("ok") is True, "Email test returns ok:true")
    except Exception:
        check(False, "Email test JSON parse")

    r = requests.post(f"{BASE}/admin/email/test", json={"to": "not-an-email"}, headers=H_admin, timeout=20)
    print(f"  Invalid -> {r.status_code}")
    check(r.status_code == 400, "Email test invalid -> 400")

    r = requests.post(f"{BASE}/admin/email/test", json={"to": "info@damsrentacar.com"}, timeout=20)
    print(f"  No auth -> {r.status_code}")
    check(r.status_code == 401, "Email test no auth -> 401")

    # Register customer
    ts = int(time.time())
    cust_email = f"maria_garcia_{ts}@example.com"
    cust_pw = "TestPwd!2025"
    r = requests.post(f"{BASE}/auth/register", json={
        "email": cust_email, "password": cust_pw, "name": "Maria Garcia"
    }, timeout=20)
    if r.status_code != 200:
        print(f"  Register failed: {r.status_code} {r.text}")
        sys.exit(1)
    cust_token = r.json()["token"]
    H_cust = {"Authorization": f"Bearer {cust_token}"}

    r = requests.post(f"{BASE}/admin/email/test", json={"to": "info@damsrentacar.com"}, headers=H_cust, timeout=20)
    print(f"  Non-admin -> {r.status_code}")
    check(r.status_code == 403, "Email test non-admin -> 403")

    print("\n== Test 2: Create cash booking ==")
    r = requests.get(f"{BASE}/cars", timeout=20)
    r.raise_for_status()
    cars = r.json()
    if not cars:
        print("  No cars!")
        sys.exit(1)
    car = cars[0]
    car_id = car["id"]
    print(f"  Using car {car_id} - {car.get('name')}")
    pickup_loc = car.get("pickup_location") or {"name": "Punta Cana Airport", "address": "Punta Cana", "city": "Punta Cana", "country": "DR"}
    drop_loc = car.get("dropoff_location") or pickup_loc

    booking_payload = {
        "car_id": car_id,
        "pickup_date": "2026-09-01T10:00:00",
        "dropoff_date": "2026-09-12T10:00:00",
        "pickup_location": pickup_loc,
        "dropoff_location": drop_loc,
        "payment_method": "cash"
    }
    r = requests.post(f"{BASE}/bookings", json=booking_payload, headers=H_cust, timeout=30)
    print(f"  Create -> {r.status_code}: {r.text[:300]}")
    check(r.status_code == 200, "Create booking -> 200")
    booking = r.json() if r.status_code == 200 else {}
    booking_id = booking.get("id")
    check(bool(booking_id), "Booking has id")
    check(booking.get("status") == "pending_payment", "Initial status pending_payment")
    check(booking.get("payment_status") == "pending", "Initial payment pending")

    if not booking_id:
        print("Aborting — no booking_id")
        sys.exit(1)

    print("\n== Test 3a: Status update -> confirmed + paid (was the regression) ==")
    r = requests.put(
        f"{BASE}/admin/bookings/{booking_id}/status",
        json={"status": "confirmed", "payment_status": "paid"},
        headers=H_admin, timeout=30
    )
    print(f"  -> {r.status_code}: {r.text[:300]}")
    check(r.status_code == 200, "Confirmed+paid update -> 200 (NOT 500)")
    if r.status_code == 200:
        u = r.json()
        check(u.get("status") == "confirmed", f"Status=confirmed (got {u.get('status')})")
        check(u.get("payment_status") == "paid", f"Payment=paid (got {u.get('payment_status')})")
        check("id" in u and u["id"] == booking_id, "Response has correct id")
        check("_id" not in u, "Response does NOT contain _id (proper serialization)")
        check(bool(u.get("user_email")), "Response has user_email")
        check(bool(u.get("car_name")), "Response has car_name")
        check(u.get("user_email") == cust_email, "user_email matches customer")

    print("\n== Test 3b: Status update -> active ==")
    r = requests.put(
        f"{BASE}/admin/bookings/{booking_id}/status",
        json={"status": "active"},
        headers=H_admin, timeout=30
    )
    print(f"  -> {r.status_code}: {r.text[:300]}")
    check(r.status_code == 200, "Active update -> 200")
    if r.status_code == 200:
        u = r.json()
        check(u.get("status") == "active", f"Status=active (got {u.get('status')})")
        check("id" in u and "_id" not in u, "Proper id serialization on active update")

    print("\n== Test 3c: Status update -> completed ==")
    r = requests.put(
        f"{BASE}/admin/bookings/{booking_id}/status",
        json={"status": "completed"},
        headers=H_admin, timeout=30
    )
    print(f"  -> {r.status_code}: {r.text[:300]}")
    check(r.status_code == 200, "Completed update -> 200")
    if r.status_code == 200:
        u = r.json()
        check(u.get("status") == "completed", f"Status=completed (got {u.get('status')})")
        check("id" in u and "_id" not in u, "Proper id serialization on completed update")

    print("\n== Test 3d: Status update -> cancelled ==")
    r = requests.put(
        f"{BASE}/admin/bookings/{booking_id}/status",
        json={"status": "cancelled"},
        headers=H_admin, timeout=30
    )
    print(f"  -> {r.status_code}: {r.text[:300]}")
    check(r.status_code == 200, "Cancelled update -> 200")
    if r.status_code == 200:
        u = r.json()
        check(u.get("status") == "cancelled", f"Status=cancelled (got {u.get('status')})")
        check("id" in u and "_id" not in u, "Proper id serialization on cancelled update")

    # Persistence cross-check
    r = requests.get(f"{BASE}/bookings/{booking_id}", headers=H_cust, timeout=20)
    if r.status_code == 200:
        gb = r.json()
        check(gb.get("status") == "cancelled", "GET shows final status=cancelled")
        check(gb.get("payment_status") == "paid", "GET shows payment_status=paid (unchanged)")

    print(f"\n\n=== Results: {passed} passed, {failed} failed ===")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
