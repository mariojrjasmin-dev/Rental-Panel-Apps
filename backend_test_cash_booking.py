"""
Backend tests for "Cash booking pending status" feature.

Verifies:
1) POST /api/bookings with payment_method=cash -> status=pending_payment, payment_status=pending
   - persisted in DB (verified via GET /api/bookings/{id})
2) POST /api/bookings with payment_method=stripe -> status=pending_payment, payment_status=pending
3) PUT /api/admin/bookings/{id}/status
   - Backward compat: only {status: "confirmed"} -> 200, only status updated
   - Only {payment_status: "paid"} -> 200, only payment_status updated
   - Both fields -> both updated
   - Invalid payment_status -> 400 with helpful error
   - Empty body {} -> 400 "No fields to update"
   - Non-admin -> 403
   - Non-existent booking id -> 404
4) End-to-end cash flow.
"""

import os
import sys
import uuid
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = "https://rental-routes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

session_admin = requests.Session()
session_user = requests.Session()
session_other = requests.Session()

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
    assert data.get("role") == "admin"
    return data


def register_user(session, label):
    suffix = uuid.uuid4().hex[:8]
    email = f"customer_{label}_{suffix}@damstest.com"
    r = session.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": "TestPass!23", "name": f"Carlos {label.title()} {suffix[:4]}"},
        timeout=15,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return r.json(), email


def get_available_car():
    """Get any available car to book."""
    r = requests.get(f"{BASE_URL}/cars", timeout=15)
    assert r.status_code == 200
    cars = r.json()
    assert len(cars) > 0, "no cars available to test booking with"
    return cars[0]


def make_booking(session, car, payment_method):
    pickup_dt = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%dT10:00:00")
    dropoff_dt = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%dT10:00:00")
    pickup_loc = car.get("pickup_location") or {"name": "Punta Cana Airport", "lat": 18.567, "lng": -68.3634, "address": "Punta Cana"}
    dropoff_loc = car.get("dropoff_location") or pickup_loc
    payload = {
        "car_id": car["id"],
        "pickup_date": pickup_dt,
        "dropoff_date": dropoff_dt,
        "pickup_location": pickup_loc,
        "dropoff_location": dropoff_loc,
        "payment_method": payment_method,
    }
    r = session.post(f"{BASE_URL}/bookings", json=payload, timeout=15)
    return r


