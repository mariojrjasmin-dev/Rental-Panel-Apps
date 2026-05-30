"""
Backend test for DAMS Car Rental — Admin Force-Cancel + POS Walk-In endpoints.

Targets:
  POST /api/admin/bookings/{id}/force-cancel
  POST /api/admin/pos/bookings
  GET  /api/admin/customers (regression — national_id/drivers_license expose)
  POST /api/bookings/{id}/cancel (customer regression)
  PUT  /api/admin/bookings/{id}/status (active→completed regression after POS)
"""
import os
import sys
import time
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BACKEND_URL = "https://rental-routes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASS = "Admin@123"
CUST_EMAIL = "reviewer@damscarrental.com"
CUST_PASS = "ReviewApp2026!"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

results: list = []
created_booking_ids: set = set()
created_user_emails: set = set()
location_state_backup: dict = {}
car_stock_backup: dict = {}


def record(name: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    results.append((name, ok, detail))
    print(f"  [{status}] {name}{' — ' + detail if detail else ''}")


def login(email: str, password: str) -> Optional[str]:
    r = requests.post(f"{BACKEND_URL}/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        print(f"!! login failed for {email}: {r.status_code} {r.text[:200]}")
        return None
    return r.json().get("token")


def hdr(tok: Optional[str]) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


# Persistent loop + Motor client bound to it (Motor sockets/futures
# are tied to the event loop they were created in, so we must reuse it).
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
_cli = AsyncIOMotorClient(MONGO_URL, io_loop=_loop)
_db_inst = _cli[DB_NAME]

def db():
    return _db_inst

def arun(coro):
    return _loop.run_until_complete(coro)


# ============================================================
# TEST A — Force Cancel
# ============================================================
def test_force_cancel(admin_tok: str, cust_tok: str, car_id: str):
    print("\n=== TEST A — Force-Cancel ===")

    # (A1) Unauth → 401
    r = requests.post(f"{BACKEND_URL}/admin/bookings/507f1f77bcf86cd799439011/force-cancel",
                      json={"reason": "x"}, timeout=15)
    record("A1 unauth → 401", r.status_code == 401,
           f"got {r.status_code}: {r.text[:120]}")

    # (A2) Customer token → 403
    r = requests.post(f"{BACKEND_URL}/admin/bookings/507f1f77bcf86cd799439011/force-cancel",
                      headers=hdr(cust_tok), json={"reason": "x"}, timeout=15)
    record("A2 customer token → 403", r.status_code == 403,
           f"got {r.status_code}: {r.text[:120]}")

    # (A7) Invalid id → 400
    r = requests.post(f"{BACKEND_URL}/admin/bookings/not-an-objectid/force-cancel",
                      headers=hdr(admin_tok), json={}, timeout=15)
    record("A7 invalid booking id → 400",
           r.status_code == 400 and "invalid" in r.text.lower(),
           f"got {r.status_code}: {r.text[:120]}")

    # (A3) Happy path — seed pending booking via POST /bookings as reviewer
    pickup_dt = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT10:00:00")
    dropoff_dt = (datetime.now(timezone.utc) + timedelta(days=12)).strftime("%Y-%m-%dT10:00:00")
    create_body = {
        "car_id": car_id,
        "pickup_date": pickup_dt,
        "dropoff_date": dropoff_dt,
        "pickup_location": {"name": "Punta Cana Airport"},
        "dropoff_location": {"name": "Punta Cana Airport"},
        "payment_method": "cash",
        "terms_accepted": True,
    }
    r = requests.post(f"{BACKEND_URL}/bookings", headers=hdr(cust_tok),
                      json=create_body, timeout=20)
    if r.status_code != 200:
        record("A3 seed pending booking (POST /bookings)", False,
               f"got {r.status_code}: {r.text[:200]}")
        return
    seed_booking = r.json()
    seed_id = seed_booking.get("id") or seed_booking.get("_id")
    if not seed_id:
        record("A3 seed booking has id", False, f"resp keys={list(seed_booking.keys())}")
        return
    created_booking_ids.add(seed_id)
    record("A3 seed pending booking via POST /bookings", True, f"id={seed_id} status={seed_booking.get('status')}")

    r = requests.post(f"{BACKEND_URL}/admin/bookings/{seed_id}/force-cancel",
                      headers=hdr(admin_tok),
                      json={"reason": "QA test cancel", "send_email": False, "refund_stock": True},
                      timeout=20)
    ok = r.status_code == 200
    record("A3 admin force-cancel 200", ok, f"got {r.status_code}: {r.text[:200]}")
    if ok:
        data = r.json()
        b = data.get("booking", {})
        record("A3 ok=true", data.get("ok") is True)
        record("A3 email_sent=false", data.get("email_sent") is False)
        record("A3 restock string present", isinstance(data.get("restock"), str), f"restock={data.get('restock')!r}")
        record("A3 booking.status=cancelled", b.get("status") == "cancelled", f"got={b.get('status')}")
        record("A3 booking.cancelled_by=admin", b.get("cancelled_by") == "admin", f"got={b.get('cancelled_by')}")
        record("A3 cancellation_reason='QA test cancel'", b.get("cancellation_reason") == "QA test cancel",
               f"got={b.get('cancellation_reason')!r}")
        record("A3 force_cancelled=True", b.get("force_cancelled") is True, f"got={b.get('force_cancelled')}")
        record("A3 previous_status in {pending,pending_payment}",
               b.get("previous_status_before_cancel") in {"pending", "pending_payment"},
               f"got={b.get('previous_status_before_cancel')!r}")

        async def _check_audit():
            return await db().audit_log.find_one(
                {"action": "booking.force_cancel", "target": seed_id},
                sort=[("created_at", -1)],
            )
        row = arun(_check_audit())
        record("A3 audit log row created (booking.force_cancel)", row is not None)
        if row:
            meta = row.get("meta") or {}
            record("A3 audit meta.reason contains 'QA test cancel'",
                   "QA test cancel" in (meta.get("reason") or ""),
                   f"meta={meta}")

    # (A4) Already cancelled → 400
    r = requests.post(f"{BACKEND_URL}/admin/bookings/{seed_id}/force-cancel",
                      headers=hdr(admin_tok),
                      json={"reason": "second try", "send_email": False},
                      timeout=15)
    ok = r.status_code == 400 and "already cancelled" in r.text.lower()
    record("A4 already-cancelled → 400 'already cancelled'", ok,
           f"got {r.status_code}: {r.text[:200]}")

    # (A5) Active booking with pickup_decremented=true → restock +1
    pickup_loc_name = "Bavaro Beach Hub"
    async def _seed_active(car_id, pickup_loc):
        car = await db().cars.find_one({"_id": ObjectId(car_id)})
        stock = (car.get("stock") or {}).get(pickup_loc, 0)
        booking_doc = {
            "user_id": "test-a5",
            "user_email": "a5seed@example.com",
            "customer_name": "A5 Seed",
            "customer_email": "a5seed@example.com",
            "car_id": car_id,
            "car_name": car.get("name") or "test",
            "pickup_date": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT10:00:00"),
            "dropoff_date": (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00"),
            "pickup_location": {"name": pickup_loc},
            "dropoff_location": {"name": pickup_loc},
            "days": 3, "price_per_day": 100.0, "subtotal": 300.0,
            "tax_rate": 18.0, "tax_amount": 54.0, "total_price": 354.0,
            "payment_method": "cash", "payment_status": "paid",
            "status": "active",
            "stock_adjustments": {
                "pickup_decremented": True,
                "pickup_at": datetime.now(timezone.utc),
                "pickup_key": pickup_loc,
                "pickup_reason": "test_seed",
            },
            "_test_marker": "a5",
            "created_at": datetime.now(timezone.utc),
        }
        res = await db().bookings.insert_one(booking_doc)
        return str(res.inserted_id), stock

    seed5_id, stock_before = arun(_seed_active(car_id, pickup_loc_name))
    created_booking_ids.add(seed5_id)
    record("A5 seed active booking with pickup_decremented", True,
           f"id={seed5_id} stock_before={stock_before}")

    r = requests.post(f"{BACKEND_URL}/admin/bookings/{seed5_id}/force-cancel",
                      headers=hdr(admin_tok),
                      json={"reason": "A5 restock test", "send_email": False},
                      timeout=20)
    ok = r.status_code == 200
    record("A5 force-cancel 200", ok, f"got {r.status_code}: {r.text[:200]}")
    if ok:
        data = r.json()
        restock = data.get("restock", "")
        record("A5 response.restock contains 'incremented'",
               "incremented" in restock.lower(), f"restock={restock!r}")

        async def _post_a5():
            car = await db().cars.find_one({"_id": ObjectId(car_id)})
            stock_after = (car.get("stock") or {}).get(pickup_loc_name, 0)
            booking = await db().bookings.find_one({"_id": ObjectId(seed5_id)})
            return stock_after, booking
        stock_after, b5 = arun(_post_a5())
        record("A5 car.stock at pickup +1 from before",
               stock_after == stock_before + 1,
               f"before={stock_before} after={stock_after}")
        record("A5 stock_adjustments.dropoff_incremented=True",
               (b5.get("stock_adjustments") or {}).get("dropoff_incremented") is True,
               f"stock_adjustments={b5.get('stock_adjustments')}")

    # (A6) Pending booking no stock decrement → unchanged
    async def _seed_pending(car_id, pickup_loc):
        car = await db().cars.find_one({"_id": ObjectId(car_id)})
        stock = (car.get("stock") or {}).get(pickup_loc, 0)
        booking_doc = {
            "user_id": "test-a6",
            "user_email": "a6seed@example.com",
            "customer_name": "A6 Seed",
            "customer_email": "a6seed@example.com",
            "car_id": car_id,
            "car_name": car.get("name") or "test",
            "pickup_date": (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT10:00:00"),
            "dropoff_date": (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%dT10:00:00"),
            "pickup_location": {"name": pickup_loc},
            "dropoff_location": {"name": pickup_loc},
            "days": 5, "price_per_day": 100.0, "subtotal": 500.0,
            "tax_rate": 18.0, "tax_amount": 90.0, "total_price": 590.0,
            "payment_method": "cash", "payment_status": "pending",
            "status": "pending",
            "stock_adjustments": {},
            "_test_marker": "a6",
            "created_at": datetime.now(timezone.utc),
        }
        res = await db().bookings.insert_one(booking_doc)
        return str(res.inserted_id), stock

    seed6_id, stock_before6 = arun(_seed_pending(car_id, pickup_loc_name))
    created_booking_ids.add(seed6_id)

    r = requests.post(f"{BACKEND_URL}/admin/bookings/{seed6_id}/force-cancel",
                      headers=hdr(admin_tok),
                      json={"reason": "A6 no-stock-inflation", "send_email": False},
                      timeout=15)
    ok = r.status_code == 200
    record("A6 force-cancel 200", ok, f"got {r.status_code}: {r.text[:200]}")
    if ok:
        restock = r.json().get("restock", "")
        record("A6 restock 'not_needed' or 'skipped'",
               ("not_needed" in restock.lower() or "skipped" in restock.lower()),
               f"restock={restock!r}")
        async def _car_stock():
            car = await db().cars.find_one({"_id": ObjectId(car_id)})
            return (car.get("stock") or {}).get(pickup_loc_name, 0)
        stock_after6 = arun(_car_stock())
        record("A6 car stock UNCHANGED",
               stock_after6 == stock_before6,
               f"before={stock_before6} after={stock_after6}")


# ============================================================
# TEST B — POS Walk-In
# ============================================================
def test_pos(admin_tok: str, cust_tok: str, car_id: str):
    print("\n=== TEST B — POS Walk-In ===")
    ts = int(time.time())
    pos_email = f"pos.qa.{ts}@example.com"
    created_user_emails.add(pos_email)

    pickup_dt = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT10:00:00")
    dropoff_dt_5 = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%dT10:00:00")
    dropoff_dt_1 = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00")

    base_payload = {
        "customer_name": "POS QA Walk-In",
        "customer_email": pos_email,
        "customer_phone": "+18095550100",
        "customer_id_number": "ID-99999",
        "customer_drivers_license": "DL-12345-QA",
        "car_id": car_id,
        "pickup_date": pickup_dt,
        "dropoff_date": dropoff_dt_5,
        "pickup_location": {"name": "Punta Cana Airport"},
        "dropoff_location": {"name": "Punta Cana Airport"},
        "payment_method": "cash",
        "mark_paid": True,
        "status": "active",
        "send_email": False,
        "notes": "QA POS booking — automated test",
    }

    # (B1) Unauth → 401/422
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings", json=base_payload, timeout=15)
    record("B1 unauth → 401/422", r.status_code in (401, 422),
           f"got {r.status_code}: {r.text[:120]}")

    # (B2) Customer token → 403
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(cust_tok), json=base_payload, timeout=15)
    record("B2 customer token → 403", r.status_code == 403,
           f"got {r.status_code}: {r.text[:120]}")

    # (B3) Admin happy path
    async def _stock_at(car_id, loc_name):
        car = await db().cars.find_one({"_id": ObjectId(car_id)})
        return (car.get("stock") or {}).get(loc_name, 0)

    stock_before_b3 = arun(_stock_at(car_id, "Punta Cana Airport"))

    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=base_payload, timeout=20)
    ok_b3 = r.status_code == 200
    record("B3 POS active happy path → 200", ok_b3,
           f"got {r.status_code}: {r.text[:200]}")
    b3_booking_id = None
    if ok_b3:
        data = r.json()
        b = data.get("booking", {})
        b3_booking_id = b.get("id")
        if b3_booking_id:
            created_booking_ids.add(b3_booking_id)

        record("B3 user_created=true", data.get("user_created") is True, f"got={data.get('user_created')}")
        record("B3 user_id present", bool(data.get("user_id")), f"got={data.get('user_id')}")
        record("B3 receipt_url correct",
               data.get("receipt_url") == f"/api/bookings/{b3_booking_id}/receipt.pdf",
               f"got={data.get('receipt_url')}")
        record("B3 booking.pos_origin=true", b.get("pos_origin") is True, f"got={b.get('pos_origin')}")
        record("B3 booking.status=active", b.get("status") == "active", f"got={b.get('status')}")
        record("B3 booking.payment_status=paid", b.get("payment_status") == "paid", f"got={b.get('payment_status')}")
        record("B3 booking.payment_method=cash", b.get("payment_method") == "cash", f"got={b.get('payment_method')}")
        record("B3 total_price > 0", float(b.get("total_price") or 0) > 0, f"got={b.get('total_price')}")
        record("B3 pos_created_by == admin email", b.get("pos_created_by") == ADMIN_EMAIL, f"got={b.get('pos_created_by')}")
        record("B3 customer_drivers_license=DL-12345-QA",
               b.get("customer_drivers_license") == "DL-12345-QA", f"got={b.get('customer_drivers_license')}")
        sa = b.get("stock_adjustments") or {}
        record("B3 stock_adjustments.pickup_decremented=true",
               sa.get("pickup_decremented") is True, f"got={sa}")

        stock_after_b3 = arun(_stock_at(car_id, "Punta Cana Airport"))
        record("B3 car stock -1 at pickup",
               stock_after_b3 == stock_before_b3 - 1,
               f"before={stock_before_b3} after={stock_after_b3}")

        async def _check_user():
            return await db().users.find_one({"email": pos_email})
        u = arun(_check_user())
        record("B3 db.users row created with email", u is not None,
               f"user_id={u and u.get('_id')}")
        if u:
            record("B3 user.drivers_license=DL-12345-QA",
                   u.get("drivers_license") == "DL-12345-QA",
                   f"got={u.get('drivers_license')!r}")
            record("B3 user.pos_walk_in=True",
                   u.get("pos_walk_in") is True,
                   f"got={u.get('pos_walk_in')!r}")

        async def _check_audit_b3():
            return await db().audit_log.find_one(
                {"action": "pos.booking_create", "target": b3_booking_id},
                sort=[("created_at", -1)],
            )
        row = arun(_check_audit_b3())
        record("B3 audit log (pos.booking_create)", row is not None)
        if row:
            record("B3 audit meta.customer_email matches",
                   (row.get("meta") or {}).get("customer_email") == pos_email,
                   f"meta={row.get('meta')}")

    # (B4) Same email re-run — backfill
    async def _clear_fields():
        await db().users.update_one(
            {"email": pos_email},
            {"$set": {"national_id": "", "phone": ""}},
        )
    arun(_clear_fields())

    payload_b4 = dict(base_payload)
    payload_b4["customer_id_number"] = "ID-NEW-77777"
    payload_b4["customer_phone"] = "+18095559999"
    payload_b4["pickup_date"] = (datetime.now(timezone.utc) + timedelta(days=8)).strftime("%Y-%m-%dT10:00:00")
    payload_b4["dropoff_date"] = (datetime.now(timezone.utc) + timedelta(days=13)).strftime("%Y-%m-%dT10:00:00")

    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b4, timeout=20)
    ok_b4 = r.status_code == 200
    record("B4 same email re-run → 200", ok_b4,
           f"got {r.status_code}: {r.text[:200]}")
    if ok_b4:
        data = r.json()
        record("B4 user_created=false", data.get("user_created") is False,
               f"got={data.get('user_created')}")
        b_id = data.get("booking", {}).get("id")
        if b_id:
            created_booking_ids.add(b_id)
        async def _user_after():
            return await db().users.find_one({"email": pos_email})
        u = arun(_user_after())
        if u:
            record("B4 user.national_id backfilled to ID-NEW-77777",
                   u.get("national_id") == "ID-NEW-77777",
                   f"got={u.get('national_id')!r}")
            record("B4 user.phone backfilled to +18095559999",
                   u.get("phone") == "+18095559999",
                   f"got={u.get('phone')!r}")

    # (B5) status='pending' → no stock change
    stock_before_b5 = arun(_stock_at(car_id, "Punta Cana Airport"))
    payload_b5 = dict(base_payload)
    payload_b5["status"] = "pending"
    payload_b5["customer_email"] = f"pos.b5.{ts}@example.com"
    created_user_emails.add(payload_b5["customer_email"])
    payload_b5["pickup_date"] = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%dT10:00:00")
    payload_b5["dropoff_date"] = (datetime.now(timezone.utc) + timedelta(days=25)).strftime("%Y-%m-%dT10:00:00")
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b5, timeout=20)
    ok_b5 = r.status_code == 200
    record("B5 status=pending → 200", ok_b5,
           f"got {r.status_code}: {r.text[:200]}")
    if ok_b5:
        b = r.json().get("booking", {})
        b_id = b.get("id")
        if b_id:
            created_booking_ids.add(b_id)
        record("B5 booking.status=pending", b.get("status") == "pending",
               f"got={b.get('status')!r}")
        sa = b.get("stock_adjustments") or {}
        record("B5 stock_adjustments has no pickup_decremented",
               not sa.get("pickup_decremented"),
               f"stock_adjustments={sa}")
        stock_after_b5 = arun(_stock_at(car_id, "Punta Cana Airport"))
        record("B5 car stock UNCHANGED",
               stock_after_b5 == stock_before_b5,
               f"before={stock_before_b5} after={stock_after_b5}")

    # (B6) Cross-country pickup/dropoff → 400
    payload_b6 = dict(base_payload)
    payload_b6["dropoff_location"] = {"name": "JFK Airport New York"}
    payload_b6["customer_email"] = f"pos.b6.{ts}@example.com"
    created_user_emails.add(payload_b6["customer_email"])
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b6, timeout=15)
    record("B6 cross-country → 400",
           r.status_code == 400 and "same country" in r.text.lower(),
           f"got {r.status_code}: {r.text[:200]}")

    # (B7) Inactive pickup → 400
    async def _set_loc_active(name, active):
        loc = await db().locations.find_one({"name": name})
        prev = bool(loc.get("active", True)) if loc else True
        await db().locations.update_one({"name": name}, {"$set": {"active": active}})
        return prev

    prev_active = arun(_set_loc_active("Bavaro Beach Hub", False))
    location_state_backup["Bavaro Beach Hub_active"] = prev_active

    payload_b7 = dict(base_payload)
    payload_b7["pickup_location"] = {"name": "Bavaro Beach Hub"}
    payload_b7["dropoff_location"] = {"name": "Bavaro Beach Hub"}
    payload_b7["customer_email"] = f"pos.b7.{ts}@example.com"
    created_user_emails.add(payload_b7["customer_email"])
    payload_b7["dropoff_date"] = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00")
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b7, timeout=15)
    record("B7 inactive pickup → 400",
           r.status_code == 400 and "inactive" in r.text.lower(),
           f"got {r.status_code}: {r.text[:200]}")

    arun(_set_loc_active("Bavaro Beach Hub", prev_active))

    # (B8) Days < min_booking_days → 400
    payload_b8 = dict(base_payload)
    payload_b8["dropoff_date"] = dropoff_dt_1
    payload_b8["customer_email"] = f"pos.b8.{ts}@example.com"
    created_user_emails.add(payload_b8["customer_email"])
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b8, timeout=15)
    record("B8 days < min_booking_days → 400",
           r.status_code == 400 and ("minimum" in r.text.lower() or "min" in r.text.lower()),
           f"got {r.status_code}: {r.text[:200]}")

    # (B9) payment_method=paypal → 400
    payload_b9 = dict(base_payload)
    payload_b9["payment_method"] = "paypal"
    payload_b9["customer_email"] = f"pos.b9.{ts}@example.com"
    created_user_emails.add(payload_b9["customer_email"])
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b9, timeout=15)
    record("B9 payment_method=paypal → 400",
           r.status_code == 400 and ("cash" in r.text.lower() and "card" in r.text.lower() and "transfer" in r.text.lower()),
           f"got {r.status_code}: {r.text[:200]}")

    # (B10) Missing customer_drivers_license → 400
    payload_b10 = dict(base_payload)
    payload_b10["customer_drivers_license"] = ""
    payload_b10["customer_email"] = f"pos.b10.{ts}@example.com"
    created_user_emails.add(payload_b10["customer_email"])
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b10, timeout=15)
    record("B10 missing drivers_license → 400",
           r.status_code == 400 and "driver" in r.text.lower(),
           f"got {r.status_code}: {r.text[:200]}")

    # (B11) mark_paid=false → payment_status=pending
    payload_b11 = dict(base_payload)
    payload_b11["mark_paid"] = False
    payload_b11["customer_email"] = f"pos.b11.{ts}@example.com"
    created_user_emails.add(payload_b11["customer_email"])
    payload_b11["pickup_date"] = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT10:00:00")
    payload_b11["dropoff_date"] = (datetime.now(timezone.utc) + timedelta(days=35)).strftime("%Y-%m-%dT10:00:00")
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b11, timeout=20)
    ok = r.status_code == 200
    record("B11 mark_paid=false → 200", ok, f"got {r.status_code}: {r.text[:200]}")
    if ok:
        b = r.json().get("booking", {})
        if b.get("id"):
            created_booking_ids.add(b.get("id"))
        record("B11 payment_status=pending", b.get("payment_status") == "pending",
               f"got={b.get('payment_status')!r}")

    # (B12) Receipt PDF
    if b3_booking_id:
        r = requests.get(f"{BACKEND_URL}/bookings/{b3_booking_id}/receipt.pdf",
                         headers=hdr(admin_tok), timeout=20)
        ct = r.headers.get("content-type", "")
        ok = r.status_code == 200 and "application/pdf" in ct and r.content.startswith(b"%PDF-")
        record("B12 receipt.pdf 200 + application/pdf + %PDF- magic",
               ok, f"status={r.status_code} ct={ct!r} head={r.content[:10]!r}")

    # (B13) Out of stock
    async def _set_stock(car_id, loc_name, value):
        car = await db().cars.find_one({"_id": ObjectId(car_id)})
        prev = (car.get("stock") or {}).get(loc_name, 0)
        await db().cars.update_one(
            {"_id": ObjectId(car_id)},
            {"$set": {f"stock.{loc_name}": value}},
        )
        return prev

    prev_stock = arun(_set_stock(car_id, "Bavaro Beach Hub", 0))
    car_stock_backup[f"{car_id}:Bavaro Beach Hub"] = prev_stock

    payload_b13 = dict(base_payload)
    payload_b13["pickup_location"] = {"name": "Bavaro Beach Hub"}
    payload_b13["dropoff_location"] = {"name": "Bavaro Beach Hub"}
    payload_b13["customer_email"] = f"pos.b13.{ts}@example.com"
    created_user_emails.add(payload_b13["customer_email"])
    payload_b13["dropoff_date"] = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00")
    r = requests.post(f"{BACKEND_URL}/admin/pos/bookings",
                      headers=hdr(admin_tok), json=payload_b13, timeout=15)
    record("B13 out-of-stock → 400",
           r.status_code == 400 and "out of stock" in r.text.lower(),
           f"got {r.status_code}: {r.text[:200]}")

    arun(_set_stock(car_id, "Bavaro Beach Hub", prev_stock))

    return b3_booking_id


