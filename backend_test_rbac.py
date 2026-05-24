#!/usr/bin/env python3
"""
Backend tests for the Multi-Admin RBAC system.

Covers:
  (1) Auth / permission shape on new endpoints
  (2) Preset role POST -> permissions resolution
  (3) Custom permissions override preset
  (4) Permission gating on sensitive endpoints
  (5) Self-protection safeguards
  (6) Audit log writes + GET /admin/audit-log shape
  (7) GET /admin/permissions shape
  (8) Revoke flow
  (9) Cleanup
"""
import os
import sys
import time
import json
import random
import string
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = "http://localhost:8001"
API = f"{BASE_URL}/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

mc = MongoClient(MONGO_URL)
db = mc[DB_NAME]

PASSED = 0
FAILED = 0
FAIL_DETAILS = []

# Track temp resources for cleanup
TEMP_USER_IDS = []          # ObjectId list - users (admins or regular) to delete
TEMP_USER_EMAILS = []       # emails to scrub
TEMP_BOOKING_IDS = []
TEMP_CAR_IDS = []
TEMP_AUDIT_FILTERS = []     # additional filters for cleanup of audit_log entries created during this test

def assertion(cond, label, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ✅ {label}")
    else:
        FAILED += 1
        msg = f"  ❌ {label}{(' :: ' + detail) if detail else ''}"
        print(msg)
        FAIL_DETAILS.append(msg)


def rand_suffix(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    return r


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def register_customer(email, password, name="Test User"):
    r = requests.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": password,
            "name": name,
            "phone": "+18095550000",
            "terms_accepted": True,
        },
        timeout=20,
    )
    return r


# ---------------------------------------------------------------------------
# Section 1 — Auth / permission shape
# ---------------------------------------------------------------------------
print("\n=== Section 1: Auth/permission shape on new endpoints ===")

# Admin login
r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
assertion(r.status_code == 200, "Legacy super admin login", f"status={r.status_code} body={r.text[:200]}")
admin_token = r.json().get("token") or r.json().get("access_token")
assertion(bool(admin_token), "Admin token present")
admin_h = auth_headers(admin_token)

# Get admin id via /admin/me
r = requests.get(f"{API}/admin/me", headers=admin_h, timeout=20)
assertion(r.status_code == 200, "GET /admin/me (legacy admin) -> 200", f"status={r.status_code} body={r.text[:200]}")
me = r.json() if r.status_code == 200 else {}
ADMIN_ID = me.get("id")
assertion(bool(ADMIN_ID), "Legacy admin id present in /admin/me")
assertion(me.get("email") == ADMIN_EMAIL, "Email matches in /admin/me")
assertion(me.get("is_super_admin") is True, "is_super_admin == True for legacy admin")
perms = me.get("permissions") or []
assertion(isinstance(perms, list) and len(perms) == 25, f"permissions list has 25 entries (got {len(perms)})")
assertion("admins.manage" in perms, "permissions contains 'admins.manage'")
assertion("audit.view" in perms, "permissions contains 'audit.view'")
assertion("bookings.bulk_cancel" in perms, "permissions contains 'bookings.bulk_cancel'")

# Ensure legacy admin doc still has NO 'permissions' field set in DB (no accidental write)
admin_doc = db.users.find_one({"email": ADMIN_EMAIL})
assertion(admin_doc is not None, "Legacy admin doc exists in DB")
assertion("permissions" not in admin_doc or admin_doc.get("permissions") is None,
          "Legacy admin still has NO 'permissions' field (fallback works without DB write)",
          f"got permissions={admin_doc.get('permissions')!r}")

# Register a regular user
reg_email = f"rbac.regular.{rand_suffix()}@example.com"
r = register_customer(reg_email, "RegularPass#1", name="Regular Tester")
assertion(r.status_code == 200, f"Register regular user {reg_email}", f"status={r.status_code} body={r.text[:200]}")
reg_token = r.json().get("token")
reg_h = auth_headers(reg_token)
reg_doc = db.users.find_one({"email": reg_email})
if reg_doc:
    TEMP_USER_IDS.append(reg_doc["_id"])
    TEMP_USER_EMAILS.append(reg_email)

