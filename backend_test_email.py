"""Test SMTP2GO email integration:
1. POST /api/admin/email/test (admin)
2. Booking creation email trigger smoke test
3. Admin status update email trigger smoke test
"""
import os
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
    print("== Test 1: POST /api/admin/email/test ==")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    H_admin = {"Authorization": f"Bearer {admin_token}"}

    # Valid recipient
    r = requests.post(f"{BASE}/admin/email/test", json={"to": "info@damsrentacar.com"}, headers=H_admin, timeout=30)
    print(f"  Valid recipient -> {r.status_code}: {r.text[:200]}")
    check(r.status_code == 200, "Valid email returns 200")
    try:
        j = r.json()
        check(j.get("ok") is True, "Response body has ok:true")
    except Exception:
        check(False, "Response is JSON")

    # Empty email
    r = requests.post(f"{BASE}/admin/email/test", json={"to": ""}, headers=H_admin, timeout=20)
    print(f"  Empty email -> {r.status_code}: {r.text[:200]}")
    check(r.status_code == 400, "Empty email returns 400")

    # Invalid email
    r = requests.post(f"{BASE}/admin/email/test", json={"to": "not-an-email"}, headers=H_admin, timeout=20)
    print(f"  Invalid email -> {r.status_code}: {r.text[:200]}")
    check(r.status_code == 400, "Invalid email returns 400")
    try:
        check("Invalid recipient email" in r.json().get("detail", ""), "Detail mentions 'Invalid recipient email'")
    except Exception:
        check(False, "Detail is parseable")

    # No auth
    r = requests.post(f"{BASE}/admin/email/test", json={"to": "info@damsrentacar.com"}, timeout=20)
    print(f"  No auth -> {r.status_code}")
    check(r.status_code == 401, "No auth returns 401")

    # Create a non-admin user and try
    ts = int(time.time())
    cust_email = f"customer_email_test_{ts}@example.com"
    cust_pw = "TestPwd!2025"
    r = requests.post(f"{BASE}/auth/register", json={
        "email": cust_email, "password": cust_pw, "name": "Carlos Rodriguez"
    }, timeout=20)
    if r.status_code != 200:
        print(f"  Register failed: {r.status_code} {r.text[:200]}")
        sys.exit(1)
    cust_token = r.json()["token"]
    H_cust = {"Authorization": f"Bearer {cust_token}"}

    r = requests.post(f"{BASE}/admin/email/test", json={"to": "info@damsrentacar.com"}, headers=H_cust, timeout=20)
    print(f"  Non-admin -> {r.status_code}")
    check(r.status_code == 403, "Non-admin returns 403")

    print("\n== Test 2: Booking creation email trigger smoke test ==")
    # Find a car
    r = requests.get(f"{BASE}/cars", timeout=20)
    r.raise_for_status()
    cars = r.json()
    if not cars:
        print("  No cars available!")
        sys.exit(1)
    car = cars[0]
    car_id = car["id"]
    print(f"  Using car {car_id} - {car.get('name')}")

    # Pickup/dropoff locations
    pickup_loc = car.get("pickup_location") or {"name": "Punta Cana Airport", "address": "Punta Cana", "city": "Punta Cana", "country": "DR"}
    drop_loc = car.get("dropoff_location") or pickup_loc

    booking_payload = {
        "car_id": car_id,
        "pickup_date": "2026-08-01T10:00:00",
        "dropoff_date": "2026-08-10T10:00:00",
        "pickup_location": pickup_loc,
        "dropoff_location": drop_loc,
        "payment_method": "cash"
    }
    t0 = time.time()
    r = requests.post(f"{BASE}/bookings", json=booking_payload, headers=H_cust, timeout=30)
    elapsed = time.time() - t0
    print(f"  Booking creation -> {r.status_code} in {elapsed:.2f}s")
    check(r.status_code == 200, "Booking creation returns 200")
    check(elapsed < 20, f"Booking creation not blocked excessively (took {elapsed:.2f}s)")
    booking = r.json() if r.status_code == 200 else {}
    booking_id = booking.get("id")
    check(bool(booking_id), "Booking has id")
    check(booking.get("status") == "pending_payment", f"Status is pending_payment (got {booking.get('status')})")
    check(booking.get("payment_status") == "pending", f"Payment status pending (got {booking.get('payment_status')})")

    # Verify persisted
    if booking_id:
        r = requests.get(f"{BASE}/bookings/{booking_id}", headers=H_cust, timeout=20)
        check(r.status_code == 200, "Persisted booking is retrievable")

    print("\n== Test 3: Admin status update email trigger smoke test ==")
    if booking_id:
        t0 = time.time()
        r = requests.put(
            f"{BASE}/admin/bookings/{booking_id}/status",
            json={"status": "confirmed", "payment_status": "paid"},
            headers=H_admin, timeout=30,
        )
        elapsed = time.time() - t0
        print(f"  Status update -> {r.status_code} in {elapsed:.2f}s")
        check(r.status_code == 200, "Status update returns 200")
        check(elapsed < 20, f"Status update not blocked (took {elapsed:.2f}s)")
        if r.status_code == 200:
            updated = r.json()
            check(updated.get("status") == "confirmed", f"Status confirmed (got {updated.get('status')})")
            check(updated.get("payment_status") == "paid", f"Payment paid (got {updated.get('payment_status')})")

    print(f"\n\n=== Results: {passed} passed, {failed} failed ===")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
