import { useEffect } from 'react';
import { useRouter } from 'expo-router';
import { View, ActivityIndicator, StyleSheet, Platform } from 'react-native';
import { useAuth } from './_layout';

export default function Index() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Host-based redirect for the admin subdomain.
    // If visitors land on adminpanel.<anything>, send them straight to the HTML admin panel
    // instead of the customer-facing mobile/web app.
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const host = window.location.hostname || '';
      if (host.startsWith('adminpanel.')) {
        window.location.replace('/api/admin-panel');
        return;
      }
    }
    if (!loading) {
      if (user) {
        router.replace('/(tabs)/home');
      } else {
        router.replace('/(auth)/login');
      }
    }
  }, [user, loading]);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#FF3B30" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
});
