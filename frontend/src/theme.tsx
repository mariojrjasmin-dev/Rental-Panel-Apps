// Mobile app theme system — light + dark palettes with AsyncStorage persistence.
// Default: light. User can toggle via the moon/sun icon on the Profile screen.
//
// Usage:
//   import { useTheme } from '../src/theme';
//   const { colors, isDark, toggle } = useTheme();
//   <View style={{ backgroundColor: colors.bg }}>...
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';

export type Palette = {
  // Surfaces
  bg: string;            // app background
  bgElevated: string;    // cards / modals
  bgSubtle: string;      // section backgrounds, hover, dividers
  // Text
  text: string;
  textMuted: string;
  textSubtle: string;
  // Borders
  border: string;
  borderStrong: string;
  // Brand & semantic colors (same red across both themes)
  brand: string;
  brandSoft: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
  // Tab bar / status bar
  tabBg: string;
  tabInactive: string;
  statusBar: 'light' | 'dark';
};

export const LIGHT: Palette = {
  bg: '#F5F5F7',
  bgElevated: '#FFFFFF',
  bgSubtle: '#FAFAFA',
  text: '#0A0A0A',
  textMuted: '#666666',
  textSubtle: '#999999',
  border: '#E5E5E5',
  borderStrong: '#D1D5DB',
  brand: '#FF3B30',
  brandSoft: '#FFE9E8',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  info: '#3B82F6',
  tabBg: '#FFFFFF',
  tabInactive: '#999999',
  statusBar: 'dark',
};

export const DARK: Palette = {
  bg: '#0B0D12',
  bgElevated: '#14171D',
  bgSubtle: '#1A1E25',
  text: '#F5F5F7',
  textMuted: '#A4A8B3',
  textSubtle: '#71757F',
  border: '#242932',
  borderStrong: '#2F3540',
  brand: '#FF453A',
  brandSoft: 'rgba(255,69,58,0.16)',
  success: '#34D399',
  warning: '#FBBF24',
  danger: '#F87171',
  info: '#60A5FA',
  tabBg: '#14171D',
  tabInactive: '#71757F',
  statusBar: 'light',
};

type ThemeCtx = {
  isDark: boolean;
  colors: Palette;
  toggle: () => void;
  setTheme: (t: 'light' | 'dark') => void;
};

const ThemeContext = createContext<ThemeCtx>({
  isDark: false,
  colors: LIGHT,
  toggle: () => {},
  setTheme: () => {},
});

const STORAGE_KEY = 'app_theme';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [isDark, setIsDark] = useState(false); // default = light

  // Load persisted preference on mount
  useEffect(() => {
    (async () => {
      try {
        const saved = await AsyncStorage.getItem(STORAGE_KEY);
        if (saved === 'dark') setIsDark(true);
        else if (saved === 'light') setIsDark(false);
      } catch (_e) {
        // ignore — keep default light
      }
    })();
  }, []);

  const setTheme = useCallback((t: 'light' | 'dark') => {
    setIsDark(t === 'dark');
    AsyncStorage.setItem(STORAGE_KEY, t).catch(() => {});
  }, []);

  const toggle = useCallback(() => {
    setIsDark(prev => {
      const next = !prev;
      AsyncStorage.setItem(STORAGE_KEY, next ? 'dark' : 'light').catch(() => {});
      return next;
    });
  }, []);

  const colors = isDark ? DARK : LIGHT;
  const value = useMemo(() => ({ isDark, colors, toggle, setTheme }), [isDark, colors, toggle, setTheme]);

  return (
    <ThemeContext.Provider value={value}>
      <StatusBar style={colors.statusBar} />
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
