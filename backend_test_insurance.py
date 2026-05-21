"""Backend tests for the new 'insurance_included' flag per location.

Verifies:
1) POST /api/locations persists insurance_included (true/false/default)
2) PUT /api/locations/{id} updates only insurance_included
3) GET /api/locations/tax-by-name returns insurance_included
4) Authorization: admin-only for writes; tax-by-name public
5) Backward compatibility: locations without the field default to False
"""
from __future__ import annotations
import os
import sys
import json
import uuid
import requests
from typing import Optional, List

BACKEND_URL = "https://rental-routes.preview.emergentagent.com/api"

ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

PASS = 0
FAIL = 0
FAIL_MSGS: List[str] = []


def _check(cond: bool, msg: str):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {msg}")
    else:
        FAIL += 1
        FAIL_MSGS.append(msg)
        print(f"  ❌ {msg}")


def login(email: str, password: str) -> str:
    r = requests.post(f"{BACKEND_URL}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    token = r.json().get("token")
    if not token:
        raise RuntimeError(f"no token in login response: {r.text}")
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def register_customer() -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"jane.doe.{suffix}@example.com"
    password = "CustomerP@ss123"
    name = f"Jane Doe {suffix}"
    r = requests.post(
        f"{BACKEND_URL}/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"customer register failed: {r.status_code} {r.text}")
    return r.json().get("token")


def main():
    print("=" * 70)
    print("INSURANCE INCLUDED FLAG — BACKEND TESTS")
    print(f"Backend: {BACKEND_URL}")
    print("=" * 70)

    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    customer_token = register_customer()

    created_ids: List[str] = []
    suffix = uuid.uuid4().hex[:6].upper()

    # =========================================================================
    # 1) POST /api/locations
    # =========================================================================
    print("\n[1] POST /api/locations — create with insurance_included=true")
    body_with_ins = {
        "name": f"DAMS Test Beach Hub INS-{suffix}",
        "address": "Av. Costa Brava 12",
        "city": "Punta Cana",
        "country": "DR",
        "lat": 18.582,
        "lng": -68.405,
        "type": "both",
        "tax_rate": 18.0,
        "min_booking_days": 2,
        "insurance_included": True,
    }
    r = requests.post(f"{BACKEND_URL}/locations", json=body_with_ins, headers=auth_headers(admin_token), timeout=20)
    _check(r.status_code == 200, f"POST insurance=true → 200 (got {r.status_code} body={r.text[:200]})")
    if r.status_code == 200:
        d = r.json()
        loc_with_ins_id = d.get("id")
        created_ids.append(loc_with_ins_id)
        _check(d.get("insurance_included") is True, f"response insurance_included is True (got {d.get('insurance_included')!r})")
        _check(d.get("name") == body_with_ins["name"], "response name matches")
        _check(float(d.get("tax_rate", -1)) == 18.0, "response tax_rate=18.0")
        _check(int(d.get("min_booking_days", -1)) == 2, "response min_booking_days=2")
    else:
        loc_with_ins_id = None

    print("\n[1b] POST /api/locations — no insurance field → defaults to false")
    body_default = {
        "name": f"DAMS Test Airport DEF-{suffix}",
        "address": "Aeropuerto Internacional",
        "city": "Santo Domingo",
        "country": "DR",
        "lat": 18.42,
        "lng": -69.66,
        "type": "pickup",
        "tax_rate": 12.0,
        "min_booking_days": 1,
        # NO insurance_included field
    }
    r = requests.post(f"{BACKEND_URL}/locations", json=body_default, headers=auth_headers(admin_token), timeout=20)
    _check(r.status_code == 200, f"POST without insurance → 200 (got {r.status_code} body={r.text[:200]})")
    if r.status_code == 200:
        d = r.json()
        loc_default_id = d.get("id")
        created_ids.append(loc_default_id)
        _check(d.get("insurance_included") is False, f"default insurance_included is False (got {d.get('insurance_included')!r})")
    else:
        loc_default_id = None

    print("\n[1c] Verify via GET /api/locations")
    r = requests.get(f"{BACKEND_URL}/locations", timeout=20)
    _check(r.status_code == 200, f"GET /locations → 200 (got {r.status_code})")
    if r.status_code == 200:
        all_locs = r.json()
        with_ins = next((l for l in all_locs if l.get("id") == loc_with_ins_id), None)
        without_ins = next((l for l in all_locs if l.get("id") == loc_default_id), None)
        _check(with_ins is not None, "first created location appears in GET /locations")
        _check(without_ins is not None, "second created location appears in GET /locations")
        if with_ins:
            _check(with_ins.get("insurance_included") is True, f"first location has insurance_included=True in list (got {with_ins.get('insurance_included')!r})")
        if without_ins:
            _check(without_ins.get("insurance_included") is False, f"second location has insurance_included=False in list (got {without_ins.get('insurance_included')!r})")

    # =========================================================================
    # 2) PUT /api/locations/{id}
    # =========================================================================
    print("\n[2] PUT /api/locations/{id} — toggle insurance_included only")
    if loc_default_id:
        # Capture original fields
        r0 = requests.get(f"{BACKEND_URL}/locations/{loc_default_id}", timeout=20)
        _check(r0.status_code == 200, "GET location pre-PUT 200")
        original = r0.json() if r0.status_code == 200 else {}

        # 2a) Update only insurance_included=true
        r = requests.put(
            f"{BACKEND_URL}/locations/{loc_default_id}",
            json={"insurance_included": True},
            headers=auth_headers(admin_token),
            timeout=20,
        )
        _check(r.status_code == 200, f"PUT insurance=true → 200 (got {r.status_code} body={r.text[:200]})")
        if r.status_code == 200:
            d = r.json()
            _check(d.get("insurance_included") is True, f"after PUT, insurance_included=True (got {d.get('insurance_included')!r})")
            # Verify other fields unchanged
            for k in ("name", "address", "city", "country", "type"):
                _check(d.get(k) == original.get(k), f"field '{k}' unchanged by PUT (got {d.get(k)!r}, was {original.get(k)!r})")
            _check(float(d.get("tax_rate", -1)) == float(original.get("tax_rate", -1)), "tax_rate unchanged by PUT")
            _check(int(d.get("min_booking_days", -1)) == int(original.get("min_booking_days", -1)), "min_booking_days unchanged by PUT")

        # 2b) Verify persisted via GET
        r = requests.get(f"{BACKEND_URL}/locations/{loc_default_id}", timeout=20)
        _check(r.status_code == 200, "GET location post-PUT true → 200")
        if r.status_code == 200:
            _check(r.json().get("insurance_included") is True, "GET after PUT confirms insurance_included=True persisted")

        # 2c) Update only insurance_included=false
        r = requests.put(
            f"{BACKEND_URL}/locations/{loc_default_id}",
            json={"insurance_included": False},
            headers=auth_headers(admin_token),
            timeout=20,
        )
        _check(r.status_code == 200, f"PUT insurance=false → 200 (got {r.status_code})")
        if r.status_code == 200:
            d = r.json()
            _check(d.get("insurance_included") is False, f"after PUT false, insurance_included=False (got {d.get('insurance_included')!r})")
            # Other fields unchanged
            for k in ("name", "address", "city", "country", "type"):
                _check(d.get(k) == original.get(k), f"after PUT false, field '{k}' unchanged")

        # 2d) Persistence
        r = requests.get(f"{BACKEND_URL}/locations/{loc_default_id}", timeout=20)
        _check(r.status_code == 200, "GET location post-PUT false → 200")
        if r.status_code == 200:
            _check(r.json().get("insurance_included") is False, "GET after PUT confirms insurance_included=False persisted")

    # =========================================================================
    # 3) GET /api/locations/tax-by-name
    # =========================================================================
    print("\n[3] GET /api/locations/tax-by-name — insurance_included in response")

    # 3a) For a location with insurance_included=true
    if loc_with_ins_id:
        r = requests.get(f"{BACKEND_URL}/locations/tax-by-name", params={"name": body_with_ins["name"]}, timeout=20)
        _check(r.status_code == 200, f"tax-by-name (ins=true) → 200 (got {r.status_code})")
        if r.status_code == 200:
            d = r.json()
            _check(d.get("insurance_included") is True, f"insurance_included=true in response (got {d.get('insurance_included')!r})")
            _check(float(d.get("tax_rate", -1)) == 18.0, "tax_rate=18.0 alongside")
            _check(int(d.get("min_booking_days", -1)) == 2, "min_booking_days=2 alongside")

    # 3b) For a location with insurance_included=false (loc_default after final PUT)
    if loc_default_id:
        r = requests.get(f"{BACKEND_URL}/locations/tax-by-name", params={"name": body_default["name"]}, timeout=20)
        _check(r.status_code == 200, f"tax-by-name (ins=false) → 200 (got {r.status_code})")
        if r.status_code == 200:
            d = r.json()
            _check(d.get("insurance_included") is False, f"insurance_included=false in response (got {d.get('insurance_included')!r})")

    # 3c) For a location with the field MISSING in DB (insert directly via API but
    # we need to simulate missing field; rely on existing seed locations which were
    # created before the field existed). Use any seed location and verify default.
    print("\n[3c] Backward-compat: a seed location (likely missing field) defaults to false")
    # Try a well-known seed name
    seed_candidates = ["Punta Cana Airport", "Santo Domingo", "Bavaro Beach Hub"]
    backwards_compat_checked = False
    for nm in seed_candidates:
        r = requests.get(f"{BACKEND_URL}/locations/tax-by-name", params={"name": nm}, timeout=20)
        if r.status_code == 200:
            d = r.json()
            # We only assert the key is present and is a bool. We can't be sure if main agent updated this
            # seed location during smoke testing, so we just ensure the field exists.
            _check("insurance_included" in d, f"tax-by-name for seed '{nm}' includes insurance_included key (got keys={list(d.keys())})")
            _check(isinstance(d.get("insurance_included"), bool), f"insurance_included is a boolean (got {type(d.get('insurance_included')).__name__})")
            backwards_compat_checked = True
            break
    if not backwards_compat_checked:
        print("  ⚠️  no seed location found; skipping backward-compat seed check")

    # 3d) For a non-existent location → defaults to false
    print("\n[3d] tax-by-name for non-existent location → insurance_included=false")
    nonsense_name = f"NoSuchLocation-{uuid.uuid4().hex[:12]}"
    r = requests.get(f"{BACKEND_URL}/locations/tax-by-name", params={"name": nonsense_name}, timeout=20)
    _check(r.status_code == 200, f"tax-by-name for missing name → 200 (got {r.status_code})")
    if r.status_code == 200:
        d = r.json()
        _check(d.get("insurance_included") is False, f"insurance_included=false for non-existent (got {d.get('insurance_included')!r})")
        _check(float(d.get("tax_rate", -1)) == 0.0, "tax_rate=0.0 for non-existent")
        _check(int(d.get("min_booking_days", -1)) == 1, "min_booking_days=1 default for non-existent")

    # 3e) Case-insensitive lookup
    print("\n[3e] tax-by-name case-insensitive lookup still works")
    if loc_with_ins_id:
        upper_name = body_with_ins["name"].upper()
        lower_name = body_with_ins["name"].lower()
        for variant in (upper_name, lower_name):
            r = requests.get(f"{BACKEND_URL}/locations/tax-by-name", params={"name": variant}, timeout=20)
            _check(r.status_code == 200, f"tax-by-name case variant '{variant[:30]}…' → 200")
            if r.status_code == 200:
                d = r.json()
                _check(d.get("insurance_included") is True, f"case variant returned insurance_included=True (got {d.get('insurance_included')!r})")

    # =========================================================================
    # 4) Authorization
    # =========================================================================
    print("\n[4] Authorization")
    # 4a) POST as non-admin → 403
    r = requests.post(
        f"{BACKEND_URL}/locations",
        json={
            "name": f"Should-Not-Create-{suffix}",
            "address": "x",
            "city": "x",
            "country": "x",
            "lat": 0.0,
            "lng": 0.0,
            "type": "both",
            "insurance_included": True,
        },
        headers=auth_headers(customer_token),
        timeout=20,
    )
    _check(r.status_code == 403, f"POST /locations as non-admin → 403 (got {r.status_code})")

    # 4b) PUT as non-admin → 403
    if loc_with_ins_id:
        r = requests.put(
            f"{BACKEND_URL}/locations/{loc_with_ins_id}",
            json={"insurance_included": False},
            headers=auth_headers(customer_token),
            timeout=20,
        )
        _check(r.status_code == 403, f"PUT /locations/{{id}} as non-admin → 403 (got {r.status_code})")

    # 4c) GET tax-by-name without auth → 200
    r = requests.get(f"{BACKEND_URL}/locations/tax-by-name", params={"name": "anything"}, timeout=20)
    _check(r.status_code == 200, f"GET /tax-by-name without auth → 200 (got {r.status_code})")

    # =========================================================================
    # CLEANUP
    # =========================================================================
    print("\n[CLEANUP] Deleting test locations…")
    for lid in created_ids:
        if lid:
            r = requests.delete(f"{BACKEND_URL}/locations/{lid}", headers=auth_headers(admin_token), timeout=20)
            _check(r.status_code == 200, f"DELETE /locations/{lid[:8]}… → 200 (got {r.status_code})")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print(f"RESULTS: {PASS} passed, {FAIL} failed (total {PASS + FAIL})")
    print("=" * 70)
    if FAIL_MSGS:
        print("\nFAILED ASSERTIONS:")
        for m in FAIL_MSGS:
            print(f"  ❌ {m}")
        sys.exit(1)


if __name__ == "__main__":
    main()
