/**
 * Biometric authentication helpers.
 *
 * - Wraps expo-local-authentication + expo-secure-store.
 * - Stores credentials in the device keychain so we can re-login after a
 *   successful biometric prompt.
 * - Falls back gracefully on web (where biometrics are unavailable) and on
 *   devices without enrolled biometrics — callers should always check
 *   `isBiometricAvailable()` before showing the biometric UI.
 */
import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const KEY_EMAIL = 'bio_email';
const KEY_PASSWORD = 'bio_password';
const KEY_ENABLED = 'bio_enabled';

export type BiometricCheck = {
  available: boolean;
  enrolled: boolean;
  type: 'face' | 'fingerprint' | 'iris' | 'unknown' | 'none';
};

export async function isBiometricAvailable(): Promise<BiometricCheck> {
  if (Platform.OS === 'web') {
    // Test-only escape hatch: when running in a browser with the flag set,
    // simulate Face ID hardware so the Profile toggle + password modal can be
    // verified end-to-end by the automated UI testing agent.
    // Has no effect on production native builds.
    try {
      if (typeof window !== 'undefined' && window.localStorage?.getItem('__bio_test') === '1') {
        return { available: true, enrolled: true, type: 'face' };
      }
    } catch {}
    return { available: false, enrolled: false, type: 'none' };
  }
  try {
    const hardware = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    const supported = await LocalAuthentication.supportedAuthenticationTypesAsync();
    let type: BiometricCheck['type'] = 'unknown';
    if (supported.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) type = 'face';
    else if (supported.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) type = 'fingerprint';
    else if (supported.includes(LocalAuthentication.AuthenticationType.IRIS)) type = 'iris';
    return { available: hardware, enrolled, type };
  } catch {
    return { available: false, enrolled: false, type: 'none' };
  }
}

export async function isBiometricEnabled(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  try {
    const v = await SecureStore.getItemAsync(KEY_ENABLED);
    return v === '1';
  } catch {
    return false;
  }
}

export async function enableBiometricLogin(email: string, password: string): Promise<void> {
  if (Platform.OS === 'web') return;
  await SecureStore.setItemAsync(KEY_EMAIL, email);
  await SecureStore.setItemAsync(KEY_PASSWORD, password);
  await SecureStore.setItemAsync(KEY_ENABLED, '1');
}

export async function disableBiometricLogin(): Promise<void> {
  if (Platform.OS === 'web') return;
  await Promise.all([
    SecureStore.deleteItemAsync(KEY_EMAIL).catch(() => {}),
    SecureStore.deleteItemAsync(KEY_PASSWORD).catch(() => {}),
    SecureStore.deleteItemAsync(KEY_ENABLED).catch(() => {}),
  ]);
}

export async function authenticateWithBiometrics(reason: string): Promise<{
  success: boolean;
  email?: string;
  password?: string;
  error?: string;
}> {
  if (Platform.OS === 'web') {
    return { success: false, error: 'Not available on web' };
  }
  const result = await LocalAuthentication.authenticateAsync({
    promptMessage: reason,
    cancelLabel: 'Cancel',
    disableDeviceFallback: false,
  });
  if (!result.success) {
    return { success: false, error: (result as any).error || 'cancelled' };
  }
  const email = await SecureStore.getItemAsync(KEY_EMAIL);
  const password = await SecureStore.getItemAsync(KEY_PASSWORD);
  if (!email || !password) {
    return { success: false, error: 'no_stored_credentials' };
  }
  return { success: true, email, password };
}
