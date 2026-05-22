import { useState, useCallback, useEffect, useContext } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator, Platform, Switch, ScrollView, Modal, TextInput, Alert, KeyboardAvoidingView } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { BottomTabBarHeightContext } from '@react-navigation/bottom-tabs';
import { useAuth } from '../_layout';
import { t } from '../../src/i18n';
import { isBiometricAvailable, isBiometricEnabled, disableBiometricLogin, enableBiometricLogin, type BiometricCheck } from '../../src/biometric';
import { BACKEND_URL } from '../../src/config';
import LegalLinks from '../../components/LegalLinks';

export default function ProfileScreen() {
  const { user, logout, locale, changeLocale } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  // Safer than useBottomTabBarHeight() which throws on web / non-tab screens.
  // Falls back to a sane default that matches the iOS tab bar + home indicator.
  const tabBarHeight = useContext(BottomTabBarHeightContext) ?? (64 + (insets.bottom || 0));
  const bottomPad = tabBarHeight + 32;
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [bioState, setBioState] = useState<BiometricCheck>({ available: false, enrolled: false, type: 'none' });
  const [bioEnabled, setBioEnabled] = useState(false);
  // Password-confirm modal state (used to enable biometric from Profile)
  const [pwdModalVisible, setPwdModalVisible] = useState(false);
  const [pwdInput, setPwdInput] = useState('');
  const [pwdError, setPwdError] = useState('');
  const [pwdSubmitting, setPwdSubmitting] = useState(false);

  // Resolve type-specific labels & icon — Face ID / Touch ID / Fingerprint
  const bioMeta = (() => {
    if (bioState.type === 'face') {
      // On iOS this is Face ID. On Android with face unlock it's a generic facial.
      const isApple = Platform.OS === 'ios';
      return {
        title: isApple ? t('faceIdTitle') : t('biometricGenericTitle'),
        subOn: t('biometricOnFace'),
        subOff: t('biometricEnableSubFace'),
        icon: 'scan-outline' as const,
        accent: '#0a84ff',
      };
    }
    if (bioState.type === 'fingerprint') {
      const isApple = Platform.OS === 'ios';
      return {
        title: isApple ? t('touchIdTitle') : t('fingerprintTitle'),
        subOn: isApple ? t('biometricOnTouch') : t('biometricOnFinger'),
        subOff: isApple ? t('biometricEnableSubTouch') : t('biometricEnableSubFinger'),
        icon: 'finger-print' as const,
        accent: '#34c759',
      };
    }
    return {
      title: t('biometricGenericTitle'),
      subOn: t('biometricEnabled'),
      subOff: t('enableBiometricSub'),
      icon: 'lock-closed-outline' as const,
      accent: '#666',
    };
  })();

  useEffect(() => {
    (async () => {
      setBioState(await isBiometricAvailable());
      setBioEnabled(await isBiometricEnabled());
    })();
  }, []);

  const askPasswordToEnable = useCallback(() => {
    if (!bioState.available || !bioState.enrolled) {
      Alert.alert(t('biometricUnenrolledTitle'), t('biometricNotEnrolled'));
      return;
    }
    setPwdError('');
    setPwdInput('');
    setPwdModalVisible(true);
  }, [bioState.available, bioState.enrolled]);

  const submitPasswordToEnable = useCallback(async () => {
    if (!user?.email) { setPwdError(t('wrongPassword')); return; }
    if (!pwdInput.trim()) { setPwdError(t('wrongPassword')); return; }
    setPwdSubmitting(true);
    setPwdError('');
    try {
      // Re-verify password by calling /api/auth/login. If 200, the password is correct.
      const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, password: pwdInput }),
      });
      if (!res.ok) {
        setPwdError(t('wrongPassword'));
        setPwdSubmitting(false);
        return;
      }
      // Persist credentials in SecureStore for future biometric unlock.
      await enableBiometricLogin(user.email, pwdInput);
      setBioEnabled(true);
      setPwdModalVisible(false);
      setPwdInput('');
      Alert.alert(bioMeta.title, t('biometricEnableSuccess'));
    } catch (e: any) {
      setPwdError(t('wrongPassword'));
    }
    setPwdSubmitting(false);
  }, [user?.email, pwdInput, bioMeta.title]);

  const toggleBiometric = useCallback(async (val: boolean) => {
    if (val) {
      // Enabling — require password confirmation.
      askPasswordToEnable();
      return;
    }
    // Disabling — clear stored credentials immediately.
    await disableBiometricLogin();
    setBioEnabled(false);
  }, [askPasswordToEnable]);

  const doLogout = useCallback(async () => {
    setLoggingOut(true);
    try {
      await logout();
      router.replace('/(auth)/login');
    } catch (e) {
      console.log('Logout error:', e);
      setLoggingOut(false);
    }
  }, [logout, router]);

  const showConfirm = useCallback(() => {
    setConfirmLogout(true);
  }, []);

  const hideConfirm = useCallback(() => {
    setConfirmLogout(false);
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[styles.content, { paddingBottom: bottomPad }]}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>{t('profile')}</Text>

        <View style={styles.profileCard}>
          <View style={styles.avatarCircle}>
            <Ionicons name="person" size={40} color="#FFF" />
          </View>
          <Text style={styles.userName}>{user?.name || t('member')}</Text>
          <Text style={styles.userEmail}>{user?.email || ''}</Text>
          {user?.role === 'admin' && (
            <View style={styles.adminBadge}>
              <Ionicons name="shield-checkmark" size={14} color="#FF3B30" />
              <Text style={styles.adminText}>Admin</Text>
            </View>
          )}
        </View>

        {/* Language toggle */}
        <View style={styles.langCard}>
          <Text style={styles.langLabel}>{t('language')}</Text>
          <View style={styles.langRow}>
            <Pressable
              style={[styles.langBtn, locale === 'en' && styles.langBtnActive]}
              onPress={() => changeLocale('en')}
            >
              <Text style={[styles.langBtnText, locale === 'en' && styles.langBtnTextActive]}>🇺🇸  English</Text>
            </Pressable>
            <Pressable
              style={[styles.langBtn, locale === 'es' && styles.langBtnActive]}
              onPress={() => changeLocale('es')}
            >
              <Text style={[styles.langBtnText, locale === 'es' && styles.langBtnTextActive]}>🇩🇴  Español</Text>
            </Pressable>
          </View>
        </View>

        {/* Biometric login (mobile only, when supported — bioState.available is false on web in prod) */}
        {bioState.available && bioState.enrolled && (
          <View style={styles.bioCard}>
            <View style={[styles.bioIconWrap, { backgroundColor: bioMeta.accent + '22' }]}>
              <Ionicons name={bioMeta.icon} size={22} color={bioMeta.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.bioTitle}>{bioMeta.title}</Text>
              <Text style={styles.bioSub}>{bioEnabled ? bioMeta.subOn : bioMeta.subOff}</Text>
            </View>
            <Switch
              testID="biometric-toggle"
              value={bioEnabled}
              onValueChange={toggleBiometric}
              trackColor={{ false: '#E5E5E5', true: '#34C759' }}
              thumbColor="#FFF"
            />
          </View>
        )}

        {/* When hardware is available but no biometrics are enrolled */}
        {bioState.available && !bioState.enrolled && Platform.OS !== 'web' && (
          <View style={[styles.bioCard, { backgroundColor: '#fff5e6', borderWidth: 1, borderColor: '#ffd48a' }]}>
            <View style={[styles.bioIconWrap, { backgroundColor: '#ffe0a3' }]}>
              <Ionicons name="warning-outline" size={20} color="#a05a00" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.bioTitle, { color: '#a05a00' }]}>{t('biometricUnenrolledTitle')}</Text>
              <Text style={[styles.bioSub, { color: '#b87600' }]}>{t('biometricNotEnrolled')}</Text>
            </View>
          </View>
        )}

        <View style={styles.menuSection}>
          <Pressable testID="my-bookings-btn" style={styles.menuItem} onPress={() => router.push('/(tabs)/bookings')}>
            <View style={styles.menuIcon}><Ionicons name="calendar-outline" size={22} color="#0A0A0A" /></View>
            <Text style={styles.menuText}>{t('myBookings')}</Text>
            <Ionicons name="chevron-forward" size={20} color="#999" />
          </Pressable>

          {user?.role === 'admin' && (
            <Pressable testID="admin-panel-btn" style={styles.menuItem} onPress={() => router.push('/admin')}>
              <View style={[styles.menuIcon, { backgroundColor: '#FFF0F0' }]}><Ionicons name="settings-outline" size={22} color="#FF3B30" /></View>
              <Text style={styles.menuText}>Admin Panel</Text>
              <Ionicons name="chevron-forward" size={20} color="#999" />
            </Pressable>
          )}

          {user?.role === 'admin' && (
            <Pressable testID="admin-locations-btn" style={styles.menuItem} onPress={() => router.push('/admin-locations')}>
              <View style={[styles.menuIcon, { backgroundColor: '#F0F8FF' }]}><Ionicons name="location-outline" size={22} color="#007AFF" /></View>
              <Text style={styles.menuText}>{t('manageLocations')}</Text>
              <Ionicons name="chevron-forward" size={20} color="#999" />
            </Pressable>
          )}
        </View>

        <View style={styles.legalWrap}>
          <LegalLinks />
        </View>

        <View style={styles.logoutArea}>
          {!confirmLogout ? (
            <Pressable
              testID="logout-button"
              style={styles.logoutBtn}
              onPress={showConfirm}
              // @ts-ignore - onClick needed for web
              onClick={showConfirm}
              accessibilityRole="button"
            >
              <Ionicons name="log-out-outline" size={22} color="#FF3B30" />
              <Text style={styles.logoutText}>{t('logout')}</Text>
            </Pressable>
          ) : (
            <View testID="logout-confirm-section" style={styles.confirmSection}>
              <Text style={styles.confirmText}>{locale === 'es' ? '¿Estás seguro de cerrar sesión?' : 'Are you sure you want to logout?'}</Text>
              <View style={styles.confirmActions}>
                <Pressable testID="logout-cancel-btn" style={styles.cancelBtn} onPress={hideConfirm} disabled={loggingOut} accessibilityRole="button"
                  // @ts-ignore
                  onClick={hideConfirm}>
                  <Text style={styles.cancelBtnText}>{t('cancel')}</Text>
                </Pressable>
                <Pressable testID="logout-confirm-btn" style={styles.confirmBtn} onPress={doLogout} disabled={loggingOut} accessibilityRole="button"
                  // @ts-ignore
                  onClick={loggingOut ? undefined : doLogout}>
                  {loggingOut ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.confirmBtnText}>{t('logout')}</Text>}
                </Pressable>
              </View>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Confirm Password Modal — required to enable biometric login from Profile */}
      <Modal
        visible={pwdModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => { if (!pwdSubmitting) setPwdModalVisible(false); }}
      >
        <KeyboardAvoidingView
          style={styles.modalBackdrop}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.modalCard}>
            <View style={[styles.modalIconWrap, { backgroundColor: bioMeta.accent + '22' }]}>
              <Ionicons name={bioMeta.icon} size={30} color={bioMeta.accent} />
            </View>
            <Text style={styles.modalTitle}>{t('confirmPasswordTitle')}</Text>
            <Text style={styles.modalSub}>{t('confirmPasswordSub')}</Text>

            <View style={styles.modalInputWrap}>
              <Ionicons name="mail-outline" size={18} color="#999" />
              <Text style={styles.modalEmail} numberOfLines={1}>{user?.email || ''}</Text>
            </View>

            <View style={styles.modalInputWrap}>
              <Ionicons name="lock-closed-outline" size={18} color="#999" />
              <TextInput
                testID="biometric-password-input"
                style={styles.modalInput}
                placeholder={t('password')}
                placeholderTextColor="#999"
                value={pwdInput}
                onChangeText={(v) => { setPwdInput(v); if (pwdError) setPwdError(''); }}
                secureTextEntry
                autoFocus
                editable={!pwdSubmitting}
                onSubmitEditing={submitPasswordToEnable}
              />
            </View>

            {pwdError ? <Text style={styles.modalErr}>{pwdError}</Text> : null}

            <View style={styles.modalActions}>
              <Pressable
                testID="biometric-pwd-cancel"
                style={[styles.modalBtn, styles.modalBtnGhost]}
                onPress={() => { if (!pwdSubmitting) { setPwdModalVisible(false); setPwdInput(''); setPwdError(''); } }}
                disabled={pwdSubmitting}
              >
                <Text style={styles.modalBtnGhostText}>{t('cancelBtn')}</Text>
              </Pressable>
              <Pressable
                testID="biometric-pwd-submit"
                style={[styles.modalBtn, styles.modalBtnPrimary]}
                onPress={submitPasswordToEnable}
                disabled={pwdSubmitting}
              >
                {pwdSubmitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.modalBtnPrimaryText}>{t('enableBtn')}</Text>}
              </Pressable>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  // ⚠️ Do NOT use `flex: 1` on a ScrollView contentContainerStyle — it constrains
  // content to viewport height and disables scrolling. Use `flexGrow: 1` so the
  // content can extend beyond viewport (making scroll actually work) while still
  // filling the screen when content is short.
  content: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 8 },
  title: { fontSize: 28, fontWeight: '900', color: '#0A0A0A', letterSpacing: -0.5, marginBottom: 24 },
  profileCard: { alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 24, padding: 32, marginBottom: 24 },
  avatarCircle: { width: 80, height: 80, borderRadius: 40, backgroundColor: '#0A0A0A', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  userName: { fontSize: 22, fontWeight: '800', color: '#0A0A0A' },
  userEmail: { fontSize: 14, color: '#666', marginTop: 4 },
  adminBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8, backgroundColor: '#FFF0F0', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 50 },
  adminText: { fontSize: 13, fontWeight: '700', color: '#FF3B30' },
  menuSection: { gap: 4, marginBottom: 24 },
  langCard: { backgroundColor: '#FAFAFA', borderRadius: 16, padding: 14, marginBottom: 16 },
  langLabel: { fontSize: 11, fontWeight: '700', color: '#999', letterSpacing: 1, marginBottom: 8, textTransform: 'uppercase' },
  langRow: { flexDirection: 'row', gap: 8 },
  langBtn: { flex: 1, paddingVertical: 12, borderRadius: 12, backgroundColor: '#FFF', alignItems: 'center', borderWidth: 1, borderColor: '#E5E5E5' },
  langBtnActive: { backgroundColor: '#0A0A0A', borderColor: '#0A0A0A' },
  langBtnText: { fontSize: 14, fontWeight: '700', color: '#0A0A0A' },
  langBtnTextActive: { color: '#FFF' },
  bioCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FAFAFA', borderRadius: 16, padding: 14, marginBottom: 16 },
  bioIconWrap: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  bioTitle: { fontSize: 15, fontWeight: '800', color: '#0A0A0A' },
  bioSub: { fontSize: 12, color: '#666', marginTop: 2, lineHeight: 16 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center', padding: 20 },
  modalCard: { width: '100%', maxWidth: 360, backgroundColor: '#FFF', borderRadius: 20, padding: 22, alignItems: 'center' },
  modalIconWrap: { width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  modalTitle: { fontSize: 18, fontWeight: '800', color: '#0A0A0A', textAlign: 'center' },
  modalSub: { fontSize: 13, color: '#666', textAlign: 'center', marginTop: 6, marginBottom: 16, lineHeight: 18 },
  modalInputWrap: { flexDirection: 'row', alignItems: 'center', gap: 10, alignSelf: 'stretch', backgroundColor: '#F5F5F5', borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 10, borderWidth: 1, borderColor: '#E5E5E5' },
  modalEmail: { flex: 1, fontSize: 14, color: '#666', fontWeight: '600' },
  modalInput: { flex: 1, fontSize: 15, color: '#0A0A0A', paddingVertical: 2 },
  modalErr: { color: '#FF3B30', fontSize: 13, alignSelf: 'stretch', marginTop: 2, marginBottom: 8, fontWeight: '600' },
  modalActions: { flexDirection: 'row', gap: 10, alignSelf: 'stretch', marginTop: 8 },
  modalBtn: { flex: 1, paddingVertical: 14, borderRadius: 50, alignItems: 'center', justifyContent: 'center' },
  modalBtnGhost: { backgroundColor: '#F5F5F5' },
  modalBtnGhostText: { color: '#0A0A0A', fontSize: 15, fontWeight: '700' },
  modalBtnPrimary: { backgroundColor: '#FF3B30' },
  modalBtnPrimaryText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
  menuItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 16, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: '#F5F5F5', cursor: 'pointer' as any },
  menuIcon: { width: 44, height: 44, borderRadius: 12, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center', marginRight: 14 },
  menuText: { flex: 1, fontSize: 16, fontWeight: '600', color: '#0A0A0A' },
  legalWrap: { marginHorizontal: -24, marginTop: 8, marginBottom: 4 },
  logoutArea: { paddingBottom: 40 },
  logoutBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 16, borderWidth: 1.5, borderColor: '#FF3B30', cursor: 'pointer' as any },
  logoutText: { fontSize: 16, fontWeight: '700', color: '#FF3B30' },
  confirmSection: { backgroundColor: '#FFF0F0', borderRadius: 16, padding: 20, alignItems: 'center', gap: 16 },
  confirmText: { fontSize: 16, fontWeight: '700', color: '#0A0A0A', textAlign: 'center' },
  confirmActions: { flexDirection: 'row', gap: 12, width: '100%' },
  cancelBtn: { flex: 1, paddingVertical: 14, borderRadius: 50, backgroundColor: '#F5F5F5', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' as any },
  cancelBtnText: { fontSize: 16, fontWeight: '700', color: '#666' },
  confirmBtn: { flex: 1, paddingVertical: 14, borderRadius: 50, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center', minHeight: 48, cursor: 'pointer' as any },
  confirmBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
