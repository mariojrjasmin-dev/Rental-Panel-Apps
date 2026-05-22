"""
Backend tests for:
  - POST /api/auth/forgot-password
  - POST /api/auth/reset-password
  - POST /api/auth/register (now requires terms_accepted=true)
  - Regression checks (login, bookings, rental-terms)
"""
import os
import sys
import uuid
import bcrypt
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from bson import ObjectId

BASE = "https://rental-routes.preview.emergentagent.com/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"
CUSTOMER_EMAIL = "customer@damscarrental.com"
CUSTOMER_PASSWORD = "Customer@123"

assertions_passed = 0
assertions_failed = 0
failures = []
created_user_emails = []
reset_emails_touched = set()


def OK(label):
    global assertions_passed
    assertions_passed += 1
    print(f"  PASS  {label}")


def FAIL(label, extra=""):
    global assertions_failed
    assertions_failed += 1
    failures.append(f"{label} :: {extra}")
    print(f"  FAIL  {label}  -- {extra}")


def check(cond, label, extra=""):
    if cond:
        OK(label)
    else:
        FAIL(label, extra)


def section(name):
    print(f"\n=== {name} ===")


def rand_email(prefix="testuser"):
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com"


def login(email, password):
    return requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)


def register(payload):
    return requests.post(f"{BASE}/auth/register", json=payload, timeout=30)


def insert_reset_record(email, code="123456", minutes_from_now=10):
    code_hash = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    db.password_resets.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "code_hash": code_hash,
            "expires_at": expires_at,
            "attempts": 0,
            "used": False,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    reset_emails_touched.add(email)


def register_temp_user():
    email = rand_email("alice.tester")
    pwd = "InitialPass#1"
    r = register({"email": email, "password": pwd, "name": "Alice Tester", "terms_accepted": True})
    if r.status_code != 200:
        print(f"  register_temp_user failed: {r.status_code} {r.text[:200]}")
        return None, None
    created_user_emails.append(email)
    return email, pwd


