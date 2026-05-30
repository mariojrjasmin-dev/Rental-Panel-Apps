"""Backend test for new geocode + SSO migration endpoints + regressions."""
import os
import sys
import json
import requests

BASE = "https://rental-routes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASS = "Admin@123"

passed = 0
failed = 0
failures = []


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        failures.append(f"{name}: {detail}")
        print(f"  FAIL: {name} -- {detail}")


def admin_login():
    r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    if r.status_code != 200:
        print(f"Admin login FAILED: {r.status_code} {r.text}")
        sys.exit(1)
    return r.json()["token"]


def auth_headers(t):
    return {"Authorization": f"Bearer {t}"}


print("\n=== TEST 1: GET /api/admin/geocode ===")
token = admin_login()

# 1a) without auth
r = requests.get(f"{BASE}/admin/geocode", params={"q": "Punta Cana Airport"}, timeout=20)
check("1a no-auth → 401", r.status_code == 401, f"got {r.status_code} body={r.text[:200]}")

# 1b) admin token, full query
r = requests.get(
    f"{BASE}/admin/geocode",
    params={"q": "Aeropuerto Internacional de Punta Cana", "country": "Dominican Republic"},
    headers=auth_headers(token),
    timeout=30,
)
print(f"  1b status={r.status_code} body={r.text[:400]}")
if r.status_code == 200:
    body = r.json()
    check("1b ok=true", body.get("ok") is True)
    lat = body.get("lat")
    lng = body.get("lng")
    check("1b lat ~ 18.5", isinstance(lat, float) and 18.0 < lat < 19.0, f"lat={lat}")
    check("1b lng ~ -68.3", isinstance(lng, float) and -69.0 < lng < -68.0, f"lng={lng}")
    check("1b has display_name", bool(body.get("display_name")))
    check("1b has query", bool(body.get("query")))
    check("1b lat/lng floats (1f)", isinstance(lat, float) and isinstance(lng, float))
else:
    check("1b 200 status", False, f"got {r.status_code} body={r.text[:200]}")

# 1c) Santo Domingo via city+country
r = requests.get(
    f"{BASE}/admin/geocode",
    params={"city": "Santo Domingo", "country": "Dominican Republic"},
    headers=auth_headers(token),
    timeout=30,
)
print(f"  1c status={r.status_code} body={r.text[:300]}")
if r.status_code == 200:
    body = r.json()
    check("1c ok=true", body.get("ok") is True)
    check("1c lat ~ 18.4", isinstance(body.get("lat"), float) and 18.0 < body["lat"] < 19.0, f"lat={body.get('lat')}")
    check("1c lng ~ -69.8", isinstance(body.get("lng"), float) and -70.5 < body["lng"] < -69.0, f"lng={body.get('lng')}")
else:
    check("1c 200 status", False, f"got {r.status_code} body={r.text[:200]}")

# 1d) empty q/city/country
r = requests.get(f"{BASE}/admin/geocode", headers=auth_headers(token), timeout=20)
check("1d empty params → 400", r.status_code == 400, f"got {r.status_code}")
if r.status_code == 400:
    detail = r.json().get("detail", "")
    check("1d detail contains 'address'", "address" in detail.lower() or "provide" in detail.lower(), f"detail={detail!r}")

# 1e) nonexistent place
r = requests.get(
    f"{BASE}/admin/geocode",
    params={"q": "zzzzznonexistentplace1234567890zzzz"},
    headers=auth_headers(token),
    timeout=30,
)
print(f"  1e status={r.status_code} body={r.text[:300]}")
check("1e nonexistent → 404", r.status_code == 404, f"got {r.status_code}")
if r.status_code == 404:
    detail = r.json().get("detail", "")
    check("1e detail mentions 'No coordinates found'", "no coordinates found" in detail.lower(), f"detail={detail!r}")

print("\n=== TEST 2: POST /api/admin/migrate-sso-users ===")

# 2a) without auth
r = requests.post(f"{BASE}/admin/migrate-sso-users", json={"dry_run": True}, timeout=20)
check("2a no-auth → 401", r.status_code == 401, f"got {r.status_code} body={r.text[:200]}")