# Endpoint matrix for unauth / regular-user / admin
ENDPOINT_MATRIX = [
    ("GET", "/admin/me"),
    ("GET", "/admin/permissions"),
    ("GET", "/admin/admins"),
    ("POST", "/admin/admins"),
    # PUT/DELETE on /admin/admins/{id} need a real id — use legacy admin id
    ("PUT", f"/admin/admins/{ADMIN_ID}"),
    ("DELETE", f"/admin/admins/{ADMIN_ID}"),
    ("GET", "/admin/audit-log"),
]

print("\n-- Unauthenticated -> 401 on all new endpoints --")
for method, path in ENDPOINT_MATRIX:
    r = requests.request(method, f"{API}{path}", timeout=20, json={} if method in ("POST", "PUT") else None)
    assertion(r.status_code == 401, f"UNAUTH {method} {path} -> 401", f"got {r.status_code}: {r.text[:120]}")

print("\n-- Regular user -> 403 on all new endpoints --")
for method, path in ENDPOINT_MATRIX:
    r = requests.request(method, f"{API}{path}", headers=reg_h, timeout=20,
                        json={} if method in ("POST", "PUT") else None)
    assertion(r.status_code == 403, f"REGULAR {method} {path} -> 403", f"got {r.status_code}: {r.text[:120]}")

print("\n-- Legacy super admin -> 200 on read endpoints --")
for method, path in [("GET", "/admin/me"), ("GET", "/admin/permissions"),
                     ("GET", "/admin/admins"), ("GET", "/admin/audit-log")]:
    r = requests.request(method, f"{API}{path}", headers=admin_h, timeout=20)
    assertion(r.status_code == 200, f"ADMIN {method} {path} -> 200", f"got {r.status_code}: {r.text[:120]}")


# ---------------------------------------------------------------------------
# Section 7 — GET /admin/permissions shape (test before creating admins so list is stable)
# ---------------------------------------------------------------------------
print("\n=== Section 7: GET /admin/permissions shape ===")
r = requests.get(f"{API}/admin/permissions", headers=admin_h, timeout=20)
assertion(r.status_code == 200, "GET /admin/permissions -> 200", f"got {r.status_code}")
data = r.json()
assertion(isinstance(data.get("permissions"), list) and len(data["permissions"]) == 25,
          f"permissions list length 25 (got {len(data.get('permissions') or [])})")
perm_keys = [p["key"] for p in data["permissions"]]
assertion(all(isinstance(p.get("key"), str) and isinstance(p.get("description"), str)
              for p in data["permissions"]),
          "Each permission has key+description")
assertion(isinstance(data.get("roles"), list) and len(data["roles"]) == 4,
          f"roles list length 4 (got {len(data.get('roles') or [])})")
roles_by_key = {r["key"]: r for r in data["roles"]}
assertion(set(roles_by_key.keys()) == {"super_admin", "manager", "front_desk", "read_only"},
          f"role keys are super_admin/manager/front_desk/read_only (got {list(roles_by_key.keys())})")
super_role = roles_by_key.get("super_admin") or {}
super_perms = super_role.get("permissions") or []
assertion(len(super_perms) == 25, f"super_admin role permissions length 25 (got {len(super_perms)})")
assertion("admins.manage" in super_perms, "super_admin contains admins.manage")
assertion("audit.view" in super_perms, "super_admin contains audit.view")

PRESET_MANAGER = roles_by_key["manager"]["permissions"]
PRESET_FRONT_DESK = roles_by_key["front_desk"]["permissions"]
PRESET_READ_ONLY = roles_by_key["read_only"]["permissions"]
print(f"   preset sizes: manager={len(PRESET_MANAGER)} front_desk={len(PRESET_FRONT_DESK)} read_only={len(PRESET_READ_ONLY)}")


# ---------------------------------------------------------------------------
# Section 2 — Preset role POST -> permissions resolution
# ---------------------------------------------------------------------------
print("\n=== Section 2: Preset role POST creates admin with correct preset perms ===")
created_admins = {}  # role_key -> {id, email, password, token}

