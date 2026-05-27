import { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator, Modal } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';
import BrandLogo from '../../components/BrandLogo';
import { BACKEND_URL } from '../../src/config';

export default function RegisterScreen() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [adultConfirmed, setAdultConfirmed] = useState(false);
  const [termsModalVisible, setTermsModalVisible] = useState(false);
  const [termsText, setTermsText] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  // Load Terms once for the modal viewer
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/settings/rental-terms`);
        if (r.ok) {
          const data = await r.json();
          setTermsText(data?.terms || '');
        }
      } catch { /* ignore */ }
    })();
  }, []);

  const handleRegister = async () => {
    if (!name || !email || !password) { setError('Please fill all fields.'); return; }
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return; }
    if (!adultConfirmed) { setError('You must confirm you are 18 years or older to register.'); return; }
    if (!termsAccepted) { setError('Please accept the Rental Terms & Conditions to continue.'); return; }
    setLoading(true);
    setError('');
    try {
      await register(name.trim(), email.trim().toLowerCase(), password, true, true);
      router.replace('/(tabs)/home');
    } catch (e: any) {
      setError(e.message || 'Registration failed');
    }
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <BrandLogo size="large" />
            <Text style={styles.subtitle}>Create your account</Text>
          </View>

          <View style={styles.form}>
            {error ? <Text testID="register-error" style={styles.error}>{error}</Text> : null}

            <View style={styles.inputContainer}>
              <Ionicons name="person-outline" size={20} color="#666" style={styles.inputIcon} />
              <TextInput testID="register-name-input" style={styles.input} placeholder="Full Name" placeholderTextColor="#999" value={name} onChangeText={setName} />
            </View>

            <View style={styles.inputContainer}>
              <Ionicons name="mail-outline" size={20} color="#666" style={styles.inputIcon} />
              <TextInput testID="register-email-input" style={styles.input} placeholder="Email" placeholderTextColor="#999" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" autoComplete="email" />
            </View>

            <View style={styles.inputContainer}>
              <Ionicons name="lock-closed-outline" size={20} color="#666" style={styles.inputIcon} />
              <TextInput testID="register-password-input" style={styles.input} placeholder="Password (min 6 chars)" placeholderTextColor="#999" value={password} onChangeText={setPassword} secureTextEntry={!showPwd} />
              <TouchableOpacity onPress={() => setShowPwd(!showPwd)} style={styles.eyeBtn}>
                <Ionicons name={showPwd ? 'eye-outline' : 'eye-off-outline'} size={20} color="#666" />
              </TouchableOpacity>
            </View>

            {/* Adult (18+) confirmation — required for car rental */}
            <TouchableOpacity
              testID="register-adult-toggle"
              activeOpacity={0.7}
              style={styles.termsRow}
              onPress={() => setAdultConfirmed(!adultConfirmed)}
            >
              <View style={[styles.termsBox, adultConfirmed && styles.termsBoxChecked]}>
                {adultConfirmed && <Ionicons name="checkmark" size={16} color="#FFF" />}
              </View>
              <Text style={styles.termsLabel}>
                I confirm that I am <Text style={{ fontWeight: '800' }}>18 years or older</Text> and legally able to enter a rental agreement.
              </Text>
            </TouchableOpacity>

            {/* Terms & Conditions checkbox (required for store compliance & legal proof) */}
            <TouchableOpacity
              testID="register-terms-toggle"
              activeOpacity={0.7}
              style={styles.termsRow}
              onPress={() => setTermsAccepted(!termsAccepted)}
            >
              <View style={[styles.termsBox, termsAccepted && styles.termsBoxChecked]}>
                {termsAccepted && <Ionicons name="checkmark" size={16} color="#FFF" />}
              </View>
              <Text style={styles.termsLabel}>
                I have read and accept the{' '}
                <Text
                  style={styles.termsLink}
                  onPress={(e: any) => { e?.stopPropagation && e.stopPropagation(); setTermsModalVisible(true); }}
                >
                  Rental Terms &amp; Conditions
                </Text>
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              testID="register-submit-button"
              style={[styles.primaryBtn, (!termsAccepted || !adultConfirmed || loading) && styles.primaryBtnDisabled]}
              onPress={handleRegister}
              disabled={loading || !termsAccepted || !adultConfirmed}
              activeOpacity={0.7}
            >
              {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>{(!termsAccepted || !adultConfirmed) ? 'Confirm details above to continue' : 'Create Account'}</Text>}
            </TouchableOpacity>

            <TouchableOpacity testID="go-to-login" onPress={() => router.push('/(auth)/login')} style={styles.linkBtn}>
              <Text style={styles.linkText}>Already have an account? <Text style={styles.linkBold}>Sign In</Text></Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Terms & Conditions modal */}
      <Modal
        visible={termsModalVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setTermsModalVisible(false)}
      >
        <SafeAreaView style={styles.modalContainer} edges={['top']}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>📜 Rental Terms &amp; Conditions</Text>
            <TouchableOpacity onPress={() => setTermsModalVisible(false)} style={styles.modalCloseBtn}>
              <Ionicons name="close" size={24} color="#0A0A0A" />
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.modalScroll} contentContainerStyle={{ padding: 20 }}>
            <Text style={styles.modalBody}>{termsText || 'Loading rental terms…'}</Text>
          </ScrollView>
          <View style={styles.modalFooter}>
            <TouchableOpacity style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setTermsModalVisible(false)}>
              <Text style={styles.modalBtnGhostText}>Close</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="register-terms-accept-btn"
              style={[styles.modalBtn, styles.modalBtnPrimary]}
              onPress={() => { setTermsAccepted(true); setTermsModalVisible(false); }}
            >
              <Text style={styles.modalBtnPrimaryText}>I Accept</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#FFFFFF' },
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 24, paddingVertical: 24 },
  header: { alignItems: 'center', marginBottom: 28 },
  subtitle: { fontSize: 15, color: '#666', marginTop: 12 },
  form: { gap: 14 },
  error: { color: '#FF3B30', fontSize: 13, textAlign: 'center', backgroundColor: '#FFF0F0', padding: 12, borderRadius: 12, fontWeight: '600' },
  inputContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 16, paddingHorizontal: 16, borderWidth: 1, borderColor: '#E5E5E5' },
  inputIcon: { marginRight: 12 },
  input: { flex: 1, fontSize: 16, color: '#0A0A0A', paddingVertical: 16 },
  eyeBtn: { padding: 4 },
  termsRow: { flexDirection: 'row', alignItems: 'flex-start', marginTop: 4, paddingHorizontal: 4 },
  termsBox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: '#999', alignItems: 'center', justifyContent: 'center', marginRight: 10, backgroundColor: '#FFF', marginTop: 1 },
  termsBoxChecked: { backgroundColor: '#FF3B30', borderColor: '#FF3B30' },
  termsLabel: { flex: 1, fontSize: 13, color: '#333', fontWeight: '600', lineHeight: 18 },
  termsLink: { color: '#007AFF', textDecorationLine: 'underline', fontWeight: '700' },
  primaryBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  primaryBtnDisabled: { backgroundColor: '#C7C7CC' },
  primaryBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  linkBtn: { alignItems: 'center', marginTop: 8 },
  linkText: { fontSize: 14, color: '#666' },
  linkBold: { color: '#FF3B30', fontWeight: '700' },
  modalContainer: { flex: 1, backgroundColor: '#FFF' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#E5E5E5' },
  modalTitle: { fontSize: 17, fontWeight: '800', color: '#0A0A0A', flex: 1 },
  modalCloseBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F5F5F5' },
  modalScroll: { flex: 1 },
  modalBody: { fontSize: 13, color: '#333', lineHeight: 20 },
  modalFooter: { flexDirection: 'row', gap: 10, padding: 16, borderTopWidth: 1, borderTopColor: '#E5E5E5', paddingBottom: 24 },
  modalBtn: { flex: 1, paddingVertical: 14, borderRadius: 50, alignItems: 'center', justifyContent: 'center' },
  modalBtnGhost: { backgroundColor: '#F5F5F5' },
  modalBtnGhostText: { color: '#0A0A0A', fontSize: 15, fontWeight: '700' },
  modalBtnPrimary: { backgroundColor: '#FF3B30' },
  modalBtnPrimaryText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
});
