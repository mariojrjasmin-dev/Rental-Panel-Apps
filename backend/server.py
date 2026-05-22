from dotenv import load_dotenv
from pathlib import Path as _Path
load_dotenv(_Path(__file__).parent / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import uuid
import secrets
import bcrypt
import jwt
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== EXPO PUSH NOTIFICATIONS ====================
import httpx
import aiosmtplib
from email.message import EmailMessage

EXPO_PUSH_API = "https://exp.host/--/api/v2/push/send"


async def send_expo_push(tokens: List[str], title: str, body: str, data: Optional[Dict] = None) -> Dict:
    """Send a push notification via the Expo Push API.
    Accepts a list of ExponentPushToken[...] strings. Silently skips empty/invalid tokens.
    Returns the parsed Expo response with ticket details and any failed tokens.
    """
    # Filter to valid Expo tokens
    valid_tokens = [t for t in (tokens or []) if isinstance(t, str) and t.startswith(("ExponentPushToken[", "ExpoPushToken["))]
    if not valid_tokens:
        return {"sent": 0, "skipped": True, "tickets": [], "errors": []}

    messages = [
        {
            "to": tok,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {},
            "priority": "high",
            "channelId": "default",
        }
        for tok in valid_tokens
    ]

    try:
        async with httpx.AsyncClient(timeout=15) as client_http:
            resp = await client_http.post(
                EXPO_PUSH_API,
                json=messages,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            raw = resp.json() if resp.status_code == 200 else {}
            tickets = raw.get("data", []) if isinstance(raw, dict) else []
            # Pair each ticket with its target token, collect errors and DeviceNotRegistered tokens
            errors: List[Dict] = []
            invalid_tokens: List[str] = []
            ok_count = 0
            for i, ticket in enumerate(tickets):
                tok = valid_tokens[i] if i < len(valid_tokens) else None
                if isinstance(ticket, dict) and ticket.get("status") == "ok":
                    ok_count += 1
                else:
                    err_code = (ticket.get("details") or {}).get("error") if isinstance(ticket, dict) else None
                    errors.append({
                        "token": tok,
                        "status": ticket.get("status") if isinstance(ticket, dict) else "unknown",
                        "message": ticket.get("message") if isinstance(ticket, dict) else None,
                        "error_code": err_code,
                    })
                    if err_code == "DeviceNotRegistered":
                        invalid_tokens.append(tok)

            # Auto-cleanup: remove DeviceNotRegistered tokens from all users
            removed = 0
            if invalid_tokens:
                try:
                    r = await db.users.update_many(
                        {"push_tokens": {"$in": invalid_tokens}},
                        {"$pull": {"push_tokens": {"$in": invalid_tokens}}},
                    )
                    removed = r.modified_count
                    logger.info(f"Removed {removed} invalid push tokens (DeviceNotRegistered)")
                except Exception as ce:
                    logger.warning(f"Failed to cleanup invalid tokens: {ce}")

            logger.info(f"Expo push: requested={len(valid_tokens)}, accepted={ok_count}, errors={len(errors)}, status={resp.status_code}")
            return {
                "sent": ok_count,
                "requested": len(valid_tokens),
                "errors": errors,
                "invalid_tokens_removed": removed,
                "raw_status": resp.status_code,
            }
    except Exception as e:
        logger.warning(f"Expo push failed: {e}")
        return {"sent": 0, "requested": len(valid_tokens), "error": str(e), "errors": []}


async def send_push_to_user(user_id: str, title: str, body: str, data: Optional[Dict] = None) -> Dict:
    """Look up a user's stored push tokens and send a notification.
    Fails silently (logs warnings) so booking flows are never blocked by push errors.
    """
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}) if ObjectId.is_valid(user_id) else None
        if not user:
            return {"sent": 0, "reason": "user_not_found"}
        tokens = user.get("push_tokens") or []
        if not tokens:
            return {"sent": 0, "reason": "no_tokens"}
        return await send_expo_push(tokens, title, body, data)
    except Exception as e:
        logger.warning(f"send_push_to_user error: {e}")
        return {"sent": 0, "error": str(e)}


async def send_push_to_admins(title: str, body: str, data: Optional[Dict] = None) -> Dict:
    """Broadcast a notification to ALL admins (e.g., new booking alerts)."""
    try:
        admins = await db.users.find({"role": "admin"}, {"push_tokens": 1}).to_list(50)
        all_tokens: List[str] = []
        for a in admins:
            all_tokens.extend(a.get("push_tokens") or [])
        # De-duplicate
        all_tokens = list(set(all_tokens))
        return await send_expo_push(all_tokens, title, body, data)
    except Exception as e:
        logger.warning(f"send_push_to_admins error: {e}")
        return {"sent": 0, "error": str(e)}



# ==================== EMAIL NOTIFICATIONS (SMTP) ====================
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USER)
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "DAMS Car Rental")


async def send_email(to: str, subject: str, html: str, text: Optional[str] = None) -> Dict:
    """Send an email via SMTP (SMTP2GO). Fire-and-forget; never raises to caller."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and to):
        return {"ok": False, "error": "SMTP not configured or no recipient"}
    try:
        msg = EmailMessage()
        msg["From"] = f'{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>'
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text or "Please open this email in an HTML-capable client.")
        msg.add_alternative(html, subtype="html")
        await aiosmtplib.send(
            msg, hostname=SMTP_HOST, port=SMTP_PORT,
            username=SMTP_USER, password=SMTP_PASSWORD,
            start_tls=True, timeout=15,
        )
        logger.info(f"Email sent to {to} (subject: {subject!r})")
        return {"ok": True}
    except Exception as e:
        logger.warning(f"Email send to {to} failed: {e}")
        return {"ok": False, "error": str(e)}


def _email_template(title: str, intro: str, body_blocks_html: str, cta_label: Optional[str] = None, cta_url: Optional[str] = None) -> str:
    cta = ""
    if cta_label and cta_url:
        cta = f'<a href="{cta_url}" style="display:inline-block;background:#FF3B30;color:#fff;text-decoration:none;padding:14px 28px;border-radius:8px;font-weight:700;margin-top:24px">{cta_label}</a>'
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <div style="max-width:600px;margin:0 auto;background:#fff;padding:32px 24px">
    <div style="text-align:center;margin-bottom:24px">
      <div style="font-size:28px;font-weight:900;color:#0a0a0a;letter-spacing:1px">DAMS</div>
      <div style="font-size:11px;font-weight:700;color:#FF3B30;letter-spacing:4px">CAR RENTAL</div>
    </div>
    <h1 style="color:#0a0a0a;font-size:22px;font-weight:800;margin:0 0 12px">{title}</h1>
    <p style="color:#555;font-size:15px;line-height:1.5;margin:0 0 20px">{intro}</p>
    {body_blocks_html}
    {cta}
    <hr style="border:0;border-top:1px solid #eee;margin:32px 0">
    <p style="color:#999;font-size:12px;line-height:1.5;margin:0;text-align:center">
      You are receiving this email because you made a booking with DAMS Car Rental.<br>
      Need help? Reply to this email or contact us at {SMTP_FROM_EMAIL}.
    </p>
  </div>
</body></html>"""


def _booking_summary_block(booking: dict) -> str:
    car = booking.get("car_name") or "Vehicle"
    pickup_date = (str(booking.get("pickup_date") or ""))[:10]
    drop_date = (str(booking.get("dropoff_date") or ""))[:10]
    pickup_loc = (booking.get("pickup_location") or {}).get("name", "—")
    drop_loc = (booking.get("dropoff_location") or {}).get("name", "—")
    total = booking.get("total_price") or 0
    subtotal = booking.get("subtotal") or 0
    tax = booking.get("tax_amount") or 0
    rows = [
        ("Vehicle", car),
        ("Pickup", f"{pickup_date} · {pickup_loc}"),
        ("Drop-off", f"{drop_date} · {drop_loc}"),
        ("Subtotal", f"${float(subtotal):,.2f}"),
        ("Tax", f"${float(tax):,.2f}"),
        ("Total", f"<strong style='color:#FF3B30'>${float(total):,.2f}</strong>"),
        ("Payment", (booking.get("payment_method") or "—").upper()),
    ]
    rows_html = "".join(
        f"<tr><td style='padding:8px 0;color:#666;font-size:13px'>{k}</td>"
        f"<td style='padding:8px 0;color:#0a0a0a;font-size:13px;text-align:right;font-weight:600'>{v}</td></tr>"
        for k, v in rows
    )
    return (
        "<div style='background:#fafafa;border-radius:12px;padding:16px;margin:16px 0'>"
        "<div style='font-size:11px;font-weight:700;color:#999;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px'>Booking summary</div>"
        f"<table style='width:100%;border-collapse:collapse'>{rows_html}</table>"
        "</div>"
    )


async def send_booking_email(event: str, booking: dict, user_email: Optional[str] = None) -> Dict:
    to = user_email or booking.get("user_email")
    if not to:
        return {"ok": False, "error": "no_recipient"}
    car = booking.get("car_name") or "your vehicle"
    short_id = str(booking.get("id") or "")[-8:].upper()
    summary = _booking_summary_block(booking)
    cfgs = {
        "created": {
            "subject": f"Booking received · #{short_id}",
            "title": "We received your booking!",
            "intro": f"Thank you for choosing DAMS Car Rental. Your booking for <strong>{car}</strong> is now pending payment confirmation.",
        },
        "payment_confirmed": {
            "subject": f"Payment confirmed · #{short_id}",
            "title": "Your booking is confirmed!",
            "intro": f"We have received payment for your booking of <strong>{car}</strong>. See you at pickup!",
        },
        "status_active": {
            "subject": f"Rental started · #{short_id}",
            "title": "Your rental is now active",
            "intro": f"Your rental of <strong>{car}</strong> has begun. Drive safely!",
        },
        "status_completed": {
            "subject": f"Thank you for renting with us · #{short_id}",
            "title": "Rental completed — thank you!",
            "intro": f"Your rental of <strong>{car}</strong> has been completed. We hope you enjoyed your trip!",
        },
        "cancelled": {
            "subject": f"Booking cancelled · #{short_id}",
            "title": "Booking cancelled",
            "intro": f"Your booking of <strong>{car}</strong> has been cancelled. If this was unexpected, please contact us.",
        },
    }
    cfg = cfgs.get(event)
    if not cfg:
        return {"ok": False, "error": f"unknown_event:{event}"}
    html = _email_template(cfg["title"], cfg["intro"], summary)
    return await send_email(to, cfg["subject"], html)


# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT config
JWT_ALGORITHM = "HS256"

def get_jwt_secret():
    return os.environ["JWT_SECRET"]

# Password helpers
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# Token helpers
def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=24), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

# Auth helper
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Optional auth (returns None if no token)
async def get_optional_user(request: Request) -> Optional[dict]:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None

# Emergent Google Auth helper
async def get_current_user_google(request: Request) -> dict:
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Unified auth helper - checks both JWT and Google session
async def get_authenticated_user(request: Request) -> dict:
    # Try JWT first
    try:
        return await get_current_user(request)
    except HTTPException:
        pass
    # Try Google session
    try:
        return await get_current_user_google(request)
    except HTTPException:
        pass
    raise HTTPException(status_code=401, detail="Not authenticated")

# Pydantic models
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    phone: Optional[str] = None
    terms_accepted: bool = False

class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

class CarCreate(BaseModel):
    name: str
    brand: str
    model: str
    year: int
    category: str
    price_per_day: float
    seats: int
    bags: int = 2
    min_booking_days: int = 1
    transmission: str = "Automatic"
    fuel_type: str = "Gasoline"
    description: str = ""
    image_url: str = ""
    images: List[str] = []  # Additional photos beyond the primary image_url
    pickup_location: Optional[Dict] = None  # DEPRECATED — kept for backward compat (mirrors pickup_locations[0])
    dropoff_location: Optional[Dict] = None  # DEPRECATED — kept for backward compat
    pickup_locations: List[Dict] = []  # Multi-select: list of {name, lat, lng}
    dropoff_locations: List[Dict] = []  # Multi-select: list of {name, lat, lng}
    available: bool = True
    # Mileage & premium features
    unlimited_mileage: bool = True
    mileage_limit: Optional[int] = None  # km/day cap when unlimited_mileage = False
    min_driver_age: int = 21
    android_auto: bool = False
    apple_carplay: bool = False
    blind_spot_warning: bool = False
    gps: bool = False
    keyless_entry: bool = False
    sunroof: bool = False

class CarUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None
    price_per_day: Optional[float] = None
    seats: Optional[int] = None
    bags: Optional[int] = None
    min_booking_days: Optional[int] = None
    transmission: Optional[str] = None
    fuel_type: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = None
    pickup_location: Optional[Dict] = None  # DEPRECATED — kept for backward compat
    dropoff_location: Optional[Dict] = None  # DEPRECATED — kept for backward compat
    pickup_locations: Optional[List[Dict]] = None  # Multi-select list
    dropoff_locations: Optional[List[Dict]] = None  # Multi-select list
    available: Optional[bool] = None
    unlimited_mileage: Optional[bool] = None
    mileage_limit: Optional[int] = None
    min_driver_age: Optional[int] = None
    android_auto: Optional[bool] = None
    apple_carplay: Optional[bool] = None
    blind_spot_warning: Optional[bool] = None
    gps: Optional[bool] = None
    keyless_entry: Optional[bool] = None
    sunroof: Optional[bool] = None

