import { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';
import BrandLogo from '../../components/BrandLogo';
import { t } from '../../src/i18n';
import {
  isBiometricAvailable,
  isBiometricEnabled,
  authenticateWithBiometrics,
  enableBiometricLogin,
  type BiometricCheck,
} from '../../src/biometric';

// NOTE: Apple Sign-In and Google Sign-In were intentionally removed from the
// UI to simplify the login flow and avoid third-party-auth maintenance.
// Backend `/api/auth/apple` and Google endpoints remain available (dormant)
// so previously-linked accounts can be re-enabled later if needed. SSO
// users from earlier builds were migrated via the password-reset flow.

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [bioState, setBioState] = useState<BiometricCheck>({ available: false, enrolled: false, type: 'none' });
  const [bioReady, setBioReady] = useState(false); // user has previously enabled biometric
  const { login, locale } = useAuth();
  const router = useRouter();

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
  linkBtn: { alignItems: 'center', marginTop: 8 },
  linkText: { fontSize: 15, color: '#666' },
  linkBold: { color: '#FF3B30', fontWeight: '700' },
});