for role_key, preset_perms in [
    ("manager", PRESET_MANAGER),
    ("front_desk", PRESET_FRONT_DESK),
    ("read_only", PRESET_READ_ONLY),
]:
    email = f"rbac.{role_key}.{rand_suffix()}@example.com"
    pwd = "TestPwd123!"
    payload = {"email": email, "name": f"RBAC {role_key} Tester", "password": pwd,
               "phone": "+18095559999", "admin_role": role_key}
    r = requests.post(f"{API}/admin/admins", headers=admin_h, json=payload, timeout=20)
    assertion(r.status_code in (200, 201), f"POST /admin/admins admin_role={role_key} -> 200",
              f"status={r.status_code} body={r.text[:200]}")
    if r.status_code in (200, 201):
        body = r.json()
        new_id = body.get("id")
        assertion(bool(new_id), f"{role_key}: response.id present")
        assertion(body.get("admin_role") == role_key, f"{role_key}: response.admin_role == {role_key}")
        assertion(set(body.get("permissions") or []) == set(preset_perms),
                  f"{role_key}: response.permissions exactly matches preset")

        # Verify DB
        doc = db.users.find_one({"_id": ObjectId(new_id)})
        assertion(doc is not None, f"{role_key}: doc exists in users")
        if doc:
            assertion(doc.get("role") == "admin", f"{role_key}: role=='admin'")
            assertion(doc.get("admin_role") == role_key, f"{role_key}: admin_role stored as preset")
            assertion(set(doc.get("permissions") or []) == set(preset_perms),
                      f"{role_key}: permissions in DB match preset exactly")
            TEMP_USER_IDS.append(doc["_id"])
            TEMP_USER_EMAILS.append(email)

        # Login flow
        lr = login(email, pwd)
        assertion(lr.status_code == 200, f"{role_key}: login succeeds with new password",
                  f"status={lr.status_code} body={lr.text[:200]}")
        tok = lr.json().get("token") if lr.status_code == 200 else None
        created_admins[role_key] = {"id": new_id, "email": email, "password": pwd, "token": tok}


# ---------------------------------------------------------------------------
# Section 3 — Custom permissions override preset
# ---------------------------------------------------------------------------
print("\n=== Section 3: Custom permissions override preset ===")
custom_email = f"rbac.custom.{rand_suffix()}@example.com"
payload = {
    "email": custom_email,
    "name": "RBAC Custom Tester",
    "password": "CustomPwd123!",
    "admin_role": "manager",                       # preset
    "permissions": ["bookings.view", "cars.view"], # override
}
r = requests.post(f"{API}/admin/admins", headers=admin_h, json=payload, timeout=20)
assertion(r.status_code in (200, 201), "POST /admin/admins with custom permissions -> 200",
          f"status={r.status_code} body={r.text[:200]}")
if r.status_code in (200, 201):
    body = r.json()
    custom_id = body.get("id")
    assertion(set(body.get("permissions") or []) == {"bookings.view", "cars.view"},
              "Response.permissions == [bookings.view, cars.view]")
    assertion(body.get("admin_role") == "custom",
              f"Response.admin_role == 'custom' (got {body.get('admin_role')!r})")
    if custom_id:
        doc = db.users.find_one({"_id": ObjectId(custom_id)})
        if doc:
            TEMP_USER_IDS.append(doc["_id"])
            TEMP_USER_EMAILS.append(custom_email)
            assertion(doc.get("admin_role") == "custom", "DB admin_role == 'custom'")
            assertion(set(doc.get("permissions") or []) == {"bookings.view", "cars.view"},
                      "DB permissions == {bookings.view, cars.view}")


# ---------------------------------------------------------------------------
# Section 4 — Permission gating on sensitive endpoints
# ---------------------------------------------------------------------------
print("\n=== Section 4: Permission gating on sensitive endpoints ===")
front_desk_token = (created_admins.get("front_desk") or {}).get("token")
manager_token = (created_admins.get("manager") or {}).get("token")
assertion(bool(front_desk_token), "front_desk admin token available")
assertion(bool(manager_token), "manager admin token available")