class BookingCreate(BaseModel):
    car_id: str
    pickup_date: str
    dropoff_date: str
    pickup_location: Dict
    dropoff_location: Dict
    payment_method: str = "cash"
    promo_code: Optional[str] = None
    refuel_opted_in: bool = False
    terms_accepted: bool = False


# ==================== PROMO CODES ====================
class PromoCodeCreate(BaseModel):
    code: str
    discount_type: str  # "percent" | "fixed"
    discount_value: float
    max_uses: int = 0  # 0 = unlimited
    expires_at: Optional[str] = None  # ISO date string or null
    min_amount: float = 0.0
    active: bool = True


class PromoCodeUpdate(BaseModel):
    code: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    max_uses: Optional[int] = None
    expires_at: Optional[str] = None
    min_amount: Optional[float] = None
    active: Optional[bool] = None


class PromoValidateRequest(BaseModel):
    code: str
    subtotal: float


def _validate_promo(promo: dict, subtotal: float):
    """Pure function; returns (is_valid, reason, discount_amount)."""
    if not promo.get("active", True):
        return False, "This promo code is inactive", 0.0
    max_uses = int(promo.get("max_uses") or 0)
    used = int(promo.get("used_count") or 0)
    if max_uses > 0 and used >= max_uses:
        return False, "This promo code has reached its usage limit", 0.0
    expires_at = promo.get("expires_at")
    if expires_at:
        try:
            if isinstance(expires_at, str):
                exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                exp = expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                return False, "This promo code has expired", 0.0
        except Exception:
            pass
    min_amt = float(promo.get("min_amount") or 0)
    if subtotal < min_amt:
        return False, f"Minimum subtotal of ${min_amt:.2f} required", 0.0
    # Compute discount
    dtype = (promo.get("discount_type") or "percent").lower()
    value = float(promo.get("discount_value") or 0)
    if dtype == "percent":
        discount = round(subtotal * (value / 100), 2)
    else:  # fixed
        discount = round(value, 2)
    # Cap discount at subtotal
    discount = min(discount, subtotal)
    return True, "ok", discount


def _serialize_promo(p: dict) -> dict:
    p["id"] = str(p.pop("_id"))
    if isinstance(p.get("expires_at"), datetime):
        p["expires_at"] = p["expires_at"].isoformat()
    if isinstance(p.get("created_at"), datetime):
        p["created_at"] = p["created_at"].isoformat()
    return p


# Promo code endpoints are registered later in the file (after api_router is defined).



class CheckoutRequest(BaseModel):
    booking_id: str
    origin_url: str

class LocationCreate(BaseModel):
    name: str
    address: str
    city: str
    country: str
    lat: float
    lng: float
    type: str = "both"  # pickup, dropoff, both
    tax_rate: float = 0.0  # percentage e.g. 18.0 for 18%
    min_booking_days: int = 1
    insurance_included: bool = False
    refuel_amount: float = 0.0  # flat fee for pre-paid refuel option (0 = disabled)

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    type: Optional[str] = None
    tax_rate: Optional[float] = None
    min_booking_days: Optional[int] = None
    insurance_included: Optional[bool] = None
    refuel_amount: Optional[float] = None

class ReviewCreate(BaseModel):
    car_id: str
    rating: int  # 1-5
    comment: str = ""

# App setup
app = FastAPI()
api_router = APIRouter(prefix="/api")

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    email = req.email.lower().strip()
    # Terms must be explicitly accepted at signup (required for app store / legal compliance)
    if not req.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Rental Terms & Conditions to create an account.")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed = hash_password(req.password)
    user_doc = {
        "email": email,
        "password_hash": hashed,
        "name": req.name,
        "phone": (req.phone or "").strip() or None,
        "role": "user",
        "terms_accepted_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    
    return {"id": user_id, "email": email, "name": req.name, "role": "user", "token": access_token}

@api_router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response):
    email = req.email.lower().strip()
    
    # Brute force check
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        lockout_until = attempt.get("locked_until")
        if lockout_until and lockout_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})
    
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(req.password, user["password_hash"]):
        # Increment failed attempts
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": datetime.now(timezone.utc) + timedelta(minutes=15)}},
            upsert=True
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Clear attempts on success
    await db.login_attempts.delete_one({"identifier": identifier})
    
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    
    return {"id": user_id, "email": email, "name": user["name"], "role": user.get("role", "user"), "token": access_token}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_authenticated_user(request)
    return user

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"message": "Logged out"}

# ==================== PASSWORD RESET (6-DIGIT CODE) ====================
import secrets as _secrets

PASSWORD_RESET_TTL_MIN = 15  # codes expire after 15 minutes
PASSWORD_RESET_MAX_ATTEMPTS = 5  # max wrong-code submissions per code

@api_router.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Send a 6-digit reset code to the user's email via SMTP2GO.
    Always returns success-shaped response (even if email not found) to avoid email enumeration."""
    email = (req.email or "").lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    user = await db.users.find_one({"email": email})
    # We always claim success to prevent attackers enumerating registered emails.
    response_payload = {"ok": True, "message": "If an account exists for this email, a reset code has been sent."}

    if not user:
        return response_payload

    # Generate 6-digit numeric code (zero-padded), store hash + expiry.
    code = f"{_secrets.randbelow(1_000_000):06d}"
    code_hash = hash_password(code)  # bcrypt-style hash (same helper as user passwords)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MIN)
    await db.password_resets.update_one(
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

    # Best-effort email delivery. Logs but does not fail the API if SMTP is down.
    try:
        subject = "DAMS Car Rental — Password reset code"
        html = (
            f"<div style='font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width:520px; margin:0 auto; padding:24px; color:#0a0a0a;'>"
            f"<h2 style='margin:0 0 12px;color:#FF3B30'>Password reset</h2>"
            f"<p>Hi {user.get('name','there')},</p>"
            f"<p>Use the following 6-digit code to reset your DAMS Car Rental password. It expires in {PASSWORD_RESET_TTL_MIN} minutes.</p>"
            f"<div style='font-size:36px;font-weight:900;letter-spacing:8px;background:#f5f5f5;padding:16px;text-align:center;border-radius:12px;margin:16px 0'>{code}</div>"
            f"<p style='color:#666;font-size:13px'>If you didn't request this, you can safely ignore this email.</p>"
            f"<p style='color:#999;font-size:11px;margin-top:24px'>— DAMS Rent a Car, S.R.L.</p>"
            f"</div>"
        )
        text = f"Your DAMS Car Rental password reset code is {code}. It expires in {PASSWORD_RESET_TTL_MIN} minutes."
        await send_email(email, subject, html, text)
    except Exception as e:
        logger.exception(f"Password reset email failed for {email}: {e}")

    return response_payload


@api_router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Verify the 6-digit code and update the user's password."""
    email = (req.email or "").lower().strip()
    code = (req.code or "").strip()
    new_password = req.new_password or ""

    if not email or not code or not new_password:
        raise HTTPException(status_code=400, detail="Email, code and new password are required.")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=400, detail="The code must be 6 digits.")

    record = await db.password_resets.find_one({"email": email})
    if not record or record.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or expired code. Please request a new one.")

    # Expiry check
    expires_at = record.get("expires_at")
    if expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await db.password_resets.delete_one({"email": email})
        raise HTTPException(status_code=400, detail="This code has expired. Please request a new one.")

    # Attempt-limit check
    attempts = int(record.get("attempts", 0))
    if attempts >= PASSWORD_RESET_MAX_ATTEMPTS:
        await db.password_resets.delete_one({"email": email})
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please request a new code.")

    # Verify code
    if not verify_password(code, record.get("code_hash", "")):
        await db.password_resets.update_one({"email": email}, {"$inc": {"attempts": 1}})
        raise HTTPException(status_code=400, detail="The code is incorrect. Please double-check and try again.")

    # All good — update the user's password
    user = await db.users.find_one({"email": email})
    if not user:
        # Defensive — should never happen given record exists
        await db.password_resets.delete_one({"email": email})
        raise HTTPException(status_code=400, detail="Account not found.")

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(new_password), "password_updated_at": datetime.now(timezone.utc)}},
    )
    # Single-use: mark consumed (and clear any brute-force lockouts for this email)
    await db.password_resets.update_one({"email": email}, {"$set": {"used": True}})
    await db.login_attempts.delete_many({"identifier": {"$regex": f":{email}$"}})

    return {"ok": True, "message": "Password updated successfully. You can now sign in with your new password."}




# ==================== PUSH NOTIFICATION TOKENS ====================
class PushTokenRequest(BaseModel):
    token: str
    platform: Optional[str] = None  # "ios" / "android" (informational)


