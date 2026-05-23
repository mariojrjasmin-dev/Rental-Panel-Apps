"""
Tests for POST /api/admin/bookings/cancel-pending-pickups
"""
import os
import sys
import asyncio
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://rental-routes.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"
CUSTOMER_EMAIL = "customer@damscarrental.com"
CUSTOMER_PASSWORD = "Customer@123"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

PASS = 0
FAIL = 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {msg}")
    else:
        FAIL += 1
        print(f"  ❌ {msg}")


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        print(f"  !!! login failed for {email}: {r.status_code} {r.text}")
        return None
    return r.json().get("token") or r.json().get("access_token")


async def get_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


async def snapshot_db():
    db = await get_db()
    snap = {}
    snap["by_status"] = {}
    async for x in db.bookings.aggregate([{"$group": {"_id": "$status", "c": {"$sum": 1}}}]):
        snap["by_status"][x["_id"]] = x["c"]
    snap["total"] = await db.bookings.count_documents({})
    snap["test_marker_count"] = await db.bookings.count_documents({"_test_marker": True})
    snap["test_marker_docs"] = []
    async for b in db.bookings.find({"_test_marker": True}):
        snap["test_marker_docs"].append({
            "id": str(b["_id"]),
            "status": b.get("status"),
            "cancelled_at": b.get("cancelled_at"),
            "cancelled_by": b.get("cancelled_by"),
            "cancelled_reason": b.get("cancelled_reason"),
            "user_email": b.get("user_email"),
            "car_id": b.get("car_id"),
        })
    # capture car.stock dict for car_id values referenced
    car_ids = list({d["car_id"] for d in snap["test_marker_docs"] if d.get("car_id")})
    snap["car_stocks"] = {}
    from bson import ObjectId
    for cid in car_ids:
        if not cid:
            continue
        try:
            doc = await db.cars.find_one({"_id": ObjectId(cid)})
        except Exception:
            doc = None
        if doc is None:
            # try by string id
            doc = await db.cars.find_one({"_id": cid})
        snap["car_stocks"][cid] = doc.get("stock") if doc else None
    return snap


