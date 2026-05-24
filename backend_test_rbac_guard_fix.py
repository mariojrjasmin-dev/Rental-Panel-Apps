"""Focused test for last-super-admin guard fix (§5) + audit log (§6).

Verifies:
(A) Legacy admin DB doc has explicit permissions+admin_role after migration.
(B) GET /api/admin/me returns is_super_admin:true and 25 perms.
(C) Demote-2nd-super flow now returns 200; demoting the only remaining super → 400.
(D) Self-protection still works (own admins.manage removal, DELETE self).
(E) Audit log entry for admin.update with admin_role + permissions fields.
(F) Cleanup the temp 2nd admin and reverify legacy admin intact.
"""

import os
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId

BASE = "http://localhost:8001"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"
ALL_PERMS_COUNT = 25

mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
db = mongo[os.environ.get("DB_NAME", "test_database")]

passed = 0
failed = 0
fail_msgs = []


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {msg}")
    else:
        failed += 1
        fail_msgs.append(msg)
        print(f"  ❌ {msg}")


def login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def hdr(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


print("=" * 80)
print("§A — Confirm migration ran on legacy admin")
print("=" * 80)
legacy_doc = db.users.find_one({"email": ADMIN_EMAIL})
assert legacy_doc, "Legacy admin not found in DB"
legacy_id = str(legacy_doc["_id"])
perms = legacy_doc.get("permissions")
check(isinstance(perms, list), "legacy admin .permissions is a list")
check(isinstance(perms, list) and len(perms) == ALL_PERMS_COUNT,
      f"legacy admin .permissions length is {ALL_PERMS_COUNT} (got {len(perms) if isinstance(perms, list) else None})")
check(isinstance(perms, list) and "admins.manage" in perms, "legacy admin .permissions contains 'admins.manage'")
check(legacy_doc.get("admin_role") == "super_admin",
      f"legacy admin .admin_role == 'super_admin' (got {legacy_doc.get('admin_role')!r})")

print()
print("=" * 80)
print("§B — GET /api/admin/me for legacy admin")
print("=" * 80)
admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
r = requests.get(f"{BASE}/api/admin/me", headers=hdr(admin_token), timeout=15)
check(r.status_code == 200, f"/api/admin/me returns 200 (got {r.status_code})")
me = r.json()
check(me.get("is_super_admin") is True, f"/api/admin/me.is_super_admin == True (got {me.get('is_super_admin')!r})")
check(isinstance(me.get("permissions"), list) and len(me["permissions"]) == ALL_PERMS_COUNT,
      f"/api/admin/me.permissions length == 25 (got {len(me.get('permissions') or [])})")
check("admins.manage" in (me.get("permissions") or []), "/api/admin/me.permissions contains 'admins.manage'")

print()
print("=" * 80)
print("§C — Last-super-admin guard fix (the previously failing flow)")
print("=" * 80)
# Use unique email
rand_suffix = datetime.now(timezone.utc).strftime("%H%M%S%f")
second_email = f"second.super.{rand_suffix}@damstest.com"
print(f"  -> Creating 2nd super admin: {second_email}")
r = requests.post(
    f"{BASE}/api/admin/admins",
    headers=hdr(admin_token),
    json={
        "email": second_email,
        "name": "Sofia Mendez",
        "password": "ChangeMe123!",
        "admin_role": "super_admin",
    },
    timeout=15,
)
check(r.status_code in (200, 201), f"POST /api/admin/admins (super_admin) -> {r.status_code} (expected 200/201). Body: {r.text[:300]}")
created = r.json() if r.status_code in (200, 201) else {}
second_id = created.get("id")
check(bool(second_id), f"2nd super has id (got {second_id!r})")
check(created.get("admin_role") == "super_admin", f"2nd super admin_role=='super_admin' (got {created.get('admin_role')!r})")
created_perms = created.get("permissions") or []
check(len(created_perms) == ALL_PERMS_COUNT, f"2nd super .permissions length == 25 (got {len(created_perms)})")

# C.2 — As legacy admin, demote 2nd super to manager → must now return 200
print(f"  -> Demoting 2nd super to manager (PUT /api/admin/admins/{second_id})")
r = requests.put(
    f"{BASE}/api/admin/admins/{second_id}",
    headers=hdr(admin_token),
    json={"admin_role": "manager"},
    timeout=15,
)
check(r.status_code == 200, f"Demote 2nd super to manager -> 200 (got {r.status_code}). Body: {r.text[:300]}")
demote_resp = r.json() if r.status_code == 200 else {}
check("admin_role" in (demote_resp.get("updated_fields") or []), "demote response.updated_fields contains 'admin_role'")
check("permissions" in (demote_resp.get("updated_fields") or []), "demote response.updated_fields contains 'permissions'")

# C.3 — DB verification
demote_ts = datetime.now(timezone.utc)
doc2 = db.users.find_one({"_id": ObjectId(second_id)})
check(doc2 and doc2.get("admin_role") == "manager", f"DB: 2nd admin admin_role == 'manager' (got {doc2.get('admin_role') if doc2 else None})")
# Check manager preset perms
mgr_perms_resp = requests.get(f"{BASE}/api/admin/permissions", headers=hdr(admin_token), timeout=10).json()
mgr_preset = next((r["permissions"] for r in mgr_perms_resp.get("roles", []) if r.get("key") == "manager"), None)
if mgr_preset is None:
    # Try different shape
    mgr_preset = (mgr_perms_resp.get("roles", {}) or {}).get("manager", {}).get("permissions") if isinstance(mgr_perms_resp.get("roles"), dict) else None
check(mgr_preset is not None, f"Found manager preset in /admin/permissions (got {mgr_preset is not None})")
if mgr_preset is not None and doc2:
    db_perms = sorted(doc2.get("permissions") or [])
    expected = sorted(mgr_preset)
    check(db_perms == expected, f"DB: 2nd admin perms match manager preset (db={len(db_perms)} vs preset={len(expected)})")
    check("admins.manage" not in (doc2.get("permissions") or []), "DB: 2nd admin no longer has 'admins.manage'")

# C.4 — Try to demote the legacy admin (the only super now) → must 400
print(f"  -> Attempting to demote legacy admin (last super) — should 400")
r = requests.put(
    f"{BASE}/api/admin/admins/{legacy_id}",
    headers=hdr(admin_token),
    json={"admin_role": "manager"},
    timeout=15,
)
check(r.status_code == 400, f"Demote legacy (last super) -> 400 (got {r.status_code}). Body: {r.text[:300]}")
det = (r.json() or {}).get("detail", "") if r.status_code == 400 else ""
check("last super" in det.lower() or "super admin" in det.lower(),
      f"400 detail mentions last super admin (got {det!r})")

print()
print("=" * 80)
print("§D — Self-protection guards still work")
print("=" * 80)
# D.1 — Remove own admins.manage via permissions[]
r = requests.put(
    f"{BASE}/api/admin/admins/{legacy_id}",
    headers=hdr(admin_token),
    json={"permissions": ["bookings.view"]},
    timeout=15,
)
check(r.status_code == 400, f"PUT legacy {{'permissions':['bookings.view']}} -> 400 (got {r.status_code})")
det = (r.json() or {}).get("detail", "") if r.status_code == 400 else ""
check("admins.manage" in det.lower() or "own" in det.lower(),
      f"400 detail mentions removing own admins.manage permission (got {det!r})")

# D.2 — DELETE self
r = requests.delete(f"{BASE}/api/admin/admins/{legacy_id}", headers=hdr(admin_token), timeout=15)
check(r.status_code == 400, f"DELETE self -> 400 (got {r.status_code})")
det = (r.json() or {}).get("detail", "") if r.status_code == 400 else ""
check("revoke yourself" in det.lower() or "cannot revoke" in det.lower(),
      f"DELETE self detail says 'cannot revoke yourself' (got {det!r})")

print()
print("=" * 80)
print("§E — Audit log entry for the successful demote")
print("=" * 80)
r = requests.get(f"{BASE}/api/admin/audit-log?action=admin.update&limit=20", headers=hdr(admin_token), timeout=15)
check(r.status_code == 200, f"GET /api/admin/audit-log?action=admin.update -> 200 (got {r.status_code})")
log_resp = r.json() if r.status_code == 200 else []
if isinstance(log_resp, list):
    entries = log_resp
elif isinstance(log_resp, dict):
    entries = (log_resp.get("entries") or log_resp.get("audit_log")
               or log_resp.get("items") or log_resp.get("log")
               or log_resp.get("data") or log_resp.get("results") or [])
else:
    entries = []
check(isinstance(entries, list) and len(entries) > 0, f"audit-log has entries (count={len(entries) if isinstance(entries, list) else 'N/A'})")

# Find the one matching the 2nd admin update
matching = [
    e for e in (entries or [])
    if e.get("action") == "admin.update" and str(e.get("target") or "") == str(second_id)
]
check(len(matching) >= 1, f"Found admin.update entry targeting 2nd admin id={second_id} (matches={len(matching)})")
if matching:
    entry = matching[0]
    check(entry.get("actor_email") == ADMIN_EMAIL,
          f"actor_email == '{ADMIN_EMAIL}' (got {entry.get('actor_email')!r})")
    meta = entry.get("meta") or {}
    fields = meta.get("fields") or []
    check("admin_role" in fields, f"meta.fields contains 'admin_role' (got fields={fields})")
    check("permissions" in fields, f"meta.fields contains 'permissions' (got fields={fields})")

print()
print("=" * 80)
print("§F — Cleanup: delete the temp 2nd admin")
print("=" * 80)
r = requests.delete(f"{BASE}/api/admin/admins/{second_id}", headers=hdr(admin_token), timeout=15)
check(r.status_code == 200, f"DELETE temp 2nd admin -> 200 (got {r.status_code}). Body: {r.text[:200]}")

# Verify revoked
doc2_after = db.users.find_one({"_id": ObjectId(second_id)})
if doc2_after:
    check(doc2_after.get("role") == "user", f"After revoke: role downgraded to 'user' (got {doc2_after.get('role')!r})")
else:
    check(False, "After revoke: 2nd admin still exists in DB")

# Hard-delete the temp user (cleanup beyond the API)
db.users.delete_one({"_id": ObjectId(second_id)})
print(f"  -> Hard-deleted temp user from db.users")

# Verify legacy admin is still intact
legacy_after = db.users.find_one({"email": ADMIN_EMAIL})
check(legacy_after is not None, "legacy admin doc still exists")
check(legacy_after.get("role") == "admin", f"legacy admin role still 'admin' (got {legacy_after.get('role')!r})")
check(legacy_after.get("admin_role") == "super_admin",
      f"legacy admin admin_role still 'super_admin' (got {legacy_after.get('admin_role')!r})")
lperms = legacy_after.get("permissions") or []
check(isinstance(lperms, list) and len(lperms) == ALL_PERMS_COUNT,
      f"legacy admin .permissions length still 25 (got {len(lperms)})")
check("admins.manage" in lperms, "legacy admin .permissions still contains 'admins.manage'")

# Sanity: legacy admin can still log in
admin_token2 = login(ADMIN_EMAIL, ADMIN_PASSWORD)
r = requests.get(f"{BASE}/api/admin/me", headers=hdr(admin_token2), timeout=15)
check(r.status_code == 200 and r.json().get("is_super_admin") is True,
      "post-cleanup login: /admin/me still is_super_admin=true")

print()
print("=" * 80)
print(f"RESULT: {passed} passed, {failed} failed")
print("=" * 80)
if failed:
    print("Failures:")
    for m in fail_msgs:
        print(f"  - {m}")
    raise SystemExit(1)