@api_router.post("/users/push-token")
async def register_push_token(req: PushTokenRequest, request: Request):
    """Register/refresh the authenticated user's Expo push token.
    A user may have multiple devices, so we store an array of unique tokens.
    """
    user = await get_authenticated_user(request)
    token = (req.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    if not token.startswith(("ExponentPushToken[", "ExpoPushToken[")):
        raise HTTPException(status_code=400, detail="Invalid Expo push token format")

    raw_id = user.get("_id") or user.get("id")
    user_id_obj = raw_id if isinstance(raw_id, ObjectId) else ObjectId(str(raw_id))
    await db.users.update_one(
        {"_id": user_id_obj},
        {"$addToSet": {"push_tokens": token}}
    )
    return {"ok": True}


@api_router.delete("/users/push-token")
async def unregister_push_token(req: PushTokenRequest, request: Request):
    """Remove a stored push token (e.g., on logout or token refresh)."""
    user = await get_authenticated_user(request)
    token = (req.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    raw_id = user.get("_id") or user.get("id")
    user_id_obj = raw_id if isinstance(raw_id, ObjectId) else ObjectId(str(raw_id))
    await db.users.update_one(
        {"_id": user_id_obj},
        {"$pull": {"push_tokens": token}}
    )
    return {"ok": True}


@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user_id = str(user["_id"])
        new_access = create_access_token(user_id, user["email"])
        response.set_cookie(key="access_token", value=new_access, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
        return {"token": new_access}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# ==================== GOOGLE OAUTH ====================
import httpx

@api_router.post("/auth/google/session")
async def google_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    async with httpx.AsyncClient() as client_http:
        resp = await client_http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        data = resp.json()
    
    email = data["email"]
    user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": data.get("name", ""),
            "picture": data.get("picture", ""),
            "role": "user",
            "auth_type": "google",
            "created_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(user)
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
    session_token = data.get("session_token", secrets.token_urlsafe(32))
    await db.user_sessions.insert_one({
        "user_id": user.get("user_id", user.get("_id")),
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    })
    
    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    
    user_clean = {k: v for k, v in user.items() if k != "_id"}
    return {**user_clean, "session_token": session_token}

# ==================== CAR ROUTES ====================

def serialize_car(car):
    car["id"] = str(car["_id"])
    del car["_id"]
    # Backward-compat normalisation: ensure both singular and plural location
    # fields are always present so old mobile clients (singular) and new clients
    # (plural) read the same data.
    pl = car.get("pickup_locations") or []
    dl = car.get("dropoff_locations") or []
    if not pl and car.get("pickup_location"):
        pl = [car["pickup_location"]]
    if not dl and car.get("dropoff_location"):
        dl = [car["dropoff_location"]]
    car["pickup_locations"] = pl
    car["dropoff_locations"] = dl
    if not car.get("pickup_location") and pl:
        car["pickup_location"] = pl[0]
    if not car.get("dropoff_location") and dl:
        car["dropoff_location"] = dl[0]
    return car

async def enrich_car_with_rating(car):
    """Add avg_rating and review_count to a car dict."""
    car_id = car.get("id") or str(car.get("_id", ""))
    pipeline = [
        {"$match": {"car_id": car_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}}
    ]
    result = await db.reviews.aggregate(pipeline).to_list(1)
    if result:
        car["avg_rating"] = round(result[0]["avg"], 1)
        car["review_count"] = result[0]["count"]
    else:
        car["avg_rating"] = 0
        car["review_count"] = 0
    return car

@api_router.get("/cars")
async def get_cars(category: Optional[str] = None, search: Optional[str] = None, location: Optional[str] = None, city: Optional[str] = None):
    query = {"available": True}
    if category and category != "All":
        query["category"] = category
    if search:
        search_conditions = [
            {"name": {"$regex": search, "$options": "i"}},
            {"brand": {"$regex": search, "$options": "i"}},
            {"model": {"$regex": search, "$options": "i"}}
        ]
        if "$and" not in query:
            query["$and"] = []
        query["$and"].append({"$or": search_conditions})
    if location:
        loc_conditions = [
            {"pickup_location.name": {"$regex": location, "$options": "i"}},
            {"dropoff_location.name": {"$regex": location, "$options": "i"}},
            {"pickup_location.address": {"$regex": location, "$options": "i"}},
            {"dropoff_location.address": {"$regex": location, "$options": "i"}}
        ]
        if "$and" not in query:
            query["$and"] = []
        query["$and"].append({"$or": loc_conditions})
    if city:
        city_conditions = [
            {"pickup_location.name": {"$regex": city, "$options": "i"}},
            {"dropoff_location.name": {"$regex": city, "$options": "i"}},
            {"pickup_location.address": {"$regex": city, "$options": "i"}},
            {"dropoff_location.address": {"$regex": city, "$options": "i"}}
        ]
        if "$and" not in query:
            query["$and"] = []
        query["$and"].append({"$or": city_conditions})
    cars = await db.cars.find(query).to_list(100)
    result = []
    for c in cars:
        c = serialize_car(c)
        c = await enrich_car_with_rating(c)
        result.append(c)
    return result

@api_router.get("/cars/all")
async def get_all_cars(request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    cars = await db.cars.find().to_list(100)
    return [serialize_car(c) for c in cars]

@api_router.get("/cars/{car_id}")
async def get_car(car_id: str):
    car = await db.cars.find_one({"_id": ObjectId(car_id)})
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    car = serialize_car(car)
    car = await enrich_car_with_rating(car)
    # Include recent reviews
    reviews = await db.reviews.find({"car_id": car_id}).sort("created_at", -1).to_list(20)
    car["reviews"] = [serialize_review(r) for r in reviews]
    return car

@api_router.post("/cars")
async def create_car(car: CarCreate, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    car_dict = car.dict()
    # ---- Multi-location backward-compat layer ----
    # If admin sent plural lists, mirror the first one back to the singular
    # field so older mobile clients still work. If admin sent the singular only,
    # auto-populate the plural list as [singular] so new clients work too.
    pl = [l for l in (car_dict.get("pickup_locations") or []) if (l.get("name") or "").strip()]
    dl = [l for l in (car_dict.get("dropoff_locations") or []) if (l.get("name") or "").strip()]
    sp = car_dict.get("pickup_location") or {}
    sd = car_dict.get("dropoff_location") or {}
    if not pl and (sp.get("name") or "").strip():
        pl = [sp]
    if not dl and (sd.get("name") or "").strip():
        dl = [sd]
    if not pl:
        raise HTTPException(status_code=400, detail="At least one Pickup location is required. Please select one or more from the list.")
    if not dl:
        raise HTTPException(status_code=400, detail="At least one Drop-off location is required. Please select one or more from the list.")
    car_dict["pickup_locations"] = pl
    car_dict["dropoff_locations"] = dl
    car_dict["pickup_location"] = pl[0]
    car_dict["dropoff_location"] = dl[0]
    car_dict["created_at"] = datetime.now(timezone.utc)
    result = await db.cars.insert_one(car_dict)
    car_dict["id"] = str(result.inserted_id)
    del car_dict["_id"]
    return car_dict

@api_router.put("/cars/{car_id}")
async def update_car(car_id: str, car: CarUpdate, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    update_data = {k: v for k, v in car.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    # ---- Multi-location backward-compat layer (PUT) ----
    if "pickup_locations" in update_data:
        pl = [l for l in (update_data.get("pickup_locations") or []) if (l.get("name") or "").strip()]
        if not pl:
            raise HTTPException(status_code=400, detail="At least one Pickup location is required.")
        update_data["pickup_locations"] = pl
        update_data["pickup_location"] = pl[0]
    elif "pickup_location" in update_data:
        p = update_data["pickup_location"] or {}
        if not (p.get("name") or "").strip():
            raise HTTPException(status_code=400, detail="Pickup location cannot be empty.")
        update_data["pickup_locations"] = [p]
    if "dropoff_locations" in update_data:
        dl = [l for l in (update_data.get("dropoff_locations") or []) if (l.get("name") or "").strip()]
        if not dl:
            raise HTTPException(status_code=400, detail="At least one Drop-off location is required.")
        update_data["dropoff_locations"] = dl
        update_data["dropoff_location"] = dl[0]
    elif "dropoff_location" in update_data:
        d = update_data["dropoff_location"] or {}
        if not (d.get("name") or "").strip():
            raise HTTPException(status_code=400, detail="Drop-off location cannot be empty.")
        update_data["dropoff_locations"] = [d]
    result = await db.cars.update_one({"_id": ObjectId(car_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Car not found")
    updated = await db.cars.find_one({"_id": ObjectId(car_id)})
    return serialize_car(updated)

@api_router.delete("/cars/{car_id}")
async def delete_car(car_id: str, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.cars.delete_one({"_id": ObjectId(car_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Car not found")
    return {"message": "Car deleted"}

@api_router.get("/cars/categories/list")
async def get_categories():
    categories = await db.cars.distinct("category")
    return ["All"] + categories

# ==================== BOOKING ROUTES ====================

def serialize_booking(b):
    b["id"] = str(b["_id"])
    del b["_id"]
    return b

@api_router.post("/bookings")
async def create_booking(booking: BookingCreate, request: Request):
    user = await get_authenticated_user(request)
    user_id = user.get("_id") or user.get("id") or user.get("user_id")
    
    car = await db.cars.find_one({"_id": ObjectId(booking.car_id)})
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Calculate total
    pickup = datetime.fromisoformat(booking.pickup_date)
    dropoff = datetime.fromisoformat(booking.dropoff_date)
    days = max(1, (dropoff - pickup).days)
    
    # Look up tax rate AND minimum booking days from pickup location.
    # Use case-insensitive exact match (anchored regex) + trim whitespace
    # so admin-entered name variations don't silently fall back to defaults.
    tax_rate = 0.0
    min_days = 1
    pickup_loc_name = (booking.pickup_location.get("name", "") or "").strip()
    if pickup_loc_name:
        import re
        escaped = re.escape(pickup_loc_name)
        loc = await db.locations.find_one(
            {"name": {"$regex": f"^{escaped}$", "$options": "i"}},
            {"_id": 0, "tax_rate": 1, "name": 1, "min_booking_days": 1},
        )
        if loc:
            tax_rate = float(loc.get("tax_rate") or 0)
            min_days = int(loc.get("min_booking_days") or 1)
        else:
            logger.warning(f"No location matched name={pickup_loc_name!r} for tax/min-days lookup")
    
    # Enforce per-location minimum booking days
    if days < min_days:
        raise HTTPException(
            status_code=400,
            detail=f"This pickup location requires a minimum rental of {min_days} day(s). Please extend your drop-off date.",
        )

    subtotal = round(days * car["price_per_day"], 2)

    # ---- Mandatory: rental terms acceptance ----
    if not booking.terms_accepted:
        raise HTTPException(
            status_code=400,
            detail="You must accept the Rental Terms & Conditions to complete this booking.",
        )

    # ---- Pre-paid refuel option (flat fee per booking, applied before tax) ----
    pickup_loc_for_refuel = await db.locations.find_one(
        {"name": {"$regex": f"^{__import__('re').escape(pickup_loc_name)}$", "$options": "i"}},
        {"_id": 0, "refuel_amount": 1},
    ) if pickup_loc_name else None
    available_refuel = float((pickup_loc_for_refuel or {}).get("refuel_amount") or 0.0)
    refuel_charge = round(available_refuel, 2) if (booking.refuel_opted_in and available_refuel > 0) else 0.0

    # ---- Promo code application ----
    promo_code_used: Optional[str] = None
    discount_amount = 0.0
    if booking.promo_code:
        normalized = booking.promo_code.strip().upper()
        promo = await db.promo_codes.find_one({"code": normalized})
        if not promo:
            raise HTTPException(status_code=400, detail="Invalid promo code")
        is_valid, reason, calc = _validate_promo(promo, subtotal)
        if not is_valid:
            raise HTTPException(status_code=400, detail=reason)
        discount_amount = float(calc)
        promo_code_used = normalized
        # Increment usage atomically
        try:
            await db.promo_codes.update_one(
                {"_id": promo["_id"]}, {"$inc": {"used_count": 1}}
            )
        except Exception as _e:
            logger.warning(f"promo code usage increment failed: {_e}")

    discounted_subtotal = round(max(subtotal - discount_amount, 0.0), 2)
    taxable_amount = round(discounted_subtotal + refuel_charge, 2)
    tax_amount = round(taxable_amount * (tax_rate / 100), 2)
    total = round(taxable_amount + tax_amount, 2)
    
    booking_doc = {
        "user_id": str(user_id),
        "user_email": user.get("email", ""),
        "user_name": user.get("name", ""),
        "car_id": booking.car_id,
        "car_name": car.get("name", f"{car.get('brand', '')} {car.get('model', '')}"),
        "car_image": car.get("image_url", ""),
        "pickup_date": booking.pickup_date,
        "dropoff_date": booking.dropoff_date,
        "pickup_location": booking.pickup_location,
        "dropoff_location": booking.dropoff_location,
        "days": days,
        "price_per_day": car["price_per_day"],
        "subtotal": subtotal,
        "promo_code": promo_code_used,
        "discount_amount": discount_amount,
        "refuel_amount": refuel_charge,
        "refuel_opted_in": bool(booking.refuel_opted_in and refuel_charge > 0),
        "terms_accepted_at": datetime.now(timezone.utc),
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "total_price": total,
        "payment_method": booking.payment_method,
        # Cash: stays pending until admin collects money on pickup and marks it paid/confirmed
        # Stripe: pending until the Stripe webhook confirms payment
        "payment_status": "pending",
        "status": "pending_payment",
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.bookings.insert_one(booking_doc)
    booking_doc["id"] = str(result.inserted_id)
    del booking_doc["_id"]

    # Push notifications (fire-and-forget; never blocks the response)
    try:
        car_label = car.get("name") or f"{car.get('brand','')} {car.get('model','')}".strip() or "your car"
        # Notify the customer
        await send_push_to_user(
            str(user_id),
            "Booking received",
            f"Your booking for {car_label} is pending payment confirmation.",
            {"type": "booking_created", "booking_id": booking_doc["id"]},
        )
        # Notify all admins
        await send_push_to_admins(
            "New booking",
            f"{user.get('name', 'A customer')} booked {car_label} (${total:.2f}).",
            {"type": "new_booking", "booking_id": booking_doc["id"]},
        )
    except Exception as _e:
        logger.warning(f"Booking push notify error: {_e}")

    # Email notification (fire-and-forget)
    try:
        await send_booking_email("created", booking_doc, user.get("email"))
    except Exception as _e:
        logger.warning(f"Booking created email error: {_e}")

    return booking_doc

@api_router.get("/bookings")
async def get_bookings(request: Request):
    user = await get_authenticated_user(request)
    user_id = str(user.get("_id") or user.get("id") or user.get("user_id"))
    bookings = await db.bookings.find({"user_id": user_id}).sort("created_at", -1).to_list(100)
    return [serialize_booking(b) for b in bookings]

@api_router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str, request: Request):
    user = await get_authenticated_user(request)
    booking = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return serialize_booking(booking)


@api_router.post("/admin/backfill-booking-taxes")
async def backfill_booking_taxes(request: Request):
    """Recompute and persist subtotal / tax_rate / tax_amount for bookings
    created before the tax feature was added. Existing total_price is preserved
    and treated as the grand total — subtotal is derived from the pickup
    location's current tax rate so that subtotal + tax = total_price.
    """
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    updated = 0
    already_ok = 0
    no_total = 0

    # Preload locations into a name -> tax_rate map
    loc_rates = {}
    for loc in await db.locations.find({}, {"name": 1, "tax_rate": 1}).to_list(500):
        loc_rates[loc.get("name", "")] = float(loc.get("tax_rate") or 0.0)

    async for b in db.bookings.find({}):
        has_complete = (
            b.get("subtotal") is not None
            and b.get("tax_rate") is not None
            and b.get("tax_amount") is not None
        )
        if has_complete:
            already_ok += 1
            continue

        total = b.get("total_price")
        if total is None:
            no_total += 1
            continue
        total = float(total)

        pickup_name = (b.get("pickup_location") or {}).get("name", "")
        tax_rate = loc_rates.get(pickup_name, 0.0)

        # total == subtotal * (1 + tax_rate/100) -> subtotal = total / (1 + r/100)
        divisor = 1.0 + (tax_rate / 100.0)
        subtotal = round(total / divisor, 2) if divisor > 0 else round(total, 2)
        tax_amount = round(total - subtotal, 2)

        # Guard against minor rounding causing subtotal+tax != total
        if abs((subtotal + tax_amount) - total) > 0.02:
            subtotal = round(total, 2)
            tax_amount = 0.0
            tax_rate = 0.0

        await db.bookings.update_one(
            {"_id": b["_id"]},
            {"$set": {"subtotal": subtotal, "tax_rate": tax_rate, "tax_amount": tax_amount}},
        )
        updated += 1

    return {
        "message": f"Backfilled tax on {updated} booking(s). {already_ok} already had full tax data, {no_total} skipped (no total_price).",
        "updated": updated,
        "already_ok": already_ok,
        "skipped_no_total": no_total,
    }


@api_router.get("/admin/bookings")
async def admin_list_bookings(request: Request, status: Optional[str] = None, q: Optional[str] = None):
    """List all bookings for admin with optional status filter and customer search."""
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    query = {}
    if status and status != "all":
        query["status"] = status
    if q:
        query["$or"] = [
            {"user_email": {"$regex": q, "$options": "i"}},
            {"user_name": {"$regex": q, "$options": "i"}},
            {"car_name": {"$regex": q, "$options": "i"}},
        ]
    bookings = await db.bookings.find(query).sort("created_at", -1).to_list(500)
    return [serialize_booking(b) for b in bookings]


class BookingStatusUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None


@api_router.put("/admin/bookings/{booking_id}/status")
async def admin_update_booking_status(booking_id: str, body: BookingStatusUpdate, request: Request):
    """Admin changes a booking's status and/or payment_status.

    - status: pending / pending_payment / confirmed / active / completed / cancelled
    - payment_status: pending / paid / refunded / failed
    Used by the admin to confirm cash collection: set status=confirmed AND payment_status=paid.
    """
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    update_data = {}
    if body.status is not None:
        valid_status = {"pending", "pending_payment", "confirmed", "active", "completed", "cancelled"}
        if body.status not in valid_status:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_status))}")
        update_data["status"] = body.status
    if body.payment_status is not None:
        valid_pay = {"pending", "paid", "refunded", "failed"}
        if body.payment_status not in valid_pay:
            raise HTTPException(status_code=400, detail=f"Invalid payment_status. Must be one of: {', '.join(sorted(valid_pay))}")
        update_data["payment_status"] = body.payment_status

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = await db.bookings.update_one({"_id": ObjectId(booking_id)}, {"$set": update_data})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    booking_payload = serialize_booking(booking)  # serialize once; serialize_booking mutates the dict

    # Send push notification to the customer about the status change
    try:
        owner_id = booking_payload.get("user_id")
        car_label = booking_payload.get("car_name") or "your car"
        new_status = update_data.get("status")
        new_pay = update_data.get("payment_status")
        # Friendly messages
        title, body_msg = None, None
        if new_pay == "paid" and new_status == "confirmed":
            title = "Payment confirmed"
            body_msg = f"Cash received for {car_label}. Your booking is confirmed!"
        elif new_status == "confirmed":
            title = "Booking confirmed"
            body_msg = f"Your booking for {car_label} is confirmed."
        elif new_status == "active":
            title = "Rental active"
            body_msg = f"Your rental of {car_label} is now active. Drive safe!"
        elif new_status == "completed":
            title = "Rental completed"
            body_msg = f"Thanks for renting {car_label}. We hope you enjoyed it!"
        elif new_status == "cancelled":
            title = "Booking cancelled"
            body_msg = f"Your booking for {car_label} has been cancelled."
        elif new_pay == "paid":
            title = "Payment received"
            body_msg = f"Payment received for {car_label}."
        elif new_pay == "refunded":
            title = "Refund issued"
            body_msg = f"A refund was issued for your booking of {car_label}."

        if title and owner_id:
            await send_push_to_user(
                owner_id, title, body_msg,
                {"type": "booking_update", "booking_id": booking_id, "status": new_status, "payment_status": new_pay},
            )
    except Exception as _e:
        logger.warning(f"Status update push notify error: {_e}")

    # Email customer about status change
    try:
        event_map = {
            "confirmed": "payment_confirmed",
            "active": "status_active",
            "completed": "status_completed",
            "cancelled": "cancelled",
        }
        event_key = None
        if update_data.get("payment_status") == "paid":
            event_key = "payment_confirmed"
        elif update_data.get("status") in event_map:
            event_key = event_map[update_data["status"]]
        if event_key and booking_payload.get("user_email"):
            await send_booking_email(event_key, booking_payload, booking_payload.get("user_email"))
    except Exception as _e:
        logger.warning(f"Status update email error: {_e}")

    return booking_payload


@api_router.get("/bookings/{booking_id}/receipt.pdf")
async def get_booking_receipt(booking_id: str, request: Request):
    """Returns a PDF receipt for the booking. Accessible by the booking owner or an admin."""
    user = await get_authenticated_user(request)
    booking = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    user_id = str(user.get("_id") or user.get("id") or user.get("user_id"))
    if user.get("role") != "admin" and booking.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this receipt")

    pdf_bytes = _generate_receipt_pdf(booking)
    from fastapi.responses import Response as FResponse
    return FResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=dams-receipt-{booking_id[:8]}.pdf"},
    )


def _generate_receipt_pdf(booking: dict) -> bytes:
    """Generate a branded PDF receipt for a booking with full tax breakdown."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as rl_canvas

    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    RED = colors.HexColor("#ff3b30")
    DARK = colors.HexColor("#0a0a0a")
    MUTED = colors.HexColor("#6b7280")
    LINE = colors.HexColor("#e5e7eb")

    # Header
    c.setFillColor(DARK)
    c.rect(0, H - 28 * mm, W, 28 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(18 * mm, H - 15 * mm, "DAMS")
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(42 * mm, H - 15 * mm, "CAR  RENTAL")
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 22 * mm, "Official Rental Receipt")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 18 * mm, H - 15 * mm, "RECEIPT")
    c.setFont("Helvetica", 9)
    booking_id = str(booking.get("_id") or booking.get("id") or "")
    c.drawRightString(W - 18 * mm, H - 22 * mm, f"# {booking_id[-10:].upper()}")

    y = H - 40 * mm

    # Customer block
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "BILLED TO")
    c.setFont("Helvetica", 10)
    c.setFillColor(MUTED)
    y -= 6 * mm
    c.drawString(18 * mm, y, booking.get("user_name") or "Customer")
    y -= 5 * mm
    c.drawString(18 * mm, y, booking.get("user_email") or "")

    # Issue date (top right)
    created = booking.get("created_at")
    try:
        if isinstance(created, datetime):
            issue_date = created.strftime("%B %d, %Y")
        else:
            issue_date = str(created)[:10]
    except Exception:
        issue_date = ""
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - 18 * mm, H - 40 * mm, "ISSUE DATE")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawRightString(W - 18 * mm, H - 46 * mm, issue_date or "—")

    # Rental details
    y -= 14 * mm
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "RENTAL DETAILS")
    y -= 2 * mm
    c.setStrokeColor(LINE)
    c.line(18 * mm, y, W - 18 * mm, y)
    y -= 7 * mm

    def row(label, value):
        nonlocal y
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(18 * mm, y, label.upper())
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(W - 18 * mm, y, str(value))
        y -= 6 * mm

    row("Vehicle", booking.get("car_name") or "—")
    pickup_date = (booking.get("pickup_date") or "")[:10]
    dropoff_date = (booking.get("dropoff_date") or "")[:10]
    row("Pickup Date", pickup_date or "—")
    row("Drop-off Date", dropoff_date or "—")
    row("Pickup Location", (booking.get("pickup_location") or {}).get("name") or "—")
    row("Drop-off Location", (booking.get("dropoff_location") or {}).get("name") or "—")
    row("Days", booking.get("days") or 0)
    row("Payment Method", (booking.get("payment_method") or "cash").upper())
    row("Status", (booking.get("status") or "").replace("_", " ").title())

    # Cost breakdown
    y -= 6 * mm
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "COST BREAKDOWN")
    y -= 2 * mm
    c.line(18 * mm, y, W - 18 * mm, y)
    y -= 7 * mm

    days = booking.get("days", 1) or 1
    subtotal = booking.get("subtotal", 0) or 0
    tax_rate = booking.get("tax_rate", 0) or 0
    tax_amount = booking.get("tax_amount", 0) or 0
    total = booking.get("total_price", 0) or 0
    # Effective daily rate = subtotal / days (handles any discounts/backfilled bookings)
    eff_rate = round(subtotal / days, 2) if days else 0

    row(f"Daily Rate × {days} day(s)", f"${eff_rate:,.2f} × {days}")
    row("Subtotal", f"${subtotal:,.2f}")
    row(f"Tax ({tax_rate}%)", f"${tax_amount:,.2f}")

    # Grand total (highlighted)
    y -= 4 * mm
    c.setFillColor(RED)
    c.rect(18 * mm, y - 4 * mm, W - 36 * mm, 12 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(22 * mm, y + 1 * mm, "GRAND TOTAL")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 22 * mm, y + 0.5 * mm, f"${total:,.2f} USD")
    y -= 18 * mm

    # Footer
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(18 * mm, 18 * mm, "Thank you for choosing DAMS Car Rental. Drive safe!")
    c.drawString(18 * mm, 14 * mm, "For questions, contact support@damscarrental.com")
    c.setFont("Helvetica-Oblique", 7)
    c.drawRightString(W - 18 * mm, 14 * mm, "This is an electronically generated receipt.")

    c.showPage()
    c.save()
    return buf.getvalue()

# ==================== STRIPE PAYMENT ROUTES ====================

from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutSessionRequest, CheckoutStatusResponse

@api_router.post("/payments/checkout")
async def create_checkout(req: CheckoutRequest, request: Request):
    user = await get_authenticated_user(request)
    
    booking = await db.bookings.find_one({"_id": ObjectId(req.booking_id)})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    amount = float(booking["total_price"])
    
    host_url = req.origin_url.rstrip("/")
    success_url = f"{host_url}/booking-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/bookings"
    
    api_key = os.environ["STRIPE_API_KEY"]
    webhook_url = f"{str(request.base_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"booking_id": req.booking_id, "user_id": str(user.get("_id") or user.get("user_id")), "email": user.get("email", "")}
    )
    
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_req)
    
    # Create payment transaction
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "booking_id": req.booking_id,
        "user_id": str(user.get("_id") or user.get("user_id")),
        "email": user.get("email", ""),
        "amount": amount,
        "currency": "usd",
        "payment_status": "initiated",
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, request: Request):
    api_key = os.environ["STRIPE_API_KEY"]
    webhook_url = f"{str(request.base_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    
    # Update transaction
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if tx:
        new_status = "paid" if status.payment_status == "paid" else status.payment_status
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": new_status, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if new_status == "paid":
            # Only update booking once
            booking = await db.bookings.find_one({"_id": ObjectId(tx["booking_id"])})
            if booking and booking.get("payment_status") != "paid":
                await db.bookings.update_one(
                    {"_id": ObjectId(tx["booking_id"])},
                    {"$set": {"payment_status": "paid", "status": "confirmed"}}
                )
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency
    }

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    api_key = os.environ["STRIPE_API_KEY"]
    webhook_url = f"{str(request.base_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    try:
        event = await stripe_checkout.handle_webhook(body, signature)
        logger.info(f"Stripe webhook: {event.event_type}, session: {event.session_id}")
        
        if event.payment_status == "paid":
            tx = await db.payment_transactions.find_one({"session_id": event.session_id})
            if tx and tx.get("payment_status") != "paid":
                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"payment_status": "paid", "updated_at": datetime.now(timezone.utc)}}
                )
                await db.bookings.update_one(
                    {"_id": ObjectId(tx["booking_id"])},
                    {"$set": {"payment_status": "paid", "status": "confirmed"}}
                )
                # Notify the customer that the card payment succeeded
                try:
                    booking = await db.bookings.find_one({"_id": ObjectId(tx["booking_id"])})
                    if booking:
                        booking_payload = serialize_booking(booking)
                        car_label = booking_payload.get("car_name") or "your car"
                        await send_push_to_user(
                            booking_payload.get("user_id", ""),
                            "Payment received",
                            f"Card payment confirmed for {car_label}. Your booking is confirmed!",
                            {"type": "booking_update", "booking_id": str(tx["booking_id"]), "status": "confirmed", "payment_status": "paid"},
                        )
                        # Email customer
                        if booking_payload.get("user_email"):
                            await send_booking_email("payment_confirmed", booking_payload, booking_payload.get("user_email"))
                except Exception as _e:
                    logger.warning(f"Stripe webhook push/email notify error: {_e}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

# ==================== ADMIN ROUTES ====================

@api_router.get("/admin/stats")
async def get_admin_stats(request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    total_cars = await db.cars.count_documents({})
    total_bookings = await db.bookings.count_documents({})
    total_users = await db.users.count_documents({})
    active_bookings = await db.bookings.count_documents({"status": "confirmed"})
    total_locations = await db.locations.count_documents({})
    
    return {
        "total_cars": total_cars,
        "total_bookings": total_bookings,
        "total_users": total_users,
        "active_bookings": active_bookings,
        "total_locations": total_locations
    }


class AdminBroadcastRequest(BaseModel):
    title: str
    body: str
    target: str = "all"  # "all" | "customers" | "admins" | "user:<user_id>"


@api_router.post("/admin/notifications/send")
async def admin_send_notification(req: AdminBroadcastRequest, request: Request):
    """Send a push notification to a chosen audience from the admin panel.

    target options:
      - "all"        → every user with at least one push token
      - "customers"  → all non-admin users with push tokens
      - "admins"     → admin users with push tokens
      - "user:<id>"  → a single specific user
    """
    admin = await get_authenticated_user(request)
    if admin.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    title = (req.title or "").strip()
    body = (req.body or "").strip()
    if not title or not body:
        raise HTTPException(status_code=400, detail="Title and body are required")
    if len(title) > 100:
        raise HTTPException(status_code=400, detail="Title must be ≤ 100 chars")
    if len(body) > 500:
        raise HTTPException(status_code=400, detail="Body must be ≤ 500 chars")

    target = (req.target or "all").strip()
    query: Dict = {}
    if target == "all":
        query = {"push_tokens": {"$exists": True, "$ne": []}}
    elif target == "customers":
        query = {"push_tokens": {"$exists": True, "$ne": []}, "role": {"$ne": "admin"}}
    elif target == "admins":
        query = {"push_tokens": {"$exists": True, "$ne": []}, "role": "admin"}
    elif target.startswith("user:"):
        uid = target.split(":", 1)[1].strip()
        if not ObjectId.is_valid(uid):
            raise HTTPException(status_code=400, detail="Invalid user id")
        query = {"_id": ObjectId(uid)}
    else:
        raise HTTPException(status_code=400, detail="Invalid target. Use 'all' | 'customers' | 'admins' | 'user:<id>'")

    users = await db.users.find(query, {"push_tokens": 1}).to_list(2000)
    all_tokens: List[str] = []
    for u in users:
        all_tokens.extend(u.get("push_tokens") or [])
    # Dedupe
    all_tokens = list({t for t in all_tokens if isinstance(t, str)})
    if not all_tokens:
        return {"sent": 0, "total_recipients": len(users), "reason": "no_tokens_in_audience"}

    result = await send_expo_push(all_tokens, title, body, {"type": "admin_broadcast"})
    return {
        "sent": int(result.get("sent") or 0),
        "requested": int(result.get("requested") or len(all_tokens)),
        "total_recipients": len(users),
        "tokens_count": len(all_tokens),
        "errors": result.get("errors") or [],
        "invalid_tokens_removed": int(result.get("invalid_tokens_removed") or 0),
        "raw_status": result.get("raw_status"),
        "error": result.get("error"),
    }


@api_router.get("/admin/notifications/audience-stats")
async def admin_audience_stats(request: Request):
    """Return how many users have push tokens, segmented by role.
    Useful so the admin sees how many devices a broadcast will reach.
    """
    admin = await get_authenticated_user(request)
    if admin.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    base = {"push_tokens": {"$exists": True, "$ne": []}}
    total = await db.users.count_documents(base)
    customers = await db.users.count_documents({**base, "role": {"$ne": "admin"}})
    admins = await db.users.count_documents({**base, "role": "admin"})
    total_users = await db.users.count_documents({})
    return {
        "total_users": total_users,
        "users_with_push": total,
        "customers_with_push": customers,
        "admins_with_push": admins,
    }


class TestEmailRequest(BaseModel):
    to: str


@api_router.post("/admin/email/test")
async def admin_test_email(req: TestEmailRequest, request: Request):
    """Send a test email to verify SMTP credentials are working. Admin-only."""
    admin = await get_authenticated_user(request)
    if admin.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not req.to or "@" not in req.to:
        raise HTTPException(status_code=400, detail="Invalid recipient email")
    html = _email_template(
        "SMTP test email",
        "If you received this, your SMTP credentials are working correctly. 🎉",
        "<p style='color:#666;font-size:13px'>Sent from the DAMS Car Rental admin panel.</p>",
    )
    result = await send_email(req.to, "DAMS Car Rental — SMTP test", html)
    return result


# ==================== RENTAL TERMS SETTINGS ====================
DEFAULT_RENTAL_TERMS = """DEFINITIONS. "Agreement" means all terms and conditions found on both sides of this form, any addenda or any additional materials we provide at the time of rental. "You" or "your" means the person identified as the renter on Page 1, any person signing this agreement, any authorized Driver and any person or organization to whom charges are billed by us on the renter's direction. All persons referred to as "you" or "your" are jointly and severally bound by this agreement. "We," "our" or "us" means the Rental Agent identified on Page 1. "Authorized Driver" means you, any additional driver approved by us and listed by us on this agreement, and any other driver authorized by the law of the state where the vehicle is rented provided that person has a valid driver's license and, unless the law of this state requires otherwise, is at least twenty-one (25) years of age. "Vehicle" means the automobile identified in this agreement and any substitute and all its tires, tools, accessories, keys, equipment, keys, and vehicle documents. "Physical damage" means all damage to, or loss of, the Vehicle caused by collision or upset; it does not include damage to, or loss of the Vehicle due to theft, vandalism, act of nature, riot or civil disturbance, hail, flood, or fire. "Loss of use" means the amount calculated by multiplying the number of days/weeks/months from the date of damages to the Vehicle until it is repaired times the corresponding periodic rental rate, unless otherwise provided by law.

RENTAL. This agreement is a contract for the rental of the Vehicle. WE MAKE NO WARRANTIES, EXPRESS, IMPLIED OR APPARENT REGARDING THE VEHICLE, INCLUDING ANY WARRANTY OF MERCHANTABILITY OR THAT THE VEHICLE IS FIT FOR A PARTICULAR PURPOSE. We may repossess the Vehicle at your expense without notice to you, if the Vehicle is abandoned or used in violation of law or this agreement. You waive all recourse against us for any criminal reports or prosecutions that we take against you that arise out of your breach of this agreement.

CONDITION AND RETURN OF VEHICLE. You must return the Vehicle to our rental office or other location we specify on the date and time specified in this agreement and in the same condition that you received it, except for ordinary wear. Service to the Vehicle or replacement of parts or accessories during the rental must have our prior approval. You will check and maintain all fluid levels including the brake fluid level in the master cylinder.

RESPONSIBILITY FOR DAMAGE OR LOSS; REPORTING TO POLICE. You are responsible for all damage to or loss of the Vehicle, loss of use of the Vehicle while it is being repaired, diminution of the Vehicle's value caused by damage to it or repair of it, missing equipment, and all administrative costs we incur due to damage to, or loss of, the Vehicle regardless of whether or not you are at fault, unless this responsibility is otherwise limited by law. You must report all accidents or incidents of theft and vandalism to the police as soon as you discover them. You must report all accidents involving the vehicle to us immediately.

LIABILITY INSURANCE. You are responsible for all damages or losses you cause to others. You agree to provide auto liability insurance covering you, us, and the Vehicle. If you have auto liability insurance, we provide no liability insurance. Where state law requires us to provide auto liability insurance, or if you have no liability insurance, we provide auto liability insurance, excess to any insurance you may have, under a policy of insurance (the "Policy"). The Policy provides bodily injury and property damage liability coverage with limits no higher than minimum levels prescribed by the vehicular financial responsibility laws of the state where the damage or loss occurs. The Policy provides uninsured/underinsured motorist coverage only in states where such coverage is mandated by law. Coverage applies only in the Unites States. Coverage is void if you violate the terms of this Agreement or if you fail to cooperate in any loss investigation conducted by us or our insurer. You and we reject PIP, no fault, and uninsured or underinsured motorist coverage. Giving the vehicle to an unauthorized driver terminates our liability insurance coverage, if any. You will indemnify, defend, and hold us harmless from all liability, costs and attorney fees arising out of use of the Vehicle that are in excess of, or excluded from, the protection provided you, if any, under the policy.

CHARGES. You will pay us on demand for all charges due under this Agreement that are allowed by law, including, but not limited to: (a) time and usage for the period during which you keep the Vehicle; (b) charges for optional services, if you elect to purchase any; (c) applicable sales use and other taxes; (d) loss of, or damage to the Vehicle, which is included in the cost of repair of the retail value of the Vehicle based on valuation methods accepted by the auto insurance industry on the date of the loss if the Vehicle is not repairable, plus loss of use, diminution of the Vehicle's value caused by damage to it or repair to it, and our administrative fees incurred for processing the claim; (e) all fines, penalties, forfeitures, court costs, towing charges and other expenses involving the Vehicle assessed against us or the Vehicle during your rental, unless these expenses are our fault; (f) all expenses we incur in locating and recovering the Vehicle if you fail to return it or we elect to repossess the Vehicle under the terms of this Agreement; (g) all costs, including pre and post judgment attorney fees, we incur collecting payment from you or otherwise enforcing our rights under this agreement; (h) a 2% late payment fee or the highest amount allowed by law, if lower, on all amounts past due; (i) One and one half percent per month interest, or the maximum amount allowed by the laws of the state where the Vehicle is rented, for monies due but not paid upon return of the Vehicle; (j) Fifty dollars ($50.00) plus $5.00 per mile between the renting location and place where the vehicle is returned or abandoned, plus any additional recovery expenses we incur, and (k) Twenty Five dollars ($25.00) or the maximum amount permitted by law, whichever is greater if you pay us with a check backed by insufficient funds.

DEPOSIT. We may use your deposit to pay any amounts owed to us under this agreement.

BREACH OF AGREEMENT. If you breach this agreement, you will be liable for all damage to, or loss of, the Vehicle caused by your breach, unless otherwise provided by law.

MODIFICATIONS. No term of this agreement can be waived or modified except by a writing that we have signed. If you wish to extend the rental period, you must return the Vehicle to our rental office for inspection and written amendment by us of the due in date or time.

MISCELLANEOUS. No waiver by us of any breach of this Agreement will constitute a waiver of any additional breach or waiver of the performance of your obligations under this agreement. Unless prohibited by law, you release us from any liability for consequential special or punitive damages in connection with this rental or the reservation of a vehicle. If any provision of this Agreement is deemed void or unenforceable, the remaining provisions are valid and enforceable. This agreement constitutes the entire Agreement between you and us. All prior representations and agreements between you and us are merged into this agreement.

RENTAL AGREEMENT VIOLATIONS. You agree to properly operate this vehicle. If any of the following acts are committed, any coverage provided to you will be voided: (a) Operation of the Vehicle by an unauthorized driver; (b) Violation of any provision of this Agreement while operating the Vehicle; (c) Driving while intoxicated or under the influence of drugs, alcohol or other substances which would impair driving ability; (d) Reckless driving of the Vehicle to include, among other things, off regularly maintained roadways, to carry hazardous or explosive substances, to carry hazardous waste of any kind, to transport weight in excess of the vehicle's maximum payload capacity, where insufficient clearance or height or width exists, improper loading; (e) Transporting more passengers than number of seat belts or transporting passengers outside of the passenger compartment; (f) Using the Vehicle to participate or act or assist in any activity that violates any law, rule, or regulation; (g) Using vehicle to carry persons or property for hire; (h) Using Vehicle to engage in an organized or any other speed contest; (i) Using Vehicle to tow or push any other vehicle, trailer or other object; (j) Operation of Vehicle by person who has used false or misleading information to obtain the Vehicle; (k) Operating the Vehicle outside the continental United States and Canada; (l) Leave the Vehicle and fail to remove the keys or close and lock all doors, windows, and the trunk and the vehicle is stolen."""


class RentalTermsUpdate(BaseModel):
    terms: str


@api_router.get("/settings/rental-terms")
async def get_rental_terms():
    """Public: return the current rental terms text customers must accept."""
    doc = await db.settings.find_one({"key": "rental_terms"})
    text = (doc or {}).get("value") or DEFAULT_RENTAL_TERMS
    return {"terms": text}


@api_router.put("/admin/settings/rental-terms")
async def update_rental_terms(body: RentalTermsUpdate, request: Request):
    """Admin: update the rental terms text. Stored in settings collection (singleton)."""
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    text = (body.terms or "").strip()
    if not text or len(text) < 10:
        raise HTTPException(status_code=400, detail="Terms text is too short")
    if len(text) > 50000:
        raise HTTPException(status_code=400, detail="Terms text is too long (max 50,000 chars)")
    await db.settings.update_one(
        {"key": "rental_terms"},
        {"$set": {"key": "rental_terms", "value": text, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"ok": True, "length": len(text)}


# ==================== PRIVACY POLICY (admin-editable settings) ====================
class PrivacyPolicyUpdate(BaseModel):
    text: str

def _load_default_privacy() -> str:
    """Load the bundled fallback privacy text from disk."""
    try:
        path = _Path(__file__).parent / "legal" / "privacy.txt"
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.exception(f"Could not load default privacy.txt: {e}")
        return "Privacy policy is being updated. Please contact info@damsrentacar.com."


@api_router.get("/settings/privacy-policy")
async def get_privacy_policy():
    """Public: return the current privacy policy text. Falls back to bundled default if admin hasn't customised it."""
    doc = await db.settings.find_one({"key": "privacy_policy"})
    text = (doc or {}).get("value") or _load_default_privacy()
    return {"text": text, "updated_at": (doc or {}).get("updated_at")}


@api_router.put("/admin/settings/privacy-policy")
async def update_privacy_policy(body: PrivacyPolicyUpdate, request: Request):
    """Admin: update the privacy policy text. Stored in settings collection (singleton)."""
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    text = (body.text or "").strip()
    if not text or len(text) < 10:
        raise HTTPException(status_code=400, detail="Privacy policy text is too short (min 10 chars)")
    if len(text) > 100000:
        raise HTTPException(status_code=400, detail="Privacy policy text is too long (max 100,000 chars)")
    await db.settings.update_one(
        {"key": "privacy_policy"},
        {"$set": {"key": "privacy_policy", "value": text, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"ok": True, "length": len(text)}





@api_router.get("/admin/analytics")
async def get_admin_analytics(request: Request):
    """Aggregated fleet analytics for the admin dashboard.

    Returns:
      - kpis: total_revenue (paid), revenue_this_month, total_bookings, paid_bookings,
              active_bookings, avg_revenue_per_booking
      - monthly_revenue: last 6 months [{month, revenue, count}]
      - top_cars: top 10 most-booked cars [{car_id, car_name, count, revenue}]
      - top_locations: top pickup locations [{name, count}]
      - status_breakdown: {status: count}
      - payment_breakdown: {payment_status: count}
    """
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    now = datetime.now(timezone.utc)
    # First day of the current month (UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    # 6 months ago (start of that month)
    six_start_year = now.year
    six_start_month = now.month - 5
    while six_start_month <= 0:
        six_start_month += 12
        six_start_year -= 1
    six_months_ago = datetime(six_start_year, six_start_month, 1, tzinfo=timezone.utc)

    # ---- KPIs ----
    total_bookings = await db.bookings.count_documents({})
    paid_bookings = await db.bookings.count_documents({"payment_status": "paid"})
    active_bookings = await db.bookings.count_documents(
        {"status": {"$in": ["confirmed", "active"]}}
    )

    # Total collected revenue (sum total_price across paid bookings)
    paid_revenue_pipeline = [
        {"$match": {"payment_status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$total_price"}}},
    ]
    paid_rev_doc = await db.bookings.aggregate(paid_revenue_pipeline).to_list(1)
    total_revenue = float(paid_rev_doc[0]["total"]) if paid_rev_doc else 0.0

    # Revenue this month (paid only, by created_at)
    month_pipeline = [
        {"$match": {"payment_status": "paid", "created_at": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_price"}}},
    ]
    month_doc = await db.bookings.aggregate(month_pipeline).to_list(1)
    revenue_this_month = float(month_doc[0]["total"]) if month_doc else 0.0

    avg_rev = (total_revenue / paid_bookings) if paid_bookings > 0 else 0.0

    # ---- Monthly revenue (last 6 months, including current) ----
    monthly_pipeline = [
        {"$match": {"created_at": {"$gte": six_months_ago}}},
        {
            "$group": {
                "_id": {"y": {"$year": "$created_at"}, "m": {"$month": "$created_at"}},
                "revenue": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$payment_status", "paid"]},
                            "$total_price",
                            0,
                        ]
                    }
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.y": 1, "_id.m": 1}},
    ]
    monthly_raw = await db.bookings.aggregate(monthly_pipeline).to_list(50)
    monthly_map = {(r["_id"]["y"], r["_id"]["m"]): r for r in monthly_raw}
    # Build a 6-slot array even when months have no data
    monthly_revenue = []
    y, m = six_start_year, six_start_month
    for _ in range(6):
        bucket = monthly_map.get((y, m))
        monthly_revenue.append({
            "month": f"{y:04d}-{m:02d}",
            "revenue": float(bucket["revenue"]) if bucket else 0.0,
            "count": int(bucket["count"]) if bucket else 0,
        })
        m += 1
        if m > 12:
            m = 1
            y += 1

    # ---- Top 10 most-booked cars ----
    cars_pipeline = [
        {
            "$group": {
                "_id": {"car_id": "$car_id", "car_name": "$car_name"},
                "count": {"$sum": 1},
                "revenue": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$payment_status", "paid"]},
                            "$total_price",
                            0,
                        ]
                    }
                },
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    cars_raw = await db.bookings.aggregate(cars_pipeline).to_list(10)
    top_cars = [
        {
            "car_id": r["_id"].get("car_id", ""),
            "car_name": r["_id"].get("car_name") or "Unknown",
            "count": int(r["count"]),
            "revenue": float(r["revenue"] or 0),
        }
        for r in cars_raw
    ]

    # ---- Top pickup locations ----
    loc_pipeline = [
        {
            "$group": {
                "_id": "$pickup_location.name",
                "count": {"$sum": 1},
            }
        },
        {"$match": {"_id": {"$ne": None}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    loc_raw = await db.bookings.aggregate(loc_pipeline).to_list(10)
    top_locations = [
        {"name": r["_id"] or "Unknown", "count": int(r["count"])} for r in loc_raw
    ]

    # ---- Status + payment breakdowns ----
    status_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_raw = await db.bookings.aggregate(status_pipeline).to_list(20)
    status_breakdown = {
        (r["_id"] or "unknown"): int(r["count"]) for r in status_raw
    }

    payment_pipeline = [
        {"$group": {"_id": "$payment_status", "count": {"$sum": 1}}},
    ]
    payment_raw = await db.bookings.aggregate(payment_pipeline).to_list(20)
    payment_breakdown = {
        (r["_id"] or "unknown"): int(r["count"]) for r in payment_raw
    }

    return {
        "kpis": {
            "total_revenue": round(total_revenue, 2),
            "revenue_this_month": round(revenue_this_month, 2),
            "total_bookings": total_bookings,
            "paid_bookings": paid_bookings,
            "active_bookings": active_bookings,
            "avg_revenue_per_booking": round(avg_rev, 2),
        },
        "monthly_revenue": monthly_revenue,
        "top_cars": top_cars,
        "top_locations": top_locations,
        "status_breakdown": status_breakdown,
        "payment_breakdown": payment_breakdown,
    }

# ==================== LOCATION ROUTES ====================

def serialize_location(loc):
    loc["id"] = str(loc["_id"])
    del loc["_id"]
    return loc

@api_router.get("/locations")
async def get_locations(city: Optional[str] = None, type: Optional[str] = None):
    query = {}
    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    if type and type != "both":
        query["$or"] = [{"type": type}, {"type": "both"}]
    locations = await db.locations.find(query).to_list(100)
    return [serialize_location(l) for l in locations]

@api_router.get("/locations/cities/list")
async def get_location_cities():
    cities = await db.locations.distinct("city")
    return cities

@api_router.get("/locations/tax-by-name")
async def get_tax_by_location_name(name: str):
    """Get tax rate AND minimum booking days for a location.

    Lookup strategy (each step is case-insensitive):
      1) Exact name match
      2) Substring match (DB name contains query OR query contains DB name)
      3) City match (treat the query as a city)
    Falls back to {tax_rate: 0, min_booking_days: 1} if nothing matches.
    """
    import re as _re
    q = (name or "").strip()
    if not q:
        return {"tax_rate": 0.0, "name": q, "city": "", "min_booking_days": 1, "insurance_included": False, "refuel_amount": 0.0}

    proj = {"_id": 0, "tax_rate": 1, "name": 1, "city": 1, "min_booking_days": 1, "insurance_included": 1, "refuel_amount": 1}
    safe_q = _re.escape(q)

    # 1) Exact (case-insensitive)
    loc = await db.locations.find_one(
        {"name": {"$regex": f"^{safe_q}$", "$options": "i"}}, proj
    )
    # 2) Substring (DB.name contains q)
    if not loc:
        loc = await db.locations.find_one(
            {"name": {"$regex": safe_q, "$options": "i"}}, proj
        )
    # 3) Reverse substring (q contains DB.name) - fetch all and check in Python
    if not loc:
        all_locs = await db.locations.find({}, proj).to_list(500)
        q_lower = q.lower()
        for l in all_locs:
            ln = (l.get("name") or "").strip()
            if ln and ln.lower() in q_lower:
                loc = l
                break
    # 4) City match (case-insensitive exact)
    if not loc:
        loc = await db.locations.find_one(
            {"city": {"$regex": f"^{safe_q}$", "$options": "i"}}, proj
        )
    # 5) City substring (DB.city contains q OR q contains DB.city)
    if not loc:
        loc = await db.locations.find_one(
            {"city": {"$regex": safe_q, "$options": "i"}}, proj
        )

    if loc:
        return {
            "tax_rate": float(loc.get("tax_rate") or 0.0),
            "name": loc.get("name", ""),
            "city": loc.get("city", ""),
            "min_booking_days": int(loc.get("min_booking_days") or 1),
            "insurance_included": bool(loc.get("insurance_included") or False),
            "refuel_amount": float(loc.get("refuel_amount") or 0.0),
        }
    return {"tax_rate": 0.0, "name": q, "city": "", "min_booking_days": 1, "insurance_included": False, "refuel_amount": 0.0}

@api_router.get("/locations/{location_id}")
async def get_location(location_id: str):
    loc = await db.locations.find_one({"_id": ObjectId(location_id)})
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return serialize_location(loc)

@api_router.post("/locations")
async def create_location(loc: LocationCreate, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    loc_dict = loc.dict()
    loc_dict["created_at"] = datetime.now(timezone.utc)
    result = await db.locations.insert_one(loc_dict)
    loc_dict["id"] = str(result.inserted_id)
    del loc_dict["_id"]
    return loc_dict

@api_router.put("/locations/{location_id}")
async def update_location(location_id: str, loc: LocationUpdate, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    update_data = {k: v for k, v in loc.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.locations.update_one({"_id": ObjectId(location_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Location not found")
    updated = await db.locations.find_one({"_id": ObjectId(location_id)})
    return serialize_location(updated)

@api_router.delete("/locations/{location_id}")
async def delete_location(location_id: str, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.locations.delete_one({"_id": ObjectId(location_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Location not found")
    return {"message": "Location deleted"}

# Browse cars by location
@api_router.get("/cars/by-location/{location_id}")
async def get_cars_by_location(location_id: str):
    loc = await db.locations.find_one({"_id": ObjectId(location_id)})
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    loc_name = loc.get("name", "")
    cars = await db.cars.find({
        "available": True,
        "$or": [
            {"pickup_location.name": loc_name},
            {"dropoff_location.name": loc_name},
            {"pickup_location.location_id": location_id},
            {"dropoff_location.location_id": location_id},
        ]
    }).to_list(100)
    return [serialize_car(c) for c in cars]

# ==================== IMAGE UPLOAD ====================

import base64

UPLOAD_DIR = _Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

class ImageUpload(BaseModel):
    image_data: str  # base64 encoded image
    filename: Optional[str] = None

@api_router.post("/upload/image")
async def upload_image(data: ImageUpload, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    try:
        # Handle data URL format (data:image/jpeg;base64,...)
        image_str = data.image_data
        if "," in image_str:
            image_str = image_str.split(",", 1)[1]
        
        # Validate base64
        image_bytes = base64.b64decode(image_str)
        
        # Determine mime type from filename extension
        ext = "jpeg"
        if data.filename:
            raw_ext = data.filename.rsplit(".", 1)[-1].lower() if "." in data.filename else "jpg"
            if raw_ext in ["jpg", "jpeg", "png", "webp", "gif"]:
                ext = "jpeg" if raw_ext == "jpg" else raw_ext
        
        # Enforce a reasonable size cap (3MB) to keep DB lean
        if len(image_bytes) > 3 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 3MB after compression). Please use a smaller photo.")
        
        # Return as a data URL embedded directly - stored in MongoDB so it survives deploys
        # and works across preview/production environments seamlessly
        data_url = f"data:image/{ext};base64,{image_str}"
        
        # Also persist to disk as a backup (best-effort, non-fatal if it fails)
        fname = f"{uuid.uuid4().hex[:12]}.{ext if ext != 'jpeg' else 'jpg'}"
        try:
            filepath = UPLOAD_DIR / fname
            filepath.write_bytes(image_bytes)
        except Exception as fe:
            logger.warning(f"Disk backup failed (ok, data URL is primary): {fe}")
        
        return {"url": data_url, "filename": fname}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")

# ==================== REVIEW ROUTES ====================

def serialize_review(rev):
    rev["id"] = str(rev["_id"])
    del rev["_id"]
    return rev

@api_router.get("/reviews/{car_id}")
async def get_car_reviews(car_id: str):
    reviews = await db.reviews.find({"car_id": car_id}).sort("created_at", -1).to_list(50)
    return [serialize_review(r) for r in reviews]

@api_router.post("/reviews")
async def create_review(review: ReviewCreate, request: Request):
    user = await get_authenticated_user(request)
    user_id = str(user.get("_id") or user.get("id") or user.get("user_id"))

    if review.rating < 1 or review.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    # Check car exists
    car = await db.cars.find_one({"_id": ObjectId(review.car_id)})
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    # Check if user already reviewed this car
    existing = await db.reviews.find_one({"car_id": review.car_id, "user_id": user_id})
    if existing:
        # Update existing review
        await db.reviews.update_one(
            {"_id": existing["_id"]},
            {"$set": {"rating": review.rating, "comment": review.comment, "updated_at": datetime.now(timezone.utc)}}
        )
        updated = await db.reviews.find_one({"_id": existing["_id"]})
        return serialize_review(updated)

    review_doc = {
        "car_id": review.car_id,
        "user_id": user_id,
        "user_name": user.get("name", "Anonymous"),
        "user_email": user.get("email", ""),
        "rating": review.rating,
        "comment": review.comment,
        "created_at": datetime.now(timezone.utc)
    }
    result = await db.reviews.insert_one(review_doc)
    review_doc["id"] = str(result.inserted_id)
    del review_doc["_id"]
    return review_doc

@api_router.delete("/reviews/{review_id}")
async def delete_review(review_id: str, request: Request):
    user = await get_authenticated_user(request)
    review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    user_id = str(user.get("_id") or user.get("id") or user.get("user_id"))
    if review["user_id"] != user_id and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.reviews.delete_one({"_id": ObjectId(review_id)})
    return {"message": "Review deleted"}

# ==================== DATA MIGRATION ====================

def _image_url_to_data_url(image_url: str) -> str:
    """Convert a file-based image URL (/api/uploads/xxx.jpg) to a base64 data URL
    by reading the file from disk. Returns the original URL if conversion fails
    or if the URL is already a data URL / external URL we cannot fetch.
    """
    if not image_url or image_url.startswith("data:"):
        return image_url
    # Extract filename from any URL that ends with /api/uploads/<filename>
    try:
        if "/api/uploads/" in image_url:
            fname = image_url.rsplit("/api/uploads/", 1)[1].split("?")[0].split("#")[0]
            fpath = UPLOAD_DIR / fname
            if fpath.exists() and fpath.is_file():
                ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "jpeg"
                if ext == "jpg":
                    ext = "jpeg"
                data = fpath.read_bytes()
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:image/{ext};base64,{b64}"
    except Exception as e:
        logger.warning(f"Could not convert image to data URL: {e}")
    return image_url


@api_router.get("/admin/export")
async def export_data(request: Request):
    """Export all cars and locations for migration to another environment.
    Car images stored as file URLs are embedded as base64 data URLs so they
    travel with the export and don't break on the destination environment.
    """
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    cars = await db.cars.find({}, {"_id": 0, "created_at": 0}).to_list(500)
    locations_data = await db.locations.find({}, {"_id": 0, "created_at": 0}).to_list(500)
    
    # Embed file-based images as data URLs so they survive migration
    for car in cars:
        if car.get("image_url"):
            car["image_url"] = _image_url_to_data_url(car["image_url"])
    
    return {"cars": cars, "locations": locations_data, "count": {"cars": len(cars), "locations": len(locations_data)}}


@api_router.post("/admin/migrate-images")
async def migrate_images(request: Request):
    """Convert all cars whose image_url points to a local file
    (/api/uploads/xxx.jpg) into embedded base64 data URLs stored in MongoDB.
    This makes images deploy-safe and portable across environments.
    """
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    converted = 0
    failed = 0
    already_ok = 0
    cars = await db.cars.find({}).to_list(500)
    for car in cars:
        url = car.get("image_url") or ""
        if not url or url.startswith("data:"):
            already_ok += 1
            continue
        if "/api/uploads/" not in url:
            # External URL (e.g. unsplash) – leave as-is, it's already portable
            already_ok += 1
            continue
        new_url = _image_url_to_data_url(url)
        if new_url.startswith("data:"):
            car_id = car.get("id") or car.get("_id")
            if car_id is not None:
                await db.cars.update_one({"_id": car["_id"]}, {"$set": {"image_url": new_url}})
                converted += 1
            else:
                failed += 1
        else:
            failed += 1
    return {
        "message": f"Converted {converted} car image(s) to embedded base64. {already_ok} already portable, {failed} could not be read from disk.",
        "converted": converted,
        "already_portable": already_ok,
        "failed": failed,
    }

@api_router.post("/admin/import")
async def import_data(request: Request):
    """Import cars and locations from another environment. Replaces existing data."""
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    body = await request.json()
    imported_cars = 0
    imported_locs = 0
    
    # Import locations first (cars reference them)
    if "locations" in body and body["locations"]:
        for loc in body["locations"]:
            existing = await db.locations.find_one({"name": loc.get("name"), "city": loc.get("city")})
            if not existing:
                loc["created_at"] = datetime.now(timezone.utc)
                await db.locations.insert_one(loc)
                imported_locs += 1
    
    # Import cars
    if "cars" in body and body["cars"]:
        for car in body["cars"]:
            existing = await db.cars.find_one({"name": car.get("name"), "brand": car.get("brand")})
            if not existing:
                car["created_at"] = datetime.now(timezone.utc)
                await db.cars.insert_one(car)
                imported_cars += 1
    
    return {"message": f"Imported {imported_cars} cars and {imported_locs} locations", "imported_cars": imported_cars, "imported_locations": imported_locs}

# ==================== SEED DATA ====================

SEED_LOCATIONS = [
    {
        "name": "Punta Cana Airport",
        "address": "Carretera Coral, Punta Cana 23000",
        "city": "Punta Cana",
        "country": "Dominican Republic",
        "lat": 18.5670,
        "lng": -68.3634,
        "type": "both",
        "tax_rate": 18.0
    },
    {
        "name": "Bavaro Beach Hub",
        "address": "Av. Alemania, Bavaro, Punta Cana 23301",
        "city": "Punta Cana",
        "country": "Dominican Republic",
        "lat": 18.6871,
        "lng": -68.4484,
        "type": "both",
        "tax_rate": 18.0
    },
    {
        "name": "Santo Domingo Downtown",
        "address": "Calle El Conde 103, Zona Colonial, Santo Domingo 10210",
        "city": "Santo Domingo",
        "country": "Dominican Republic",
        "lat": 18.4722,
        "lng": -69.8830,
        "type": "both",
        "tax_rate": 18.0
    },
    {
        "name": "Las Americas Airport SDQ",
        "address": "Autopista Las Americas Km 22, Santo Domingo Este",
        "city": "Santo Domingo",
        "country": "Dominican Republic",
        "lat": 18.4297,
        "lng": -69.6689,
        "type": "both",
        "tax_rate": 18.0
    },
    {
        "name": "Miami International Airport",
        "address": "2100 NW 42nd Ave, Miami, FL 33126",
        "city": "Miami",
        "country": "USA",
        "lat": 25.7959,
        "lng": -80.2870,
        "type": "both",
        "tax_rate": 7.0
    },
    {
        "name": "Miami Beach Rental Center",
        "address": "1200 Collins Ave, Miami Beach, FL 33139",
        "city": "Miami",
        "country": "USA",
        "lat": 25.7826,
        "lng": -80.1341,
        "type": "both",
        "tax_rate": 7.0
    },
    {
        "name": "JFK Airport New York",
        "address": "Queens, NY 11430",
        "city": "New York",
        "country": "USA",
        "lat": 40.6413,
        "lng": -73.7781,
        "type": "both",
        "tax_rate": 8.875
    },
    {
        "name": "Manhattan Midtown Hub",
        "address": "420 W 42nd St, New York, NY 10036",
        "city": "New York",
        "country": "USA",
        "lat": 40.7580,
        "lng": -73.9941,
        "type": "both",
        "tax_rate": 8.875
    }
]

SEED_CARS = [
    {
        "name": "Tesla Model 3",
        "brand": "Tesla",
        "model": "Model 3",
        "year": 2024,
        "category": "Electric",
        "price_per_day": 89.00,
        "seats": 5,
        "transmission": "Automatic",
        "fuel_type": "Electric",
        "description": "Premium electric sedan with autopilot. 358 miles of range.",
        "image_url": "https://images.unsplash.com/photo-1560958089-b8a1929cea89?w=800",
        "pickup_location": {"name": "Punta Cana Airport", "lat": 18.5670, "lng": -68.3634, "address": "Carretera Coral, Punta Cana 23000"},
        "dropoff_location": {"name": "Bavaro Beach Hub", "lat": 18.6871, "lng": -68.4484, "address": "Av. Alemania, Bavaro, Punta Cana 23301"},
        "available": True
    },
    {
        "name": "BMW X5 xDrive",
        "brand": "BMW",
        "model": "X5",
        "year": 2024,
        "category": "SUV",
        "price_per_day": 120.00,
        "seats": 7,
        "transmission": "Automatic",
        "fuel_type": "Gasoline",
        "description": "Luxury SUV with spacious interior and advanced tech.",
        "image_url": "https://images.unsplash.com/photo-1637575694029-383a6c97a806?w=800",
        "pickup_location": {"name": "Santo Domingo Downtown", "lat": 18.4722, "lng": -69.8830, "address": "Calle El Conde 103, Zona Colonial"},
        "dropoff_location": {"name": "Las Americas Airport SDQ", "lat": 18.4297, "lng": -69.6689, "address": "Autopista Las Americas Km 22"},
        "available": True
    },
    {
        "name": "Mercedes-Benz S-Class",
        "brand": "Mercedes-Benz",
        "model": "S-Class",
        "year": 2024,
        "category": "Luxury",
        "price_per_day": 199.00,
        "seats": 5,
        "transmission": "Automatic",
        "fuel_type": "Gasoline",
        "description": "The pinnacle of luxury sedans. Unmatched comfort and technology.",
        "image_url": "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?w=800",
        "pickup_location": {"name": "Miami International Airport", "lat": 25.7959, "lng": -80.2870, "address": "2100 NW 42nd Ave, Miami, FL 33126"},
        "dropoff_location": {"name": "Miami Beach Rental Center", "lat": 25.7826, "lng": -80.1341, "address": "1200 Collins Ave, Miami Beach"},
        "available": True
    },
    {
        "name": "Toyota Camry",
        "brand": "Toyota",
        "model": "Camry",
        "year": 2024,
        "category": "Sedan",
        "price_per_day": 55.00,
        "seats": 5,
        "transmission": "Automatic",
        "fuel_type": "Gasoline",
        "description": "Reliable and fuel-efficient sedan. Perfect for daily commuting.",
        "image_url": "https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800",
        "pickup_location": {"name": "JFK Airport New York", "lat": 40.6413, "lng": -73.7781, "address": "Queens, NY 11430"},
        "dropoff_location": {"name": "Manhattan Midtown Hub", "lat": 40.7580, "lng": -73.9941, "address": "420 W 42nd St, New York, NY 10036"},
        "available": True
    },
    {
        "name": "Porsche 911 Carrera",
        "brand": "Porsche",
        "model": "911",
        "year": 2024,
        "category": "Sports",
        "price_per_day": 299.00,
        "seats": 2,
        "transmission": "Automatic",
        "fuel_type": "Gasoline",
        "description": "Iconic sports car. Raw driving thrills with everyday usability.",
        "image_url": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=800",
        "pickup_location": {"name": "Miami Beach Rental Center", "lat": 25.7826, "lng": -80.1341, "address": "1200 Collins Ave, Miami Beach"},
        "dropoff_location": {"name": "Miami International Airport", "lat": 25.7959, "lng": -80.2870, "address": "2100 NW 42nd Ave, Miami, FL 33126"},
        "available": True
    },
    {
        "name": "Range Rover Sport",
        "brand": "Land Rover",
        "model": "Range Rover Sport",
        "year": 2024,
        "category": "SUV",
        "price_per_day": 175.00,
        "seats": 5,
        "transmission": "Automatic",
        "fuel_type": "Gasoline",
        "description": "Premium SUV combining off-road capability with luxury.",
        "image_url": "https://images.unsplash.com/photo-1736794111724-f7ddff6ab8f4?w=800",
        "pickup_location": {"name": "Bavaro Beach Hub", "lat": 18.6871, "lng": -68.4484, "address": "Av. Alemania, Bavaro, Punta Cana 23301"},
        "dropoff_location": {"name": "Punta Cana Airport", "lat": 18.5670, "lng": -68.3634, "address": "Carretera Coral, Punta Cana 23000"},
        "available": True
    }
]

async def seed_data():
    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@damscarrental.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc)
        })
        logger.info(f"Admin seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info("Admin password updated")
    
    # Seed locations
    loc_count = await db.locations.count_documents({})
    if loc_count == 0:
        for loc in SEED_LOCATIONS:
            loc["created_at"] = datetime.now(timezone.utc)
            await db.locations.insert_one(loc)
        logger.info(f"Seeded {len(SEED_LOCATIONS)} locations")
    
    # Seed cars - drop old and reseed with new locations
    car_count = await db.cars.count_documents({})
    if car_count == 0:
        for car in SEED_CARS:
            car["created_at"] = datetime.now(timezone.utc)
            await db.cars.insert_one(car)
        logger.info(f"Seeded {len(SEED_CARS)} cars")
    
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.cars.create_index("category")
    await db.bookings.create_index("user_id")
    await db.payment_transactions.create_index("session_id")
    await db.locations.create_index("city")
    await db.reviews.create_index("car_id")
    await db.reviews.create_index([("car_id", 1), ("user_id", 1)], unique=True)
    
    # Write test credentials
    creds_path = Path("/app/memory/test_credentials.md")
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(f"""# Test Credentials - Dams Car Rental

## Admin Account
- Email: {admin_email}
- Password: {admin_password}
- Role: admin

## Auth Endpoints
- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me
- POST /api/auth/logout
- POST /api/auth/refresh
- POST /api/auth/google/session

## Location Endpoints
- GET /api/locations
- POST /api/locations (admin)
- PUT /api/locations/{{id}} (admin)
- DELETE /api/locations/{{id}} (admin)
""")

@app.on_event("startup")
async def startup():
    await seed_data()

@app.on_event("shutdown")
async def shutdown():
    client.close()

# Include router

# ==================== PROMO CODE ENDPOINTS ====================
@api_router.get("/admin/promo-codes")
async def admin_list_promo_codes(request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    rows = await db.promo_codes.find({}).sort("created_at", -1).to_list(500)
    return [_serialize_promo(r) for r in rows]


@api_router.post("/admin/promo-codes")
async def admin_create_promo_code(body: PromoCodeCreate, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    code = (body.code or "").strip().upper()
    if not code or len(code) < 2:
        raise HTTPException(status_code=400, detail="Code must be at least 2 characters")
    if body.discount_type not in ("percent", "fixed"):
        raise HTTPException(status_code=400, detail="discount_type must be 'percent' or 'fixed'")
    if body.discount_value <= 0:
        raise HTTPException(status_code=400, detail="discount_value must be > 0")
    if body.discount_type == "percent" and body.discount_value > 100:
        raise HTTPException(status_code=400, detail="Percentage discount cannot exceed 100")
    if await db.promo_codes.find_one({"code": code}):
        raise HTTPException(status_code=400, detail="Promo code already exists")
    doc = {
        "code": code,
        "discount_type": body.discount_type,
        "discount_value": float(body.discount_value),
        "max_uses": int(body.max_uses or 0),
        "used_count": 0,
        "expires_at": body.expires_at,
        "min_amount": float(body.min_amount or 0),
        "active": bool(body.active),
        "created_at": datetime.now(timezone.utc),
    }
    res = await db.promo_codes.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize_promo(doc)


@api_router.put("/admin/promo-codes/{promo_id}")
async def admin_update_promo_code(promo_id: str, body: PromoCodeUpdate, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not ObjectId.is_valid(promo_id):
        raise HTTPException(status_code=400, detail="Invalid promo id")
    update_data: Dict = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "code" in update_data:
        update_data["code"] = update_data["code"].strip().upper()
    if "discount_type" in update_data and update_data["discount_type"] not in ("percent", "fixed"):
        raise HTTPException(status_code=400, detail="discount_type must be 'percent' or 'fixed'")
    if "discount_value" in update_data and update_data["discount_value"] <= 0:
        raise HTTPException(status_code=400, detail="discount_value must be > 0")
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = await db.promo_codes.update_one({"_id": ObjectId(promo_id)}, {"$set": update_data})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Promo code not found")
    p = await db.promo_codes.find_one({"_id": ObjectId(promo_id)})
    return _serialize_promo(p)


@api_router.delete("/admin/promo-codes/{promo_id}")
async def admin_delete_promo_code(promo_id: str, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not ObjectId.is_valid(promo_id):
        raise HTTPException(status_code=400, detail="Invalid promo id")
    res = await db.promo_codes.delete_one({"_id": ObjectId(promo_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Promo code not found")
    return {"ok": True}


@api_router.post("/promo-codes/validate")
async def validate_promo_code(body: PromoValidateRequest, request: Request):
    """Validate a promo code against a given subtotal. Auth required."""
    await get_authenticated_user(request)
    code = (body.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Code is required")
    promo = await db.promo_codes.find_one({"code": code})
    if not promo:
        return {"valid": False, "message": "Invalid promo code", "discount": 0}
    is_valid, reason, discount = _validate_promo(promo, float(body.subtotal or 0))
    return {
        "valid": is_valid,
        "code": promo.get("code"),
        "discount_type": promo.get("discount_type"),
        "discount_value": promo.get("discount_value"),
        "discount": discount,
        "message": reason if not is_valid else "Promo applied",
    }

# ==================== PUBLIC LEGAL HTML PAGES ====================
# Public HTML pages for /api/legal/terms and /api/legal/privacy so that
# the customer-facing marketing website (damsrentacar.com) can link the
# footer "Terms" / "Privacy" links to a publicly hosted, mobile-responsive,
# branded page. The Terms text is the live `rental_terms` setting (the same
# one the admin manages in the Admin Panel → 📜 Terms tab). The Privacy text
# is stored in /app/backend/legal/privacy.txt.
_PRIVACY_TXT_PATH = _Path(__file__).parent / "legal" / "privacy.txt"
PRIVACY_UPDATED_AT = "May 21st, 2026"

def _legal_layout(title: str, subtitle: str, body_html: str, accent: str = "#FF3B30") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
<title>{title} · DAMS Rent a Car</title>
<meta name="robots" content="index, follow" />
<meta name="description" content="{title} for DAMS Rent a Car. Read our policies before booking your next rental." />
<meta property="og:title" content="{title} · DAMS Rent a Car" />
<meta property="og:type" content="article" />
<style>
  :root {{ --accent: {accent}; --ink: #0a0a0a; --muted: #555; --bg: #fafafa; --card: #ffffff; --border: #e5e5e5; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: var(--ink); background: var(--bg); -webkit-font-smoothing: antialiased; }}
  a {{ color: #007AFF; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  header {{ background: #0a0a0a; color: #fff; padding: 20px 24px; }}
  header .wrap {{ max-width: 920px; margin: 0 auto; display: flex; align-items: center; gap: 14px; }}
  header .badge {{ width: 44px; height: 44px; border-radius: 12px; background: var(--accent); display: inline-flex; align-items: center; justify-content: center; font-weight: 900; color: #fff; font-size: 18px; letter-spacing: -1px; }}
  header h1 {{ margin: 0; font-size: 16px; font-weight: 800; letter-spacing: 0.5px; }}
  header .sub {{ margin: 2px 0 0; font-size: 11px; color: #cfcfcf; letter-spacing: 1px; font-weight: 600; }}
  main {{ max-width: 920px; margin: 0 auto; padding: 32px 24px 64px; }}
  .titlewrap {{ margin-bottom: 24px; }}
  .titlewrap h2 {{ font-size: 32px; font-weight: 900; margin: 0 0 6px; line-height: 1.15; letter-spacing: -0.5px; }}
  .titlewrap p {{ font-size: 14px; color: var(--muted); margin: 0; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 28px 32px; box-shadow: 0 1px 4px rgba(0,0,0,0.03); }}
  .card pre {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14.5px; color: #1a1a1a; line-height: 1.7; white-space: pre-wrap; word-wrap: break-word; margin: 0; }}
  .notice {{ display: flex; align-items: flex-start; gap: 10px; background: #f0f8ff; border: 1px solid #cfe3ff; border-radius: 12px; padding: 12px 14px; margin: 0 0 22px; color: #0a5dff; font-size: 13px; font-weight: 600; }}
  .notice.privacy {{ background: #e6f9ed; border-color: #bce7c8; color: #0a5d2b; }}
  .notice strong {{ font-weight: 800; }}
  .crumbs {{ font-size: 12px; color: var(--muted); margin: 0 0 10px; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700; }}
  footer {{ max-width: 920px; margin: 0 auto; padding: 24px; color: var(--muted); font-size: 12px; text-align: center; }}
  footer a {{ color: var(--accent); font-weight: 700; }}
  @media (max-width: 640px) {{
    .titlewrap h2 {{ font-size: 26px; }}
    .card {{ padding: 20px 18px; border-radius: 14px; }}
    .card pre {{ font-size: 13.5px; line-height: 1.65; }}
    header {{ padding: 14px 18px; }}
    main {{ padding: 24px 16px 48px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <span class="badge">DR</span>
    <div>
      <h1>DAMS RENT A CAR, S.R.L.</h1>
      <div class="sub">PREMIUM CAR RENTALS · DOMINICAN REPUBLIC</div>
    </div>
  </div>
</header>
<main>
  <div class="crumbs">Legal · {title}</div>
  <div class="titlewrap">
    <h2>{title}</h2>
    <p>{subtitle}</p>
  </div>
  {body_html}
</main>
<footer>
  © 2026 DAMS Car Rental · <a href="mailto:info@damsrentacar.com">info@damsrentacar.com</a> · <a href="/api/legal/terms">Terms</a> · <a href="/api/legal/privacy">Privacy</a>
</footer>
</body>
</html>"""


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@app.get("/api/legal/terms", response_class=HTMLResponse)
async def legal_terms_html():
    """Public, branded HTML rendering of the rental Terms & Conditions for the customer-facing website footer link."""
    setting = await db.settings.find_one({"key": "rental_terms"})
    terms = (setting or {}).get("value") or DEFAULT_RENTAL_TERMS
    body = f"""
      <div class="notice"><span>📜</span><div>These are the rental Terms &amp; Conditions you accept when booking with DAMS Rent a Car. By using our service, you agree to these terms.</div></div>
      <div class="card"><pre>{_esc(terms)}</pre></div>
    """
    html = _legal_layout("Terms & Conditions", "The rental agreement applicable to all bookings.", body)
    return HTMLResponse(content=html, headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/legal/privacy", response_class=HTMLResponse)
async def legal_privacy_html():
    """Public, branded HTML rendering of the Privacy Policy for the customer-facing website footer link."""
    # First check admin-customised version in db.settings; fall back to bundled default.
    setting = await db.settings.find_one({"key": "privacy_policy"})
    privacy_text = (setting or {}).get("value")
    if not privacy_text:
        try:
            privacy_text = _PRIVACY_TXT_PATH.read_text(encoding="utf-8")
        except Exception as e:
            logger.exception(f"Could not read privacy.txt: {e}")
            privacy_text = "Privacy policy not available. Please contact info@damsrentacar.com."
    body = f"""
      <div class="notice privacy"><span>🔒</span><div><strong>Your privacy matters to us.</strong> &nbsp;Last updated: {PRIVACY_UPDATED_AT}</div></div>
      <div class="card"><pre>{_esc(privacy_text)}</pre></div>
    """
    html = _legal_layout("Privacy Policy", "How we collect, use, and protect your data.", body, accent="#34c759")
    return HTMLResponse(content=html, headers={"Cache-Control": "public, max-age=300"})


app.include_router(api_router)


# ==================== ADMIN: CUSTOMERS ====================
# These are registered directly on `app` so they sit after include_router.

@app.get("/api/admin/customers")
async def admin_list_customers(request: Request, q: Optional[str] = None, role: Optional[str] = None, page: int = 1, limit: int = 50):
    """List all registered customers/users for the admin panel.
    Supports search by name/email/phone (case-insensitive), optional role filter, and pagination."""
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    page = max(1, int(page or 1))
    limit = max(1, min(200, int(limit or 50)))
    skip = (page - 1) * limit

    query: Dict[str, Any] = {}
    if role and role in ("user", "admin"):
        query["role"] = role
    if q and q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"name": rx}, {"email": rx}, {"phone": rx}]

    total = await db.users.count_documents(query)
    cursor = db.users.find(query).sort("created_at", -1).skip(skip).limit(limit)
    users_list = await cursor.to_list(length=limit)

    # Batch fetch booking counts for the returned users for performance.
    user_ids = [str(u.get("_id")) for u in users_list]
    counts_pipeline = [
        {"$match": {"user_id": {"$in": user_ids}}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}, "total_spent": {"$sum": {"$ifNull": ["$total_price", 0]}}}},
    ]
    counts_map: Dict[str, Dict[str, Any]] = {}
    async for row in db.bookings.aggregate(counts_pipeline):
        counts_map[row["_id"]] = {"count": row.get("count", 0), "total_spent": row.get("total_spent", 0)}

    items = []
    for u in users_list:
        uid = str(u.get("_id"))
        stats = counts_map.get(uid, {"count": 0, "total_spent": 0})
        created_at = u.get("created_at")
        terms_at = u.get("terms_accepted_at")
        items.append({
            "id": uid,
            "name": u.get("name") or "",
            "email": u.get("email") or "",
            "phone": u.get("phone") or "",
            "role": u.get("role") or "user",
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
            "terms_accepted_at": terms_at.isoformat() if isinstance(terms_at, datetime) else None,
            "bookings_count": stats["count"],
            "total_spent": round(float(stats.get("total_spent") or 0), 2),
        })
    return {"items": items, "total": total, "page": page, "limit": limit, "pages": (total + limit - 1) // limit}


@app.get("/api/admin/customers/{customer_id}")
async def admin_customer_detail(customer_id: str, request: Request):
    """Full profile + booking history of a single customer."""
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        oid = ObjectId(customer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid customer id")
    u = await db.users.find_one({"_id": oid})
    if not u:
        raise HTTPException(status_code=404, detail="Customer not found")

    bookings_cursor = db.bookings.find({"user_id": str(u.get("_id"))}).sort("created_at", -1).limit(100)
    bookings_list = []
    total_spent = 0.0
    async for b in bookings_cursor:
        car = await db.cars.find_one({"_id": ObjectId(b.get("car_id"))}) if b.get("car_id") else None
        created = b.get("created_at")
        pickup = b.get("pickup_date")
        dropoff = b.get("dropoff_date")
        bookings_list.append({
            "id": str(b.get("_id")),
            "car_name": (car.get("name") if car else None) or "(deleted car)",
            "car_brand": (car.get("brand") if car else None) or "",
            "pickup_date": pickup.isoformat() if isinstance(pickup, datetime) else pickup,
            "dropoff_date": dropoff.isoformat() if isinstance(dropoff, datetime) else dropoff,
            "status": b.get("status") or "pending",
            "payment_status": b.get("payment_status") or "unpaid",
            "payment_method": b.get("payment_method") or "",
            "total_price": float(b.get("total_price") or 0),
            "created_at": created.isoformat() if isinstance(created, datetime) else None,
        })
        total_spent += float(b.get("total_price") or 0)

    created_at = u.get("created_at")
    terms_at = u.get("terms_accepted_at")
    pwd_at = u.get("password_updated_at")
    return {
        "id": str(u.get("_id")),
        "name": u.get("name") or "",
        "email": u.get("email") or "",
        "phone": u.get("phone") or "",
        "role": u.get("role") or "user",
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
        "terms_accepted_at": terms_at.isoformat() if isinstance(terms_at, datetime) else None,
        "password_updated_at": pwd_at.isoformat() if isinstance(pwd_at, datetime) else None,
        "bookings": bookings_list,
        "bookings_count": len(bookings_list),
        "total_spent": round(total_spent, 2),
    }

# Serve admin panel HTML
ADMIN_HTML = _Path(__file__).parent / "admin_panel.html"

@app.get("/api/admin-panel", response_class=HTMLResponse)
async def serve_admin_panel():
    if ADMIN_HTML.exists():
        return HTMLResponse(content=ADMIN_HTML.read_text(), status_code=200)
    return HTMLResponse(content="<h1>Admin panel not found</h1>", status_code=404)

# Serve uploaded images
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    # Explicit origins are required when allow_credentials=True (the CORS spec
    # forbids wildcard "*" with credentials). We allow:
    #   - the customer marketing website damsrentacar.com (+ www) so it can do
    #     full booking flow with cookies/JWT.
    #   - the Expo packager preview URL and the production deploy host.
    # Anything else (third-party tools, dev tunnels, etc.) is matched by the
    # regex below so the Expo Go QR-code session and any Emergent preview URL
    # work out-of-the-box.
    allow_origins=[
        "https://damsrentacar.com",
        "https://www.damsrentacar.com",
        "https://rental-routes.emergent.host",
        "https://rental-routes.preview.emergentagent.com",
        "http://localhost:3000",
        "http://localhost:19006",
        "http://localhost:8081",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|[\w-]+\.preview\.emergentagent\.com|[\w-]+\.emergent\.host|[\w-]+\.exp\.direct|[\w-]+\.expo\.dev|[\w-]+\.damsrentacar\.com):?\d*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