# 2b) dry_run=true
r = requests.post(
    f"{BASE}/admin/migrate-sso-users",
    json={"dry_run": True},
    headers=auth_headers(token),
    timeout=30,
)
print(f"  2b status={r.status_code} body={r.text[:400]}")
if r.status_code == 200:
    body = r.json()
    check("2b ok=true", body.get("ok") is True)
    check("2b dry_run=true", body.get("dry_run") is True)
    check("2b has scanned (int)", isinstance(body.get("scanned"), int), f"scanned={body.get('scanned')}")
    check("2b emailed=0", body.get("emailed") == 0)
    check("2b has skipped (int)", isinstance(body.get("skipped"), int))
    check("2b has errors (int)", isinstance(body.get("errors"), int))
    check("2b has users list", isinstance(body.get("users"), list))
else:
    check("2b 200 status", False, f"got {r.status_code} body={r.text[:200]}")

# 2c) dry_run with provider filter
r = requests.post(
    f"{BASE}/admin/migrate-sso-users",
    json={"dry_run": True, "providers": ["apple"]},
    headers=auth_headers(token),
    timeout=30,
)
print(f"  2c status={r.status_code} body={r.text[:300]}")
if r.status_code == 200:
    body = r.json()
    check("2c ok=true", body.get("ok") is True)
    check("2c dry_run=true", body.get("dry_run") is True)
    check("2c users all have provider=apple or list empty",
          all(u.get("provider") == "apple" for u in body.get("users", [])),
          f"users={body.get('users')}")
else:
    check("2c 200 status", False, f"got {r.status_code} body={r.text[:200]}")

# 2d) dry_run=false (real send) — but there are likely 0 SSO users so this should not crash
r = requests.post(
    f"{BASE}/admin/migrate-sso-users",
    json={"dry_run": False},
    headers=auth_headers(token),
    timeout=60,
)
print(f"  2d status={r.status_code} body={r.text[:400]}")
if r.status_code == 200:
    body = r.json()
    check("2d ok=true", body.get("ok") is True)
    check("2d dry_run=false", body.get("dry_run") is False or body.get("dry_run") is None)
    check("2d has scanned (int)", isinstance(body.get("scanned"), int))
    check("2d has emailed (int)", isinstance(body.get("emailed"), int))
    check("2d does not crash with 0 SSO users", True)
else:
    check("2d 200 status", False, f"got {r.status_code} body={r.text[:300]}")

print("\n=== TEST 3: Regression — existing endpoints ===")

# 3a) GET /api/cars
r = requests.get(f"{BASE}/cars", timeout=20)
check("3a GET /cars → 200", r.status_code == 200, f"got {r.status_code}")

# 3b) admin login (already done above, redo to confirm)
r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
check("3b POST /auth/login admin → 200", r.status_code == 200, f"got {r.status_code} body={r.text[:200]}")
if r.status_code == 200:
    check("3b login has token", bool(r.json().get("token")))

# 3c) GET /api/locations
r = requests.get(f"{BASE}/locations", timeout=20)
check("3c GET /locations → 200", r.status_code == 200, f"got {r.status_code}")
if r.status_code == 200:
    check("3c locations is array", isinstance(r.json(), list))

# 3d) forgot-password with random email
r = requests.post(f"{BASE}/auth/forgot-password",
                  json={"email": "nosuchuser_zzz999@example.com"},
                  timeout=20)
check("3d forgot-password random email → 200", r.status_code == 200, f"got {r.status_code} body={r.text[:200]}")

print("\n=== TEST 4: Apple Sign-In endpoint exists ===")

r = requests.post(f"{BASE}/auth/apple", json={"identity_token": "invalid"}, timeout=20)
print(f"  4 status={r.status_code} body={r.text[:300]}")
check("4 /auth/apple with invalid token → 400 or 401", r.status_code in (400, 401),
      f"got {r.status_code} body={r.text[:200]}")

print("\n" + "=" * 60)
print(f"RESULTS: {passed} PASSED, {failed} FAILED")
if failures:
    print("\nFAILURES:")
    for f in failures:
        print(f"  - {f}")
sys.exit(0 if failed == 0 else 1)
