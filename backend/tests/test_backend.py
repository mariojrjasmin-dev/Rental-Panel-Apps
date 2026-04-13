"""
Backend API Tests for Dams Car Rental
Tests: Auth (register, login, me), Cars (list, detail, admin CRUD), Bookings, Admin Stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("EXPO_PUBLIC_BACKEND_URL not set", allow_module_level=True)

# Test credentials
ADMIN_EMAIL = "admin@damscarrental.com"
ADMIN_PASSWORD = "Admin@123"

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def admin_token(api_client):
    """Get admin auth token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code}")
    data = response.json()
    return data.get("token")

@pytest.fixture
def test_user_token(api_client):
    """Create test user and return token"""
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@test.com"
    response = api_client.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": "Test@123",
        "name": "Test User"
    })
    if response.status_code != 200:
        pytest.skip(f"User registration failed: {response.status_code}")
    data = response.json()
    return data.get("token"), email

# ==================== AUTH TESTS ====================

class TestAuth:
    """Authentication endpoint tests"""

    def test_register_success(self, api_client):
        """Test user registration"""
        import uuid
        email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "Test@123",
            "name": "Test User"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Token not in response"
        assert data["email"] == email, "Email mismatch"
        assert data["role"] == "user", "Role should be user"
        print(f"✓ Register success: {email}")

    def test_register_duplicate_email(self, api_client):
        """Test duplicate email registration fails"""
        response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": ADMIN_EMAIL,
            "password": "Test@123",
            "name": "Test"
        })
        assert response.status_code == 400, f"Expected 400 for duplicate email, got {response.status_code}"
        print("✓ Duplicate email rejected")

    def test_login_success(self, api_client):
        """Test admin login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Token not in response"
        assert data["email"] == ADMIN_EMAIL, "Email mismatch"
        assert data["role"] == "admin", "Role should be admin"
        print(f"✓ Login success: {ADMIN_EMAIL}")

    def test_login_invalid_credentials(self, api_client):
        """Test login with wrong password"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials rejected")

    def test_get_me_authenticated(self, api_client, admin_token):
        """Test GET /api/auth/me with valid token"""
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["email"] == ADMIN_EMAIL, "Email mismatch"
        assert data["role"] == "admin", "Role should be admin"
        print("✓ GET /api/auth/me success")

    def test_get_me_unauthenticated(self, api_client):
        """Test GET /api/auth/me without token"""
        response = api_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated request rejected")

# ==================== CAR TESTS ====================