def main():
    global PASS, FAIL
    print(f"BASE: {API}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initial snapshot
    print("\n[0] Pre-test DB snapshot")
    snap_before = loop.run_until_complete(snapshot_db())
    print(f"  status counts BEFORE: {snap_before['by_status']}")
    print(f"  test_marker count: {snap_before['test_marker_count']}")
    check(snap_before["test_marker_count"] == 3, "3 seeded test-marker bookings exist in DB")

    # ---------- (1) Auth ----------
    print("\n[1] Auth checks")
    r = requests.post(f"{API}/admin/bookings/cancel-pending-pickups", timeout=20)
    check(r.status_code == 401, f"Unauthenticated → 401 (got {r.status_code})")

    cust_token = login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    if not cust_token:
        # Register a fresh test customer
        import secrets as _sec
        email = f"noadmin.tester.{_sec.token_hex(4)}@example.com"
        rr = requests.post(f"{API}/auth/register", json={
            "email": email, "password": "TempPass#1", "name": "No Admin Tester",
            "terms_accepted": True,
        }, timeout=20)
        if rr.status_code == 200:
            cust_token = rr.json().get("token") or rr.json().get("access_token")
            print(f"  [info] Created temp non-admin: {email}")
        else:
            print(f"  [warn] Could not create temp user: {rr.status_code} {rr.text}")
    check(cust_token is not None, "Customer (non-admin) login or temp registration succeeded")
    r = requests.post(
        f"{API}/admin/bookings/cancel-pending-pickups",
        headers={"Authorization": f"Bearer {cust_token}"},
        timeout=20,
    )
    check(r.status_code == 403, f"Non-admin → 403 (got {r.status_code})")

    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    check(admin_token is not None, "Admin login succeeded")
    if not admin_token:
        print("Cannot continue without admin token.")
        sys.exit(1)
    auth_hdr = {"Authorization": f"Bearer {admin_token}"}

    # ---------- (2) Admin happy path ----------
    print("\n[2] Admin happy path call")
    r = requests.post(f"{API}/admin/bookings/cancel-pending-pickups", headers=auth_hdr, timeout=20)
    check(r.status_code == 200, f"Admin → 200 (got {r.status_code} body={r.text[:300]})")
    body = r.json() if r.status_code == 200 else {}
    cancelled_count = body.get("cancelled_count")
    matched_count = body.get("matched_count")
    sample = body.get("sample") or []
    print(f"  Response: cancelled_count={cancelled_count}, matched_count={matched_count}, sample_len={len(sample)}")
    check(cancelled_count == 3, f"cancelled_count == 3 (got {cancelled_count})")
    check(matched_count == 3, f"matched_count == 3 (got {matched_count})")
    check(isinstance(sample, list) and len(sample) == 3, f"sample list length == 3 (got {len(sample)})")
    needed_keys = {"id", "car_name", "user_email", "pickup_date", "status_before"}
    for i, item in enumerate(sample):
        check(needed_keys.issubset(set(item.keys())), f"sample[{i}] has keys id/car_name/user_email/pickup_date/status_before (got {sorted(item.keys())})")
        check(item.get("status_before") in {"pending", "pending_payment", "confirmed"},
              f"sample[{i}].status_before is one of pending/pending_payment/confirmed (got {item.get('status_before')})")
        check(isinstance(item.get("pickup_date"), str) and "T" in item["pickup_date"],
              f"sample[{i}].pickup_date is ISO string (got {item.get('pickup_date')})")
        check(item.get("user_email", "").endswith("@test.com"), f"sample[{i}].user_email is one of fake*@test.com (got {item.get('user_email')})")

    # DB verification: bookings now cancelled with cancelled_at
    print("\n[2b] DB verification for the 3 seeded bookings")
    snap_after1 = loop.run_until_complete(snapshot_db())
    for doc in snap_after1["test_marker_docs"]:
        check(doc["status"] == "cancelled", f"  test booking {doc['user_email']} status='cancelled' (got {doc['status']})")
        check(doc["cancelled_at"] is not None and isinstance(doc["cancelled_at"], datetime),
              f"  test booking {doc['user_email']} has cancelled_at datetime (got {type(doc['cancelled_at']).__name__})")
        check(doc.get("cancelled_by") == "admin_bulk", f"  test booking {doc['user_email']} cancelled_by='admin_bulk' (got {doc.get('cancelled_by')})")
        check(doc.get("cancelled_reason") == "Bulk cleanup of pending pickups by admin",
              f"  test booking {doc['user_email']} cancelled_reason matches (got {doc.get('cancelled_reason')})")

    # GET /api/admin/bookings shows them cancelled
    print("\n[2c] GET /api/admin/bookings shows them cancelled")
    r_ab = requests.get(f"{API}/admin/bookings", headers=auth_hdr, timeout=20)
    check(r_ab.status_code == 200, f"GET /admin/bookings → 200 (got {r_ab.status_code})")
    if r_ab.status_code == 200:
        all_bks = r_ab.json()
        test_ids = {d["id"] for d in snap_after1["test_marker_docs"]}
        found = [b for b in all_bks if b.get("id") in test_ids]
        check(len(found) == 3, f"Found all 3 seeded bookings in admin list (got {len(found)})")
        for b in found:
            check(b.get("status") == "cancelled", f"  admin-list booking {b.get('user_email')} status=cancelled (got {b.get('status')})")

    # ---------- (3) Idempotency ----------
    print("\n[3] Idempotent second call")
    r = requests.post(f"{API}/admin/bookings/cancel-pending-pickups", headers=auth_hdr, timeout=20)
    check(r.status_code == 200, f"Second admin → 200 (got {r.status_code})")
    body2 = r.json()
    check(body2.get("cancelled_count") == 0, f"Second cancelled_count == 0 (got {body2.get('cancelled_count')})")
    check(body2.get("matched_count") == 0, f"Second matched_count == 0 (got {body2.get('matched_count')})")
    check(body2.get("sample") == [], f"Second sample == [] (got {body2.get('sample')})")

    # ---------- (4) Isolation: counts of other statuses unchanged ----------
    print("\n[4] Isolation: non-pending statuses unchanged")
    snap_after = loop.run_until_complete(snapshot_db())
    for status in ("active", "completed"):
        b = snap_before["by_status"].get(status, 0)
        a = snap_after["by_status"].get(status, 0)
        check(b == a, f"  status='{status}' count unchanged ({b} → {a})")
    # 'cancelled' should have grown by exactly 3 (or seeded count)
    canc_before = snap_before["by_status"].get("cancelled", 0)
    canc_after = snap_after["by_status"].get("cancelled", 0)
    check(canc_after == canc_before + 3, f"  cancelled count grew by exactly 3 ({canc_before} → {canc_after})")
    # pending statuses should be 0
    for status in ("pending", "pending_payment", "confirmed"):
        a = snap_after["by_status"].get(status, 0)
        check(a == 0, f"  status='{status}' is now 0 (got {a})")
    # total docs unchanged
    check(snap_before["total"] == snap_after["total"], f"  Total booking count unchanged ({snap_before['total']} → {snap_after['total']})")

    # ---------- (5) Stock invariance ----------
    print("\n[5] Car stock invariance")
    for cid, stock_before in snap_before["car_stocks"].items():
        stock_after = snap_after["car_stocks"].get(cid)
        check(stock_before == stock_after, f"  car {cid} stock unchanged ({stock_before} → {stock_after})")

    # ---------- Cleanup ----------
    print("\n[CLEANUP] Removing seeded test bookings (_test_marker=true)")
    async def cleanup():
        db = await get_db()
        res = await db.bookings.delete_many({"_test_marker": True})
        return res.deleted_count
    deleted = loop.run_until_complete(cleanup())
    print(f"  Deleted {deleted} test bookings.")
    check(deleted == 3, f"Cleanup deleted 3 test bookings (got {deleted})")
    snap_final = loop.run_until_complete(snapshot_db())
    print(f"  Final total bookings in DB: {snap_final['total']} (statuses={snap_final['by_status']})")
    check(snap_final["total"] == snap_before["total"] - 3,
          f"DB returned to prior count (was {snap_before['total']}, now {snap_final['total']})")
    check(snap_final["test_marker_count"] == 0, "No test_marker docs remain")

    # ---------- Final report ----------
    print(f"\n=== RESULT: {PASS} passed, {FAIL} failed ===")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