# ============================================================
# TEST C — Regression
# ============================================================
def test_regression(admin_tok: str, cust_tok: str, b3_booking_id: Optional[str], car_id: str):
    print("\n=== TEST C — Regression ===")

    # (C1) /admin/customers exposes national_id + drivers_license
    target_email = None
    if created_user_emails:
        target_email = sorted(created_user_emails)[0]
    if target_email:
        r = requests.get(f"{BACKEND_URL}/admin/customers?q={target_email}",
                         headers=hdr(admin_tok), timeout=15)
        ok = r.status_code == 200
        record("C1 GET /admin/customers 200", ok, f"got {r.status_code}: {r.text[:200]}")
        if ok:
            items = r.json().get("items", [])
            if items:
                first = items[0]
                record("C1 items[0] has 'national_id' key", "national_id" in first,
                       f"keys={list(first.keys())}")
                record("C1 items[0] has 'drivers_license' key", "drivers_license" in first,
                       f"keys={list(first.keys())}")
            else:
                record("C1 items present", False, "items array empty")

    # (C2) Customer cancel on >24h-future pending → 200
    pickup_dt = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT10:00:00")
    dropoff_dt = (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%dT10:00:00")
    create_body = {
        "car_id": car_id,
        "pickup_date": pickup_dt,
        "dropoff_date": dropoff_dt,
        "pickup_location": {"name": "Punta Cana Airport"},
        "dropoff_location": {"name": "Punta Cana Airport"},
        "payment_method": "cash",
        "terms_accepted": True,
    }
    r = requests.post(f"{BACKEND_URL}/bookings", headers=hdr(cust_tok),
                      json=create_body, timeout=20)
    if r.status_code != 200:
        record("C2 create pending booking", False, f"got {r.status_code}: {r.text[:200]}")
    else:
        bid = r.json().get("id")
        created_booking_ids.add(bid)
        r2 = requests.post(f"{BACKEND_URL}/bookings/{bid}/cancel",
                           headers=hdr(cust_tok), timeout=20)
        record("C2 customer cancel 200", r2.status_code == 200,
               f"got {r2.status_code}: {r2.text[:200]}")

    # (C3) PUT status=completed on the B3 booking → dropoff_incremented + stock +1
    if b3_booking_id:
        async def _stock_at(car_id, loc_name):
            car = await db().cars.find_one({"_id": ObjectId(car_id)})
            return (car.get("stock") or {}).get(loc_name, 0)

        dropoff_loc_name = "Punta Cana Airport"
        stock_before = arun(_stock_at(car_id, dropoff_loc_name))

        r = requests.put(f"{BACKEND_URL}/admin/bookings/{b3_booking_id}/status",
                         headers=hdr(admin_tok),
                         json={"status": "completed", "odometer_out": 50000, "odometer_in": 49000},
                         timeout=20)
        record("C3 PUT status=completed 200", r.status_code == 200,
               f"got {r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            async def _check():
                b = await db().bookings.find_one({"_id": ObjectId(b3_booking_id)})
                car = await db().cars.find_one({"_id": ObjectId(car_id)})
                return b, (car.get("stock") or {}).get(dropoff_loc_name, 0)
            b, stock_after = arun(_check())
            sa = (b or {}).get("stock_adjustments") or {}
            record("C3 stock_adjustments.dropoff_incremented=True",
                   sa.get("dropoff_incremented") is True,
                   f"stock_adjustments={sa}")
            record("C3 car stock +1 at dropoff",
                   stock_after == stock_before + 1,
                   f"before={stock_before} after={stock_after}")


# ============================================================
# Cleanup
# ============================================================
async def cleanup_async():
    print("\n=== CLEANUP ===")
    bids = []
    for b in created_booking_ids:
        if b:
            try:
                bids.append(ObjectId(b))
            except Exception:
                pass
    if bids:
        res = await db().bookings.delete_many({"_id": {"$in": bids}})
        print(f"  Deleted {res.deleted_count} test bookings")
    res = await db().bookings.delete_many({"_test_marker": {"$in": ["a5", "a6"]}})
    print(f"  Deleted {res.deleted_count} stray _test_marker bookings")

    if created_user_emails:
        res = await db().users.delete_many({"email": {"$in": list(created_user_emails)}})
        print(f"  Deleted {res.deleted_count} test users")
    leftovers = await db().users.count_documents({"pos_walk_in": True, "email": {"$regex": "^pos\\."}})
    print(f"  Remaining pos.* users with pos_walk_in=True: {leftovers}")
    test_book_left = await db().bookings.count_documents({"_test_marker": {"$exists": True}})
    print(f"  Remaining _test_marker bookings: {test_book_left}")


# ============================================================
# Main
# ============================================================
def main():
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Mongo: {MONGO_URL} db={DB_NAME}")

    admin_tok = login(ADMIN_EMAIL, ADMIN_PASS)
    cust_tok = login(CUST_EMAIL, CUST_PASS)
    if not admin_tok or not cust_tok:
        print("!! Could not log in. Aborting.")
        sys.exit(2)
    print("Admin token OK, customer token OK")

    CAR_ID = "69dd1f06a11b586d32ab7a31"  # Mercedes Benz

    # Ensure enough stock at Punta Cana for the cascade of POS tests
    async def _ensure_stock():
        await db().cars.update_one(
            {"_id": ObjectId(CAR_ID)},
            {"$set": {"stock.Punta Cana Airport": 10}},
        )
    arun(_ensure_stock())

    b3_id = None
    try:
        test_force_cancel(admin_tok, cust_tok, CAR_ID)
        b3_id = test_pos(admin_tok, cust_tok, CAR_ID)
        test_regression(admin_tok, cust_tok, b3_id, CAR_ID)
    finally:
        try:
            arun(cleanup_async())
        except Exception as e:
            print(f"Cleanup error: {e}")
        try:
            arun(db().cars.update_one(
                {"_id": ObjectId(CAR_ID)},
                {"$set": {"stock.Punta Cana Airport": 3}},
            ))
            print("  Reset Mercedes Benz Punta Cana stock to 3")
        except Exception as e:
            print(f"Stock reset error: {e}")

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"RESULT: {passed} passed, {failed} failed (total {len(results)})")
    print("=" * 60)
    if failed:
        print("\nFAILED:")
        for name, ok, detail in results:
            if not ok:
                print(f"  ✗ {name} :: {detail}")
        sys.exit(1)
    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
