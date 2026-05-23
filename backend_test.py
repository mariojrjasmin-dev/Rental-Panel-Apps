"""Tests for POST /api/admin/backfill-booking-taxes optimized endpoint."""
import os
import sys
import time
import requests
from bson import ObjectId
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path('/app/backend/.env'))

BASE = "http://localhost:8001/api"
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

results = []  # (name, ok, detail)


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}{(' - ' + detail) if detail else ''}")


def admin_token():
    r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def register_customer():
    suffix = int(time.time() * 1000) % 10_000_000
    email = f"backfill.cust.{suffix}@example.com"
    r = requests.post(
        f"{BASE}/auth/register",
        json={
            "name": "Backfill Tester",
            "email": email,
            "password": "Customer@123",
            "phone": "+18095551234",
            "terms_accepted": True,
        },
        timeout=10,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return r.json()["token"], email


def main():
    mc = MongoClient(MONGO_URL)
    db = mc[DB_NAME]

    # Defensive: clean any leftover test markers from previous failed runs
    db.bookings.delete_many({"_test_marker": True})

    loc = db.locations.find_one({"tax_rate": {"$gt": 0}})
    if not loc:
        loc = db.locations.find_one({})
        if loc:
            db.locations.update_one({"_id": loc["_id"]}, {"$set": {"tax_rate": 18.0}})
            loc = db.locations.find_one({"_id": loc["_id"]})
    assert loc is not None, "No location available in DB to test against"
    loc_name = loc["name"]
    loc_tax_rate = float(loc.get("tax_rate") or 0.0)
    print(f"Using location: '{loc_name}' tax_rate={loc_tax_rate}")

    # === (1) AUTH ===
    r_unauth = requests.post(f"{BASE}/admin/backfill-booking-taxes", timeout=10)
    check("AUTH: unauth → 401", r_unauth.status_code == 401, f"got {r_unauth.status_code}")

    cust_token, cust_email = register_customer()
    r_nonadmin = requests.post(
        f"{BASE}/admin/backfill-booking-taxes",
        headers={"Authorization": f"Bearer {cust_token}"},
        timeout=10,
    )
    check("AUTH: non-admin → 403", r_nonadmin.status_code == 403, f"got {r_nonadmin.status_code}")

    tok = admin_token()
    hdrs = {"Authorization": f"Bearer {tok}"}

    r_admin = requests.post(f"{BASE}/admin/backfill-booking-taxes", headers=hdrs, timeout=30)
    check("AUTH: admin → 200", r_admin.status_code == 200, f"got {r_admin.status_code} body={r_admin.text[:200]}")

    # === (2) FUNCTIONAL CORRECTNESS — seed 3 incomplete bookings ===
    totals = [100.0, 250.0, 500.0]
    seeded_ids = []
    for t in totals:
        doc = {
            "user_id": "test-user",
            "user_email": cust_email,
            "user_name": "Backfill Test",
            "car_id": "test-car",
            "car_name": "Test Car",
            "pickup_location": {"name": loc_name, "lat": 0.0, "lng": 0.0},
            "dropoff_location": {"name": loc_name, "lat": 0.0, "lng": 0.0},
            "pickup_date": datetime.now(timezone.utc),
            "dropoff_date": datetime.now(timezone.utc),
            "total_price": t,
            "status": "completed",
            "payment_status": "paid",
            "payment_method": "cash",
            "created_at": datetime.now(timezone.utc),
            "_test_marker": True,
        }
        ins = db.bookings.insert_one(doc)
        seeded_ids.append(ins.inserted_id)

    already_ok_doc = {
        "user_id": "test-user",
        "user_email": cust_email,
        "user_name": "Backfill Test",
        "car_id": "test-car",
        "car_name": "Test Car",
        "pickup_location": {"name": loc_name},
        "dropoff_location": {"name": loc_name},
        "pickup_date": datetime.now(timezone.utc),
        "dropoff_date": datetime.now(timezone.utc),
        "total_price": 999.0,
        "subtotal": 900.0,
        "tax_rate": 11.0,
        "tax_amount": 99.0,
        "status": "completed",
        "payment_status": "paid",
        "payment_method": "cash",
        "created_at": datetime.now(timezone.utc),
        "_test_marker": True,
    }
    already_ok_id = db.bookings.insert_one(already_ok_doc).inserted_id

    no_total_doc = {
        "user_id": "test-user",
        "user_email": cust_email,
        "user_name": "Backfill Test",
        "car_id": "test-car",
        "car_name": "Test Car",
        "pickup_location": {"name": loc_name},
        "dropoff_location": {"name": loc_name},
        "pickup_date": datetime.now(timezone.utc),
        "dropoff_date": datetime.now(timezone.utc),
        "status": "pending",
        "payment_status": "pending",
        "payment_method": "cash",
        "created_at": datetime.now(timezone.utc),
        "_test_marker": True,
    }
    no_total_id = db.bookings.insert_one(no_total_doc).inserted_id

    r = requests.post(f"{BASE}/admin/backfill-booking-taxes", headers=hdrs, timeout=60)
    check("BACKFILL: returns 200", r.status_code == 200, r.text[:200])
    body = r.json()
    check("BACKFILL: response has 'message'", "message" in body)
    check("BACKFILL: response has 'updated' int", isinstance(body.get("updated"), int))
    check("BACKFILL: response has 'already_ok' int >=0", isinstance(body.get("already_ok"), int) and body["already_ok"] >= 0)
    check("BACKFILL: response has 'skipped_no_total' int", isinstance(body.get("skipped_no_total"), int))
    check("BACKFILL: response 'limit' == 1000 default", body.get("limit") == 1000)
    check("BACKFILL: updated >= 3 (seeded 3 incomplete)", body.get("updated", 0) >= 3, f"updated={body.get('updated')}")
    check("BACKFILL: skipped_no_total >= 1", body.get("skipped_no_total", 0) >= 1, f"skipped={body.get('skipped_no_total')}")

    for sid, total in zip(seeded_ids, totals):
        doc = db.bookings.find_one({"_id": sid})
        assert doc is not None
        subtotal = doc.get("subtotal")
        tax_amount = doc.get("tax_amount")
        tax_rate_val = doc.get("tax_rate")
        check(f"MATH({total}): subtotal present", subtotal is not None)
        check(f"MATH({total}): tax_amount present", tax_amount is not None)
        check(f"MATH({total}): tax_rate matches location ({loc_tax_rate})", abs((tax_rate_val or 0) - loc_tax_rate) < 0.001, f"got tax_rate={tax_rate_val}")
        expected_sub = round(total / (1 + loc_tax_rate / 100.0), 2)
        check(f"MATH({total}): subtotal == round(total/(1+rate/100),2) == {expected_sub}",
              abs((subtotal or 0) - expected_sub) < 0.005, f"got {subtotal} expected {expected_sub}")
        check(f"MATH({total}): subtotal+tax_amount ≈ total_price",
              abs(((subtotal or 0) + (tax_amount or 0)) - total) < 0.02,
              f"sub={subtotal} tax={tax_amount} total={total}")

    # === (3) FILTER CORRECTNESS ===
    after = db.bookings.find_one({"_id": already_ok_id})
    check("FILTER: already-ok subtotal unchanged (900.0)", after.get("subtotal") == 900.0, f"got {after.get('subtotal')}")
    check("FILTER: already-ok tax_rate unchanged (11.0)", after.get("tax_rate") == 11.0, f"got {after.get('tax_rate')}")
    check("FILTER: already-ok tax_amount unchanged (99.0)", after.get("tax_amount") == 99.0, f"got {after.get('tax_amount')}")
    check("FILTER: already_ok response count >= 1", body.get("already_ok", 0) >= 1)

    # === (4) MISSING total_price ===
    no_total_after = db.bookings.find_one({"_id": no_total_id})
    check("NO_TOTAL: doc still has no subtotal", "subtotal" not in no_total_after or no_total_after.get("subtotal") is None)
    check("NO_TOTAL: doc still has no total_price", "total_price" not in no_total_after)

    # === (5) LIMIT QUERY PARAM ===
    for t in [111.0, 222.0, 333.0]:
        db.bookings.insert_one({
            "user_id": "test-user",
            "user_email": cust_email,
            "car_id": "test-car",
            "car_name": "Test Car",
            "pickup_location": {"name": loc_name},
            "dropoff_location": {"name": loc_name},
            "pickup_date": datetime.now(timezone.utc),
            "dropoff_date": datetime.now(timezone.utc),
            "total_price": t,
            "status": "completed",
            "payment_status": "paid",
            "payment_method": "cash",
            "created_at": datetime.now(timezone.utc),
            "_test_marker": True,
        })

    r1 = requests.post(f"{BASE}/admin/backfill-booking-taxes?limit=1", headers=hdrs, timeout=30)
    check("LIMIT=1: 200", r1.status_code == 200)
    b1 = r1.json()
    check("LIMIT=1: response.limit==1", b1.get("limit") == 1, f"got {b1.get('limit')}")
    check("LIMIT=1: updated<=1", b1.get("updated", 0) <= 1, f"updated={b1.get('updated')}")

    r0 = requests.post(f"{BASE}/admin/backfill-booking-taxes?limit=0", headers=hdrs, timeout=30)
    check("LIMIT=0: 200", r0.status_code == 200)
    check("LIMIT=0: clamped to 1", r0.json().get("limit") == 1, f"got {r0.json().get('limit')}")

    r99 = requests.post(f"{BASE}/admin/backfill-booking-taxes?limit=99999", headers=hdrs, timeout=30)
    check("LIMIT=99999: 200", r99.status_code == 200)
    check("LIMIT=99999: clamped to 10000", r99.json().get("limit") == 10000, f"got {r99.json().get('limit')}")

    rabc = requests.post(f"{BASE}/admin/backfill-booking-taxes?limit=abc", headers=hdrs, timeout=30)
    check("LIMIT=abc: 200 (no crash)", rabc.status_code == 200, f"got {rabc.status_code} body={rabc.text[:200]}")
    check("LIMIT=abc: defaults to 1000", rabc.json().get("limit") == 1000, f"got {rabc.json().get('limit')}")

    # === (6) IDEMPOTENCY ===
    r_idem = requests.post(f"{BASE}/admin/backfill-booking-taxes", headers=hdrs, timeout=30)
    check("IDEMPOTENT: 200", r_idem.status_code == 200)
    check("IDEMPOTENT: updated==0 (no new incomplete docs)", r_idem.json().get("updated") == 0,
          f"updated={r_idem.json().get('updated')}")

    # === (7) BULK WRITE SAFETY ===
    with open('/app/backend/server.py') as f:
        first_lines = "".join(f.readlines()[:30])
    check("IMPORT: 'from pymongo import UpdateOne' present (top of server.py)",
          "from pymongo import UpdateOne" in first_lines)

    err_log_issues = []
    try:
        import glob
        for path in glob.glob('/var/log/supervisor/backend.err*.log'):
            with open(path) as f:
                content = f.read()[-30000:]
            for line in content.splitlines():
                low = line.lower()
                if ('bulk_write' in low or 'updateone' in low or 'pymongo import' in low) and ('error' in low or 'traceback' in low or 'exception' in low):
                    err_log_issues.append(f"{path}: {line[:200]}")
    except Exception as e:
        err_log_issues.append(f"log-read-error: {e}")
    check("LOG: no bulk_write/UpdateOne/pymongo errors in backend.err.log", len(err_log_issues) == 0,
          f"issues={err_log_issues[:3]}")

    # === CLEANUP ===
    cleanup_count = db.bookings.delete_many({"_test_marker": True}).deleted_count
    print(f"\nCleaned up {cleanup_count} test bookings.")

    try:
        db.users.delete_one({"email": cust_email})
    except Exception:
        pass

    print("\n" + "=" * 70)
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    if failed:
        print("\nFAILURES:")
        for n, ok, d in results:
            if not ok:
                print(f"  ✗ {n}: {d}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
