"""Backend tests for admin push notification broadcast endpoints.

Targets:
- POST /api/admin/notifications/send
- GET /api/admin/notifications/audience-stats
"""
import os
import re
import sys
import uuid
import json
import requests
from typing import Tuple, Optional

BASE_URL = "https://rental-routes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

results = []  # list of (ok, label, info)


def record(ok: bool, label: str, info: str = ""):
    results.append((ok, label, info))
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {label} {('- ' + info) if info else ''}")


def login(email: str, password: str) -> Tuple[Optional[str], Optional[dict]]:
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    if r.status_code != 200:
        return None, None
    data = r.json()
    return data.get("token"), data


def register(email: str, password: str, name: str) -> Tuple[Optional[str], Optional[dict]]:
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=20,
    )
    if r.status_code != 200:
        return None, None
    data = r.json()
    return data.get("token"), data


def headers(token: Optional[str]) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def main():
    print("=== Admin broadcast push notification tests ===")
    print(f"BASE_URL: {BASE_URL}")

    # ---- Login admin ----
    admin_token, admin_data = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        record(False, "admin login", "failed - cannot continue")
        print_summary()
        sys.exit(1)
    record(True, "admin login", f"role={admin_data.get('role')}")

    # ---- Register a fresh customer for audience filtering tests ----
    unique = uuid.uuid4().hex[:10]
    cust_email = f"carlos.{unique}@damstest.com"
    cust_password = "Customer@2026"
    cust_name = f"Carlos Test {unique[:4]}"
    cust_token, cust_data = register(cust_email, cust_password, cust_name)
    if not cust_token:
        record(False, "customer register", "failed")
        print_summary()
        sys.exit(1)
    cust_id = cust_data.get("id")
    record(True, "customer register", f"id={cust_id}, role={cust_data.get('role')}")

    # ---- 1) GET /api/admin/notifications/audience-stats ----
    r = requests.get(
        f"{BASE_URL}/admin/notifications/audience-stats", headers=headers(admin_token), timeout=20
    )
    record(r.status_code == 200, "audience-stats: admin 200", f"status={r.status_code}")
    if r.status_code == 200:
        stats = r.json()
        needed = ["total_users", "users_with_push", "customers_with_push", "admins_with_push"]
        for k in needed:
            record(k in stats, f"audience-stats: has key '{k}'", str(stats.get(k)))
            record(
                isinstance(stats.get(k), int) and stats.get(k) >= 0,
                f"audience-stats: '{k}' is non-negative int",
                str(stats.get(k)),
            )
        # admins_with_push + customers_with_push <= users_with_push
        try:
            record(
                stats["admins_with_push"] + stats["customers_with_push"] <= stats["users_with_push"],
                "audience-stats: admins+customers <= users_with_push",
                f"{stats['admins_with_push']}+{stats['customers_with_push']} vs {stats['users_with_push']}",
            )
        except Exception as e:
            record(False, "audience-stats: sum check", str(e))

    # Authorization on audience-stats
    r2 = requests.get(f"{BASE_URL}/admin/notifications/audience-stats", timeout=15)
    record(r2.status_code == 401, "audience-stats: unauthenticated → 401", f"got {r2.status_code}")
    r3 = requests.get(
        f"{BASE_URL}/admin/notifications/audience-stats", headers=headers(cust_token), timeout=15
    )
    record(r3.status_code == 403, "audience-stats: non-admin → 403", f"got {r3.status_code}")

    # ---- 2) POST /api/admin/notifications/send validation ----
    send_url = f"{BASE_URL}/admin/notifications/send"
    h_admin = headers(admin_token)

    # Empty title
    r = requests.post(send_url, json={"title": "", "body": "Hello", "target": "all"}, headers=h_admin, timeout=15)
    record(
        r.status_code == 400 and "Title and body are required" in r.text,
        "send: empty title → 400 'Title and body are required'",
        f"{r.status_code} {r.text[:120]}",
    )

    # Empty body
    r = requests.post(send_url, json={"title": "Hello", "body": "", "target": "all"}, headers=h_admin, timeout=15)
    record(
        r.status_code == 400 and "Title and body are required" in r.text,
        "send: empty body → 400 'Title and body are required'",
        f"{r.status_code} {r.text[:120]}",
    )

    # Title > 100
    long_title = "T" * 101
    r = requests.post(send_url, json={"title": long_title, "body": "Body", "target": "all"}, headers=h_admin, timeout=15)
    record(
        r.status_code == 400 and "Title must be" in r.text and "100" in r.text,
        "send: title > 100 chars → 400",
        f"{r.status_code} {r.text[:160]}",
    )

    # Body > 500
    long_body = "B" * 501
    r = requests.post(send_url, json={"title": "OK", "body": long_body, "target": "all"}, headers=h_admin, timeout=15)
    record(
        r.status_code == 400 and "Body must be" in r.text and "500" in r.text,
        "send: body > 500 chars → 400",
        f"{r.status_code} {r.text[:160]}",
    )

    # Target validation: garbage
    r = requests.post(
        send_url,
        json={"title": "Hi", "body": "There", "target": "garbage"},
        headers=h_admin,
        timeout=15,
    )
    record(
        r.status_code == 400 and "Invalid target" in r.text and "all" in r.text,
        "send: target='garbage' → 400 with helpful message",
        f"{r.status_code} {r.text[:200]}",
    )

    # Target: user:not-a-valid-id
    r = requests.post(
        send_url,
        json={"title": "Hi", "body": "There", "target": "user:not-a-valid-id"},
        headers=h_admin,
        timeout=15,
    )
    record(
        r.status_code == 400 and "Invalid user id" in r.text,
        "send: target='user:not-a-valid-id' → 400 'Invalid user id'",
        f"{r.status_code} {r.text[:160]}",
    )

    # Target: user:<valid-objectid> (existing customer)
    r = requests.post(
        send_url,
        json={"title": "Hi", "body": "There", "target": f"user:{cust_id}"},
        headers=h_admin,
        timeout=15,
    )
    record(
        r.status_code == 200,
        "send: target='user:<valid-objectid>' → 200",
        f"{r.status_code} {r.text[:240]}",
    )

    # Target: all → 200
    r = requests.post(send_url, json={"title": "Hi", "body": "All users hi", "target": "all"}, headers=h_admin, timeout=20)
    record(r.status_code == 200, "send: target='all' → 200", f"{r.status_code}")
    if r.status_code == 200:
        d = r.json()
        valid_shape = (
            isinstance(d.get("sent"), int)
            and isinstance(d.get("total_recipients"), int)
            and (isinstance(d.get("tokens_count"), int) or d.get("reason") == "no_tokens_in_audience")
        )
        record(valid_shape, "send: target='all' response shape", json.dumps(d))

    # Target: customers → 200
    r = requests.post(send_url, json={"title": "Hi", "body": "Customers hi", "target": "customers"}, headers=h_admin, timeout=20)
    record(r.status_code == 200, "send: target='customers' → 200", f"{r.status_code} {r.text[:160]}")
    customers_resp_no_token = r.json() if r.status_code == 200 else {}

    # Target: admins → 200
    r = requests.post(send_url, json={"title": "Hi", "body": "Admins hi", "target": "admins"}, headers=h_admin, timeout=20)
    record(r.status_code == 200, "send: target='admins' → 200", f"{r.status_code} {r.text[:160]}")

    # Default target (no target field) → all → 200
    r = requests.post(send_url, json={"title": "Hi", "body": "Default target"}, headers=h_admin, timeout=20)
    record(r.status_code == 200, "send: omitted target defaults to 'all' → 200", f"{r.status_code} {r.text[:160]}")

    # ---- Audience filtering: register a push token for the new customer ----
    push_token = f"ExponentPushToken[broadcast-test-{unique}]"
    r = requests.post(
        f"{BASE_URL}/users/push-token",
        json={"token": push_token, "platform": "ios"},
        headers=headers(cust_token),
        timeout=15,
    )
    record(r.status_code == 200, "customer registers push token", f"{r.status_code} {r.text[:120]}")

    # Now broadcast to customers → total_recipients should be >= 1 and include this user (we can't see ids but we can assert it grew)
    r_before = requests.post(send_url, json={"title": "Hi", "body": "Customers hi", "target": "customers"}, headers=h_admin, timeout=20)
    record(r_before.status_code == 200, "send: target='customers' after token registration → 200", f"{r_before.status_code}")
    cust_total = r_before.json().get("total_recipients") if r_before.status_code == 200 else None
    cust_tokens = r_before.json().get("tokens_count") if r_before.status_code == 200 else None
    record(
        isinstance(cust_total, int) and cust_total >= 1,
        "send: target='customers' total_recipients >= 1 after token registered",
        f"total_recipients={cust_total}, tokens_count={cust_tokens}",
    )
    # The customer's token should now be part of admins-broadcast audience? No — assert the customer is NOT in admins
    r_adm = requests.post(send_url, json={"title": "Hi", "body": "Admins hi", "target": "admins"}, headers=h_admin, timeout=20)
    record(r_adm.status_code == 200, "send: target='admins' (post token reg) → 200", f"{r_adm.status_code}")
    adm_resp = r_adm.json() if r_adm.status_code == 200 else {}
    # Subtle assertion: admins audience size should NOT include the test customer (we can't directly probe, but verify all admin tokens are <= admin user count from audience-stats)
    stats_r = requests.get(f"{BASE_URL}/admin/notifications/audience-stats", headers=h_admin, timeout=15)
    admins_with_push = stats_r.json().get("admins_with_push") if stats_r.status_code == 200 else None
    customers_with_push = stats_r.json().get("customers_with_push") if stats_r.status_code == 200 else None
    record(
        isinstance(admins_with_push, int) and adm_resp.get("total_recipients") == admins_with_push,
        "send: target='admins' total_recipients matches audience-stats admins_with_push",
        f"recipients={adm_resp.get('total_recipients')} stat={admins_with_push}",
    )
    record(
        isinstance(customers_with_push, int) and cust_total == customers_with_push,
        "send: target='customers' total_recipients matches audience-stats customers_with_push",
        f"recipients={cust_total} stat={customers_with_push}",
    )

    # Target user:<cust_id> after token registered → 200 with total_recipients=1
    r = requests.post(
        send_url,
        json={"title": "Hi", "body": "Single user", "target": f"user:{cust_id}"},
        headers=h_admin,
        timeout=15,
    )
    record(r.status_code == 200, "send: target='user:<cust_id>' (after token) → 200", f"{r.status_code} {r.text[:200]}")
    if r.status_code == 200:
        d = r.json()
        record(
            d.get("total_recipients") == 1,
            "send: target='user:<cust_id>' total_recipients == 1",
            json.dumps(d),
        )

    # ---- 3) Authorization on /admin/notifications/send ----
    r = requests.post(send_url, json={"title": "Hi", "body": "x", "target": "all"}, timeout=15)
    record(r.status_code == 401, "send: unauthenticated → 401", f"got {r.status_code}")

    r = requests.post(
        send_url,
        json={"title": "Hi", "body": "x", "target": "all"},
        headers=headers(cust_token),
        timeout=15,
    )
    record(r.status_code == 403, "send: non-admin → 403", f"got {r.status_code}")

    # Cleanup: delete the push token & customer (best-effort)
    requests.delete(
        f"{BASE_URL}/users/push-token",
        json={"token": push_token},
        headers=headers(cust_token),
        timeout=15,
    )

    print_summary()


def print_summary():
    print("\n=== SUMMARY ===")
    passed = sum(1 for ok, *_ in results if ok)
    total = len(results)
    print(f"{passed}/{total} assertions passed")
    fails = [r for r in results if not r[0]]
    if fails:
        print("\nFailures:")
        for ok, label, info in fails:
            print(f"  - {label} :: {info}")
    sys.exit(0 if passed == total else 2)


if __name__ == "__main__":
    main()
