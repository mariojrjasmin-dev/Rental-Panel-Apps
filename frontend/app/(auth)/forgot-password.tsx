import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import BrandLogo from '../../components/BrandLogo';
import { BACKEND_URL } from '../../src/config';

type Step = 'request' | 'verify';

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('request');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  const handleRequest = async () => {
    const e = (email || '').trim().toLowerCase();
    if (!e || !e.includes('@')) { setError('Please enter a valid email address.'); return; }
    setError(''); setInfo(''); setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: e }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || 'Could not send the reset code. Please try again.');
      } else {
        setInfo(data?.message || 'If an account exists for this email, a reset code has been sent.');
        setEmail(e);
        setStep('verify');
      }
    } catch (err: any) {
      setError(err?.message || 'Network error. Please try again.');
    }
    setLoading(false);
  };

  const handleReset = async () => {
    if (!code || code.length !== 6 || !/^\d{6}$/.test(code)) { setError('Enter the 6-digit code we emailed you.'); return; }
    if (!newPwd || newPwd.length < 6) { setError('Password must be at least 6 characters.'); return; }
    if (newPwd !== confirmPwd) { setError('Passwords do not match.'); return; }
    setError(''); setInfo(''); setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code, new_password: newPwd }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || 'Could not reset password. Please try again.');
      } else {
        Alert.alert('Password updated', 'Your password has been changed. Please sign in with your new password.', [
          { text: 'Sign in', onPress: () => router.replace('/(auth)/login') },
        ]);
      }
    } catch (err: any) {
      setError(err?.message || 'Network error. Please try again.');
    }
    setLoading(false);
  };

  const handleResend = async () => {
    setError(''); setInfo('');
    if (!email) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (res.ok) setInfo('A new code has been sent. Check your email.');
      else setError(data?.detail || 'Could not resend.');
    } catch (err: any) { setError(err?.message || 'Network error.'); }
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.topBar}>
            <TouchableOpacity testID="forgot-back-btn" onPress={() => router.back()} style={styles.backBtn}>
              <Ionicons name="arrow-back" size={22} color="#0A0A0A" />
            </TouchableOpacity>
          </View>

          <View style={styles.header}>
            <BrandLogo size="large" />
            <Text style={styles.title}>{step === 'request' ? 'Forgot password?' : 'Enter reset code'}</Text>
            <Text style={styles.subtitle}>
              {step === 'request'
                ? "Enter your email and we'll send you a 6-digit code to reset your password."
                : `We sent a code to ${email}. Enter it below along with your new password.`}
            </Text>
          </View>

          <View style={styles.form}>
            {error ? <Text testID="forgot-error" style={styles.error}>{error}</Text> : null}
            {info && !error ? <Text testID="forgot-info" style={styles.info}>{info}</Text> : null}

            {step === 'request' ? (
              <>
                <View style={styles.inputContainer}>
                  <Ionicons name="mail-outline" size={20} color="#666" style={styles.inputIcon} />
                  <TextInput
                    testID="forgot-email-input"
                    style={styles.input}
                    placeholder="Email"
                    placeholderTextColor="#999"
                    value={email}
                    onChangeText={(v) => { setEmail(v); if (error) setError(''); }}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoComplete="email"
                  />
                </View>
                <TouchableOpacity
                  testID="forgot-request-btn"
                  style={[styles.primaryBtn, loading && styles.primaryBtnDisabled]}
                  onPress={handleRequest}
                  disabled={loading}
                  activeOpacity={0.7}
                >
                  {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>Send reset code</Text>}
                </TouchableOpacity>
              </>
            ) : (
              <>
                <View style={styles.inputContainer}>
                  <Ionicons name="keypad-outline" size={20} color="#666" style={styles.inputIcon} />
                  <TextInput
                    testID="forgot-code-input"
                    style={[styles.input, styles.codeInput]}
                    placeholder="6-digit code"
                    placeholderTextColor="#999"
                    value={code}
                    onChangeText={(v) => { setCode(v.replace(/[^0-9]/g, '').slice(0, 6)); if (error) setError(''); }}
                    keyboardType="number-pad"
                    maxLength={6}
                    autoComplete="one-time-code"
                  />
                </View>
                <View style={styles.inputContainer}>
                  <Ionicons name="lock-closed-outline" size={20} color="#666" style={styles.inputIcon} />
                  <TextInput
                    testID="forgot-newpwd-input"
                    style={styles.input}
                    placeholder="New password (min 6 chars)"
                    placeholderTextColor="#999"
                    value={newPwd}
                    onChangeText={(v) => { setNewPwd(v); if (error) setError(''); }}
                    secureTextEntry={!showPwd}
                  />
                  <TouchableOpacity onPress={() => setShowPwd(!showPwd)} style={styles.eyeBtn}>
                    <Ionicons name={showPwd ? 'eye-outline' : 'eye-off-outline'} size={20} color="#666" />
                  </TouchableOpacity>
                </View>
                <View style={styles.inputContainer}>
                  <Ionicons name="lock-closed-outline" size={20} color="#666" style={styles.inputIcon} />
                  <TextInput
                    testID="forgot-confirmpwd-input"
                    style={styles.input}
                    placeholder="Confirm new password"
                    placeholderTextColor="#999"
                    value={confirmPwd}
                    onChangeText={(v) => { setConfirmPwd(v); if (error) setError(''); }}
                    secureTextEntry={!showPwd}
                  />
                </View>

                <TouchableOpacity
                  testID="forgot-reset-btn"
                  style={[styles.primaryBtn, loading && styles.primaryBtnDisabled]}
                  onPress={handleReset}
                  disabled={loading}
                  activeOpacity={0.7}
                >
                  {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>Reset password</Text>}
                </TouchableOpacity>

                <View style={styles.resendRow}>
                  <Text style={styles.resendText}>Didn't get the code? </Text>
                  <TouchableOpacity testID="forgot-resend-btn" onPress={handleResend} disabled={loading}>
                    <Text style={styles.resendLink}>Resend</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}

            <TouchableOpacity testID="forgot-back-to-login" onPress={() => router.replace('/(auth)/login')} style={styles.linkBtn}>
              <Text style={styles.linkText}>Remember your password? <Text style={styles.linkBold}>Sign In</Text></Text>
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
  scroll: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 24, paddingBottom: 24 },
  topBar: { position: 'absolute', top: 12, left: 16 },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#F5F5F5', alignItems: 'center', justifyContent: 'center' },
  header: { alignItems: 'center', marginBottom: 24, marginTop: 12 },
  title: { fontSize: 26, fontWeight: '900', color: '#0A0A0A', marginTop: 20, textAlign: 'center' },
  subtitle: { fontSize: 14, color: '#666', marginTop: 8, textAlign: 'center', paddingHorizontal: 12, lineHeight: 20 },
  form: { gap: 14 },
  error: { color: '#FF3B30', fontSize: 13, textAlign: 'center', backgroundColor: '#FFF0F0', padding: 12, borderRadius: 12, fontWeight: '600' },
  info: { color: '#0a5d2b', fontSize: 13, textAlign: 'center', backgroundColor: '#e6f9ed', padding: 12, borderRadius: 12, fontWeight: '600' },
  inputContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 16, paddingHorizontal: 16, borderWidth: 1, borderColor: '#E5E5E5' },
  inputIcon: { marginRight: 12 },
  input: { flex: 1, fontSize: 16, color: '#0A0A0A', paddingVertical: 16 },
  codeInput: { letterSpacing: 6, fontSize: 20, fontWeight: '800' },
  eyeBtn: { padding: 4 },
  primaryBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  primaryBtnDisabled: { backgroundColor: '#C7C7CC' },
  primaryBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  linkBtn: { alignItems: 'center', marginTop: 8 },
  linkText: { fontSize: 14, color: '#666' },
  linkBold: { color: '#FF3B30', fontWeight: '700' },
  resendRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 4 },
  resendText: { fontSize: 13, color: '#666' },
  resendLink: { fontSize: 13, fontWeight: '800', color: '#FF3B30' },
});