def main():
    # Setup
    login_admin()
    user, user_email = register_user(session_user, "primary")
    other_user, other_email = register_user(session_other, "other")
    car = get_available_car()
    print(f"[info] Using car: {car.get('name')} (id={car['id']})")

    # ============================
    # 1) Cash booking starts as pending
    # ============================
    r = make_booking(session_user, car, "cash")
    if r.status_code != 200:
        record("Create cash booking returns 200", False, f"got {r.status_code}: {r.text[:200]}")
        return
    cash_booking = r.json()
    record("Create cash booking returns 200", True)
    record(
        "Cash booking response status == 'pending_payment'",
        cash_booking.get("status") == "pending_payment",
        f"got {cash_booking.get('status')!r}",
    )
    record(
        "Cash booking response payment_status == 'pending'",
        cash_booking.get("payment_status") == "pending",
        f"got {cash_booking.get('payment_status')!r}",
    )
    cash_booking_id = cash_booking.get("id")

    # Verify persisted via GET /api/bookings/{id}
    r = session_user.get(f"{BASE_URL}/bookings/{cash_booking_id}", timeout=15)
    if r.status_code == 200:
        persisted = r.json()
        record(
            "GET cash booking persisted status=='pending_payment'",
            persisted.get("status") == "pending_payment",
            f"got {persisted.get('status')!r}",
        )
        record(
            "GET cash booking persisted payment_status=='pending'",
            persisted.get("payment_status") == "pending",
            f"got {persisted.get('payment_status')!r}",
        )
    else:
        record("GET cash booking 200", False, f"got {r.status_code}: {r.text[:200]}")

    # ============================
    # 2) Stripe booking starts as pending
    # ============================
    r = make_booking(session_user, car, "stripe")
    if r.status_code != 200:
        record("Create stripe booking returns 200", False, f"got {r.status_code}: {r.text[:200]}")
    else:
        stripe_booking = r.json()
        record("Create stripe booking returns 200", True)
        record(
            "Stripe booking response status == 'pending_payment'",
            stripe_booking.get("status") == "pending_payment",
            f"got {stripe_booking.get('status')!r}",
        )
        record(
            "Stripe booking response payment_status == 'pending'",
            stripe_booking.get("payment_status") == "pending",
            f"got {stripe_booking.get('payment_status')!r}",
        )

    # ============================
    # 3) PUT /api/admin/bookings/{id}/status
    # ============================
    # Create a fresh booking for these tests so updates don't pollute the e2e check
    r = make_booking(session_user, car, "cash")
    assert r.status_code == 200
    bkid = r.json()["id"]

    # 3a) Backward compat: only status
    r = session_admin.put(
        f"{BASE_URL}/admin/bookings/{bkid}/status",
        json={"status": "confirmed"},
        timeout=15,
    )
    if r.status_code == 200:
        body = r.json()
        record("PUT admin status with only {status:'confirmed'} -> 200", True)
        record(
            "Only-status update: status becomes 'confirmed'",
            body.get("status") == "confirmed",
            f"got {body.get('status')!r}",
        )
        record(
            "Only-status update: payment_status unchanged ('pending')",
            body.get("payment_status") == "pending",
            f"got {body.get('payment_status')!r}",
        )
    else:
        record("PUT admin status with only {status:'confirmed'} -> 200", False, f"got {r.status_code}: {r.text[:200]}")

    # 3b) Only payment_status
    r = session_admin.put(
        f"{BASE_URL}/admin/bookings/{bkid}/status",
        json={"payment_status": "paid"},
        timeout=15,
    )
    if r.status_code == 200:
        body = r.json()
        record("PUT admin status with only {payment_status:'paid'} -> 200", True)
        record(
            "Only-payment_status update: payment_status becomes 'paid'",
            body.get("payment_status") == "paid",
            f"got {body.get('payment_status')!r}",
        )
        record(
            "Only-payment_status update: status unchanged ('confirmed')",
            body.get("status") == "confirmed",
            f"got {body.get('status')!r}",
        )
    else:
        record("PUT admin status with only {payment_status:'paid'} -> 200", False, f"got {r.status_code}: {r.text[:200]}")

    # 3c) Both fields - need fresh booking
    r = make_booking(session_user, car, "cash")
    assert r.status_code == 200
    bkid2 = r.json()["id"]
    r = session_admin.put(
        f"{BASE_URL}/admin/bookings/{bkid2}/status",
        json={"status": "confirmed", "payment_status": "paid"},
        timeout=15,
    )
    if r.status_code == 200:
        body = r.json()
        record("PUT admin status with both fields -> 200", True)
        record(
            "Both-fields update: status='confirmed'",
            body.get("status") == "confirmed",
            f"got {body.get('status')!r}",
        )
        record(
            "Both-fields update: payment_status='paid'",
            body.get("payment_status") == "paid",
            f"got {body.get('payment_status')!r}",
        )
    else:
        record("PUT admin status with both fields -> 200", False, f"got {r.status_code}: {r.text[:200]}")

    # 3d) Invalid payment_status -> 400 with valid values listed
    r = session_admin.put(
        f"{BASE_URL}/admin/bookings/{bkid2}/status",
        json={"payment_status": "invalid_value"},
        timeout=15,
    )
    if r.status_code == 400:
        detail = (r.json().get("detail") or "").lower()
        record("Invalid payment_status -> 400", True)
        has_all = all(v in detail for v in ["pending", "paid", "refunded", "failed"])
        record(
            "Invalid payment_status error lists valid values",
            has_all,
            f"detail={detail!r}",
        )
    else:
        record("Invalid payment_status -> 400", False, f"got {r.status_code}: {r.text[:200]}")

    # 3e) Empty body -> 400 "No fields to update"
    r = session_admin.put(
        f"{BASE_URL}/admin/bookings/{bkid2}/status",
        json={},
        timeout=15,
    )
    if r.status_code == 400:
        detail = (r.json().get("detail") or "").lower()
        record("Empty body -> 400", True)
        record(
            "Empty body error contains 'no fields to update'",
            "no fields" in detail,
            f"detail={detail!r}",
        )
    else:
        record("Empty body -> 400", False, f"got {r.status_code}: {r.text[:200]}")

    # 3f) Non-admin -> 403
    r = session_other.put(
        f"{BASE_URL}/admin/bookings/{bkid2}/status",
        json={"status": "cancelled"},
        timeout=15,
    )
    record(
        "Non-admin user PUT admin status -> 403",
        r.status_code == 403,
        f"got {r.status_code}: {r.text[:200]}",
    )

    # 3g) Non-existent booking id -> 404 (use valid ObjectId format)
    fake_id = "000000000000000000000000"
    r = session_admin.put(
        f"{BASE_URL}/admin/bookings/{fake_id}/status",
        json={"status": "confirmed"},
        timeout=15,
    )
    record(
        "Non-existent booking id -> 404",
        r.status_code == 404,
        f"got {r.status_code}: {r.text[:200]}",
    )

    # ============================
    # 4) End-to-end cash flow
    # ============================
    r = make_booking(session_user, car, "cash")
    assert r.status_code == 200
    e2e = r.json()
    e2e_id = e2e["id"]
    e2e_ok = (e2e.get("status") == "pending_payment" and e2e.get("payment_status") == "pending")
    record("E2E step1: cash booking created pending", e2e_ok, f"status={e2e.get('status')!r}, payment_status={e2e.get('payment_status')!r}")

    r = session_admin.put(
        f"{BASE_URL}/admin/bookings/{e2e_id}/status",
        json={"status": "confirmed", "payment_status": "paid"},
        timeout=15,
    )
    record("E2E step2: admin updates to confirmed+paid -> 200", r.status_code == 200, f"got {r.status_code}")

    r = session_user.get(f"{BASE_URL}/bookings/{e2e_id}", timeout=15)
    if r.status_code == 200:
        final = r.json()
        record(
            "E2E step3: GET reflects status='confirmed'",
            final.get("status") == "confirmed",
            f"got {final.get('status')!r}",
        )
        record(
            "E2E step3: GET reflects payment_status='paid'",
            final.get("payment_status") == "paid",
            f"got {final.get('payment_status')!r}",
        )
    else:
        record("E2E step3: GET booking -> 200", False, f"got {r.status_code}: {r.text[:200]}")

    # Summary
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [r for r in results if not r[1]]
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed")
    if failed:
        print("FAILURES:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
    print("=" * 60)
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
