// Centralized backend URL configuration.
//
// In development (running locally via Expo Go / Metro / web preview):
//   - Uses EXPO_PUBLIC_BACKEND_URL from .env (preview backend)
//   - Lets developers test safely without hitting production data
//
// In production builds (APK / iOS release / web prod build):
//   - Uses EXPO_PUBLIC_PROD_BACKEND_URL when defined at build time (recommended
//     for multi-tenant / per-deploy overrides — set it in the build env before
//     `eas build` or in the Emergent deployment env).
//   - Falls back to the hardcoded production host below for single-tenant
//     deployments where the build env var isn't set.
//
// __DEV__ is a React Native global: true in dev mode, false in release builds.

// Hardcoded fallback for the single-tenant production deployment. Override at
// build time via EXPO_PUBLIC_PROD_BACKEND_URL for per-environment deploys.
const DEFAULT_PRODUCTION_BACKEND_URL = 'https://rental-routes.emergent.host';

export const PRODUCTION_BACKEND_URL =
  process.env.EXPO_PUBLIC_PROD_BACKEND_URL || DEFAULT_PRODUCTION_BACKEND_URL;

export const BACKEND_URL: string =
  __DEV__
    ? (process.env.EXPO_PUBLIC_BACKEND_URL || PRODUCTION_BACKEND_URL)
    : PRODUCTION_BACKEND_URL;
