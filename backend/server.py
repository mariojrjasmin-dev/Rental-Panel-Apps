from dotenv import load_dotenv
from pathlib import Path as _Path
load_dotenv(_Path(__file__).parent / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
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
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=60), "type": "access"}
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

class LoginRequest(BaseModel):
    email: str
    password: str

class CarCreate(BaseModel):
    name: str
    brand: str
    model: str
    year: int
    category: str
    price_per_day: float
    seats: int
    transmission: str = "Automatic"
    fuel_type: str = "Gasoline"
    description: str = ""
    image_url: str = ""
    pickup_location: Optional[Dict] = None
    dropoff_location: Optional[Dict] = None
    available: bool = True

class CarUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None
    price_per_day: Optional[float] = None
    seats: Optional[int] = None
    transmission: Optional[str] = None
    fuel_type: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    pickup_location: Optional[Dict] = None
    dropoff_location: Optional[Dict] = None
    available: Optional[bool] = None

class BookingCreate(BaseModel):
    car_id: str
    pickup_date: str
    dropoff_date: str
    pickup_location: Dict
    dropoff_location: Dict
    payment_method: str = "cash"

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

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    type: Optional[str] = None

# App setup
app = FastAPI()
api_router = APIRouter(prefix="/api")

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    email = req.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed = hash_password(req.password)
    user_doc = {
        "email": email,
        "password_hash": hashed,
        "name": req.name,
        "role": "user",
        "created_at": datetime.now(timezone.utc)
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
    return [serialize_car(c) for c in cars]

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
    return serialize_car(car)

@api_router.post("/cars")
async def create_car(car: CarCreate, request: Request):
    user = await get_authenticated_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    car_dict = car.dict()
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
    total = round(days * car["price_per_day"], 2)
    
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
        "total_price": total,
        "payment_method": booking.payment_method,
        "payment_status": "pending" if booking.payment_method == "stripe" else "paid",
        "status": "confirmed" if booking.payment_method == "cash" else "pending_payment",
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.bookings.insert_one(booking_doc)
    booking_doc["id"] = str(result.inserted_id)
    del booking_doc["_id"]
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

@api_router.get("/locations/cities/list")
async def get_location_cities():
    cities = await db.locations.distinct("city")
    return cities

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

# ==================== SEED DATA ====================

SEED_LOCATIONS = [
    {
        "name": "Punta Cana Airport",
        "address": "Carretera Coral, Punta Cana 23000",
        "city": "Punta Cana",
        "country": "Dominican Republic",
        "lat": 18.5670,
        "lng": -68.3634,
        "type": "both"
    },
    {
        "name": "Bavaro Beach Hub",
        "address": "Av. Alemania, Bavaro, Punta Cana 23301",
        "city": "Punta Cana",
        "country": "Dominican Republic",
        "lat": 18.6871,
        "lng": -68.4484,
        "type": "both"
    },
    {
        "name": "Santo Domingo Downtown",
        "address": "Calle El Conde 103, Zona Colonial, Santo Domingo 10210",
        "city": "Santo Domingo",
        "country": "Dominican Republic",
        "lat": 18.4722,
        "lng": -69.8830,
        "type": "both"
    },
    {
        "name": "Las Americas Airport SDQ",
        "address": "Autopista Las Americas Km 22, Santo Domingo Este",
        "city": "Santo Domingo",
        "country": "Dominican Republic",
        "lat": 18.4297,
        "lng": -69.6689,
        "type": "both"
    },
    {
        "name": "Miami International Airport",
        "address": "2100 NW 42nd Ave, Miami, FL 33126",
        "city": "Miami",
        "country": "USA",
        "lat": 25.7959,
        "lng": -80.2870,
        "type": "both"
    },
    {
        "name": "Miami Beach Rental Center",
        "address": "1200 Collins Ave, Miami Beach, FL 33139",
        "city": "Miami",
        "country": "USA",
        "lat": 25.7826,
        "lng": -80.1341,
        "type": "both"
    },
    {
        "name": "JFK Airport New York",
        "address": "Queens, NY 11430",
        "city": "New York",
        "country": "USA",
        "lat": 40.6413,
        "lng": -73.7781,
        "type": "both"
    },
    {
        "name": "Manhattan Midtown Hub",
        "address": "420 W 42nd St, New York, NY 10036",
        "city": "New York",
        "country": "USA",
        "lat": 40.7580,
        "lng": -73.9941,
        "type": "both"
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
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
