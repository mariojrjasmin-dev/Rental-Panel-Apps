// Push notification helper using expo-notifications.
//
// Usage (typically called once after login):
//   import { registerForPushNotifications, setupNotificationHandler } from '../src/notifications';
//   setupNotificationHandler();
//   await registerForPushNotifications();
//
// Notes:
//  - Works only on physical devices (Expo Go on real phones, or release builds).
//  - Silently no-ops on web or simulators where push is unavailable.
//  - Persists the token in AsyncStorage so we don't re-send unnecessarily.

import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { BACKEND_URL } from './config';

const STORAGE_KEY = 'expo_push_token';

/** Configure how foreground notifications are displayed. */
export function setupNotificationHandler() {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

/** Request permission and register the device's Expo push token with the backend. */
export async function registerForPushNotifications(): Promise<string | null> {
  // Skip on web entirely
  if (Platform.OS === 'web') return null;
  // Skip on simulators
  if (!Device.isDevice) {
    console.log('Push notifications skipped: not a physical device');
    return null;
  }

  try {
    // Android requires an explicit notification channel
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'default',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#FF3B30',
      });
    }

    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== 'granted') {
      const req = await Notifications.requestPermissionsAsync();
      status = req.status;
    }
    if (status !== 'granted') {
      console.log('Push notification permission not granted');
      return null;
    }

    const projectId =
      (Constants?.expoConfig as any)?.extra?.eas?.projectId ||
      (Constants as any)?.easConfig?.projectId;
    const tokenResp = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    const token = tokenResp.data;
    if (!token) return null;

    // Send to backend (avoid resending the same token)
    const lastSent = await AsyncStorage.getItem(STORAGE_KEY);
    if (lastSent !== token) {
      const authToken = await AsyncStorage.getItem('auth_token');
      if (authToken) {
        try {
          await fetch(`${BACKEND_URL}/api/users/push-token`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${authToken}`,
            },
            body: JSON.stringify({ token, platform: Platform.OS }),
          });
          await AsyncStorage.setItem(STORAGE_KEY, token);
        } catch (e) {
          console.log('Failed to register push token:', e);
        }
      }
    }
    return token;
  } catch (e) {
    console.log('registerForPushNotifications error:', e);
    return null;
  }
}

/** Optionally remove the token (e.g., on logout) so the server stops sending to this device. */
export async function unregisterPushToken(): Promise<void> {
  try {
    if (Platform.OS === 'web') return;
    const token = await AsyncStorage.getItem(STORAGE_KEY);
    const authToken = await AsyncStorage.getItem('auth_token');
    if (!token || !authToken) return;
    await fetch(`${BACKEND_URL}/api/users/push-token`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ token }),
    });
    await AsyncStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    console.log('unregisterPushToken error:', e);
  }
}
