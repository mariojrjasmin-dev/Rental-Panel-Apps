import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Alert, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';

export default function ProfileScreen() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const doLogout = async () => {
    await logout();
    router.replace('/(auth)/login');
  };

  const handleLogout = () => {
    if (Platform.OS === 'web') {
      if (typeof window !== 'undefined' && window.confirm('Are you sure you want to logout?')) {
        doLogout();
      }
    } else {
      Alert.alert('Logout', 'Are you sure you want to logout?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Logout', style: 'destructive', onPress: doLogout },
      ]);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>Profile</Text>

        <View style={styles.profileCard}>
          <View style={styles.avatarCircle}>
            <Ionicons name="person" size={40} color="#FFF" />
          </View>
          <Text style={styles.userName}>{user?.name || 'User'}</Text>
          <Text style={styles.userEmail}>{user?.email || ''}</Text>
          {user?.role === 'admin' && (
            <View style={styles.adminBadge}>
              <Ionicons name="shield-checkmark" size={14} color="#FF3B30" />
              <Text style={styles.adminText}>Admin</Text>
            </View>
          )}
        </View>

        <View style={styles.menuSection}>
          <TouchableOpacity testID="my-bookings-btn" style={styles.menuItem} onPress={() => router.push('/(tabs)/bookings')} activeOpacity={0.7}>
            <View style={styles.menuIcon}><Ionicons name="calendar-outline" size={22} color="#0A0A0A" /></View>
            <Text style={styles.menuText}>My Bookings</Text>
            <Ionicons name="chevron-forward" size={20} color="#999" />
          </TouchableOpacity>

          {user?.role === 'admin' && (
            <TouchableOpacity testID="admin-panel-btn" style={styles.menuItem} onPress={() => router.push('/admin')} activeOpacity={0.7}>
              <View style={[styles.menuIcon, { backgroundColor: '#FFF0F0' }]}><Ionicons name="settings-outline" size={22} color="#FF3B30" /></View>
              <Text style={styles.menuText}>Admin Panel</Text>
              <Ionicons name="chevron-forward" size={20} color="#999" />
            </TouchableOpacity>
          )}

          {user?.role === 'admin' && (
            <TouchableOpacity testID="admin-locations-btn" style={styles.menuItem} onPress={() => router.push('/admin-locations')} activeOpacity={0.7}>
              <View style={[styles.menuIcon, { backgroundColor: '#F0F8FF' }]}><Ionicons name="location-outline" size={22} color="#007AFF" /></View>
              <Text style={styles.menuText}>Manage Locations</Text>
              <Ionicons name="chevron-forward" size={20} color="#999" />
            </TouchableOpacity>
          )}
        </View>

        <TouchableOpacity testID="logout-button" style={styles.logoutBtn} onPress={handleLogout} activeOpacity={0.7}>
          <Ionicons name="log-out-outline" size={22} color="#FF3B30" />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: '900', color: '#0A0A0A', letterSpacing: -0.5, marginBottom: 24 },
  profileCard: { alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 24, padding: 32, marginBottom: 24 },
  avatarCircle: { width: 80, height: 80, borderRadius: 40, backgroundColor: '#0A0A0A', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  userName: { fontSize: 22, fontWeight: '800', color: '#0A0A0A' },
  userEmail: { fontSize: 14, color: '#666', marginTop: 4 },
  adminBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8, backgroundColor: '#FFF0F0', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 50 },
  adminText: { fontSize: 13, fontWeight: '700', color: '#FF3B30' },
  menuSection: { gap: 4, marginBottom: 32 },
  menuItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 16, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: '#F5F5F5' },
  menuIcon: { width: 44, height: 44, borderRadius: 12, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center', marginRight: 14 },
  menuText: { flex: 1, fontSize: 16, fontWeight: '600', color: '#0A0A0A' },
  logoutBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 16, borderWidth: 1.5, borderColor: '#FF3B30' },
  logoutText: { fontSize: 16, fontWeight: '700', color: '#FF3B30' },
});
