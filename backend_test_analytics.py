"""Tests for GET /api/admin/analytics fleet analytics endpoint."""
import os
import sys
import time
import requests
from datetime import datetime, timezone

BACKEND_URL = os.environ.get(
    "BACKEND_URL", "https://rental-routes.preview.emergentagent.com"
)
API = f"{BACKEND_URL}/api"

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

results = []  # list[(ok: bool, msg: str)]

def check(cond, msg):
    results.append((bool(cond), msg))
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {msg}")


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    print(f"Using backend: {API}")

    # 1) Login admin
    admin = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_token = admin["token"]
    check(admin.get("role") == "admin", f"Admin login returns role=admin (got {admin.get('role')})")

    # 2) Call analytics as admin
    r = requests.get(f"{API}/admin/analytics", headers=auth_headers(admin_token), timeout=30)
    check(r.status_code == 200, f"GET /api/admin/analytics as admin returns 200 (got {r.status_code} body={r.text[:200]})")
    if r.status_code != 200:
        finalize()
        return
    data = r.json()

    # 3) Top-level keys
    expected_keys = {"kpis", "monthly_revenue", "top_cars", "top_locations", "status_breakdown", "payment_breakdown"}
    missing = expected_keys - set(data.keys())
    check(not missing, f"Top-level keys present (missing: {missing})")

    # 4) kpis structure
    kpis = data.get("kpis", {})
    kpi_keys = {"total_revenue", "revenue_this_month", "total_bookings", "paid_bookings", "active_bookings", "avg_revenue_per_booking"}
    kpi_missing = kpi_keys - set(kpis.keys())
    check(not kpi_missing, f"kpis has all required keys (missing: {kpi_missing})")
    for k in kpi_keys:
        v = kpis.get(k)
        check(isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.{k} is numeric (got {type(v).__name__}={v})")
        if isinstance(v, (int, float)):
            check(v >= 0, f"kpis.{k} >= 0 (got {v})")

    # 5) monthly_revenue list of exactly 6
    mr = data.get("monthly_revenue")
    check(isinstance(mr, list), f"monthly_revenue is list (got {type(mr).__name__})")
    if isinstance(mr, list):
        check(len(mr) == 6, f"monthly_revenue has exactly 6 items (got {len(mr)})")
        # Each item shape
        for i, item in enumerate(mr):
            check(isinstance(item, dict), f"monthly_revenue[{i}] is dict")
            if isinstance(item, dict):
                check(set(["month", "revenue", "count"]).issubset(item.keys()), f"monthly_revenue[{i}] has keys month/revenue/count")
                month = item.get("month")
                check(isinstance(month, str) and len(month) == 7 and month[4] == "-",
                      f"monthly_revenue[{i}].month is 'YYYY-MM' string (got {month!r})")
                # Validate format strictly
                try:
                    datetime.strptime(month, "%Y-%m")
                    fmt_ok = True
                except Exception:
                    fmt_ok = False
                check(fmt_ok, f"monthly_revenue[{i}].month parses as YYYY-MM ({month!r})")
                check(isinstance(item.get("revenue"), (int, float)) and not isinstance(item.get("revenue"), bool),
                      f"monthly_revenue[{i}].revenue is numeric (got {item.get('revenue')!r})")
                check(isinstance(item.get("count"), int) and not isinstance(item.get("count"), bool),
                      f"monthly_revenue[{i}].count is int (got {item.get('count')!r})")
                check((item.get("revenue") or 0) >= 0, f"monthly_revenue[{i}].revenue >= 0")
                check((item.get("count") or 0) >= 0, f"monthly_revenue[{i}].count >= 0")

        # chronological order
        months = [it.get("month") for it in mr if isinstance(it, dict)]
        sorted_months = sorted(months)
        check(months == sorted_months, f"monthly_revenue is sorted chronologically (oldest first): {months}")

        # Validate that the last month is the current UTC month
        now = datetime.now(timezone.utc)
        expected_current = f"{now.year:04d}-{now.month:02d}"
        check(months[-1] == expected_current, f"monthly_revenue last item is current month {expected_current} (got {months[-1]})")

    # 6) top_cars structure
    tc = data.get("top_cars")
    check(isinstance(tc, list), f"top_cars is list (got {type(tc).__name__})")
    if isinstance(tc, list):
        check(len(tc) <= 10, f"top_cars length <= 10 (got {len(tc)})")
        for i, item in enumerate(tc):
            check(isinstance(item, dict), f"top_cars[{i}] is dict")
            if isinstance(item, dict):
                for key in ("car_id", "car_name", "count", "revenue"):
                    check(key in item, f"top_cars[{i}] has key '{key}'")
                check(isinstance(item.get("count"), int), f"top_cars[{i}].count is int (got {item.get('count')!r})")
                check(isinstance(item.get("revenue"), (int, float)) and not isinstance(item.get("revenue"), bool),
                      f"top_cars[{i}].revenue is numeric")
                check((item.get("count") or 0) >= 0 and (item.get("revenue") or 0) >= 0,
                      f"top_cars[{i}] count and revenue >= 0")
        # Sorted by count desc
        counts = [it.get("count", 0) for it in tc]
        check(counts == sorted(counts, reverse=True), f"top_cars sorted by count desc: {counts}")

    # 7) top_locations structure
    tl = data.get("top_locations")
    check(isinstance(tl, list), f"top_locations is list (got {type(tl).__name__})")
    if isinstance(tl, list):
        check(len(tl) <= 10, f"top_locations length <= 10 (got {len(tl)})")
        for i, item in enumerate(tl):
            check(isinstance(item, dict), f"top_locations[{i}] is dict")
            if isinstance(item, dict):
                check("name" in item and "count" in item, f"top_locations[{i}] has keys name & count")
                check(isinstance(item.get("name"), str), f"top_locations[{i}].name is string")
                check(isinstance(item.get("count"), int), f"top_locations[{i}].count is int")
                check((item.get("count") or 0) >= 0, f"top_locations[{i}].count >= 0")

    # 8) status_breakdown & payment_breakdown
    sb = data.get("status_breakdown")
    pb = data.get("payment_breakdown")
    check(isinstance(sb, dict), f"status_breakdown is dict (got {type(sb).__name__})")
    check(isinstance(pb, dict), f"payment_breakdown is dict (got {type(pb).__name__})")
    if isinstance(sb, dict):
        for k, v in sb.items():
            check(isinstance(k, str), f"status_breakdown key '{k}' is string")
            check(isinstance(v, int) and v >= 0, f"status_breakdown[{k!r}] is non-negative int (got {v!r})")
    if isinstance(pb, dict):
        for k, v in pb.items():
            check(isinstance(k, str), f"payment_breakdown key '{k}' is string")
            check(isinstance(v, int) and v >= 0, f"payment_breakdown[{k!r}] is non-negative int (got {v!r})")

    # 9) total_revenue == sum of total_price for all bookings with payment_status='paid'
    # Get all admin bookings (using existing admin endpoint)
    rb = requests.get(f"{API}/admin/bookings", headers=auth_headers(admin_token), timeout=30)
    check(rb.status_code == 200, f"GET /api/admin/bookings returns 200 (got {rb.status_code})")
    if rb.status_code == 200:
        bookings = rb.json()
        paid = [b for b in bookings if (b.get("payment_status") == "paid")]
        expected_total = round(sum(float(b.get("total_price") or 0) for b in paid), 2)
        expected_paid_count = len(paid)
        actual_total = round(float(kpis.get("total_revenue") or 0), 2)
        actual_paid_count = kpis.get("paid_bookings")
        # Allow small float diff
        check(abs(actual_total - expected_total) < 0.05,
              f"kpis.total_revenue ({actual_total}) == sum of total_price across paid bookings ({expected_total})")
        check(actual_paid_count == expected_paid_count,
              f"kpis.paid_bookings ({actual_paid_count}) == count of paid bookings ({expected_paid_count})")
        # total_bookings sanity
        check(kpis.get("total_bookings") == len(bookings),
              f"kpis.total_bookings ({kpis.get('total_bookings')}) == len(admin bookings) ({len(bookings)})")

    # 10) avg_revenue_per_booking = total_revenue / paid_bookings (or 0 if no paid)
    tr = float(kpis.get("total_revenue") or 0)
    pbk = int(kpis.get("paid_bookings") or 0)
    expected_avg = round((tr / pbk), 2) if pbk > 0 else 0.0
    actual_avg = round(float(kpis.get("avg_revenue_per_booking") or 0), 2)
    check(abs(expected_avg - actual_avg) < 0.05,
          f"avg_revenue_per_booking ({actual_avg}) matches total_revenue/paid_bookings ({expected_avg})")

    # 11) Unauthenticated -> 401
    ru = requests.get(f"{API}/admin/analytics", timeout=20)
    check(ru.status_code == 401, f"GET /api/admin/analytics without auth returns 401 (got {ru.status_code})")

    # 12) Non-admin -> 403
    # Register a fresh user
    rnd = int(time.time() * 1000)
    user_email = f"analytics.tester.{rnd}@damscarrental.com"
    user_pwd = "TestPass@123"
    reg = requests.post(f"{API}/auth/register",
                        json={"email": user_email, "password": user_pwd, "name": "Analytics Tester"},
                        timeout=20)
    user_token = None
    if reg.status_code == 200:
        user_token = reg.json().get("token")
    else:
        # if already exists, login
        login_resp = requests.post(f"{API}/auth/login", json={"email": user_email, "password": user_pwd}, timeout=20)
        if login_resp.status_code == 200:
            user_token = login_resp.json().get("token")
    check(bool(user_token), f"Created/logged in non-admin user for 403 test (reg status={reg.status_code})")

    if user_token:
        rn = requests.get(f"{API}/admin/analytics", headers=auth_headers(user_token), timeout=20)
        check(rn.status_code == 403, f"GET /api/admin/analytics as non-admin returns 403 (got {rn.status_code} body={rn.text[:200]})")

    finalize()


def finalize():
    passed = sum(1 for ok, _ in results if ok)
    failed = [m for ok, m in results if not ok]
    print("\n========== SUMMARY ==========")
    print(f"PASSED: {passed}/{len(results)}")
    if failed:
        print("FAILED:")
        for m in failed:
            print(f"  - {m}")
        sys.exit(1)
    print("ALL GREEN")


if __name__ == "__main__":
    main()
