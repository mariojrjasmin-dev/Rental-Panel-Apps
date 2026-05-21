import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState, createContext, useContext } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { loadSavedLocale, setLocale as persistLocale, AppLocale } from '../src/i18n';
import {
  setupNotificationHandler,
  registerForPushNotifications,
  unregisterPushToken,
} from '../src/notifications';

import { BACKEND_URL } from '../src/config';

export type User = {
  id?: string;
  user_id?: string;
  email: string;
  name: string;
  role?: string;
  token?: string;
  session_token?: string;
  picture?: string;
};

type AuthContextType = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User | null) => void;
  locale: AppLocale;
  changeLocale: (l: AppLocale) => Promise<void>;
};

export const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
  setUser: () => {},
  locale: 'en',
  changeLocale: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export default function RootLayout() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [locale, setLocaleState] = useState<AppLocale>('en');

  useEffect(() => {
    setupNotificationHandler();
    (async () => {
      const lang = await loadSavedLocale();
      setLocaleState(lang);
      checkAuth();
    })();
  }, []);

  // Re-register for push whenever user becomes logged in
  useEffect(() => {
    if (user?.token) {
      registerForPushNotifications().catch(() => {});
    }
  }, [user?.token]);

  const changeLocale = async (l: AppLocale) => {
    await persistLocale(l);
    setLocaleState(l);
  };

  const checkAuth = async () => {
    try {
      const token = await AsyncStorage.getItem('auth_token');
      if (!token) { setLoading(false); return; }
      const res = await fetch(`${BACKEND_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser({ ...data, token });
      } else {
        await AsyncStorage.removeItem('auth_token');
      }
    } catch (e) {
      console.log('Auth check failed:', e);
    }
    setLoading(false);
  };

  const login = async (email: string, password: string) => {
    const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(typeof err.detail === 'string' ? err.detail : 'Login failed');
    }
    const data = await res.json();
    await AsyncStorage.setItem('auth_token', data.token);
    setUser(data);
  };

  const register = async (name: string, email: string, password: string) => {
    const res = await fetch(`${BACKEND_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(typeof err.detail === 'string' ? err.detail : 'Registration failed');
    }
    const data = await res.json();
    await AsyncStorage.setItem('auth_token', data.token);
    setUser(data);
  };

  const logout = async () => {
    try {
      const token = await AsyncStorage.getItem('auth_token');
      // Unregister this device from receiving push notifications first
      try { await unregisterPushToken(); } catch {}
      await fetch(`${BACKEND_URL}/api/auth/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
    } catch (e) {}
    await AsyncStorage.removeItem('auth_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, setUser, locale, changeLocale }}>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="car-detail" options={{ headerShown: false }} />
        <Stack.Screen name="booking" options={{ headerShown: false }} />
        <Stack.Screen name="booking-success" options={{ headerShown: false }} />
        <Stack.Screen name="map-view" options={{ headerShown: false }} />
        <Stack.Screen name="admin" options={{ headerShown: false }} />
        <Stack.Screen name="admin-locations" options={{ headerShown: false }} />
      </Stack>
    </AuthContext.Provider>
  );
}
