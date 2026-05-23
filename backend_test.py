"""Tests for POST /api/admin/customers/{customer_id}/reset-password.

Covers:
  - Auth (unauth=401, customer=403)
  - Happy path + login flips (old=401, new=200)
  - Validation (short/empty/missing)
  - Bad id (invalid → 400, valid unknown ObjectId → 404)
  - Self-protection (admin -> own id → 400)
  - Side-effects (password_resets and login_attempts rows deleted)
  - Audit log line in backend stderr
"""
import os
import sys
import time
import secrets
import asyncio
import requests
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BACKEND = "https://rental-routes.preview.emergentagent.com"
API = BACKEND + "/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "test_database")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

PASS = []
FAIL = []


def check(cond, msg):
    if cond:
        PASS.append(msg)
        print(f"  PASS  {msg}")
    else:
        FAIL.append(msg)
        print(f"  FAIL  {msg}")


def login(email, password):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)


def H(token):
    return {"Authorization": f"Bearer {token}"}


async def main():
    print("=" * 70)
    print("Admin Reset Customer Password — endpoint tests")
    print("=" * 70)

    # [0] Admin login
    print("\n[0] Admin login")
    r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    check(r.status_code == 200, f"Admin login status=200 (got {r.status_code})")
    admin_token = r.json().get("token")
    check(bool(admin_token), "Admin token returned")
    me = requests.get(f"{API}/auth/me", headers=H(admin_token)).json()
    admin_id = me.get("id") or me.get("_id")
    check(bool(admin_id), f"Admin id resolved: {admin_id}")

    # [1] Register temp customer
    print("\n[1] Register temp customer")
    rnd = secrets.token_hex(4)
    cust_email = f"cust.pwreset.{rnd}@example.com"
    cust_password_old = "InitialPass#1"
    cust_password_new = "NewStrong#123"
    r = requests.post(f"{API}/auth/register", json={
        "email": cust_email,
        "password": cust_password_old,
        "name": "Patricia PwReset",
        "phone": "+18095559090",
        "terms_accepted": True,
    }, timeout=15)
    check(r.status_code == 200, f"Customer register status=200 (got {r.status_code} {r.text[:200]})")
    body = r.json()
    cust_token = body.get("token")
    cust_id = body.get("id")
    check(bool(cust_id), f"Customer id returned: {cust_id}")

    rr = login(cust_email, cust_password_old)
    check(rr.status_code == 200, f"Pre-reset login OLD password OK (status {rr.status_code})")

    # [2] Auth checks
    print("\n[2] Auth checks")
    r = requests.post(f"{API}/admin/customers/{cust_id}/reset-password",
                      json={"new_password": cust_password_new}, timeout=15)
    check(r.status_code == 401, f"Unauth -> 401 (got {r.status_code})")

    r = requests.post(f"{API}/admin/customers/{cust_id}/reset-password",
                      headers=H(cust_token),
                      json={"new_password": cust_password_new}, timeout=15)
    check(r.status_code == 403, f"Customer JWT -> 403 (got {r.status_code})")

    # [3] Validation
    print("\n[3] Validation")
    r = requests.post(f"{API}/admin/customers/{cust_id}/reset-password",
                      headers=H(admin_token),
                      json={"new_password": "shortpw"}, timeout=15)
    check(r.status_code == 400, f"new_password='shortpw' (7 chars) -> 400 (got {r.status_code})")
    check("at least 8" in (r.json().get("detail") or "").lower(),
          f"400 detail mentions 'at least 8' (got: {r.json().get('detail')})")

    r = requests.post(f"{API}/admin/customers/{cust_id}/reset-password",
                      headers=H(admin_token),
                      json={"new_password": ""}, timeout=15)
    check(r.status_code == 400, f"empty new_password -> 400 (got {r.status_code})")

    r = requests.post(f"{API}/admin/customers/{cust_id}/reset-password",
                      headers=H(admin_token),
                      json={}, timeout=15)
    check(r.status_code in (400, 422),
          f"missing new_password field -> 400/422 (got {r.status_code})")

    # [4] Bad id
    print("\n[4] Bad id")
    r = requests.post(f"{API}/admin/customers/abc/reset-password",
                      headers=H(admin_token),
                      json={"new_password": cust_password_new}, timeout=15)
    check(r.status_code == 400, f"customer_id='abc' -> 400 (got {r.status_code})")
    check("invalid customer id" in (r.json().get("detail") or "").lower(),
          f"detail mentions 'Invalid customer id' (got: {r.json().get('detail')})")

    unknown_oid = "0" * 24
    r = requests.post(f"{API}/admin/customers/{unknown_oid}/reset-password",
                      headers=H(admin_token),
                      json={"new_password": cust_password_new}, timeout=15)
    check(r.status_code == 404, f"unknown ObjectId -> 404 (got {r.status_code})")
    check("customer not found" in (r.json().get("detail") or "").lower(),
          f"detail mentions 'Customer not found' (got: {r.json().get('detail')})")

    # [5] Self-protection (admin -> own id)
    print("\n[5] Self-protection (admin -> own id)")
    r = requests.post(f"{API}/admin/customers/{admin_id}/reset-password",
                      headers=H(admin_token),
                      json={"new_password": "SomethingStrong#1"}, timeout=15)
    check(r.status_code == 400, f"admin -> own id -> 400 (got {r.status_code})")
    detail = (r.json().get("detail") or "").lower()
    check("/api/auth/change-password" in detail,
          f"detail points to /api/auth/change-password (got: {r.json().get('detail')})")

    # [6] Seed side-effect rows
    print("\n[6] Seed side-effect rows (password_resets + login_attempts)")
    await db.password_resets.insert_one({
        "email": cust_email,
        "code_hash": "$2b$12$dummyhashfortest" + "x" * 30,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
        "attempts": 0,
        "used": False,
        "_test_marker": True,
    })
    await db.login_attempts.insert_one({
        "email": cust_email,
        "count": 3,
        "locked_until": None,
        "_test_marker": True,
    })

    pre_resets = await db.password_resets.count_documents({"email": cust_email})
    pre_attempts = await db.login_attempts.count_documents({"email": cust_email})
    check(pre_resets >= 1, f"Seeded password_resets row exists pre-call (count={pre_resets})")
    check(pre_attempts >= 1, f"Seeded login_attempts row exists pre-call (count={pre_attempts})")

    # Capture backend stderr offset BEFORE happy-path
    log_path = "/var/log/supervisor/backend.err.log"
    log_size_before = 0
    try:
        log_size_before = os.path.getsize(log_path)
    except OSError:
        pass

    # [7] Happy path
    print("\n[7] Happy path: admin resets customer password")
    r = requests.post(f"{API}/admin/customers/{cust_id}/reset-password",
                      headers=H(admin_token),
                      json={"new_password": cust_password_new}, timeout=15)
    check(r.status_code == 200, f"Happy path status=200 (got {r.status_code} {r.text[:200]})")
    body = r.json()
    check(body.get("ok") is True, f"ok=True (got {body.get('ok')})")
    check(body.get("customer_id") == cust_id, f"customer_id echoed (got {body.get('customer_id')})")
    check(body.get("email") == cust_email, f"email echoed (got {body.get('email')})")
    check(body.get("name") == "Patricia PwReset", f"name echoed (got {body.get('name')})")
    pwd_at = body.get("password_updated_at")
    check(isinstance(pwd_at, str) and pwd_at.startswith("20"),
          f"password_updated_at ISO string (got {pwd_at})")
    try:
        parsed = datetime.fromisoformat(pwd_at.replace("Z", "+00:00"))
        check(parsed.tzinfo is not None, "password_updated_at is tz-aware ISO")
    except Exception as e:
        check(False, f"password_updated_at parses as ISO: {e}")

    # [8] Login flips
    print("\n[8] Login flips after reset")
    r_old = login(cust_email, cust_password_old)
    check(r_old.status_code == 401, f"Login with OLD password -> 401 (got {r_old.status_code})")
    r_new = login(cust_email, cust_password_new)
    check(r_new.status_code == 200, f"Login with NEW password -> 200 (got {r_new.status_code})")
    check(bool(r_new.json().get("token")), "NEW-password login returns token")

    # [9] Side-effects post-call
    print("\n[9] Verify side-effects rows are GONE")
    post_resets = await db.password_resets.count_documents({"email": cust_email})
    post_attempts = await db.login_attempts.count_documents({"email": cust_email})
    check(post_resets == 0,
          f"password_resets rows for {cust_email} are gone (post count={post_resets})")
    check(post_attempts == 0,
          f"login_attempts rows for {cust_email} are gone (post count={post_attempts})")

    # [10] Audit log
    print("\n[10] Audit log line in backend stderr")
    time.sleep(0.5)
    found_audit = False
    new_log_chunk = ""
    try:
        with open(log_path, "rb") as fh:
            fh.seek(log_size_before)
            new_log_chunk = fh.read().decode("utf-8", errors="replace")
        expected = f"reset password for customer {cust_email}"
        found_audit = expected in new_log_chunk
    except OSError as e:
        new_log_chunk = f"<could not read log: {e}>"
    check(found_audit,
          f"Audit log contains 'reset password for customer {cust_email}'"
          f"{'' if found_audit else ' -- sample tail: ' + new_log_chunk[-400:]}")

    # CLEANUP
    print("\n[CLEANUP] Removing temp test user + leftover marker rows")
    res_u = await db.users.delete_one({"email": cust_email})
    print(f"  users.delete_one({cust_email}) -> deleted_count={res_u.deleted_count}")
    res_pr = await db.password_resets.delete_many({"_test_marker": True})
    print(f"  password_resets._test_marker -> deleted_count={res_pr.deleted_count}")
    res_la = await db.login_attempts.delete_many({"_test_marker": True})
    print(f"  login_attempts._test_marker -> deleted_count={res_la.deleted_count}")
    res_pr2 = await db.password_resets.delete_many({"email": cust_email})
    res_la2 = await db.login_attempts.delete_many({"email": cust_email})
    print(f"  defensive password_resets cleanup -> {res_pr2.deleted_count}")
    print(f"  defensive login_attempts cleanup -> {res_la2.deleted_count}")

    print("\n[SANITY] Admin login still works with original password")
    r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    check(r.status_code == 200, f"Admin login still 200 after tests (got {r.status_code})")

    print("\n" + "=" * 70)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailed assertions:")
        for f in FAIL:
            print(f"  - {f}")
    print("=" * 70)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