# ===== A =====
def test_A_forgot_password():
    section("A. POST /api/auth/forgot-password")
    r = requests.post(f"{BASE}/auth/forgot-password", json={"email": CUSTOMER_EMAIL}, timeout=30)
    check(r.status_code == 200, "A1 status=200 valid email", f"got {r.status_code} body={r.text[:200]}")
    j = r.json() if r.status_code == 200 else {}
    check(j.get("ok") is True, "A1 ok:true")
    check("If an account exists" in (j.get("message") or ""),
          "A1 message contains 'If an account exists...'", f"got {j.get('message')!r}")
    reset_emails_touched.add(CUSTOMER_EMAIL)

    rec = db.password_resets.find_one({"email": CUSTOMER_EMAIL})
    check(rec is not None, "A5 password_resets doc exists for customer")
    if rec:
        ch = rec.get("code_hash") or ""
        check(isinstance(ch, str) and ch.startswith(("$2b$", "$2a$", "$2y$")),
              "A5 code_hash bcrypt-shaped", f"prefix={ch[:4]!r}")
        ea = rec.get("expires_at")
        if isinstance(ea, datetime):
            if ea.tzinfo is None:
                ea = ea.replace(tzinfo=timezone.utc)
            delta = (ea - datetime.now(timezone.utc)).total_seconds()
            check(13 * 60 < delta < 16 * 60, "A5 expires_at ~15 min in future", f"delta={delta:.1f}s")
        else:
            FAIL("A5 expires_at is datetime", f"got {type(ea)}")
        check(int(rec.get("attempts", -1)) == 0, "A5 attempts=0")
        check(rec.get("used") is False, "A5 used=false")

    # A2 unknown email
    unknown = f"nosuchuser_{uuid.uuid4().hex[:8]}@example.com"
    before = db.password_resets.count_documents({"email": unknown})
    r = requests.post(f"{BASE}/auth/forgot-password", json={"email": unknown}, timeout=30)
    check(r.status_code == 200, "A2 status=200 unknown email")
    j = r.json() if r.status_code == 200 else {}
    check(j.get("ok") is True, "A2 ok:true")
    check("If an account exists" in (j.get("message") or ""), "A2 same generic message")
    after = db.password_resets.count_documents({"email": unknown})
    check(after == before, "A2 no DB record created for unknown email")

    # A3 malformed
    r = requests.post(f"{BASE}/auth/forgot-password", json={"email": "notanemail"}, timeout=30)
    check(r.status_code == 400, "A3 malformed email → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("email" in d, "A3 detail mentions email", f"got {d!r}")

    # A4
    r1 = requests.post(f"{BASE}/auth/forgot-password", json={"email": ""}, timeout=30)
    check(r1.status_code == 400, "A4 empty email → 400", f"got {r1.status_code}")
    r2 = requests.post(f"{BASE}/auth/forgot-password", json={}, timeout=30)
    check(r2.status_code in (400, 422), "A4 missing email → 400/422", f"got {r2.status_code}")


# ===== B =====
def test_B_reset_password():
    section("B. POST /api/auth/reset-password")
    email, original_pwd = register_temp_user()
    check(email is not None, "B1 setup: temp user registered with terms_accepted=true")
    if not email:
        return
    insert_reset_record(email, code="123456", minutes_from_now=10)
    new_pwd = "NewStrong#1"
    r = requests.post(f"{BASE}/auth/reset-password",
                      json={"email": email, "code": "123456", "new_password": new_pwd}, timeout=30)
    check(r.status_code == 200, "B1 reset with correct code → 200", f"got {r.status_code} body={r.text[:200]}")
    if r.status_code == 200:
        check(r.json().get("ok") is True, "B1 ok:true")
    rL = login(email, new_pwd)
    check(rL.status_code == 200, "B1a login with NewStrong#1 → 200", f"got {rL.status_code}")
    if rL.status_code == 200:
        check(bool(rL.json().get("token")), "B1a token returned")
    rL2 = login(email, original_pwd)
    check(rL2.status_code == 401, "B1b login with OLD password → 401", f"got {rL2.status_code}")
    rec = db.password_resets.find_one({"email": email})
    check(rec is not None and rec.get("used") is True, "B1c reset record used=true")
    rR = requests.post(f"{BASE}/auth/reset-password",
                       json={"email": email, "code": "123456", "new_password": "AnotherPass#9"}, timeout=30)
    check(rR.status_code == 400, "B1d reuse code → 400", f"got {rR.status_code}")
    if rR.status_code == 400:
        d = (rR.json().get("detail") or "").lower()
        check("invalid" in d or "expired" in d, "B1d detail mentions invalid/expired", f"got {d!r}")

    # B2
    email2, _ = register_temp_user()
    insert_reset_record(email2, code="654321", minutes_from_now=10)
    r = requests.post(f"{BASE}/auth/reset-password",
                      json={"email": email2, "code": "000000", "new_password": "WhateverX#9"}, timeout=30)
    check(r.status_code == 400, "B2 wrong code → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("incorrect" in d, "B2 detail 'incorrect'", f"got {d!r}")
    rec = db.password_resets.find_one({"email": email2})
    check(rec is not None and int(rec.get("attempts", 0)) == 1, "B2 attempts incremented to 1",
          f"got {rec.get('attempts') if rec else None}")

    # B3
    email3, _ = register_temp_user()
    insert_reset_record(email3, code="111111", minutes_from_now=10)
    last_status, last_detail = None, None
    for i in range(5):
        r = requests.post(f"{BASE}/auth/reset-password",
                          json={"email": email3, "code": "000000", "new_password": "WhateverX#9"}, timeout=30)
        last_status = r.status_code
        try:
            last_detail = r.json().get("detail")
        except Exception:
            last_detail = None
    check(last_status in (400, 429), "B3 5th attempt is 400 or 429",
          f"got {last_status} detail={last_detail!r}")
    r_after = requests.post(f"{BASE}/auth/reset-password",
                            json={"email": email3, "code": "111111", "new_password": "WhateverX#9"}, timeout=30)
    check(r_after.status_code in (400, 429),
          "B3 subsequent attempt → 400/429", f"got {r_after.status_code}")
    if r_after.status_code == 400:
        d = (r_after.json().get("detail") or "").lower()
        check("invalid" in d or "expired" in d or "incorrect" in d,
              "B3 follow-up detail mentions invalid/expired", f"got {d!r}")
    rec_final = db.password_resets.find_one({"email": email3})
    check(rec_final is None, "B3 record deleted after threshold", f"still present: {rec_final}")

    # B4
    email4, _ = register_temp_user()
    code_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode("utf-8")
    db.password_resets.update_one(
        {"email": email4},
        {"$set": {
            "email": email4, "code_hash": code_hash,
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "attempts": 0, "used": False,
            "created_at": datetime.now(timezone.utc),
        }}, upsert=True,
    )
    reset_emails_touched.add(email4)
    r = requests.post(f"{BASE}/auth/reset-password",
                      json={"email": email4, "code": "123456", "new_password": "WhateverX#9"}, timeout=30)
    check(r.status_code == 400, "B4 expired code → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("expired" in d, "B4 detail mentions 'expired'", f"got {d!r}")
    rec = db.password_resets.find_one({"email": email4})
    check(rec is None, "B4 expired record was deleted")

    # B5
    email5, _ = register_temp_user()
    insert_reset_record(email5, code="222222", minutes_from_now=10)
    r = requests.post(f"{BASE}/auth/reset-password",
                      json={"email": email5, "code": "abcdef", "new_password": "Validpw#1"}, timeout=30)
    check(r.status_code == 400, "B5 non-digit code 'abcdef' → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("6 digit" in d or "must be 6" in d, "B5 detail '6 digits'", f"got {d!r}")
    r = requests.post(f"{BASE}/auth/reset-password",
                      json={"email": email5, "code": "123", "new_password": "Validpw#1"}, timeout=30)
    check(r.status_code == 400, "B5 short code '123' → 400", f"got {r.status_code}")
    r = requests.post(f"{BASE}/auth/reset-password",
                      json={"email": email5, "code": "222222", "new_password": "abc"}, timeout=30)
    check(r.status_code == 400, "B5 short password → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("6 character" in d or "at least 6" in d, "B5 detail '6 characters'", f"got {d!r}")
    for missing in [
        {"code": "222222", "new_password": "Validpw#1"},
        {"email": email5, "new_password": "Validpw#1"},
        {"email": email5, "code": "222222"},
        {"email": "", "code": "222222", "new_password": "Validpw#1"},
    ]:
        r = requests.post(f"{BASE}/auth/reset-password", json=missing, timeout=30)
        check(r.status_code in (400, 422), f"B5 missing field {list(missing.keys())} → 400/422",
              f"got {r.status_code}")


# ===== C =====
def test_C_register():
    section("C. POST /api/auth/register (terms_accepted required)")
    email = rand_email("bob.refusal")
    r = register({"email": email, "password": "Strong#Pw1", "name": "Bob Refusal", "terms_accepted": False})
    check(r.status_code == 400, "C1 terms_accepted=false → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("rental terms" in d or "accept" in d, "C1 detail mentions 'Rental Terms' or 'accept'",
              f"got {d!r}")
    u = db.users.find_one({"email": email})
    check(u is None, "C1 NO user created with terms_accepted=false")

    email_ok = rand_email("carla.signup")
    payload = {
        "email": email_ok, "password": "Strong#Pw1",
        "name": "Carla Signup", "phone": "+18095551234", "terms_accepted": True,
    }
    r = register(payload)
    check(r.status_code == 200, "C2 register with terms_accepted=true → 200",
          f"got {r.status_code} body={r.text[:200]}")
    if r.status_code == 200:
        created_user_emails.append(email_ok)
        j = r.json()
        for k in ["id", "email", "name", "role", "token"]:
            check(k in j, f"C2 response has '{k}'")
        check(j.get("role") == "user", "C2 role='user'")
        check(j.get("email") == email_ok.lower(), "C2 email matches")
    u = db.users.find_one({"email": email_ok.lower()})
    check(u is not None, "C2 user exists in DB")
    if u:
        ta = u.get("terms_accepted_at")
        check(isinstance(ta, datetime), "C2 terms_accepted_at is datetime",
              f"got type={type(ta)}")
        if isinstance(ta, datetime):
            if ta.tzinfo is None:
                ta = ta.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ta).total_seconds()
            check(0 <= age < 120, "C2 terms_accepted_at is recent", f"age={age:.1f}s")
        check(u.get("phone") == "+18095551234", "C2 phone stored", f"got {u.get('phone')!r}")
        check(u.get("role") == "user", "C2 role='user' in DB")
        ph = u.get("password_hash") or ""
        check(isinstance(ph, str) and ph.startswith(("$2b$", "$2a$", "$2y$")),
              "C2 password_hash bcrypt-shaped", f"prefix={ph[:4]!r}")
        check(u.get("password") != "Strong#Pw1", "C2 raw password not stored")
        check(isinstance(u.get("created_at"), datetime), "C2 created_at is datetime")

    r = register({"email": rand_email(), "password": "Strong#Pw1", "name": "", "terms_accepted": True})
    check(r.status_code == 400, "C3 empty name → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("name" in d, "C3 detail mentions 'name'", f"got {d!r}")

    r = register({"email": rand_email(), "password": "abc", "name": "Short Pw", "terms_accepted": True})
    check(r.status_code == 400, "C4 short password → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("6 character" in d or "at least 6" in d, "C4 detail '6 characters'", f"got {d!r}")

    r = register({"email": CUSTOMER_EMAIL, "password": "WhateverPw#1", "name": "Dup",
                  "terms_accepted": True})
    check(r.status_code == 400, "C5 duplicate email → 400", f"got {r.status_code}")
    if r.status_code == 400:
        d = (r.json().get("detail") or "").lower()
        check("already" in d, "C5 detail 'already registered'", f"got {d!r}")

    rL = login(email_ok, "Strong#Pw1")
    check(rL.status_code == 200, "C6 login with new account → 200", f"got {rL.status_code}")
    if rL.status_code == 200:
        check(bool(rL.json().get("token")), "C6 token returned")


# ===== D =====
def test_D_regression():
    section("D. Regression (login / bookings / rental-terms)")
    r = login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    check(r.status_code == 200, "D1 customer login still works",
          f"got {r.status_code} body={r.text[:200]}")
    cust_token = r.json().get("token") if r.status_code == 200 else None

    r = requests.get(f"{BASE}/settings/rental-terms", timeout=30)
    check(r.status_code == 200, "D3 GET /api/settings/rental-terms public → 200",
          f"got {r.status_code}")
    j = r.json() if r.status_code == 200 else {}
    check(isinstance(j.get("terms"), str) and len(j.get("terms") or "") > 10,
          "D3 returns terms string")

    if not cust_token:
        return
    headers = {"Authorization": f"Bearer {cust_token}"}
    rc = requests.get(f"{BASE}/cars", timeout=30)
    if rc.status_code != 200 or not rc.json():
        FAIL("D2 setup cars list", f"status={rc.status_code}")
        return
    car = rc.json()[0]
    car_id = car["id"]
    if car.get("pickup_location") and car["pickup_location"].get("name"):
        loc = {"name": car["pickup_location"]["name"],
               "city": car["pickup_location"].get("city", "")}
    else:
        loc = {"name": "Punta Cana Airport", "city": "Punta Cana"}

    pickup = datetime.now(timezone.utc) + timedelta(days=14)
    dropoff = pickup + timedelta(days=10)
    body = {
        "car_id": car_id,
        "pickup_date": pickup.isoformat(),
        "dropoff_date": dropoff.isoformat(),
        "pickup_location": loc, "dropoff_location": loc,
        "payment_method": "cash",
        "refuel_opted_in": False,
        "terms_accepted": True,
    }
    rb = requests.post(f"{BASE}/bookings", headers=headers, json=body, timeout=30)
    check(rb.status_code == 200, "D2 POST /api/bookings (terms_accepted=true) → 200",
          f"got {rb.status_code} body={rb.text[:300]}")
    booking_id = None
    if rb.status_code == 200:
        bj = rb.json()
        booking_id = bj.get("id")
        check(bj.get("status") == "pending_payment", "D2 status=pending_payment")
        check(bj.get("payment_status") == "pending", "D2 payment_status=pending")

    body_bad = {**body, "terms_accepted": False}
    rb2 = requests.post(f"{BASE}/bookings", headers=headers, json=body_bad, timeout=30)
    check(rb2.status_code == 400, "D2 booking with terms_accepted=false → 400 (regression)",
          f"got {rb2.status_code}")
    if booking_id:
        try:
            db.bookings.delete_one({"_id": ObjectId(booking_id)})
        except Exception:
            pass


def cleanup():
    section("CLEANUP")
    n_users = 0
    for em in created_user_emails:
        try:
            r = db.users.delete_one({"email": em.lower()})
            n_users += r.deleted_count
        except Exception as e:
            print(f"  cleanup user {em}: {e}")
    print(f"  Deleted {n_users} temp test user(s).")
    n_pr = 0
    for em in reset_emails_touched:
        try:
            r = db.password_resets.delete_many({"email": em.lower()})
            n_pr += r.deleted_count
        except Exception as e:
            print(f"  cleanup pr {em}: {e}")
    print(f"  Deleted {n_pr} password_resets doc(s).")
    r = login(CUSTOMER_EMAIL, CUSTOMER_PASSWORD)
    if r.status_code == 200:
        print("  Customer password intact (login OK).")
    else:
        print(f"  WARNING: customer login {r.status_code} — restoring password directly.")
        user = db.users.find_one({"email": CUSTOMER_EMAIL})
        if user:
            new_hash = bcrypt.hashpw(CUSTOMER_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": new_hash}})


def main():
    print(f"Testing against: {BASE}")
    test_A_forgot_password()
    test_B_reset_password()
    test_C_register()
    test_D_regression()
    cleanup()
    print("\n========== SUMMARY ==========")
    print(f"Passed: {assertions_passed}")
    print(f"Failed: {assertions_failed}")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
    sys.exit(0 if assertions_failed == 0 else 1)


if __name__ == "__main__":
    main()
