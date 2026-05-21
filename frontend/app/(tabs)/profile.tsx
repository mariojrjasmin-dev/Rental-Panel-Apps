import { useState, useCallback, useEffect } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator, Platform, Switch, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';
import { t } from '../../src/i18n';
import { isBiometricAvailable, isBiometricEnabled, disableBiometricLogin, type BiometricCheck } from '../../src/biometric';
import LegalLinks from '../../components/LegalLinks';

export default function ProfileScreen() {
  const { user, logout, locale, changeLocale } = useAuth();
  const router = useRouter();
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [bioState, setBioState] = useState<BiometricCheck>({ available: false, enrolled: false, type: 'none' });
  const [bioEnabled, setBioEnabled] = useState(false);

  useEffect(() => {
    (async () => {
      setBioState(await isBiometricAvailable());
      setBioEnabled(await isBiometricEnabled());
    })();
  }, []);

  const toggleBiometric = useCallback(async (val: boolean) => {
    if (!val) {
      await disableBiometricLogin();
      setBioEnabled(false);
    }
    // Enabling requires the user to login normally first (in login screen).
  }, []);

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
        contentContainerStyle={styles.content}
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

        {/* Biometric login (mobile only, when supported) */}
        {bioState.available && bioState.enrolled && Platform.OS !== 'web' && (
          <View style={styles.bioCard}>
            <View style={{ flex: 1 }}>
              <Text style={styles.bioTitle}>{t('biometricLogin')}</Text>
              <Text style={styles.bioSub}>{bioEnabled ? t('biometricEnabled') : t('enableBiometricSub')}</Text>
            </View>
            <Switch
              value={bioEnabled}
              onValueChange={toggleBiometric}
              trackColor={{ false: '#E5E5E5', true: '#34C759' }}
              thumbColor="#FFF"
              disabled={!bioEnabled /* enabling happens during login */}
            />
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { flex: 1, paddingHorizontal: 24, paddingTop: 8 },
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
  bioTitle: { fontSize: 14, fontWeight: '700', color: '#0A0A0A' },
  bioSub: { fontSize: 12, color: '#666', marginTop: 2 },
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