if front_desk_token:
    fd_h = auth_headers(front_desk_token)

    # bookings.bulk_cancel
    r = requests.post(f"{API}/admin/bookings/cancel-pending-pickups",
                      headers=fd_h, json={"dry_run": True}, timeout=20)
    assertion(r.status_code == 403, "front_desk POST cancel-pending-pickups -> 403",
              f"got {r.status_code}: {r.text[:200]}")
    assertion("bookings.bulk_cancel" in r.text or "Missing permission" in r.text,
              "403 mentions missing permission",
              f"body={r.text[:200]}")

    # customers.reset_password (need a target customer id — use the regular user)
    reg_user = db.users.find_one({"email": reg_email})
    target_cust_id = str(reg_user["_id"]) if reg_user else "000000000000000000000000"
    r = requests.post(f"{API}/admin/customers/{target_cust_id}/reset-password",
                      headers=fd_h, json={"new_password": "NewPassword#1"}, timeout=20)
    assertion(r.status_code == 403,
              "front_desk POST customers/{id}/reset-password -> 403",
              f"got {r.status_code}: {r.text[:200]}")

    # cars.delete - find a car id (use a real one but don't actually delete because of 403)
    cars_resp = requests.get(f"{API}/cars", timeout=20).json()
    car_id = cars_resp[0]["id"] if cars_resp else None
    if car_id:
        r = requests.delete(f"{API}/cars/{car_id}", headers=fd_h, timeout=20)
        assertion(r.status_code == 403, "front_desk DELETE /cars/{id} -> 403",
                  f"got {r.status_code}: {r.text[:200]}")
    else:
        assertion(False, "Found at least one car to test DELETE gating")

