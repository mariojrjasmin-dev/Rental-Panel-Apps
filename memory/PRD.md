# Dams Car Rental - Product Requirements Document

## Overview
A modern car rental mobile app built with Expo React Native and FastAPI, allowing users to browse, book, and manage car rentals with integrated maps for pickup/dropoff navigation.

## Tech Stack
- **Frontend**: Expo SDK 54, React Native, Expo Router (file-based routing)
- **Backend**: FastAPI, MongoDB (Motor async driver)
- **Auth**: JWT + Emergent Google OAuth
- **Payments**: Stripe + Cash
- **Maps**: react-native-maps (native) / Google Maps web fallback

## Features

### Authentication
- JWT email/password registration and login
- Google OAuth social login (Emergent Auth)
- Admin account seeding
- Brute force protection (5 attempts, 15 min lockout)
- Secure password hashing with bcrypt

### Car Browsing
- Browse all available cars with images
- Search by name, brand, or model
- Filter by category (SUV, Sedan, Luxury, Electric, Sports)
- Pull-to-refresh

### Car Details
- Hero image with specs grid (seats, transmission, fuel)
- Pickup/dropoff locations with map links
- Book Now CTA

### Booking Flow
- Date selection (pickup + dropoff)
- Map view for locations with navigation buttons
- Payment method selection (Cash or Card/Stripe)
- Order summary with total calculation
- Stripe checkout integration
- Booking confirmation screen

### Maps Integration
- Native MapView with markers for pickup/dropoff (mobile)
- Google Maps link fallback (web)
- Open native maps app for turn-by-turn directions

### Bookings Management
- View all user bookings with status
- Booking cards showing car info, dates, payment method, total

### Admin Panel
- Dashboard stats (total cars, bookings, users, active)
- Full CRUD for car management
- Add/Edit/Delete cars with categories, pricing, images

### Profile
- User info display with admin badge
- Navigation to bookings and admin panel
- Logout with confirmation

## Database Collections
- `users` - User accounts
- `cars` - Car listings
- `bookings` - Rental bookings
- `payment_transactions` - Stripe payment records
- `login_attempts` - Brute force protection
- `user_sessions` - Google OAuth sessions

## API Endpoints
- Auth: /api/auth/* (register, login, logout, me, refresh, google/session)
- Cars: /api/cars/* (CRUD + search + categories)
- Bookings: /api/bookings/* (create, list, detail)
- Payments: /api/payments/* (checkout, status)
- Admin: /api/admin/stats
- Webhook: /api/webhook/stripe
