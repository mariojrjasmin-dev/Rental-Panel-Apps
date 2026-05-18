// Centralized backend URL configuration.
//
// In development (running locally via Expo Go / Metro / web preview):
//   - Uses EXPO_PUBLIC_BACKEND_URL from .env (preview backend)
//   - Lets developers test safely without hitting production data
//
// In production builds (APK / iOS release / web prod build):
//   - Automatically uses the production backend
//   - APK end-users always hit the production admin panel / DB
//
// __DEV__ is a React Native global: true in dev mode, false in release builds.

export const PRODUCTION_BACKEND_URL = 'https://rental-routes.emergent.host';

export const BACKEND_URL: string =
  __DEV__
    ? (process.env.EXPO_PUBLIC_BACKEND_URL || PRODUCTION_BACKEND_URL)
    : PRODUCTION_BACKEND_URL;