class TestCars:
    """Car endpoint tests"""

    def test_get_cars_public(self, api_client):
        """Test GET /api/cars (public endpoint)"""
        response = api_client.get(f"{BASE_URL}/api/cars")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have seeded cars"
        
        # Verify car structure
        car = data[0]
        assert "id" in car, "Car should have id"
        assert "name" in car, "Car should have name"
        assert "price_per_day" in car, "Car should have price_per_day"
        assert "_id" not in car, "MongoDB _id should be excluded"
        print(f"✓ GET /api/cars success: {len(data)} cars")

    def test_get_cars_with_category_filter(self, api_client):
        """Test GET /api/cars with category filter"""
        response = api_client.get(f"{BASE_URL}/api/cars?category=SUV")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        if len(data) > 0:
            for car in data:
                assert car["category"] == "SUV", "All cars should be SUV category"
        print(f"✓ Category filter works: {len(data)} SUVs")

    def test_get_cars_with_search(self, api_client):
        """Test GET /api/cars with search query"""
        response = api_client.get(f"{BASE_URL}/api/cars?search=Tesla")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        if len(data) > 0:
            # Check if Tesla is in name, brand, or model
            car = data[0]
            search_fields = f"{car.get('name', '')} {car.get('brand', '')} {car.get('model', '')}".lower()
            assert "tesla" in search_fields, "Search should match Tesla"
        print(f"✓ Search works: {len(data)} results for 'Tesla'")

    def test_get_car_detail(self, api_client):
        """Test GET /api/cars/{id}"""
        # First get a car ID
        cars_response = api_client.get(f"{BASE_URL}/api/cars")
        cars = cars_response.json()
        assert len(cars) > 0, "Need at least one car"
        
        car_id = cars[0]["id"]
        response = api_client.get(f"{BASE_URL}/api/cars/{car_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["id"] == car_id, "Car ID should match"
        assert "name" in data, "Car should have name"
        assert "_id" not in data, "MongoDB _id should be excluded"
        print(f"✓ GET /api/cars/{car_id} success")

    def test_get_car_not_found(self, api_client):
        """Test GET /api/cars/{id} with invalid ID"""
        response = api_client.get(f"{BASE_URL}/api/cars/000000000000000000000000")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid car ID returns 404")

    def test_get_all_cars_admin(self, api_client, admin_token):
        """Test GET /api/cars/all (admin only)"""
        response = api_client.get(f"{BASE_URL}/api/cars/all", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/cars/all (admin): {len(data)} cars")

    def test_get_all_cars_non_admin(self, api_client, test_user_token):
        """Test GET /api/cars/all as non-admin (should fail)"""
        token, _ = test_user_token
        response = api_client.get(f"{BASE_URL}/api/cars/all", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Non-admin blocked from /api/cars/all")

    def test_create_car_admin(self, api_client, admin_token):
        """Test POST /api/cars (admin only) - Create and verify"""
        car_data = {
            "name": "TEST_Honda Civic",
            "brand": "Honda",
            "model": "Civic",
            "year": 2024,
            "category": "Sedan",
            "price_per_day": 45.00,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Gasoline",
            "description": "Test car",
            "image_url": "https://example.com/civic.jpg",
            "available": True
        }
        
        response = api_client.post(f"{BASE_URL}/api/cars", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json=car_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        created_car = response.json()
        assert "id" in created_car, "Created car should have id"
        assert created_car["name"] == car_data["name"], "Name should match"
        car_id = created_car["id"]
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/cars/{car_id}")
        assert get_response.status_code == 200, "Created car should be retrievable"
        retrieved_car = get_response.json()
        assert retrieved_car["name"] == car_data["name"], "Retrieved car name should match"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/cars/{car_id}", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"✓ POST /api/cars success and verified: {car_id}")

    def test_update_car_admin(self, api_client, admin_token):
        """Test PUT /api/cars/{id} (admin only) - Update and verify"""
        # Create test car first
        car_data = {
            "name": "TEST_Update Car",
            "brand": "Test",
            "model": "Update",
            "year": 2024,
            "category": "Sedan",
            "price_per_day": 50.00,
            "seats": 5,
            "transmission": "Automatic",
            "fuel_type": "Gasoline"
        }
        create_response = api_client.post(f"{BASE_URL}/api/cars",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=car_data
        )
        car_id = create_response.json()["id"]
        
        # Update car
        update_data = {"price_per_day": 75.00, "name": "TEST_Updated Car"}
        response = api_client.put(f"{BASE_URL}/api/cars/{car_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        updated_car = response.json()
        assert updated_car["price_per_day"] == 75.00, "Price should be updated"
        assert updated_car["name"] == "TEST_Updated Car", "Name should be updated"
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/cars/{car_id}")
        retrieved_car = get_response.json()
        assert retrieved_car["price_per_day"] == 75.00, "Updated price should persist"
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/cars/{car_id}", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"✓ PUT /api/cars/{car_id} success and verified")

    def test_delete_car_admin(self, api_client, admin_token):
        """Test DELETE /api/cars/{id} (admin only) - Delete and verify"""
        # Create test car first
        car_data = {
            "name": "TEST_Delete Car",
            "brand": "Test",
            "model": "Delete",
            "year": 2024,
            "category": "Sedan",
            "price_per_day": 50.00,
            "seats": 5
        }
        create_response = api_client.post(f"{BASE_URL}/api/cars",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=car_data
        )
        car_id = create_response.json()["id"]
        
        # Delete car
        response = api_client.delete(f"{BASE_URL}/api/cars/{car_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify deletion with GET (should return 404)
        get_response = api_client.get(f"{BASE_URL}/api/cars/{car_id}")
        assert get_response.status_code == 404, "Deleted car should return 404"
        print(f"✓ DELETE /api/cars/{car_id} success and verified")

# ==================== BOOKING TESTS ====================

class TestBookings:
    """Booking endpoint tests"""

    def test_create_booking_authenticated(self, api_client, test_user_token):
        """Test POST /api/bookings (authenticated) - Create and verify"""
        token, email = test_user_token
        
        # Get a car first
        cars_response = api_client.get(f"{BASE_URL}/api/cars")
        cars = cars_response.json()
        assert len(cars) > 0, "Need at least one car"
        car_id = cars[0]["id"]
        
        booking_data = {
            "car_id": car_id,
            "pickup_date": "2024-12-20T10:00:00",
            "dropoff_date": "2024-12-25T10:00:00",
            "pickup_location": {"name": "Test Pickup", "lat": 40.7128, "lng": -74.0060},
            "dropoff_location": {"name": "Test Dropoff", "lat": 40.7580, "lng": -73.9855},
            "payment_method": "cash"
        }
        
        response = api_client.post(f"{BASE_URL}/api/bookings",
            headers={"Authorization": f"Bearer {token}"},
            json=booking_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        created_booking = response.json()
        assert "id" in created_booking, "Booking should have id"
        assert created_booking["car_id"] == car_id, "Car ID should match"
        assert created_booking["payment_method"] == "cash", "Payment method should match"
        assert created_booking["status"] == "confirmed", "Cash bookings should be confirmed"
        booking_id = created_booking["id"]
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/bookings/{booking_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert get_response.status_code == 200, "Created booking should be retrievable"
        retrieved_booking = get_response.json()
        assert retrieved_booking["car_id"] == car_id, "Retrieved booking car_id should match"
        print(f"✓ POST /api/bookings success and verified: {booking_id}")

    def test_get_bookings_authenticated(self, api_client, test_user_token):
        """Test GET /api/bookings (authenticated)"""
        token, email = test_user_token
        
        response = api_client.get(f"{BASE_URL}/api/bookings",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/bookings success: {len(data)} bookings")

    def test_get_bookings_unauthenticated(self, api_client):
        """Test GET /api/bookings without auth"""
        response = api_client.get(f"{BASE_URL}/api/bookings")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated booking request rejected")

# ==================== ADMIN TESTS ====================

class TestAdmin:
    """Admin endpoint tests"""

    def test_get_admin_stats(self, api_client, admin_token):
        """Test GET /api/admin/stats (admin only)"""
        response = api_client.get(f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_cars" in data, "Stats should include total_cars"
        assert "total_bookings" in data, "Stats should include total_bookings"
        assert "total_users" in data, "Stats should include total_users"
        assert "active_bookings" in data, "Stats should include active_bookings"
        print(f"✓ GET /api/admin/stats success: {data}")

    def test_get_admin_stats_non_admin(self, api_client, test_user_token):
        """Test GET /api/admin/stats as non-admin (should fail)"""
        token, _ = test_user_token
        response = api_client.get(f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Non-admin blocked from /api/admin/stats")
