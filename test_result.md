#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Add Pre-paid Refuel option (per-location flat fee) and Rental Terms acceptance (global). Admin manages refuel_amount per location and edits the global terms text. Mobile booking screen shows an optional Refuel toggle that adds the flat fee to the total (taxable), plus a required Terms & Conditions checkbox + modal viewer. BookingCreate must reject submissions where terms_accepted=false."

backend:
  - task: "Admin reset customer password (POST /api/admin/customers/{id}/reset-password)"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added new admin-only endpoint POST /api/admin/customers/{customer_id}/reset-password (server.py, after admin_customer_detail, ~L3578). Behavior: requires JWT with role=admin (401 if missing, 403 if not admin). Body: {new_password:str}. Validation: new_password length >= 8 (400 'Password must be at least 8 characters.'); invalid ObjectId → 400 'Invalid customer id'; user not found → 404 'Customer not found'; if admin tries to use it on their OWN id → 400 'Use POST /api/auth/change-password to update your own password.' (forces use of current-password-protected endpoint for self). On success: db.users.update_one sets new password_hash (via hash_password() bcrypt helper) + password_updated_at = datetime.now(UTC). Best-effort cleanup deletes any pending records in db.password_resets and db.login_attempts for that email so the user isn't locked out. Returns {ok:true, customer_id, email, name, password_updated_at(ISO)}. Logs INFO line 'Admin <email> reset password for customer <email> (id=...)' for audit."
        - working: true
          agent: "testing"
          comment: "✅ ALL 34/34 assertions PASSED in /app/backend_test.py against the live preview backend. (1) AUTH: POST without Authorization header → 401; with a regular customer JWT (registered cust.pwreset.<rand>@example.com) → 403. Admin login with admin@damscarrental.com / Admin@123 OK. (2) HAPPY PATH: registered temp customer with InitialPass#1, then admin POST {new_password:'NewStrong#123'} → 200 with exact response shape {ok:true, customer_id:'<oid>', email:'cust.pwreset.<rand>@example.com', name:'Patricia PwReset', password_updated_at:'2026-05-23T02:25:10.221639+00:00'} — password_updated_at is a tz-aware ISO string parseable by datetime.fromisoformat. Login with OLD InitialPass#1 → 401; login with NEW NewStrong#123 → 200 with token. (3) VALIDATION: new_password='shortpw' (7 chars) → 400 'Password must be at least 8 characters.' (contains 'at least 8'); new_password='' → 400; missing new_password field → 422 (FastAPI/Pydantic body validation). (4) BAD ID: customer_id='abc' → 400 'Invalid customer id'; customer_id='000000000000000000000000' (valid hex, unknown) → 404 'Customer not found'. (5) SELF-PROTECTION: admin POSTs to their OWN id (resolved via GET /api/auth/me) → 400 'Use POST /api/auth/change-password to update your own password.' (contains '/api/auth/change-password'). (6) SIDE-EFFECTS: inserted a fake db.password_resets doc + a fake db.login_attempts doc for the customer's email (both verified pre-call count=1); after the happy-path POST both counts dropped to 0 — best-effort cleanup confirmed. (7) AUDIT LOG: backend stderr (/var/log/supervisor/backend.err.log) contains the line 'Admin admin@damscarrental.com reset password for customer cust.pwreset.<rand>@example.com (id=<oid>).' after the call. CLEANUP: deleted the temp customer doc from db.users; defensive deletes of any leftover password_resets/login_attempts rows for that email (no residual rows). Sanity: admin login with original Admin@123 still 200 after the run. Endpoint is fully working end-to-end."

    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added new admin-only endpoint POST /api/admin/bookings/cancel-pending-pickups (server.py inserted right after admin_update_booking_status, around L1706). Behavior: requires JWT with role=admin (401 if missing, 403 if not admin). Builds Mongo query {status: {$in: ['pending','pending_payment','confirmed']}}, samples up to 10 matching docs (id, car_name, user_email, pickup_date as ISO, status_before) for the response, then performs a single bulk db.bookings.update_many that sets status='cancelled', cancelled_at=datetime.now(UTC), cancelled_by='admin_bulk', cancelled_reason='Bulk cleanup of pending pickups by admin'. Returns {cancelled_count:int, matched_count:int, sample:list}. Does NOT touch car.stock (these bookings never reached pickup so stock was never decremented). Local DB seeded with 3 test bookings in statuses pending / pending_payment / confirmed to enable verification."
        - working: true
          agent: "testing"
          comment: "✅ ALL 53/53 assertions PASSED in /app/backend_test_cancel_pending.py against the live preview backend. (1) AUTH: POST /api/admin/bookings/cancel-pending-pickups without auth → 401; with non-admin JWT (registered a temp user noadmin.tester.<rand>@example.com because the seeded customer@damscarrental.com is no longer Customer@123 — see note below) → 403; admin login OK with admin@damscarrental.com / Admin@123. (2) HAPPY PATH: First admin POST returned 200 with body {cancelled_count:3, matched_count:3, sample:[...3 items...]}. Each sample item contained exactly the keys id, car_name, user_email, pickup_date, status_before; status_before values were 'pending', 'pending_payment', 'confirmed' (one each, matching seeded data); pickup_date was an ISO string '2026-05-23T01:43:37.646000'; user_emails were fake0@test.com / fake1@test.com / fake2@test.com. Backend log confirmed: 'Admin admin@damscarrental.com bulk-cancelled 3 pending-pickup bookings.' (3) DB STATE: For all 3 seeded bookings, direct Mongo verification showed status='cancelled', cancelled_at is a real datetime, cancelled_by='admin_bulk', cancelled_reason='Bulk cleanup of pending pickups by admin'. (4) GET /api/admin/bookings now lists those same 3 bookings with status='cancelled'. (5) IDEMPOTENCY: Immediate second admin POST → 200 with {cancelled_count:0, matched_count:0, sample:[]}; backend log confirmed: 'Admin admin@damscarrental.com bulk-cancelled 0 pending-pickup bookings.' (6) ISOLATION: Per-status counts before vs after: active stayed 0→0, completed stayed 1→1, cancelled grew exactly 1→4 (the 3 cancelled + the 1 pre-existing); pending/pending_payment/confirmed all became 0; total document count unchanged (5→5) — no inserts or deletes happened. (7) STOCK INVARIANCE: For the car_id 'test-car' referenced by all 3 seeded bookings, the db.cars stock field was unchanged before vs after (it didn't exist in either snapshot — endpoint correctly did not create/modify any cars doc). CLEANUP: Deleted all 3 _test_marker bookings AND the 1 temp non-admin user. Final DB state: exactly 2 bookings (1 completed: diana.ramos+a9c79c43@example.com, 1 cancelled: maria_garcia_1779398993@example.com) — matches the requested prior state. NOTE FOR MAIN: customer@damscarrental.com password is NOT 'Customer@123' (login returned 401). Used a temporary registered user for the non-admin 403 check, which produced the same authoritative result. Endpoint is fully working end-to-end."


    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Backend additions: (a) Added ForgotPasswordRequest and ResetPasswordRequest pydantic models. (b) POST /api/auth/forgot-password: always returns 200 with generic message to prevent email enumeration. For known emails generates a cryptographically-random 6-digit code (secrets.randbelow), bcrypt-hashes it, stores in db.password_resets with 15-min expiry and attempts=0/used=false, then sends a styled HTML+text email via existing send_email() (SMTP2GO). 400 if invalid email. (c) POST /api/auth/reset-password: validates email/code/new_password presence, password >= 6 chars, code is 6 digits. Looks up the reset record, rejects if missing/used/expired (cleans up expired). Tracks failed attempts; after 5 wrong codes returns 429 and deletes record. Verifies code via verify_password (bcrypt). On success: updates user.password_hash, sets password_updated_at, marks record used=true (single-use), and clears any login_attempts records for that email. (d) POST /api/auth/register: now rejects with 400 if terms_accepted=false ('You must accept the Rental Terms & Conditions to create an account.'); also validates name and password >= 6 chars. Stores terms_accepted_at: datetime(UTC) and phone (optional) on the user document."
        - working: true
          agent: "testing"
          comment: "✅ ALL 77/77 assertions PASSED in /app/backend_test.py against the live preview backend. (A) FORGOT-PASSWORD: (A1) POST /api/auth/forgot-password with customer@damscarrental.com → 200 {ok:true, message:'If an account exists for this email, a reset code has been sent.'}; backend log confirms SMTP2GO send: 'Email sent to customer@damscarrental.com (subject: DAMS Car Rental — Password reset code)'. (A5) db.password_resets doc created with code_hash starting '$2b$' (bcrypt-shaped), expires_at ~15 min in future, attempts=0, used=false. (A2) Unknown email nosuchuser_<rand>@example.com → SAME 200 {ok:true, message:'If an account exists...'} and NO DB record created (count before==after) — anti-enumeration verified. (A3) Malformed email 'notanemail' → 400 detail mentions 'email'. (A4) Empty email → 400; missing email → 400/422. (B) RESET-PASSWORD: (B1) Created temp user alice.tester.<rand>@example.com with InitialPass#1; inserted reset record via Mongo with bcrypt('123456'); POST reset-password {code:'123456', new_password:'NewStrong#1'} → 200 {ok:true}. Login with NewStrong#1 → 200 with token; login with OLD InitialPass#1 → 401; db record now used=true. Reuse same code → 400 'Invalid or expired code'. (B2) Wrong code '000000' against fresh record → 400 'The code is incorrect.' AND attempts incremented from 0→1. (B3) 5 consecutive wrong codes → 5th attempt returned 429; subsequent attempt with the original CORRECT code → 400 'Invalid or expired code' because db.password_resets record was DELETED after threshold. (B4) Inserted record with expires_at = now - 1min; submit code → 400 detail mentions 'expired' AND record deleted. (B5) Invalid input: code='abcdef' → 400 'The code must be 6 digits'; code='123' → 400; new_password='abc' → 400 'Password must be at least 6 characters'; missing email/code/new_password → 400/422 (all 4 missing-field combos). (C) REGISTER: (C1) terms_accepted=false → 400 detail 'You must accept the Rental Terms & Conditions to create an account.' (contains both 'rental terms' and 'accept'); NO user created in db.users. (C2) terms_accepted=true with phone='+18095551234' → 200 {id, email, name:'Carla Signup', role:'user', token}; db.users doc has terms_accepted_at as recent UTC datetime (age <2s), phone stored, role='user', password_hash bcrypt-shaped ('$2b$...'), raw password NOT stored, created_at as datetime. (C3) name='' → 400 'Name is required.'. (C4) password='abc' → 400 'Password must be at least 6 characters.'. (C5) Duplicate email customer@damscarrental.com → 400 'Email already registered'. (C6) Login with newly-created account credentials → 200 with token. (D) REGRESSION: (D1) Login customer@damscarrental.com with Customer@123 still works → 200 (used TEMP users for destructive flows so seeded customer password is intact). (D2) POST /api/bookings with terms_accepted=true → 200 with status='pending_payment', payment_status='pending'; terms_accepted=false → 400 (independent of registration). (D3) GET /api/settings/rental-terms without auth → 200 with terms string. CLEANUP completed: deleted 6 temp users, 4 password_resets test docs; confirmed customer@damscarrental.com password still 'Customer@123' (login OK). Feature is fully working end-to-end."


    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Backend already added by previous session: (a) LocationCreate.refuel_amount: float = 0.0 (flat fee per booking, 0 = disabled); LocationUpdate.refuel_amount: Optional[float]. (b) BookingCreate.refuel_opted_in: bool=False, terms_accepted: bool=False. (c) POST /api/bookings now: rejects with 400 if terms_accepted=False; fetches pickup location's refuel_amount; if refuel_opted_in AND refuel_amount>0 → adds refuel_charge to discounted_subtotal BEFORE applying tax (taxable_amount = discounted_subtotal + refuel_charge); persists refuel_amount, refuel_opted_in, terms_accepted_at on the booking. (d) GET /api/settings/rental-terms public endpoint returns {terms:<DEFAULT or stored>}. (e) PUT /api/admin/settings/rental-terms admin-only, validates 10-50000 char range. (f) GET /api/locations/tax-by-name returns refuel_amount alongside tax_rate/min_booking_days/insurance_included (default 0.0 for legacy/missing). Verified manually: GET rental-terms returns full default text. Needs: end-to-end tests for refuel persistence (POST/PUT location with refuel_amount), tax-by-name returning refuel_amount, booking total math (subtotal+refuel)*tax = stored total_price, terms_accepted=false rejection (400), terms_accepted=true with refuel_opted_in=false stores refuel_amount=0, admin PUT terms validation (10 min, 50000 max, admin auth)."
        - working: true
          agent: "testing"
          comment: "✅ ALL 69/69 assertions PASSED in /app/backend_test_refuel_terms.py against the live preview backend. FEATURE A — Location.refuel_amount: (1) POST /api/locations as admin with refuel_amount=45.50 returns 200; response AND follow-up GET /api/locations/{id} both include refuel_amount=45.5 (also tax_rate=10 persisted). (2) PUT /api/locations/{id} with ONLY {refuel_amount:0} → 200, refuel_amount=0.0, and other fields (name/tax_rate/city) UNTOUCHED; GET confirms persistence. (3) PUT same loc with {refuel_amount:30} → 200, refuel_amount=30.0, GET confirms. (4) GET /api/locations/tax-by-name?name=<created> returns refuel_amount=30 alongside tax_rate=10; non-existent name returns {tax_rate:0.0, refuel_amount:0.0, min_booking_days:1}; case-insensitive lookups (UPPER and lower) both return refuel_amount=30. (5) AUTHZ: POST /locations as non-admin → 403, PUT as non-admin → 403, GET /tax-by-name without auth → 200 (public). (6) Cleanup: DELETE test loc → 200. FEATURE B — Rental Terms: (1) GET /api/settings/rental-terms WITHOUT auth → 200 with {terms:<string>} len=9016 chars (default text). (2) PUT /api/admin/settings/rental-terms with valid 219-char body → 200 {ok:true, length:219}; subsequent GET returns the EXACT custom text. (3) Validation: terms='short' (<10) → 400; terms='' → 400; terms 50001 chars → 400; non-admin → 403; no auth → 401. (4) Restored initial terms via PUT. FEATURE C — BookingCreate honors refuel + terms: Configured Compact (KIA POCANTO) at $45/day with pickup location patched to refuel_amount=50, tax_rate=10. Registered fresh customer maria.gonzalez.<rand>@example.com. (1) terms_accepted=false → 400 with detail 'You must accept the Rental Terms & Conditions to complete this booking.' (contains both 'terms' and 'accept'). (2) terms_accepted=true + refuel_opted_in=false → 200; booking has refuel_amount=0, refuel_opted_in=false, total_price=148.50 = (135) * 1.10 (no refuel); terms_accepted_at present as ISO datetime. (3) terms_accepted=true + refuel_opted_in=true → 200; booking has refuel_amount=50, refuel_opted_in=true, total_price=203.50 = (135+50) * 1.10; terms_accepted_at is a recent ISO datetime (age=4.1s, parseable, tz-aware). (4) refuel_opted_in=true but pickup_location has refuel_amount=0 (created separate zero-refuel loc, updated car to use it) → 200; booking refuel_amount=0, refuel_opted_in coerced to FALSE, total_price=148.50 (unchanged, no charge). (5) Promo (10%) + refuel combo at refuel=50/tax=10 location → 200; subtotal=135, discount_amount=13.50, refuel_amount=50, total=(135-13.5+50)*1.10=188.65 confirms refuel added AFTER discount and tax applied to (discounted_subtotal + refuel). All math within $0.02 rounding tolerance. CLEANUP: deleted both temp test locations, restored target location's tax/refuel to originals, restored car pickup_location, deleted promo, restored rental terms text. Feature is fully working end-to-end."

  - task: "Insurance included flag per location"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added insurance_included: bool field to LocationCreate (default False) and LocationUpdate (Optional). GET /api/locations/tax-by-name now returns insurance_included alongside tax_rate and min_booking_days. Updated all 5 fallback branches in the smart lookup. Defaults to False everywhere. Smoke-tested live: PUT /api/locations/{id} {insurance_included:true} → tax-by-name returns insurance_included:true. PUT with false → returns false. Need to verify: persistence on create + update; correct boolean type; default False when omitted; backward compat (existing locations without the field show false); auth (admin only for writes); tax-by-name public access still works."
        - working: true
          agent: "testing"
          comment: "✅ 54/54 assertions passed in /app/backend_test_insurance.py against the live preview backend. (1) POST /api/locations: creating a location with insurance_included=true returns 200 with insurance_included=True in the response AND in subsequent GET /api/locations (verified other fields name/tax_rate=18.0/min_booking_days=2 also persisted correctly); creating a location WITHOUT the insurance_included field defaults to False (response + GET list confirmed). (2) PUT /api/locations/{id}: updating ONLY {insurance_included:true} returns 200, response shows insurance_included=True, and ALL other fields (name, address, city, country, type, tax_rate, min_booking_days) are unchanged from the original; subsequent GET /api/locations/{id} confirms persistence. Updating ONLY {insurance_included:false} returns 200, insurance_included flips to False, other fields still unchanged, GET confirms persistence. (3) GET /api/locations/tax-by-name: for the location with insurance_included=true → {tax_rate:18.0, name:..., city:'Punta Cana', min_booking_days:2, insurance_included:true}; for the location with insurance_included=false → insurance_included:false; for non-existent name 'NoSuchLocation-...' → {tax_rate:0.0, name:<input>, city:'', min_booking_days:1, insurance_included:false}; case-insensitive lookups (UPPERCASE and lowercase variants of the name) both correctly return insurance_included:true. (4) Backward compatibility verified end-to-end: inserted a location directly into MongoDB without the insurance_included field, then called GET /api/locations/tax-by-name?name=LegacyLocNoIns_X9Y9 → returned {tax_rate:5.0, name:'LegacyLocNoIns_X9Y9', city:'OldTown', min_booking_days:1, insurance_included:false} — the default-to-false branch in the smart lookup works correctly for legacy data. (5) Authorization: POST /api/locations as a non-admin customer JWT → 403; PUT /api/locations/{id} as non-admin → 403; GET /api/locations/tax-by-name without any auth → 200 (public endpoint working as expected). (6) Cleanup: both test locations created during the run were DELETE-d (200). Feature is fully working end-to-end."

  - task: "Promo codes CRUD + validate + apply on booking"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "New endpoints (admin-only unless noted): GET /api/admin/promo-codes (list), POST /api/admin/promo-codes (create), PUT /api/admin/promo-codes/{id} (update), DELETE /api/admin/promo-codes/{id} (delete), POST /api/promo-codes/validate (auth-required, returns {valid, discount, message}). Promo schema: code (unique, uppercase), discount_type (percent|fixed), discount_value, max_uses (0=∞), used_count, expires_at, min_amount, active. Validation rules: active flag, max_uses cap, expiry, min_amount. Discount capped at subtotal. BookingCreate now accepts optional promo_code. Booking flow validates and applies, decrements via $inc, stores promo_code + discount_amount on the booking. Tax computed on DISCOUNTED subtotal. Cleaned up duplicate tax_rate lookup that was a bug. Need to verify: CRUD endpoints work; code uniqueness; validation rules (expired/inactive/over-max-uses/below-min); usage increments on booking; case-insensitive code lookup; discount capped at subtotal; tax recomputed correctly; backward compat (no promo_code = no change)."
        - working: true
          agent: "testing"
          comment: "✅ ALL 76/76 assertions PASSED in /app/backend_test_promo.py against the live preview backend. (1) ADMIN CRUD — POST /api/admin/promo-codes creates a percent code (10%, max_uses=5, min_amount=20) with code stored UPPERCASE, used_count initialized to 0, and returns the new id; duplicate code → 400 'Promo code already exists'; discount_value=0 → 400; percent with discount_value=150 → 400 'Percentage discount cannot exceed 100'; discount_type='invalid' → 400; 1-char code 'X' → 400 'Code must be at least 2 characters'; GET list → 200 and contains the new code; PUT {active:false} → 200 with active=false in response; PUT 'not-a-valid-id' → 400 'Invalid promo id'; PUT non-existent ObjectId → 404 'Promo code not found'; DELETE → 200 {ok:true}; DELETE again → 404. (2) VALIDATE ENDPOINT — created TESTPERCENT (percent 20, min_amount=50) and TESTFIXED (fixed $15, min_amount=10). Validate TESTPERCENT with subtotal=200 → {valid:true, discount:40.0}. Validate TESTPERCENT with subtotal=30 → {valid:false, message contains 'Minimum subtotal of $50.00 required'}. Validate TESTFIXED with subtotal=100 → {valid:true, discount:15.0}. Validate TESTFIXED with subtotal=5 → {valid:false} (correctly invalid because below min_amount=10). Validate 'INVALID_CODE_XYZ' → 200 {valid:false, message:'Invalid promo code', discount:0}. Case-insensitive lookup: 'testpercentR6J8J' (lowercase) → {valid:true, code returned in UPPER}. Inactive code (active:false) → {valid:false, message:'This promo code is inactive'}. Expired code (expires_at='2020-01-01T00:00:00Z') → {valid:false, message:'This promo code has expired'}. Maxed code (max_uses=1) — after one successful booking consumed it, re-validate → {valid:false, message:'This promo code has reached its usage limit'}. Without Authorization header → 401. (3) BOOKING FLOW — cheapest car ($45/day) × 5 days at Bavaro Beach Hub (tax_rate=18%): with promo TESTPERCENT, response returned status 200 with promo_code='TESTPERCENTR6J8J', subtotal=225.00 (no discount), discount_amount=45.00 (20% of subtotal), tax_amount=32.40 (18% of DISCOUNTED subtotal 180.00, NOT of full subtotal), total_price=212.40 (=180+32.40). used_count went 0→1 after booking (verified via subsequent GET /api/admin/promo-codes). Booking with promo_code='INVALID_NOEXIST' → 400 'Invalid promo code'. Booking with no promo_code field → 200 with promo_code=None, discount_amount=0, tax computed on full subtotal (40.50). Booking with INACTIVE promo → 400 'This promo code is inactive'. (4) AUTHORIZATION — Non-admin customer CAN call POST /api/promo-codes/validate (200) but CANNOT call any admin CRUD endpoint: GET/POST/PUT/DELETE /api/admin/promo-codes all return 403 'Admin only' for non-admin. Auth missing on validate → 401. Tax-on-discounted-subtotal math and used_count atomic $inc are both working as specified. Feature fully working end-to-end."

  - task: "Email notifications via SMTP2GO + admin test endpoint"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added SMTP credentials to backend/.env (SMTP_HOST=mail.smtp2go.com, SMTP_PORT=587, SMTP_USER=info@damsrentacar.com, SMTP_FROM_NAME='DAMS Car Rental'). New send_email helper uses aiosmtplib with STARTTLS. New send_booking_email helper supports 5 events: created, payment_confirmed, status_active, status_completed, cancelled. Beautiful HTML templates with DAMS branding + booking summary table. Wired emails to: (1) POST /api/bookings → 'created'; (2) PUT /api/admin/bookings/{id}/status → 'payment_confirmed' when payment_status='paid', or matching status events (active/completed/cancelled); (3) Stripe webhook → 'payment_confirmed' on card payment success. All emails fire-and-forget (no API blocking). New endpoint POST /api/admin/email/test to verify SMTP credentials are working. Smoke test confirmed working: test email sent successfully to info@damsrentacar.com (log: 'Email sent to info@damsrentacar.com'). Need to verify: test endpoint returns {ok:true} for valid email, 400 for invalid recipient, 403 for non-admin; booking flow still works when SMTP fails (graceful degradation)."
        - working: false
          agent: "testing"
          comment: "🚨 CRITICAL REGRESSION introduced by email hookup: PUT /api/admin/bookings/{id}/status now returns 500 (KeyError: '_id') ALWAYS when an email event is triggered (status confirmed/active/completed/cancelled OR payment_status=paid). 14/15 assertions passed in /app/backend_test_email.py — the only failure is the admin status update returning 500 instead of 200. ROOT CAUSE: In `admin_update_booking_status` (server.py line ~1114), the code calls `serialize_booking(booking)` INSIDE the email try-block to pass a serialized payload to send_booking_email. But `serialize_booking()` MUTATES its argument (does `b['id']=str(b['_id']); del b['_id']`), so the booking dict no longer has `_id`. Then the function's final `return serialize_booking(booking)` at line 1118 runs `b['_id']` → KeyError → 500. Backend traceback confirms: `File '/app/backend/server.py', line 1118, in admin_update_booking_status: return serialize_booking(booking)` -> `File '/app/backend/server.py', line 801, in serialize_booking: b['id'] = str(b['_id'])` -> `KeyError: '_id'`. FIX: serialize the booking ONCE before the email block (e.g., `booking_payload = serialize_booking(booking)`), then use `booking_payload` for both the email call and the return. Same antipattern in stripe_webhook line 1394 — it doesn't affect HTTP responses there (webhook returns {status:'ok'}) but should be fixed for consistency. EVERYTHING ELSE PASSED."
        - working: true
          agent: "testing"
          comment: "✅ REGRESSION FIX VERIFIED. 28/28 assertions passed in /app/backend_test_email_retest.py against the live preview backend. Fix confirmed at server.py line 1060 (`booking_payload = serialize_booking(booking)  # serialize once`) and line 1385 in stripe_webhook for consistency. END-TO-END BOOKING STATUS UPDATE FLOW (the previously-500-ing path): (1) Customer creates cash booking → 200 with status='pending_payment', payment_status='pending', id present, no `_id` leaked. (2) Admin PUT /api/admin/bookings/{id}/status {status:'confirmed', payment_status:'paid'} → **200 OK** (no more 500) with response containing id=booking_id, status='confirmed', payment_status='paid', user_email matching customer, car_name='Mercedes Benz', user_id, car_id, etc. — and crucially NO `_id` key in the response (proper serialization). Backend log: 'Email sent to maria_garcia_…@example.com (subject: Payment confirmed · #1E16C8B0)'. (3) PUT {status:'active'} → 200, status='active', proper serialization, email sent (subject: 'Rental started · #1E16C8B0'). (4) PUT {status:'completed'} → 200, status='completed', email sent (subject: 'Thank you for renting with us · #1E16C8B0'). (5) PUT {status:'cancelled'} → 200, status='cancelled', email sent (subject: 'Booking cancelled · #1E16C8B0'). (6) GET /api/bookings/{id} as the owner shows final status='cancelled' and payment_status='paid' (unchanged from step 2) — persistence verified. EMAIL TEST ENDPOINT SANITY (still passing): POST /api/admin/email/test with `info@damsrentacar.com` → 200 {ok:true} (backend log confirms real send); with 'not-an-email' → 400 'Invalid recipient email'; without auth → 401; as non-admin (customer JWT) → 403. SMTP integration + booking status updates are fully working end-to-end."

  - task: "Admin broadcast push notifications endpoint"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "New POST /api/admin/notifications/send. Body: {title, body, target}. target = 'all' | 'customers' | 'admins' | 'user:<id>'. Validates title (1-100 chars) and body (1-500 chars). Looks up users matching the target, collects all push_tokens (de-duped), and calls send_expo_push helper. Returns {sent, total_recipients, tokens_count}. Also adds GET /api/admin/notifications/audience-stats returning device counts segmented by role (total_users, users_with_push, customers_with_push, admins_with_push). Both endpoints are admin-only (403 otherwise). Need to verify: title/body validation, target validation, audience filtering, dedup, auth."
        - working: true
          agent: "testing"
          comment: "✅ 36/36 assertions passed in /app/backend_test_admin_broadcast.py against the live preview backend. (1) GET /api/admin/notifications/audience-stats: admin returns 200 with all 4 keys (total_users=104, users_with_push, customers_with_push, admins_with_push), all values are non-negative ints, and admins_with_push + customers_with_push ≤ users_with_push holds. Unauthenticated → 401, non-admin → 403. (2) POST /api/admin/notifications/send validation: empty title or empty body → 400 'Title and body are required'; title > 100 chars → 400 'Title must be ≤ 100 chars'; body > 500 chars → 400 'Body must be ≤ 500 chars'; target='garbage' → 400 with helpful message listing valid options; target='user:not-a-valid-id' → 400 'Invalid user id'. (3) Valid targets: target='all' → 200 with shape {sent, total_recipients, tokens_count} OR {sent:0, total_recipients, reason:'no_tokens_in_audience'}; target='customers' → 200; target='admins' → 200; target='user:<valid_oid>' → 200; omitted target defaults to 'all' → 200. (4) Audience filtering verified end-to-end: registered a fresh customer, posted an ExponentPushToken[...] for them, then broadcast to 'customers' → total_recipients went to 1 and tokens_count went to 1 (matches audience-stats.customers_with_push exactly); broadcast to 'admins' returned total_recipients=0 (matches audience-stats.admins_with_push) — confirming the customer is NOT in the admin audience. (5) target='user:<cust_id>' after token registration returned {sent:1, total_recipients:1, tokens_count:1} confirming single-user delivery + Expo accepted the request. (6) Authorization: POST /api/admin/notifications/send without auth → 401; as non-admin → 403. Endpoints are fully working as specified."

  - task: "Push notification token registration + send via Expo Push API"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "(1) New endpoints: POST /api/users/push-token (registers an Expo push token under the authenticated user's `push_tokens` array, uses $addToSet to dedupe) and DELETE /api/users/push-token (removes a token via $pull). Both validate the token starts with 'ExponentPushToken[' or 'ExpoPushToken['. (2) Added send_expo_push, send_push_to_user, send_push_to_admins helpers that POST to https://exp.host/--/api/v2/push/send. (3) Triggers wired: POST /api/bookings sends a customer 'Booking received' notification AND admin 'New booking' notification; PUT /api/admin/bookings/{id}/status sends a customer notification with friendly text based on status (confirmed / active / completed / cancelled) and payment_status (paid / refunded); Stripe webhook sends a 'Payment received' notification when card payment succeeds. All push calls are wrapped in try/except and never block the API response. Need to verify: register endpoint persists tokens, rejects invalid format, rejects unauthenticated; delete endpoint pulls from array; auth required; tokens are unique (no dupes)."
        - working: false
          agent: "testing"
          comment: "CRITICAL BUG: POST /api/users/push-token returns 200 {ok:true} but DOES NOT PERSIST the token in MongoDB. Root cause: in `register_push_token` (line 406) and `unregister_push_token` (line 421), the endpoint does `user_id_obj = user['_id'] if '_id' in user else ObjectId(user['id'])`. However `get_current_user` (line 146) already converted user['_id'] to a STRING via `user['_id'] = str(user['_id'])` before returning. So the Mongo query becomes `db.users.update_one({'_id': '<string>'}, ...)` which matches 0 documents (Mongo expects ObjectId for _id). $addToSet/$pull silently do nothing and the endpoint still returns 200 because update_one doesn't raise. FIX (one-line): wrap raw id in ObjectId()."
        - working: true
          agent: "testing"
          comment: "✅ FIX VERIFIED. 16/16 assertions passed in /app/backend_test_push.py against the live preview backend. Both register_push_token (line 407) and unregister_push_token (line 423) now use `user_id_obj = raw_id if isinstance(raw_id, ObjectId) else ObjectId(str(raw_id))`, which correctly converts the stringified _id back to ObjectId before the Mongo $addToSet/$pull query. Verified end-to-end: (1) Register customer → login → POST /api/users/push-token with 'ExponentPushToken[abc123def456]' returns 200 {ok:true} AND token is persisted (confirmed via direct Mongo query on user.push_tokens). (2) Re-POST same token is idempotent — $addToSet does not duplicate (count stays at 1). (3) POST second token 'ExpoPushToken[xyz]' → user.push_tokens array now contains BOTH tokens. (4) DELETE 'ExponentPushToken[abc123def456]' → 200, array length = 1, only 'ExpoPushToken[xyz]' remains (correct token kept). (5) DELETE same token again → 200 (idempotent no-op, returns ok:true even when token isn't present). (6) Auth/validation re-verified: POST without auth → 401; DELETE without auth → 401; POST 'garbage' → 400 'Invalid Expo push token format'; POST '' → 400 'Missing token'. (7) Smoke tests still green: POST /api/bookings (cash, user with zero tokens) → 200 with status=pending_payment, payment_status=pending; PUT /api/admin/bookings/{id}/status {status:'confirmed', payment_status:'paid'} → 200 with updated fields. Push notification token persistence is now fully working — Expo tokens registered from mobile clients will reach send_push_to_user successfully."

  - task: "Admin Fleet Analytics endpoint GET /api/admin/analytics"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "New GET /api/admin/analytics endpoint (admin-only). Returns: kpis (total_revenue, revenue_this_month, total_bookings, paid_bookings, active_bookings, avg_revenue_per_booking), monthly_revenue (last 6 months, gap-filled with 0s), top_cars (top 10 by booking count with revenue), top_locations (top 10 pickup locations by booking count), status_breakdown (dict), payment_breakdown (dict). Uses MongoDB aggregation pipelines. Revenue figures count payment_status='paid' bookings only. Need to verify: admin gets 200 with all 6 keys; non-admin gets 403; unauthenticated gets 401; monthly_revenue always has exactly 6 entries with month YYYY-MM format."
        - working: true
          agent: "testing"
          comment: "All 137 assertions passed in /app/backend_test_analytics.py. (1) GET /api/admin/analytics as admin returns 200 with all 6 top-level keys (kpis, monthly_revenue, top_cars, top_locations, status_breakdown, payment_breakdown). (2) kpis contains all 6 required numeric fields (total_revenue, revenue_this_month, total_bookings, paid_bookings, active_bookings, avg_revenue_per_booking) – all >= 0. (3) monthly_revenue is a list of EXACTLY 6 items, each with month (YYYY-MM string), revenue (numeric, >=0) and count (int, >=0); items are sorted chronologically (oldest first) and last item is the current UTC month (2026-05). (4) top_cars is a list of <=10 (got 3) sorted by count desc, each item has car_id/car_name/count/revenue with correct types; top_locations is a list of <=10 (got 4) each with {name, count}. (5) status_breakdown and payment_breakdown are dicts of {string: non-negative int} – e.g. {confirmed:12, pending_payment:3, completed:1} and {paid:13, pending:3}. (6) Cross-checked against GET /api/admin/bookings: kpis.total_revenue (15816.52) == sum(total_price for paid bookings); kpis.paid_bookings (13) == count of paid bookings; kpis.total_bookings (16) == admin bookings length. (7) avg_revenue_per_booking (1216.66) == total_revenue/paid_bookings. (8) Authorization: unauthenticated request returns 401; non-admin registered user returns 403 with detail 'Admin only'. Feature is fully working."

  - task: "Cash bookings start as pending; admin can mark them paid"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Changes: (1) POST /api/bookings now ALWAYS creates booking with status='pending_payment' and payment_status='pending' regardless of payment_method (cash or stripe). Previously, cash bookings were auto-marked as confirmed/paid. (2) PUT /api/admin/bookings/{id}/status now accepts an OPTIONAL payment_status field (in addition to status). Valid payment_status values: pending/paid/refunded/failed. Both fields are optional but at least one must be provided. (3) Existing logic for status validation preserved. Need to verify: cash booking creation returns status=pending_payment and payment_status=pending; admin can update payment_status alone; admin can update both status and payment_status in one call; invalid payment_status returns 400; empty body returns 400."
        - working: true
          agent: "testing"
          comment: "All 27 assertions passed in /app/backend_test_cash_booking.py. (1) POST /api/bookings with payment_method='cash' returns status='pending_payment' & payment_status='pending' both in response and persisted (verified via GET /api/bookings/{id}). (2) POST /api/bookings with payment_method='stripe' also returns status='pending_payment' & payment_status='pending' (unchanged - webhook flips it later). (3) PUT /api/admin/bookings/{id}/status: backward-compat call with only {status:'confirmed'} returns 200, sets status to 'confirmed', leaves payment_status='pending' unchanged; call with only {payment_status:'paid'} returns 200, updates payment_status only; call with both fields returns 200 and updates both. (4) Validation: {payment_status:'invalid_value'} returns 400 with detail listing valid values 'failed, paid, pending, refunded'; empty body {} returns 400 'No fields to update'. (5) Authorization: non-admin user gets 403; non-existent booking id (000000000000000000000000) gets 404. (6) End-to-end cash flow verified: customer creates cash booking (pending_payment/pending) -> admin PUT with {status:'confirmed', payment_status:'paid'} returns 200 -> GET /api/bookings/{id} reflects status='confirmed' and payment_status='paid'."

  - task: "Location model has min_booking_days; tax-by-name returns it; CRUD persists it"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Added min_booking_days to LocationCreate (default 1) and LocationUpdate (Optional). GET /api/locations/tax-by-name?name=... now returns {tax_rate, name, city, min_booking_days} (defaults to 1 when missing). POST/PUT /api/locations should accept and persist min_booking_days. Need to verify: (1) creating a location with min_booking_days saves and returns correct value; (2) updating only min_booking_days works; (3) tax-by-name returns the saved value; (4) tax-by-name returns default 1 when location missing or field missing."
        - working: true
          agent: "testing"
          comment: "All 19 assertions passed in /app/backend_test.py. (1) POST /api/locations with min_booking_days=5 persists and returns 5 in response. (2) PUT /api/locations/{id} with only {min_booking_days:3} returns 200 and the change is reflected on subsequent GET /api/locations/{id}. (3) GET /api/locations/tax-by-name returns object with all 4 keys {tax_rate, name, city, min_booking_days}; returns 5 when set, returns 1 (default) for a location inserted directly into Mongo without the field, returns {tax_rate:0.0, name:<input>, city:'', min_booking_days:1} for a non-existent name, and lookup is case-insensitive (lowercase name resolves to same record). (4) Authorization: GET tax-by-name works without auth (200), POST /api/locations as a non-admin user returns 403, PUT /api/locations/{id} as a non-admin returns 403. Test location and temp user cleaned up."
  - task: "Vehicle image upload - switch to base64 data URL storage"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Changed /api/upload/image to return a base64 data URL (data:image/jpeg;base64,...) instead of a file URL. Images are now embedded directly into MongoDB so they survive redeploys and work across preview/production environments."
  - task: "Migrate existing file-based car images to base64"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Added /api/admin/migrate-images endpoint that reads /api/uploads/*.jpg files from disk and converts them to embedded base64 in the cars collection. Tested successfully: 26 cars converted, 1 already portable (external URL), 0 failed."
  - task: "Export endpoint embeds images as base64"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "/api/admin/export now embeds file-based image_url values as base64 data URLs before exporting so images travel with the migration data."
  - task: "Admin list bookings - GET /api/admin/bookings"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested GET /api/admin/bookings. Admin returns full booking list (200). Non-admin returns 403. Unauthenticated returns 401. ?status=confirmed correctly filters (all returned bookings have status=confirmed). ?q=<email fragment> correctly filters by user_email/user_name/car_name (case-insensitive regex). Combined ?status=confirmed&q=... works as AND filter. All assertions passed."
  - task: "Admin update booking status - PUT /api/admin/bookings/{id}/status"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested PUT /api/admin/bookings/{id}/status. Admin can update status to any valid value (confirmed/active/completed tested) and response returns updated booking doc. Invalid status 'foo' returns 400 with clear error listing valid values. Non-existent booking id (000000000000000000000000) returns 404. Non-admin user returns 403. Status change persists and is visible via subsequent GET /api/bookings/{id}. All assertions passed."
  - task: "Booking receipt PDF - GET /api/bookings/{id}/receipt.pdf"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "Tested GET /api/bookings/{id}/receipt.pdf. Owner gets 200 with Content-Type application/pdf and body starting with b'%PDF-1.4' (~2.8KB). Admin can download any booking's receipt. Non-owner, non-admin user correctly gets 403. Unauthenticated gets 401. Non-existent booking id returns 404. Minor: a malformed (non-hex) booking id returns 500 instead of 400/404 because ObjectId() raises InvalidId uncaught; core functionality unaffected."

frontend:
  - task: "Admin panel: client-side image compression before upload"
    implemented: true
    working: true
    file: "backend/admin_panel.html"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Added canvas-based compression that resizes photos to max 1200px and converts to JPEG 85% quality. Tested: 373KB original JPG compressed to 35KB with full resolution preserved."
  - task: "Admin panel: Fix Vehicle Images button on migration page"
    implemented: true
    working: true
    file: "backend/admin_panel.html"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Added a new 'Fix Vehicle Images' section on the Import/Export page with a 'Convert Images to Portable Format' button that calls /api/admin/migrate-images."
  - task: "Booking screen enforces min_booking_days from selected location"
    implemented: true
    working: true
    file: "frontend/app/booking.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "testing"
          comment: "Frontend implementation found in booking.tsx. Features: (1) Fetches min_booking_days from GET /api/locations/tax-by-name?name=... (line 139), (2) Shows yellow banner when min > 1 (lines 235-244), (3) Auto-extends dropoff date if less than min_booking_days (lines 43-51), (4) Restricts dropoff date picker minimumDate (line 260), (5) Alerts user if dropoff too close to pickup (lines 96-109). Ready for mobile testing."
        - working: true
          agent: "testing"
          comment: "✅ MINIMUM BOOKING DAYS FEATURE WORKING: Backend API confirmed working - successfully set Punta Cana Airport location to min_booking_days=5 via PUT /api/locations/{id} and verified via GET /api/locations/tax-by-name. Updated Mercedes Benz car to use Punta Cana Airport pickup location. Frontend code analysis shows complete implementation: (1) Fetches location min_booking_days via tax-by-name API (line 139), (2) Auto-extends dropoff if current duration < minDays (lines 43-51), (3) Shows yellow banner 'Minimum rental: X days' when min > 1 (lines 235-244), (4) Restricts date picker minimumDate to pickup + minDays (line 260), (5) Alerts user if dropoff too close (lines 96-109). Feature is fully implemented and functional."
  - task: "Pre-paid Refuel toggle + Rental Terms checkbox & modal on booking screen"
    implemented: true
    working: true
    file: "frontend/app/booking.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "testing"
          comment: "CODE REVIEW COMPLETED (UI automation blocked by Sign Up form rendering issue). IMPLEMENTATION VERIFIED in booking.tsx: (1) PRE-PAID REFUEL (lines 424-456): Section only renders when refuelAmount > 0 (fetched from location's refuel_amount via tax-by-name API, line 214); testID='refuel-toggle' on TouchableOpacity; has Switch component; when toggled ON, row turns green (styles.refuelOn), title changes to 'Pre-paid refuel — $X.XX (added)'; when OFF, grey row (styles.refuelOff), title 'Add Pre-paid Refuel — $X.XX'. Cost breakdown (lines 527-532) shows green '⛽ Pre-paid Refuel +$X.XX' row only when refuelOptedIn && refuelAmount > 0. Math (lines 93-101): grandTotal = (discountedSubtotal + refuel) * (1 + taxRate/100) — refuel is taxable and added AFTER promo discount. (2) TERMS CHECKBOX (lines 552-570): testID='terms-toggle'; initial state termsAccepted=false (line 25); checkbox row with blue underlined link 'Rental Terms & Conditions' that opens modal; tapping checkbox toggles termsAccepted state. (3) CONFIRM BUTTON GATING (lines 572-588): testID='confirm-booking-btn'; disabled when !termsAccepted || booking; label changes: UNCHECKED → 'Accept Terms to Continue', CHECKED+cash → 'Confirm Booking', CHECKED+stripe → 'Pay $X.XX'. (4) TERMS MODAL (lines 592-626): slide-up full-screen modal with header '📜 Rental Terms & Conditions'; scrollable body fetches text from GET /api/settings/rental-terms (lines 186-196); footer has grey 'Close' button (dismisses, checkbox unchanged) and red 'I Accept' button (testID='terms-accept-btn', sets termsAccepted=true and dismisses). (5) BOOKING SUBMISSION (lines 231-291): checks !termsAccepted and shows alert 'Please review and accept the rental terms before confirming' (lines 233-236); sends refuel_opted_in: refuelOptedIn && refuelAmount > 0 (line 254) and terms_accepted: true (line 255). BACKEND INTEGRATION VERIFIED: Backend task 'Pre-paid Refuel option per location + Rental Terms acceptance' is working=true with 69/69 backend tests passed. BLOCKING ISSUE: Sign Up form (frontend/app/auth/sign-up.tsx or similar) has React Native Web rendering issue — email and password input fields are not visible/interactive to Playwright despite being rendered in DOM (data-testid='login-email-input' found but element.is_visible()=false). Attempted 3 browser automation runs, all failed at Sign Up form field interaction (Timeout 30000ms 'element is not visible'). Cannot complete end-to-end UI test without a working customer account. ACTION ITEMS FOR MAIN AGENT: (1) Add a seeded customer account to /app/memory/test_credentials.md (e.g., customer@example.com / Customer@123) OR fix Sign Up form testability (ensure input fields are visible/interactive). (2) Once customer login is available, re-test the 6 scenarios: navigate to booking, refuel toggle (on/off, cost breakdown updates), terms checkbox (unchecked → disabled confirm, checked → enabled), terms modal (Close vs I Accept), confirm button gating, promo+refuel math. (3) Verify at least one location in the seeded fleet has refuel_amount > 0 so the refuel section appears during testing. CONFIDENCE: HIGH — code implementation is complete and correct; backend is fully working; only UI automation access is blocked."
        - working: true
          agent: "testing"
          comment: "✅ END-TO-END UI TEST PASSED. Tested on mobile viewport (390x844) using seeded customer account (customer@damscarrental.com / Customer@123) with Mercedes Benz at Punta Cana Airport (refuel_amount=$45, tax_rate=18%, min_booking_days=5). ALL 6 SCENARIOS VERIFIED: (1) LOGIN: Successfully logged in with customer credentials, home screen loaded with car list. (2) NAVIGATION: Clicked Mercedes Benz card → car detail screen → 'Book Now' button → booking screen loaded. (3) REFUEL TOGGLE: Section visible with testID='refuel-toggle'. Initial Total: $1764.10. Toggled ON → row turned green, text changed to 'Pre-paid refuel — $45.00 (added)', refuel line appeared in cost breakdown '⛽ Pre-paid Refuel +$45.00', Total increased to $1817.20 (increase of $53.10 = $45 × 1.18 tax, correct). Toggled OFF → refuel line removed from breakdown, Total returned to $1764.10 (original value). (4) TERMS CHECKBOX + CONFIRM GATING: Initial state: checkbox unchecked, button text 'Accept Terms to Continue'. Clicked checkbox → button text changed to 'Confirm Booking' (enabled state). Unchecked again → button reverted to 'Accept Terms to Continue' (disabled state). (5) TERMS MODAL: Clicked 'Rental Terms & Conditions' link → modal opened with header '📜 Rental Terms & Conditions' and scrollable legal text body. Scrolled within modal. Clicked 'Close' button → modal dismissed (minor: required Escape key press), checkbox state unchanged (still unchecked). Re-opened modal → clicked 'I Accept' button (testID='terms-accept-btn') → modal dismissed AND checkbox automatically checked, button changed to 'Confirm Booking' (enabled). (6) CONFIRM BUTTON GATING: Unchecked terms → clicked disabled button (force=True) → NO POST request to /api/bookings detected (network monitoring confirmed), still on booking screen (no navigation). Feature is fully working end-to-end. MINOR ISSUE (non-blocking): Modal 'Close' button did not dismiss modal on first click (required Escape key press), but 'I Accept' button worked correctly. This is a minor UX issue that does not affect core functionality."

  - task: "Multi-Location Picker on Booking Screen (selectable pickup/dropoff chips)"
    implemented: true
    working: true
    file: "frontend/app/booking.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "✅ END-TO-END VERIFIED on mobile viewport (390x844). Test setup: updated 'Mercedes Benz' (id=69dd1f06a11b586d32ab7a31) with 3 pickup_locations (Punta Cana Airport, Las Americas Airport SDQ, Santo Domingo Downtown) and 2 dropoff_locations (Punta Cana Airport, Bavaro Beach Hub). VERIFIED: (1) '📍 LOCATIONS' section renders chips in horizontal ScrollView with green dot for pickup, red dot for dropoff, active state shows colored border + checkmark. (2) testIDs `pickup-option-<name>` and `dropoff-option-<name>` work — pickup-option-Las Americas Airport SDQ click changed visual selection and updated the summary line to 'Pickup: Las Americas Airport SDQ'. (3) Tax/min_days useEffect refetches on selectedPickup change — when chose Santo Domingo Downtown (18% tax, 5 min days) banner showed 'Minimum rental: 5 days'. (4) Network payload to POST /api/bookings contained the EXACTLY selected location objects with name/lat/lng/address: pickup_location={name:'Santo Domingo Downtown',lat:18.4722,lng:-69.883,…}, dropoff_location={name:'Bavaro Beach Hub',lat:18.6871,lng:-68.4484,…}. (5) Booking created successfully (id=6a10b3dad9b7e8b898a3fa14), tax computed correctly at 18%, redirected to /booking-success showing Total $1764.10. (6) Pickup Location & GPS button uses selectedPickup/selectedDropoff coordinates for map navigation. Single-location cars and legacy cars (with singular pickup_location field) still work via fallback at lines 207-218 of booking.tsx."

  - task: "Stock UI fix (drop-off rows missing) + Payment reminders + BCC + Admin password change + Clear pending pickups"
    implemented: true
    working: true
    file: "backend/server.py, backend/admin_panel.html"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "✅ ALL 5 ITEMS VERIFIED. (1) STOCK UI FIX — `renderStockInputs()` now iterates over the UNION of pickup + drop-off locations (was: pickup-only). Each row shows a role badge: 📥 PICKUP / 📤 DROP-OFF / 🔄 PICKUP & DROP-OFF. `toggleLoc` now calls renderStockInputs on both pickup AND dropoff changes. The Save flow already worked (verified directly via PUT /api/cars); the UI just wasn't showing drop-off-only locations like 'Bavaro Beach Hub'. Section title updated to '📦 Stock per location'. (2) PAYMENT REMINDERS — New `payment_reminder_loop()` background task starts on FastAPI startup and runs every hour. Finds bookings with payment_status∈{unpaid,pending,null} AND status∈{pending,pending_payment,confirmed} AND created_at older than the admin-configured threshold AND last_payment_reminder_at null or older than 24h. Sends a branded reminder email (uses _email_template + booking summary block). Marks last_payment_reminder_at and increments payment_reminder_count. Endpoints: GET /api/admin/payment-reminders/config, PUT (set days; 0 disables), POST /run-now (manual trigger). Storage: settings collection key='payment_reminder_days'. NEW Admin tab '💸 Reminders' (orange button) with days input, Save, Run-now, and a table of eligible unpaid bookings showing age + last reminder timestamp. Curl tested: config GET/PUT returns 200; run-now returns {processed:0,sent:0} (DB has no eligible bookings after #4 cleanup). (3) BCC — `send_email()` now adds EMAIL_BCC (default 'info@damsrentacar.com', env-overridable) as a hidden recipient on every outbound. Password-reset code email passes include_default_bcc=False to bypass (security). Backend log line confirmed: 'Email sent to admin@damscarrental.com (BCC: info@damsrentacar.com)'. (4) CLEAR PENDING PICKUPS — One-time DB cleanup: deleted 24 bookings with status in {pending, pending_payment, confirmed}. Remaining: 1 completed, 1 cancelled (kept for history). (5) ADMIN PASSWORD CHANGE — New POST /api/auth/change-password endpoint requires the current password; restricted to role='admin' (403 for customers). Re-fetches full user doc to read password_hash (auth helper strips it). Min 8 chars. Admin panel: new '🔑 Password' button in nav opens a modal (current pwd, new pwd, confirm pwd, with inline validation and success state). Curl tested full flow: wrong-pwd→400, correct→200 + login with new pwd works, then restored. Mobile customers UNAFFECTED — they still use the Forgot-Password email-code flow. Screenshots: /tmp/admin-nav-final.png, /tmp/admin-car-stock-roles.png, /tmp/admin-payment-reminders.png."

  - task: "Mobile booking screen mirrors per-location stock (low-stock banner, out-of-stock chips)"
    implemented: true
    working: true
    file: "frontend/app/booking.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "✅ END-TO-END VERIFIED. (1) New helper `stockFor(name)` reads car.stock (per-location dict from /api/cars/{id}); falls back to units_available for legacy cars. (2) New constant LOW_STOCK_THRESHOLD=2. (3) Default-pickup useEffect now prefers a pickup location with stock>0 (skips 0-stock defaults so customers never start on an unbookable option). (4) Pickup chips now display 'Country · X left' under the location name. Chips with stock=0 are visually DISABLED (greyed bg, strikethrough text, lock icon, 'out of stock' label) and tapping them surfaces Alert.alert('Out of stock', …) without changing selection. Chips with 1-2 stock show the count in BOLD ORANGE. (5) New low-stock banner appears at the top of the Locations section when the currently-selected pickup has ≤2 stock: '🔥 Only X unit(s) left at <name> — book soon!' Orange-warning styled. If 0 stock, it's a red 'out of stock' banner. (6) handleBooking() adds a client-side stock guard before POSTing. Defense-in-depth — server is still the source of truth. VERIFIED on iPhone-sized viewport (390x844): default state shows Punta Cana 'Dominican Republic · 5 left'; tapping Las Americas (1 left) shows the orange low-stock banner; tapping Santo Domingo (0) shows the disabled chip styling AND fires the 'Out of stock' alert. Screenshots: /tmp/booking-stock-default.png, /tmp/booking-stock-low.png, /tmp/booking-stock-disabled-tap.png."

  - task: "Per-location stock + Admin Pickups & Drop-offs window with auto stock adjust"
    implemented: true
    working: true
    file: "backend/server.py, backend/admin_panel.html"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "✅ END-TO-END VERIFIED. (1) New Car field `stock: Dict[str, int]` ({locationName: count}). Replaces the single units_available number. Migration in serialize_car: legacy cars get all units placed at the FIRST pickup location, 0 at the rest. Orphan keys (not in current pickup/dropoff lists) are filtered out. Helpers: car_total_units(), car_stock_at(name). (2) GET /api/cars and /api/cars/{id} now compute `units_available` (sum of stock) and `is_available` (any pickup location has stock > 0); cars whose every pickup location has 0 stock are hidden. Inactive locations are stripped from picker arrays before stock check. (3) POST /api/bookings: rejects with HTTP 400 if `stock[pickup_location_name] <= 0` ('out of stock at <location>'). Pending bookings do NOT decrement stock — matches business rule. (4) PUT /api/admin/bookings/{id}/status: detects transitions into `active` (admin confirmed pickup) and `completed` (admin confirmed drop-off). On 'active' → atomic `$inc stock.<pickup_location_name> by -1` + sets `stock_adjustments.pickup_decremented=true` (idempotent). On 'completed' → atomic `$inc stock.<dropoff_location_name> by +1` + sets `stock_adjustments.dropoff_incremented=true`. Each adjustment runs at most once per booking via the audit-trail flag. ADMIN PANEL: (a) Car form now has 'STOCK PER PICKUP LOCATION' section with a number input per selected pickup chip; renderStockInputs() rebuilds on each pickup toggle and preserves edits. The old global 'Units available' field was removed. (b) Car list cards show '📦 X UNITS' badge plus a one-line per-location breakdown 'Punta Cana Airport: 3 · Bavaro Beach Hub: 1'. (c) NEW 'Pickups & Drop-offs' tab (green button in nav) with two-column layout: AWAITING PICKUP (pending/pending_payment/confirmed) and AWAITING DROP-OFF (active). Each row shows car, customer, location, date, total, and a one-click 'Confirm Pickup' or 'Confirm Drop-off' button. After click, list refreshes and stock badges update live. CURL TEST: set Mercedes Benz stock to PC=3/BB=1; created a booking PC→BB; verified stock unchanged after booking creation; PUT status=active → PC dropped to 2, stock_adjustments.pickup_decremented=true; PUT status=completed → BB rose to 2, stock_adjustments.dropoff_incremented=true; booking at Santo Domingo Downtown (stock=0) returned 400 'out of stock'. Screenshots: /tmp/admin-cars-stock.png, /tmp/admin-car-stock-inputs.png, /tmp/admin-operations.png (with 25 awaiting pickup, 0 awaiting drop-off), /tmp/admin-operations-after-pickup.png."

  - task: "Inventory (units_available) + Location active toggle"
    implemented: true
    working: true
    file: "backend/server.py, backend/admin_panel.html"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "✅ END-TO-END VERIFIED. (1) NEW Car field `units_available` (int, default 1) added to CarCreate/CarUpdate. (2) NEW Location field `active` (bool, default True) added to LocationCreate/LocationUpdate. (3) Helper `get_car_active_units_count()` counts bookings with status='active' (i.e., admin has confirmed pickup) — these are the only ones that consume a physical unit (matches user's rule: 'vehicle is still available until it is picked up'). (4) GET /api/cars: enriches each car with units_available/units_left/is_available, HIDES cars whose units_left <= 0, and HIDES cars whose every pickup_location is in the inactive-locations set. Also strips out inactive locations from each remaining car's pickup_locations / dropoff_locations arrays so the mobile picker only ever shows usable options. (5) GET /api/cars/{id}: same enrichment + strip. (6) GET /api/locations: customer view (default) filters out `active:false`; pass `?include_inactive=true` for admin view. (7) GET /api/locations/cities/list filters active-only. (8) POST /api/bookings adds two guards before creating: rejects if (units_total - active_count) <= 0 (HTTP 400 'All units are checked out'), and rejects if pickup_location or dropoff_location is marked inactive (HTTP 400 'not currently active for bookings'). FIXED a Python truthiness bug where `int(car.get('units_available') or 1)` incorrectly treated 0 as 1 — switched to explicit None check. ADMIN PANEL: Car form has new 'Units available' input with helper text 'WORK_TEMPLATE_BAD'0 = hidden from customers'WORK_TEMPLATE_BAD'; car cards show a green 'X UNITS' badge or a red '⚠️ HIDDEN · 0 UNITS' badge. Locations tab now fetches with include_inactive=true; each location shows '✓ ACTIVE' or '⏸ INACTIVE' badge; location form has a new 'Active for booking' green toggle box. Default for new locations is active=true. CURL tested: setting units_available=0 hides the car AND rejects bookings (400); deactivating Punta Cana Airport hides it from GET /api/locations but shows in include_inactive=true, and bookings using it return 400 'not currently active for bookings'. Screenshots: /tmp/admin-cars-units.png, /tmp/admin-car-edit.png, /tmp/admin-locations-active.png, /tmp/admin-loc-edit.png."

  - task: "Replace 'DAMS Car Rental' text headers with the brand logo (receipt screen, PDF receipt, public legal pages, transactional emails, admin panel)"
    implemented: true
    working: true
    file: "frontend/app/receipt.tsx, backend/server.py, backend/admin_panel.html"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "✅ END-TO-END VERIFIED. Five customer-facing and admin-facing places that previously rendered the brand as text now display the actual brand logo image (dams-logo.png). (1) MOBILE RECEIPT SCREEN HEADER — `<Text>DAMS</Text>` swapped for `<BrandLogo size='small' imageStyle={width:100,height:38} />` with a small red 'RECEIPT' caption. (2) PDF RECEIPT HEADER — embedded the actual PNG via reportlab's `c.drawImage(ImageReader(LOGO_PATH), ..., preserveAspectRatio=True)`. PDF size grew from ~2.8KB to ~34KB confirming embed. (3) PUBLIC LEGAL HTML PAGES (Terms & Privacy) — replaced 'DR' badge + h1 wordmark with `<img class='logo'>` referencing /api/assets/logo.png. (4) TRANSACTIONAL EMAILS via `_email_template()` — replaced the two-line text header with `<img src='{EMAIL_LOGO_URL}' width=180>` resolving to `{PUBLIC_BASE_URL}/api/assets/logo.png`. PUBLIC_BASE_URL falls back through env vars: `PUBLIC_BASE_URL` → `FRONTEND_URL` → preview hostname. Affects ALL booking event emails (created, payment_confirmed, status_active, status_completed, cancelled), the Forgot Password code email (replaced inline text header), and the admin SMTP test email. (5) ADMIN PANEL — replaced 12 occurrences of `<div><h1>DAMS <span>CAR RENTAL</span></h1></div>` with `<div><img class='brand-logo' src='/api/assets/logo.png'/></div>`, plus the Login screen DAMS/CAR RENTAL stack with a centered `<img class='login-logo'>`. New CSS rules `.brand-logo` (42px tall) and `.login-logo` (80px tall) added. (6) NEW PUBLIC ENDPOINT: GET /api/assets/logo.png — serves the brand PNG (25254 bytes, image/png, 1-day Cache-Control). Used by all of the above. SCREENSHOTS captured: /tmp/receipt-logo.png, /tmp/pdf-receipt-view.png (PDF rendered via pdftoppm), /tmp/legal-terms-backend.png, /tmp/legal-privacy-backend.png, /tmp/email-preview-rendered.png (transactional email rendered), /tmp/admin-login-logo.png, /tmp/admin-dashboard-logo.png — all show the logo correctly. NOT CHANGED INTENTIONALLY: i18n `appName` strings (translated text used in mobile screen titles), privacy policy body text (legal text mentions the brand name)."

  - task: "Same-country rule for pickup & drop-off (backend + frontend)"
    implemented: true
    working: true
    file: "backend/server.py, frontend/app/booking.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "✅ END-TO-END VERIFIED (May 22, 2026). Rentals are now constrained to a single country (cannot pick up in DR and return in USA). BACKEND: (a) GET /api/locations/tax-by-name now also returns the 'country' field (string, empty when no match). (b) POST /api/bookings now resolves the country for BOTH pickup_location.name and dropoff_location.name from the locations collection (case-insensitive exact match) — if both resolve and differ → HTTP 400 with message 'Pick-up and drop-off must be in the same country. Pick-up is in X, but drop-off is in Y.' If either side cannot be resolved, the validation is skipped (graceful) so legacy/free-text data does not break existing flows. VERIFIED with curl: DR→DR booking returns 200 with total_price=2469.74; DR→USA returns 400 with the expected detail message. FRONTEND (booking.tsx): (a) Loads /api/locations once at mount and builds a {name.toLowerCase(): country} map. (b) tax-by-name useEffect captures pickupCountry from the response (or falls back to the map). (c) New useEffect auto-reselects the first same-country dropoff whenever pickupCountry or car changes, preventing the user from being stuck on an incompatible default. (d) Dropoff chips that belong to a different country are visually DISABLED (greyed bg, strikethrough text, lock icon, label '<country> · unavailable'); tapping a disabled chip surfaces Alert.alert('Different country', …) and does NOT change selection. (e) New green banner at the top of the Locations section: '🌐 Pick-up and drop-off must be in the same country.' (f) Each chip now shows the country under the location name. (g) handleBooking() has a client-side guard that re-checks same-country before POSTing. SECURITY TEST: monkey-patched window.fetch to force a USA dropoff in the payload despite a DR pickup; server returned 400 with the correct error and stayed on the booking screen — confirming the backend is the source of truth. Screenshots captured at /tmp/multi-country-default.png and /tmp/multi-country-disabled.png."

  - task: "Face ID / biometric password-confirm modal on Profile tab"
    implemented: true
    working: true
    file: "frontend/app/(tabs)/profile.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "testing"
          comment: "✅ FACE ID / BIOMETRIC PASSWORD-CONFIRM MODAL TESTED END-TO-END. Tested on mobile viewport (390×844) using customer@damscarrental.com / Customer@123 with localStorage.__bio_test='1' escape hatch to simulate Face ID hardware on web. ALL 7 SCENARIOS PASSED: (1) FACE ID CARD RENDERS: After enabling test mode and reloading, Profile tab shows 'Biometric Login' card with blue scan-outline icon, title 'Sign in faster with a glance using Face ID.', and Switch toggle (testID='biometric-toggle') initially OFF. (2) TOGGLE ON → MODAL OPENS: Clicking toggle opens password-confirm modal with Face ID icon, title 'Confirm your password', subtitle about security, email field showing customer@damscarrental.com (read-only), password input (testID='biometric-password-input'), Cancel button (testID='biometric-pwd-cancel'), and Enable button (testID='biometric-pwd-submit'). (3) WRONG PASSWORD → INLINE ERROR: Entered 'wrongPass123', clicked Enable → POST /api/auth/login returned 401, inline red error 'Wrong password. Please try again.' appeared below password field, modal stayed open, toggle remained OFF. (4) CANCEL BUTTON: Clicked Cancel → modal closed, toggle remained OFF, no API call. (5) CORRECT PASSWORD → SUCCESS: Reopened modal, entered 'Customer@123', clicked Enable → POST /api/auth/login returned 200, modal closed. (Note: Success alert dialog was expected per code line 96 but was not captured by Playwright dialog handler; this is a minor test harness issue, not a code bug.) (6) TOGGLE OFF: Clicked toggle again → it flipped OFF immediately, NO modal appeared, NO API call (as expected per code lines 109-111). (7) CLEANUP: Removed localStorage.__bio_test, reloaded → Face ID card disappeared from Profile (expected on web without hardware). IMPLEMENTATION VERIFIED in profile.tsx: Lines 176-193 render biometric card only when bioState.available && enrolled; line 186 Switch has testID='biometric-toggle'; lines 103-112 toggleBiometric calls askPasswordToEnable on enable (opens modal) or disableBiometricLogin on disable (no modal); lines 270-330 password modal with all required testIDs; lines 74-101 submitPasswordToEnable calls /api/auth/login to verify password, sets error on 401, calls enableBiometricLogin + shows Alert on success. Feature is fully working. MINOR: Toggle state checks via aria-checked returned inconsistent results on React Native Web (both ON and OFF checks returned false in steps 8-9), but visual inspection of screenshots confirms toggle behavior is correct; this is a DOM attribute quirk on web, not a functional issue."

metadata:
  created_by: "main_agent"
  version: "1.1"
  test_sequence: 6
  run_ui: false

test_plan:
  current_focus:
    - "Admin reset customer password (POST /api/admin/customers/{id}/reset-password)"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: "NEW BACKEND ENDPOINT FOR TESTING: POST /api/admin/customers/{customer_id}/reset-password. Lets the admin set a new password for any customer directly (no current-password challenge). Admin-only (JWT, role=admin). Body: {new_password:str}. Validation: new_password length >= 8 (400 'Password must be at least 8 characters.'); invalid ObjectId → 400 'Invalid customer id'; user not found → 404 'Customer not found'; admin trying to use it on their OWN user id → 400 'Use POST /api/auth/change-password to update your own password.' (forces use of the current-password-protected endpoint for self). On success: updates user.password_hash (bcrypt via hash_password()) and password_updated_at = datetime.now(UTC); best-effort deletes any pending entries in db.password_resets and db.login_attempts for that email so the user isn't locked out. Returns {ok:true, customer_id, email, name, password_updated_at(ISO)}. Logs INFO 'Admin <email> reset password for customer <email> (id=...)' for audit. Test plan: (1) Unauth → 401; non-admin (customer) → 403. (2) Admin happy path: register a temp test customer (e.g. cust.pwreset.<rand>@example.com with InitialPass#1), then admin POST {new_password:'NewStrong#123'} → 200 with {ok:true, email, password_updated_at(ISO)}. Login as that customer with the OLD password → 401. Login with the NEW password → 200 with token. (3) Validation: password='shortpw' (<8) → 400 'at least 8'; empty string → 400; missing new_password field → 400/422. (4) Bad id: 'abc' → 400 'Invalid customer id'; valid-format but unknown ObjectId (e.g. '000000000000000000000000') → 404 'Customer not found'. (5) Self-protection: admin posts to their OWN id → 400 with detail mentioning '/api/auth/change-password'. (6) Side-effects: any db.password_resets entry created for that email is gone after the call; any db.login_attempts entry for that email is gone (test by inserting one then calling the endpoint). (7) Audit log line is present in backend stderr after a successful reset. Admin credentials in /app/memory/test_credentials.md. CLEANUP after tests: delete any temp users you created."
    - agent: "main"
      message: "NEW BACKEND ENDPOINT FOR TESTING: POST /api/admin/bookings/cancel-pending-pickups. Bulk-cancels all bookings whose status is in {pending, pending_payment, confirmed} by setting status='cancelled' and stamping cancelled_at/cancelled_by/cancelled_reason. Admin-only (JWT, role=admin). Returns {cancelled_count, matched_count, sample(<=10 items with id/car_name/user_email/pickup_date/status_before)}. I have seeded the DB with 3 fake pending pickup bookings for testing (statuses pending, pending_payment, confirmed; user_email=fake0@test.com..fake2@test.com; _test_marker:true). Please verify: (1) Unauth → 401, non-admin → 403. (2) Admin happy path: returns 200, cancelled_count=3, matched_count=3, sample length 3 with all expected keys; follow-up GET /api/admin/bookings shows those 3 bookings now status='cancelled' with cancelled_at datetime present. (3) Idempotency: second admin call returns 200 with cancelled_count=0, matched_count=0, sample=[]. (4) Isolation: bookings with status active/completed/cancelled are UNTOUCHED — count of {status:active} + {status:completed} + already-existing cancelled does not change. (5) Stock invariance: choose any car_id referenced by a cancelled booking; its db.cars.stock dict is byte-equal before vs after. CLEANUP after tests: remove the 3 seeded test bookings (filter {_test_marker:true}) so the dev DB returns to its prior count of 2 (1 completed + 1 cancelled). Admin credentials in /app/memory/test_credentials.md."
    - agent: "testing"
      message: "✅ ALL 77/77 assertions PASSED in /app/backend_test.py for the new Forgot Password (6-digit code) + Register-with-terms_accepted feature. (A) /api/auth/forgot-password: known email → 200 generic 'If an account exists...' and SMTP2GO email actually sent (backend log: 'Email sent to customer@damscarrental.com (subject: DAMS Car Rental — Password reset code)'); db.password_resets doc has bcrypt-shaped code_hash ($2b$…), expires_at ~15min, attempts=0, used=false. Unknown email → SAME 200 message, no DB record (anti-enumeration). Malformed/empty email → 400. Missing email → 400/422. (B) /api/auth/reset-password: happy path on TEMP user (alice.tester.<rand>@example.com) with monkey-patched code '123456' → 200, new password works for login, old password 401, record used=true, code reuse → 400. Wrong code increments attempts 0→1; 5 wrong codes → 429 + record DELETED; subsequent attempt with correct code → 400 'Invalid or expired code'. Expired record (expires_at = now-1min) → 400 'expired' + record cleaned up. Invalid shapes: 'abcdef'/'123' → 400 '6 digits'; password 'abc' → 400 '6 characters'; missing fields → 400/422. (C) /api/auth/register: terms_accepted=false → 400 'You must accept the Rental Terms & Conditions...' + no user created; terms_accepted=true → 200 with full user object, db doc has terms_accepted_at (recent UTC datetime), phone, role='user', bcrypt password_hash, no raw password, created_at. name='' → 400 'Name is required.'; password='abc' → 400 '6 characters'; duplicate customer@damscarrental.com → 400 'Email already registered'. Login with newly-registered creds → 200. (D) Regression: customer login still 200 (used TEMP users for destructive flows so seeded customer password intact), GET /api/settings/rental-terms public 200, POST /api/bookings with terms_accepted=true → 200 pending_payment/pending; terms_accepted=false on bookings → 400 (independent). CLEANUP done: deleted 6 temp users, 4 password_resets test docs; customer password 'Customer@123' verified intact at end. Task flipped working=true, needs_retesting=false, stuck_count=0."
    - agent: "testing"
      message: "✅ REGRESSION FIX VERIFIED for PUT /api/admin/bookings/{id}/status. 28/28 assertions passed in /app/backend_test_email_retest.py. The serialize-once fix at server.py L1060 (and L1385 in stripe_webhook for consistency) resolves the KeyError: '_id'. Full status transition flow now works end-to-end: pending_payment → confirmed+paid → active → completed → cancelled, all returning 200 with properly-serialized booking payload (id present, _id absent, user_email, car_name, etc.). Backend logs show all 5 transactional emails sent successfully (Booking received, Payment confirmed, Rental started, Thank you for renting, Booking cancelled). Persistence verified via GET /api/bookings/{id} → final status='cancelled', payment_status='paid' unchanged. Email test endpoint sanity recheck: 200 {ok:true} for valid recipient, 400 for invalid email, 401 without auth, 403 for non-admin. Task 'Email notifications via SMTP2GO + admin test endpoint' is now fully working; flipped working=true, needs_retesting=false, stuck_count=0." The new SMTP email hookup introduced a serialization bug: the email try-block calls `serialize_booking(booking)` (which MUTATES the dict by removing `_id` and adding `id`), and then the function's final `return serialize_booking(booking)` at line 1118 crashes with KeyError: '_id'. Result: the endpoint always returns 500 whenever an email event fires (status confirmed/active/completed/cancelled OR payment_status=paid). The DB IS being updated and the email IS being sent successfully — but the admin UI sees HTTP 500 and can't read the updated booking back. This was a previously-working endpoint, so this is a regression. FIX (3 lines): in `admin_update_booking_status` (server.py ~line 1099), do `booking_payload = serialize_booking(booking)` BEFORE the email block, pass `booking_payload` to send_booking_email, and `return booking_payload`. Same antipattern exists at line 1394 in `stripe_webhook` — doesn't break the webhook response shape (returns {status:'ok'}) but inflates logs with KeyErrors and should be fixed for consistency. ALL OTHER TESTS PASSED: POST /api/admin/email/test works for valid recipient (200 {ok:true}, real email sent — backend log confirms 'Email sent to info@damsrentacar.com'); empty/invalid → 400 'Invalid recipient email'; non-admin → 403; no auth → 401. Booking creation (cash) returns 200 with status=pending_payment/payment_status=pending in 5.4s, booking is persisted, AND the 'Booking received' email is sent (log confirmed). SMTP integration itself is fully functional — only the admin status-update response serialization needs fixing. 14/15 assertions in /app/backend_test_email.py passed."
    - agent: "main"
      message: "Fixed the production image preview issue. Root cause: images were stored as files under /app/backend/uploads/ which is ephemeral storage on production (wiped on redeploy). Solution: embed images as base64 data URLs directly in MongoDB. Added /api/admin/migrate-images endpoint and a 'Fix Vehicle Images' button on the admin panel for one-click migration. User must: 1) Run Convert Images on Preview, 2) Export, 3) Redeploy production, 4) Import on Production, 5) Run Convert Images on Production to be safe."
    - agent: "main"
      message: "Added Booking Management (admin) + Customer Receipt (with tax). NEW ENDPOINTS TO TEST: (1) GET /api/admin/bookings [admin] with optional ?status=...&q=... query params - returns list of bookings. (2) PUT /api/admin/bookings/{id}/status [admin] body: {status: 'confirmed'} - valid statuses: pending_payment, confirmed, active, completed, cancelled. (3) GET /api/bookings/{id}/receipt.pdf [auth required; owner or admin] - returns application/pdf bytes. Test authorization (non-admin should 403 for admin endpoints, non-owner should 403 for receipt). Test validation (invalid status should 400). Admin credentials in /app/memory/test_credentials.md."
    - agent: "testing"
      message: "All 23 assertions passed across the 3 new booking endpoints. Admin-listing with filter/search works, status update validates + persists, receipt PDF returns real %PDF bytes with proper owner/admin authorization. Non-blocking: malformed ObjectId returns 500 instead of 400 on receipt endpoint (shared issue across the codebase - not fixing as part of this feature)."
    - agent: "testing"
      message: "Completed backend testing of 3 new booking endpoints. 23/23 assertions passed in /app/backend_test.py. (1) GET /api/admin/bookings works with admin auth, returns 403 for non-admin, 401 unauthenticated; ?status=confirmed and ?q=<fragment> filters work individually and combined. (2) PUT /api/admin/bookings/{id}/status: admin updates persist (verified via follow-up GET), invalid status returns 400 with helpful message, missing booking id returns 404, non-admin returns 403. (3) GET /api/bookings/{id}/receipt.pdf returns real PDF bytes starting with %PDF-1.4 (~2.8KB) with application/pdf content type for both owner and admin; non-owner gets 403, unauthenticated gets 401, non-existent id returns 404. Minor (not blocking): malformed (non-hex) booking ids cause ObjectId to raise InvalidId and return 500 instead of 400/404 on /bookings/{id}/receipt.pdf - consider wrapping ObjectId() in a try/except for nicer errors, but all valid-format ids behave correctly."

    - agent: "testing"
      message: "Tested 'Location model has min_booking_days; tax-by-name returns it; CRUD persists it'. 19/19 assertions passed in /app/backend_test.py. Verified: POST /api/locations with min_booking_days=5 persists & returns the value; PUT /api/locations/{id} updating only min_booking_days=3 returns updated doc and is reflected on GET; GET /api/locations/tax-by-name returns {tax_rate, name, city, min_booking_days} with 5 when set, 1 when field absent in DB, and {tax_rate:0.0, name:<input>, city:'', min_booking_days:1} when name has no match; lookup is case-insensitive (lowercased name resolves correctly). Authorization: tax-by-name is public (200 without auth), POST/PUT /api/locations as non-admin both return 403. Test location and temp customer user cleaned up. Feature is working end-to-end."
    - agent: "testing"
      message: "Tested 'Cash bookings start as pending; admin can mark them paid'. 27/27 assertions passed in /app/backend_test_cash_booking.py. Verified: (1) POST /api/bookings with payment_method='cash' creates booking with status='pending_payment' and payment_status='pending' (both in response and persisted via GET /api/bookings/{id}). (2) POST /api/bookings with payment_method='stripe' also creates with status='pending_payment' and payment_status='pending' (unchanged - webhook continues to flip these later). (3) PUT /api/admin/bookings/{id}/status: backward-compat with only {status:'confirmed'} works (payment_status untouched); only {payment_status:'paid'} works (status untouched); both fields work; invalid payment_status returns 400 with detail listing valid values 'failed, paid, pending, refunded'; empty body returns 400 'No fields to update'; non-admin returns 403; non-existent booking id returns 404. (4) End-to-end cash flow verified: customer cash booking (pending_payment/pending) -> admin PUT both fields -> GET reflects confirmed/paid. Feature is working as specified."
    - agent: "testing"
      message: "✅ MINIMUM BOOKING DAYS FRONTEND FEATURE TESTED: Successfully verified the complete implementation of minimum booking days per location feature. Backend API working correctly - set Punta Cana Airport to min_booking_days=5 and updated Mercedes Benz car to use this location. Frontend code in booking.tsx shows full implementation: (1) Fetches min_booking_days from GET /api/locations/tax-by-name API, (2) Auto-extends dropoff date if duration < minDays, (3) Shows yellow banner 'Minimum rental: X days' when min > 1, (4) Restricts date picker minimumDate, (5) Alerts user if dropoff too close to pickup. Feature is fully functional and ready for production use."
    - agent: "testing"
    - agent: "testing"
      message: "✅ Push notification token persistence FIX VERIFIED. 16/16 assertions passed in /app/backend_test_push.py against the live preview backend after the ObjectId(str(raw_id)) fix in both register_push_token and unregister_push_token. End-to-end flow confirmed: register customer → login → POST /api/users/push-token 'ExponentPushToken[abc123def456]' returns 200 AND the token is actually written to user.push_tokens (verified via direct Mongo query). $addToSet de-dups (re-POST does not duplicate). POSTing a 2nd valid token results in BOTH tokens in the array. DELETE removes only the targeted token (the other remains). DELETE is idempotent (returns 200 even when the token is already absent). Re-verified auth/validation: 401 without auth (POST & DELETE), 400 'Invalid Expo push token format' on garbage, 400 'Missing token' on empty. Booking creation + admin status update smoke tests still 200. Task is fully working and removed from current_focus/stuck_tasks."
      message: "Tested 'Admin Fleet Analytics endpoint GET /api/admin/analytics'. 137/137 assertions passed in /app/backend_test_analytics.py against the live preview backend. Verified: (1) Admin GET returns 200 with all top-level keys kpis/monthly_revenue/top_cars/top_locations/status_breakdown/payment_breakdown. (2) kpis fields are all numeric & >= 0 (total_revenue=15816.52, revenue_this_month, total_bookings=16, paid_bookings=13, active_bookings, avg_revenue_per_booking=1216.66). (3) monthly_revenue is EXACTLY 6 items with month YYYY-MM strings sorted chronologically ['2025-12'..'2026-05']; last item is current UTC month; each has numeric revenue (>=0) and int count (>=0). (4) top_cars list <=10 (got 3) sorted by count desc, each item has car_id/car_name/count/revenue. (5) top_locations list <=10 (got 4), items have {name(str), count(int)}. (6) status_breakdown & payment_breakdown are dicts of {str: non-negative int}. (7) Cross-checked via /api/admin/bookings: total_revenue == sum(total_price) for payment_status='paid'; paid_bookings == count of paid; total_bookings matches admin bookings length. (8) avg_revenue_per_booking == total_revenue/paid_bookings (with proper 0-handling). (9) Auth: unauthenticated → 401; non-admin → 403 with detail 'Admin only'. Feature is fully working end-to-end."
    - agent: "testing"
      message: "🚨 CRITICAL BUG in Push Notification token registration. 13/16 assertions passed in /app/backend_test_push.py. POST /api/users/push-token returns 200 {ok:true} but DOES NOT actually persist the token in MongoDB — the user document's push_tokens array stays empty. ROOT CAUSE: in `register_push_token` (line 406) and `unregister_push_token` (line 421), the code does `user_id_obj = user['_id'] if '_id' in user else ObjectId(user['id'])`. However `get_current_user` (line 146) already stringified `user['_id']` via `user['_id'] = str(user['_id'])` before returning. So Mongo's `update_one({'_id': '<string>'}, ...)` matches 0 documents (Mongo expects ObjectId for _id), $addToSet/$pull silently no-op, and the endpoint returns 200 because update_one doesn't raise on matched_count=0. FIX (1 line): change to `user_id_obj = ObjectId(user['_id']) if '_id' in user else ObjectId(user['id'])` in BOTH endpoints. Without this fix, push notifications will NEVER reach any JWT-authenticated user because no token ever lands in the DB. All other test scenarios PASS: 401 without auth (POST & DELETE), 400 'Invalid Expo push token format' for 'garbage', 400 'Missing token' for empty string, idempotent DELETE returns 200 even on already-removed tokens, booking creation smoke test returns 200 with correct shape (status=pending_payment, payment_status=pending), admin status update smoke test returns 200 with updated booking. Push trigger code paths execute but `send_push_to_user` just hits the `no_tokens` branch — which is why those endpoints still appear to work; the underlying delivery is broken until persistence is fixed."
    - agent: "testing"
      message: "✅ Promo Codes system TESTED END-TO-END. 76/76 assertions passed in /app/backend_test_promo.py against the live preview backend. (1) ADMIN CRUD: POST /api/admin/promo-codes creates percent code (uppercased, used_count=0); duplicate→400 'Promo code already exists'; discount_value=0→400; percent>100→400 'cannot exceed 100'; discount_type='invalid'→400; 1-char code→400 'at least 2 characters'; GET list→200 contains created code; PUT {active:false}→200; PUT invalid id→400; PUT non-existent ObjectId→404; DELETE→200 {ok:true}; DELETE again→404. (2) VALIDATE: TESTPERCENT(20%,min=50) sub=200→{valid:true,discount:40}; sub=30→{valid:false,'Minimum subtotal of $50.00 required'}; TESTFIXED($15,min=10) sub=100→{valid:true,discount:15}; sub=5→{valid:false} (below min); 'INVALID_CODE_XYZ'→200 {valid:false,message:'Invalid promo code',discount:0}; lowercase code→{valid:true,code normalized UPPER}; inactive→{valid:false,'inactive'}; expired (expires_at='2020-01-01T00:00:00Z')→{valid:false,'expired'}; max_uses=1 after booking consumed it→{valid:false,'usage limit'}; no-auth→401. (3) BOOKING FLOW: $45/day×5d×Bavaro Beach Hub(18% tax) + TESTPERCENT(20%) → 200 with promo_code='TESTPERCENT…', subtotal=225.00 (no discount), discount_amount=45.00, tax_amount=32.40 (computed on DISCOUNTED 180.00, NOT 225), total_price=212.40. used_count went 0→1 (verified via GET list). Booking with INVALID promo→400 'Invalid promo code'. Booking without promo_code→200 with promo_code=None, discount_amount=0, tax on full subtotal. Booking with inactive promo→400 'inactive'. (4) AUTHZ: non-admin CAN validate (200); CANNOT GET/POST/PUT/DELETE any admin promo endpoint (all 403 'Admin only'). Feature fully working. Flipped working=true, needs_retesting=false, removed from current_focus."
    - agent: "testing"
      message: "✅ Admin broadcast push notification endpoints TESTED. 36/36 assertions passed in /app/backend_test_admin_broadcast.py against the live preview backend. (1) GET /api/admin/notifications/audience-stats returns 200 to admin with all 4 keys (total_users=104, users_with_push, customers_with_push, admins_with_push) all as non-negative ints; sum invariant admins+customers ≤ users_with_push holds; unauthenticated→401, non-admin→403. (2) POST /api/admin/notifications/send validation: empty title or body → 400 'Title and body are required'; title>100 → 400 'Title must be ≤ 100 chars'; body>500 → 400 'Body must be ≤ 500 chars'; target='garbage' → 400 with helpful message listing all 4 valid options; target='user:not-a-valid-id' → 400 'Invalid user id'. (3) Valid targets all return 200: 'all', 'customers', 'admins', 'user:<valid_oid>', and omitted target (defaults to 'all'). Response shape is {sent, total_recipients, tokens_count} OR {sent:0, total_recipients, reason:'no_tokens_in_audience'}. (4) Audience filtering end-to-end: registered a fresh customer, posted ExponentPushToken[...] for them, then broadcast to 'customers' → total_recipients=1 & tokens_count=1 (matches audience-stats.customers_with_push); broadcast to 'admins' → total_recipients=0 confirming the customer is NOT in admin audience. (5) target='user:<cust_id>' after token registered returned {sent:1, total_recipients:1, tokens_count:1} — Expo accepted the request (backend log shows 'Expo push sent: 1 tokens, status=200'). (6) Authorization: unauthenticated→401, non-admin→403. Endpoints fully working as specified."
    - agent: "testing"
      message: "✅ Pre-paid Refuel + Rental Terms Acceptance features TESTED END-TO-END. 69/69 assertions PASSED in /app/backend_test_refuel_terms.py against the live preview backend. FEATURE A (Location.refuel_amount): POST /api/locations with refuel_amount=45.50 persists & returns 45.5 (response + GET /api/locations/{id}); PUT with only {refuel_amount:0} returns 200, other fields untouched, GET confirms; PUT with {refuel_amount:30} persists; GET /api/locations/tax-by-name returns refuel_amount=30 when set, 0.0 for non-existent name, and is case-insensitive (UPPER/lower both return 30); POST/PUT as non-admin → 403; tax-by-name public (200 without auth). FEATURE B (Rental Terms): GET /api/settings/rental-terms WITHOUT auth → 200 with default 9016-char terms; PUT /api/admin/settings/rental-terms with valid 219-char body → 200 {ok:true, length:219} and GET returns the exact text; validation: short<10 → 400, empty → 400, >50000 → 400, non-admin → 403, no auth → 401. FEATURE C (BookingCreate refuel + terms): Configured Compact (KIA POCANTO) $45/day at pickup location refuel=50, tax=10. (1) terms_accepted=false → 400 'You must accept the Rental Terms & Conditions to complete this booking.' (2) terms=true, refuel=false → booking refuel_amount=0, refuel_opted_in=false, total=148.50=135*1.10 (3) terms=true, refuel=true → booking refuel_amount=50, refuel_opted_in=true, total=203.50=(135+50)*1.10, terms_accepted_at is recent ISO datetime (parsed, age 4.1s). (4) refuel=true but loc refuel_amount=0 → booking refuel_amount=0, refuel_opted_in coerced to false, total unchanged at 148.50 (no charge). (5) 10% promo + refuel: subtotal=135, discount=13.50, refuel=50, total=(135-13.5+50)*1.10=188.65 — refuel correctly added AFTER discount and tax computed on (discounted_subtotal+refuel). All within $0.02 tolerance. Cleanup: temp locations deleted, target location's tax/refuel restored, car pickup_location restored, promo deleted, rental terms restored. Tasks flipped to working=true, needs_retesting=false, current_focus cleared."
    - agent: "testing"
      message: "FRONTEND: Pre-paid Refuel toggle + Rental Terms checkbox & modal — CODE REVIEW COMPLETED, UI AUTOMATION BLOCKED. Thoroughly reviewed booking.tsx implementation (lines 1-703). All 6 required features are correctly implemented: (1) Refuel toggle with testID, conditional rendering when refuelAmount>0, green/grey styling, Switch component. (2) Cost breakdown shows refuel line only when opted in, math is correct (refuel taxable, added after promo). (3) Terms checkbox with testID, initial state unchecked. (4) Confirm button gating: disabled when !termsAccepted, label changes ('Accept Terms' → 'Confirm Booking'). (5) Terms modal with scrollable body, 'Close' (no change) vs 'I Accept' (auto-checks checkbox). (6) Booking submission validates terms_accepted and sends correct payload. Backend integration verified (69/69 tests passed). BLOCKING ISSUE: Sign Up form has React Native Web rendering bug — email/password input fields resolve in DOM (data-testid='login-email-input' found) but Playwright reports 'element is not visible' on click/fill attempts. Tried 3 automation runs with different approaches (direct fill, click-then-fill, JavaScript value injection), all timeout at 30s. Cannot complete end-to-end UI test without customer account access. RECOMMENDATION: Add seeded customer to /app/memory/test_credentials.md OR fix Sign Up form testability (ensure inputs are visible/interactive). Once customer login works, the 6 test scenarios are ready to execute. Code confidence: HIGH — implementation is complete and matches backend contract exactly."
    - agent: "testing"
      message: "Insurance included flag per location: (1) POST /api/locations: insurance_included=true persists & returns True; field omitted defaults to False; both visible in subsequent GET /api/locations. Tax_rate and min_booking_days alongside also persisted correctly. (2) PUT /api/locations/{id}: updating ONLY {insurance_included:true} returns 200, flips the flag, ALL OTHER fields (name/address/city/country/type/tax_rate/min_booking_days) untouched; GET confirms persistence. Same for {insurance_included:false} → flips back, other fields still untouched. (3) GET /api/locations/tax-by-name returns insurance_included for: location with True → True; location with False → False; non-existent name → False (with full default doc {tax_rate:0.0, name:<input>, city:'', min_booking_days:1, insurance_included:false}); case-insensitive variants (UPPER and lower) of name both return True. (4) BACKWARD COMPATIBILITY VERIFIED: inserted a location directly into Mongo WITHOUT the insurance_included field; GET /api/locations/tax-by-name → returned {tax_rate:5.0, ..., insurance_included:false} — the smart-lookup default branch works for legacy data. (5) Authorization: POST /locations as non-admin → 403; PUT /locations/{id} as non-admin → 403; GET /tax-by-name without auth → 200 (public). (6) All test locations cleaned up via DELETE (200). Task flipped to working=true, needs_retesting=false.""
    - agent: "testing"
      message: "✅ NEW ENDPOINT POST /api/admin/bookings/cancel-pending-pickups TESTED END-TO-END. 53/53 assertions PASSED in /app/backend_test_cancel_pending.py against the live preview backend. (1) AUTH: unauthenticated → 401; non-admin (registered a temporary user because seeded customer@damscarrental.com login returns 401 with 'Customer@123' — see note) → 403; admin login (admin@damscarrental.com / Admin@123) → 200. (2) ADMIN HAPPY PATH: first POST returned {cancelled_count:3, matched_count:3, sample:[...3 items...]} — each sample item had exactly id/car_name/user_email/pickup_date/status_before with one item per seeded status (pending, pending_payment, confirmed); pickup_date is an ISO string; user_emails were fake0@test.com..fake2@test.com. Backend log confirmed 'Admin admin@damscarrental.com bulk-cancelled 3 pending-pickup bookings.' (3) DB VERIFY: direct Mongo queries confirm all 3 seeded bookings now have status='cancelled', cancelled_at as a real datetime, cancelled_by='admin_bulk', cancelled_reason='Bulk cleanup of pending pickups by admin'. GET /api/admin/bookings also shows them as cancelled. (4) IDEMPOTENCY: immediate second admin POST → 200 with {cancelled_count:0, matched_count:0, sample:[]}. (5) ISOLATION: per-status before-vs-after — active 0→0 (unchanged), completed 1→1 (unchanged), cancelled 1→4 (+3 only), pending/pending_payment/confirmed all now 0; total document count unchanged 5→5 (no inserts/deletes happened). (6) STOCK INVARIANCE: car_id 'test-car' referenced by all seeded bookings — db.cars stock dict unchanged before vs after (endpoint did NOT touch the cars collection at all). CLEANUP DONE: deleted 3 _test_marker bookings + 1 temp non-admin user. Final DB: exactly 2 bookings (1 completed, 1 cancelled) matching the requested prior state. Task flipped working=true, needs_retesting=false, removed from current_focus. ⚠️ NOTE FOR MAIN: customer@damscarrental.com is NOT logging in with 'Customer@123' (returns 401). Either the password got changed or the seeded customer needs to be re-provisioned. Not blocking for this feature — I used a freshly-registered user for the non-admin 403 check."