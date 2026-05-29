import { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';
import BrandLogo from '../../components/BrandLogo';
import { t } from '../../src/i18n';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import {
  isBiometricAvailable,
  isBiometricEnabled,
  authenticateWithBiometrics,
  enableBiometricLogin,
  type BiometricCheck,
} from '../../src/biometric';

// expo-apple-authentication is iOS-native-only. Importing it on web or
// Android would crash, so we lazy-resolve at call time.
const BACKEND_URL =
  (process.env.EXPO_PUBLIC_BACKEND_URL as string | undefined) ||
  (Constants?.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL as string | undefined) ||
  '';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [bioState, setBioState] = useState<BiometricCheck>({ available: false, enrolled: false, type: 'none' });
  const [bioReady, setBioReady] = useState(false); // user has previously enabled biometric
  const [appleAvailable, setAppleAvailable] = useState(false);
  const [appleSubmitting, setAppleSubmitting] = useState(false);
  const { login, locale } = useAuth();
  const router = useRouter();

  // Check if Sign In with Apple is supported. iOS 13+ device and
  // the expo-apple-authentication native module must be linked
  // (requires a custom dev/EAS build — not Expo Go).
  useEffect(() => {
    (async () => {
      if (Platform.OS !== 'ios') { setAppleAvailable(false); return; }
      try {
        const AA = await import('expo-apple-authentication');
        const ok = await AA.isAvailableAsync();
        setAppleAvailable(!!ok);
      } catch {
        setAppleAvailable(false);
      }
    })();
  }, []);

  const handleAppleSignIn = async () => {
    if (appleSubmitting) return;
    setError('');
    setAppleSubmitting(true);
    try {
      const AA = await import('expo-apple-authentication');
      const credential = await AA.signInAsync({
        requestedScopes: [
          AA.AppleAuthenticationScope.FULL_NAME,
          AA.AppleAuthenticationScope.EMAIL,
        ],
      });
      const identityToken = credential.identityToken;
      if (!identityToken) {
        setError(t('appleSignInError'));
        setAppleSubmitting(false);
        return;
      }
      // Apple gives the full name only on the FIRST sign-in. Concatenate
      // first + last when available so the backend can save it.
      const fullName = [credential.fullName?.givenName, credential.fullName?.familyName]
        .filter(Boolean).join(' ').trim() || undefined;

      const res = await fetch(`${BACKEND_URL}/api/auth/apple`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identity_token: identityToken,
          full_name: fullName,
          email: credential.email || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data?.token) {
        setError(data?.detail || t('appleSignInError'));
        setAppleSubmitting(false);
        return;
      }
      // Persist token + user — match the email-login flow exactly.
      await AsyncStorage.setItem('auth_token', data.token);
      await AsyncStorage.setItem('user', JSON.stringify({
        id: data.id, email: data.email, name: data.name,
        role: data.role || 'user', provider: data.provider || 'apple',
      }));
      // Route to the customer home tab.
      router.replace('/(tabs)/home');
    } catch (e: any) {
      const code = e?.code || '';
      if (code === 'ERR_REQUEST_CANCELED' || /cancel/i.test(String(e?.message))) {
        // Silent — user backed out of the Apple sheet.
        setAppleSubmitting(false);
        return;
      }
      console.log('Apple Sign In error:', e);
      setError(t('appleSignInError'));
    } finally {
      setAppleSubmitting(false);
    }
  };

  useEffect(() => {
    (async () => {
      const check = await isBiometricAvailable();
      setBioState(check);
      const enabled = await isBiometricEnabled();
      setBioReady(enabled);
    })();
  }, []);

  const offerBiometricEnable = (mail: string, pass: string) => {
    if (!bioState.available || !bioState.enrolled || Platform.OS === 'web') return;
    if (bioReady) return; // already enabled
    Alert.alert(
      t('enableBiometric'),
      t('enableBiometricSub'),
      [
        { text: t('notNow'), style: 'cancel' },
        {
          text: t('yes'),
          onPress: async () => {
            try {
              await enableBiometricLogin(mail, pass);
              setBioReady(true);
            } catch {}
          },
        },
      ]
    );
  };

  const handleLogin = async () => {
    if (!email || !password) { setError(t('fillAllFields')); return; }
    setLoading(true);
    setError('');
    try {
      await login(email, password);
      offerBiometricEnable(email, password);
      router.replace('/(tabs)/home');
    } catch (e: any) {
      setError(e.message || t('invalidLogin'));
    }
    setLoading(false);
  };

  const handleBiometricLogin = async () => {
    setError('');
    setLoading(true);
    try {
      const r = await authenticateWithBiometrics(t('biometricPrompt'));
      if (r.success && r.email && r.password) {
        await login(r.email, r.password);
        router.replace('/(tabs)/home');
      } else if (r.error && r.error !== 'cancelled') {
        setError(t('invalidLogin'));
      }
    } catch (e: any) {
      setError(e.message || t('invalidLogin'));
    }
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <BrandLogo size="large" variant="light" />
            <Text style={styles.subtitle}>{t('signInSub')}</Text>
          </View>

        <View style={styles.form}>
          {error ? <Text testID="login-error" style={styles.error}>{error}</Text> : null}
          
          <View style={styles.inputContainer}>
            <Ionicons name="mail-outline" size={20} color="#666" style={styles.inputIcon} />
            <TextInput
              testID="login-email-input"
              style={styles.input}
              placeholder={t('email')}
              placeholderTextColor="#999"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />
          </View>

          <View style={styles.inputContainer}>
            <Ionicons name="lock-closed-outline" size={20} color="#666" style={styles.inputIcon} />
            <TextInput
              testID="login-password-input"
              style={styles.input}
              placeholder={t('password')}
              placeholderTextColor="#999"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
            />
            <TouchableOpacity onPress={() => setShowPassword(!showPassword)} style={styles.eyeBtn}>
              <Ionicons name={showPassword ? "eye-outline" : "eye-off-outline"} size={20} color="#666" />
            </TouchableOpacity>
          </View>

          <TouchableOpacity testID="login-submit-button" style={styles.primaryBtn} onPress={handleLogin} disabled={loading} activeOpacity={0.7}>
            {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>{t('signIn')}</Text>}
          </TouchableOpacity>

          <TouchableOpacity
            testID="forgot-password-link"
            onPress={() => router.push('/(auth)/forgot-password')}
            style={styles.forgotBtn}
            activeOpacity={0.6}
          >
            <Text style={styles.forgotText}>{t('forgotPassword')}</Text>
          </TouchableOpacity>

          {bioReady && bioState.available && bioState.enrolled && Platform.OS !== 'web' && (
            <TouchableOpacity testID="biometric-login-btn" style={styles.bioBtn} onPress={handleBiometricLogin} disabled={loading} activeOpacity={0.7}>
              <Ionicons
                name={bioState.type === 'face' ? 'scan-outline' : 'finger-print'}
                size={22}
                color="#0A0A0A"
              />
              <Text style={styles.bioBtnText}>{t('signInWithBiometric')}</Text>
            </TouchableOpacity>
          )}

          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>{t('or').toLowerCase()}</Text>
            <View style={styles.dividerLine} />
          </View>

          <TouchableOpacity testID="google-login-button" style={styles.googleBtn} activeOpacity={0.7}
            onPress={() => {
              // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
              // Web-only: native builds (Android/iOS) don't have `window` and would crash on access.
              if (Platform.OS !== 'web') {
                Alert.alert(
                  t('continueWithGoogle'),
                  'Google Sign-In is currently available on the web version only. Please sign in with your email and password.'
                );
                return;
              }
              if (typeof window !== 'undefined') {
                const redirectUrl = window.location.origin + '/(tabs)/home';
                window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
              }
            }}
          >
            <Ionicons name="logo-google" size={20} color="#0A0A0A" />
            <Text style={styles.googleBtnText}>{t('continueWithGoogle')}</Text>
          </TouchableOpacity>

          {/* Apple Sign In — App Store guideline 4.8 requires it whenever
              another third-party auth (Google/Facebook) is offered. iOS-only;
              never shows on Android or web. */}
          {appleAvailable && (
            <TouchableOpacity
              testID="apple-login-button"
              style={styles.appleBtn}
              activeOpacity={0.85}
              onPress={handleAppleSignIn}
              disabled={appleSubmitting}
            >
              {appleSubmitting ? (
                <ActivityIndicator color="#FFF" size="small" />
              ) : (
                <>
                  <Ionicons name="logo-apple" size={20} color="#FFF" />
                  <Text style={styles.appleBtnText}>{t('continueWithApple')}</Text>
                </>
              )}
            </TouchableOpacity>
          )}

          <TouchableOpacity testID="go-to-register" onPress={() => router.push('/(auth)/register')} style={styles.linkBtn}>
            <Text style={styles.linkText}>{t('noAccountYet')} <Text style={styles.linkBold}>{t('signUp')}</Text></Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#FFFFFF' },
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 24, paddingVertical: 24 },
  header: { alignItems: 'center', marginBottom: 28 },
  subtitle: { fontSize: 15, color: '#666', marginTop: 12, textAlign: 'center' },
  form: { gap: 16 },
  error: { color: '#FF3B30', fontSize: 14, textAlign: 'center', backgroundColor: '#FFF0F0', padding: 12, borderRadius: 12 },
  inputContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 16, paddingHorizontal: 16, borderWidth: 1, borderColor: '#E5E5E5' },
  inputIcon: { marginRight: 12 },
  input: { flex: 1, fontSize: 16, color: '#0A0A0A', paddingVertical: 16 },
  eyeBtn: { padding: 4 },
  primaryBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  bioBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF', borderRadius: 50, paddingVertical: 14, borderWidth: 2, borderColor: '#0A0A0A', gap: 10, marginTop: 12 },
  bioBtnText: { color: '#0A0A0A', fontWeight: '700', fontSize: 15 },
  primaryBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  forgotBtn: { alignSelf: 'center', paddingVertical: 4, paddingHorizontal: 8 },
  forgotText: { fontSize: 14, fontWeight: '700', color: '#007AFF' },
  divider: { flexDirection: 'row', alignItems: 'center', marginVertical: 8 },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#E5E5E5' },
  dividerText: { marginHorizontal: 16, color: '#999', fontSize: 14 },
  googleBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#F5F5F5', borderRadius: 50, paddingVertical: 16, borderWidth: 1, borderColor: '#E5E5E5', gap: 10 },
  googleBtnText: { fontSize: 16, fontWeight: '600', color: '#0A0A0A' },
  // Apple's Human Interface Guidelines: solid black button with white SF Pro
  // text + the official Apple logo glyph. Same shape & padding as Google.
  appleBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#000000', borderRadius: 50, paddingVertical: 16, gap: 10, marginTop: 10 },
  appleBtnText: { fontSize: 16, fontWeight: '600', color: '#FFFFFF' },
  linkBtn: { alignItems: 'center', marginTop: 8 },
  linkText: { fontSize: 15, color: '#666' },
  linkBold: { color: '#FF3B30', fontWeight: '700' },
});