if manager_token:
    mgr_h = auth_headers(manager_token)
    # manager has bookings.bulk_cancel - call with dry_run-like payload (endpoint accepts no body)
    r = requests.post(f"{API}/admin/bookings/cancel-pending-pickups",
                      headers=mgr_h, json={"dry_run": True}, timeout=20)
    assertion(r.status_code == 200, "manager POST cancel-pending-pickups -> 200 (has bookings.bulk_cancel)",
              f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        body = r.json()
        assertion("cancelled_count" in body and "matched_count" in body and "sample" in body,
                  "Response has cancelled_count/matched_count/sample keys")


# ---------------------------------------------------------------------------
# Section 5 — Self-protection safeguards
# ---------------------------------------------------------------------------
print("\n=== Section 5: Self-protection safeguards ===")

# 5a) Legacy super admin tries to strip own admins.manage
r = requests.put(f"{API}/admin/admins/{ADMIN_ID}", headers=admin_h,
                 json={"permissions": ["bookings.view"]}, timeout=20)
assertion(r.status_code == 400, "PUT self with permissions lacking admins.manage -> 400",
          f"got {r.status_code}: {r.text[:200]}")
detail = ""
try:
    detail = r.json().get("detail", "")
except Exception:
    pass
assertion("admins.manage" in detail.lower() or "own" in detail.lower(),
          f"400 detail mentions own admins.manage (got {detail[:200]!r})")

# 5b) Create a 2nd super admin, demote it to manager, then try to revoke / demote legacy
second_super_email = f"rbac.super2.{rand_suffix()}@example.com"
r = requests.post(f"{API}/admin/admins", headers=admin_h, json={
    "email": second_super_email,
    "name": "RBAC Second Super",
    "password": "Super2Pwd!23",
    "admin_role": "super_admin",
}, timeout=20)
assertion(r.status_code in (200, 201), "Create 2nd super admin -> 200",
          f"status={r.status_code} body={r.text[:200]}")
second_super_id = None
if r.status_code in (200, 201):
    second_super_id = r.json().get("id")
    if second_super_id:
        TEMP_USER_IDS.append(ObjectId(second_super_id))
        TEMP_USER_EMAILS.append(second_super_email)
    doc = db.users.find_one({"_id": ObjectId(second_super_id)})
    assertion(doc and "admins.manage" in (doc.get("permissions") or []),
              "2nd super has admins.manage in DB")

    # Demote second super to manager
    r2 = requests.put(f"{API}/admin/admins/{second_super_id}", headers=admin_h,
                      json={"admin_role": "manager"}, timeout=20)
    assertion(r2.status_code == 200, "Demote 2nd super to manager -> 200",
              f"got {r2.status_code}: {r2.text[:200]}")
    doc2 = db.users.find_one({"_id": ObjectId(second_super_id)})
    if doc2:
        assertion(doc2.get("admin_role") == "manager", "2nd super now admin_role=='manager'")
        assertion("admins.manage" not in (doc2.get("permissions") or []),
                  "2nd super no longer has admins.manage")

# 5c) Now legacy is sole super -> try DELETE on legacy super
r = requests.delete(f"{API}/admin/admins/{ADMIN_ID}", headers=admin_h, timeout=20)
assertion(r.status_code == 400, "DELETE legacy super (self) -> 400",
          f"got {r.status_code}: {r.text[:200]}")
try:
    d = r.json().get("detail", "")
except Exception:
    d = ""
assertion("revoke yourself" in d.lower() or "cannot" in d.lower(),
          f"DELETE-self detail mentions cannot revoke yourself (got {d[:200]!r})")

# 5d) PUT legacy super to remove admins.manage -> last-super guard (also self -> 400)
# (Already covered in 5a, but try again now that 2nd super is demoted)
r = requests.put(f"{API}/admin/admins/{ADMIN_ID}", headers=admin_h,
                 json={"permissions": ["bookings.view", "cars.view"]}, timeout=20)
assertion(r.status_code == 400, "PUT legacy super removing admins.manage -> 400 (self/last-super)",
          f"got {r.status_code}: {r.text[:200]}")


# ---------------------------------------------------------------------------
# Section 6 — Audit log writes
# ---------------------------------------------------------------------------
print("\n=== Section 6: Audit log writes ===")

# Create a temporary car as the legacy admin so we can test the audit `car.delete` action
# (cars.delete is gated by `cars.delete` permission)
new_car_payload = {
    "name": f"RBAC Test Car {rand_suffix(4).upper()}",
    "brand": "Test",
    "category": "Compact",
    "transmission": "automatic",
    "seats": 4,
    "fuel_type": "petrol",
    "price_per_day": 30,
    "image_url": "",
    "stock": {},
}
r = requests.post(f"{API}/cars", headers=admin_h, json=new_car_payload, timeout=20)
test_car_id = None
if r.status_code == 200:
    test_car_id = r.json().get("id")
    print(f"   created temp car id={test_car_id}")
else:
    print(f"   ! could not create temp car: {r.status_code} {r.text[:200]}")

if test_car_id:
    r = requests.delete(f"{API}/cars/{test_car_id}", headers=admin_h, timeout=20)
    assertion(r.status_code == 200, "Admin DELETE /cars/{id} -> 200 (has cars.delete)",
              f"got {r.status_code}: {r.text[:200]}")

# Check audit_log directly via DB
time.sleep(0.3)
audit_rows = list(db.audit_log.find({}).sort("created_at", -1).limit(50))
recent_actions = [r.get("action") for r in audit_rows]
print(f"   recent audit actions (last 50): {recent_actions[:15]}...")

assertion("admin.create" in recent_actions, "audit_log has admin.create entries")
assertion("admin.update" in recent_actions, "audit_log has admin.update entries")
# admin.revoke we haven't done yet — will check in section 8
assertion("car.delete" in recent_actions, "audit_log has car.delete entry")

# Check actor_email
create_rows = [r for r in audit_rows if r.get("action") == "admin.create"]
assertion(any(r.get("actor_email") == ADMIN_EMAIL for r in create_rows),
          "audit_log admin.create rows have actor_email == legacy admin")

# GET /admin/audit-log
r = requests.get(f"{API}/admin/audit-log?limit=10", headers=admin_h, timeout=20)
assertion(r.status_code == 200, "GET /admin/audit-log?limit=10 -> 200",
          f"got {r.status_code}: {r.text[:200]}")
rows = r.json() if r.status_code == 200 else []
assertion(isinstance(rows, list) and len(rows) > 0, f"audit-log returned >0 rows (got {len(rows)})")
assertion(len(rows) <= 10, f"audit-log respects limit=10 (got {len(rows)})")
if rows:
    expected_keys = {"id", "actor_id", "actor_email", "action", "target", "meta", "ip", "created_at"}
    sample = rows[0]
    missing = expected_keys - set(sample.keys())
    assertion(not missing, f"audit-log row has all expected keys (missing: {missing})",
              f"sample keys: {sorted(sample.keys())}")

# Filter by action
r = requests.get(f"{API}/admin/audit-log?action=admin.create&limit=20", headers=admin_h, timeout=20)
assertion(r.status_code == 200, "GET /admin/audit-log?action=admin.create -> 200")
filt = r.json() if r.status_code == 200 else []
assertion(all(row.get("action") == "admin.create" for row in filt),
          "Filter action=admin.create returns only admin.create rows")


# ---------------------------------------------------------------------------
# Section 8 — Revoke flow
# ---------------------------------------------------------------------------
print("\n=== Section 8: Revoke (DELETE /admin/admins/{id}) ===")
# Create a fresh temp admin
temp_email = f"rbac.revoke.{rand_suffix()}@example.com"
temp_pwd = "RevokeMe123!"
r = requests.post(f"{API}/admin/admins", headers=admin_h, json={
    "email": temp_email, "name": "RBAC Revoke Tester",
    "password": temp_pwd, "admin_role": "manager",
}, timeout=20)
assertion(r.status_code in (200, 201), "Create temp admin to revoke -> 200")
temp_id = r.json().get("id") if r.status_code in (200, 201) else None
if temp_id:
    TEMP_USER_IDS.append(ObjectId(temp_id))
    TEMP_USER_EMAILS.append(temp_email)

# login first (so we have a valid pre-revoke token)
lr = login(temp_email, temp_pwd)
assertion(lr.status_code == 200, "Login temp admin pre-revoke")
temp_tok = lr.json().get("token") if lr.status_code == 200 else None

# DELETE it
r = requests.delete(f"{API}/admin/admins/{temp_id}", headers=admin_h, timeout=20)
assertion(r.status_code == 200, "DELETE temp admin -> 200",
          f"got {r.status_code}: {r.text[:200]}")
assertion(r.json().get("ok") is True, "DELETE response ok==True")

# Verify DB state - role=='user', no permissions, no admin_role
doc = db.users.find_one({"_id": ObjectId(temp_id)})
assertion(doc is not None, "Revoked user still exists in DB (downgraded, not deleted)")
if doc:
    assertion(doc.get("role") == "user", f"role=='user' after revoke (got {doc.get('role')!r})")
    assertion("permissions" not in doc,
              f"'permissions' field unset after revoke (got {doc.get('permissions')!r})")
    assertion("admin_role" not in doc,
              f"'admin_role' field unset after revoke (got {doc.get('admin_role')!r})")

# Verify revoked user cannot call admin endpoints
if temp_tok:
    t_h = auth_headers(temp_tok)
    r = requests.get(f"{API}/admin/me", headers=t_h, timeout=20)
    assertion(r.status_code in (401, 403), f"Revoked user GET /admin/me -> 401/403 (got {r.status_code})")
    r = requests.get(f"{API}/admin/admins", headers=t_h, timeout=20)
    assertion(r.status_code in (401, 403), f"Revoked user GET /admin/admins -> 401/403 (got {r.status_code})")

# Verify audit.revoke entry created
time.sleep(0.3)
revoke_rows = list(db.audit_log.find({"action": "admin.revoke"}).sort("created_at", -1).limit(5))
assertion(any(r.get("target") == temp_id for r in revoke_rows),
          f"audit_log has admin.revoke entry with target={temp_id}")
assertion(any(r.get("actor_email") == ADMIN_EMAIL for r in revoke_rows),
          "audit_log admin.revoke rows have actor_email == legacy admin")


# ---------------------------------------------------------------------------
# Section 9 — Cleanup
# ---------------------------------------------------------------------------
print("\n=== Section 9: Cleanup ===")
# Delete all temp users
to_delete = set(TEMP_USER_IDS)
for uid in to_delete:
    res = db.users.delete_one({"_id": uid})
    print(f"   deleted user _id={uid} count={res.deleted_count}")

# Scrub any orphan emails (idempotent)
for em in set(TEMP_USER_EMAILS):
    db.users.delete_many({"email": em})

# Verify legacy admin untouched
admin_doc_after = db.users.find_one({"email": ADMIN_EMAIL})
assertion(admin_doc_after is not None, "Seed admin@damscarrental.com still present")
if admin_doc_after:
    assertion(admin_doc_after.get("role") == "admin", "Seed admin role still 'admin'")
    assertion(admin_doc_after.get("permissions") in (None, [], False) or "permissions" not in admin_doc_after,
              f"Seed admin still has NO explicit permissions field after test (got {admin_doc_after.get('permissions')!r})")

# Legacy admin login still works
r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
assertion(r.status_code == 200, "Legacy admin login still works post-cleanup")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 60}")
print(f"RESULTS: {PASSED} passed, {FAILED} failed (total {PASSED + FAILED})")
print(f"{'=' * 60}")
if FAILED:
    print("\nFAILED ASSERTIONS:")
    for d in FAIL_DETAILS:
        print(d)
    sys.exit(1)
print("\n🎉 All RBAC assertions passed.")
sys.exit(0)
