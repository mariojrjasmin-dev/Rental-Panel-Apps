import { useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, StyleSheet, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BACKEND_URL } from '../src/config';

export default function TermsScreen() {
  const router = useRouter();
  const [terms, setTerms] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let aborted = false;
    (async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/settings/rental-terms`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!aborted) setTerms(data?.terms || '');
      } catch (e: any) {
        if (!aborted) setError(e?.message || 'Could not load terms');
      }
      if (!aborted) setLoading(false);
    })();
    return () => { aborted = true; };
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="terms-back-btn" onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
        </TouchableOpacity>
        <Text style={styles.title}>📜 Terms &amp; Conditions</Text>
        <View style={{ width: 44 }} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#FF3B30" />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Ionicons name="alert-circle-outline" size={48} color="#FF3B30" />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity
            testID="terms-retry-btn"
            style={styles.retryBtn}
            onPress={() => { setError(null); setLoading(true); setTerms(''); /* trigger refetch */
              fetch(`${BACKEND_URL}/api/settings/rental-terms`).then(r => r.json()).then(d => { setTerms(d?.terms || ''); setLoading(false); }).catch(e => { setError(e?.message || 'Failed'); setLoading(false); }); }}
          >
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={true}>
          <View style={styles.intro}>
            <Ionicons name="information-circle" size={18} color="#007AFF" />
            <Text style={styles.introText}>These are the rental Terms &amp; Conditions you accept when confirming a booking.</Text>
          </View>
          <Text style={styles.bodyText} testID="terms-text">{terms}</Text>
          <Text style={styles.footnote}>© Dams Rent a Car</Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  title: { fontSize: 17, fontWeight: '800', color: '#0A0A0A', flex: 1, textAlign: 'center', marginHorizontal: 8 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, paddingHorizontal: 24 },
  errorText: { fontSize: 14, color: '#666', textAlign: 'center' },
  retryBtn: { backgroundColor: '#FF3B30', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 50 },
  retryText: { color: '#FFF', fontWeight: '700' },
  body: { padding: 20, paddingBottom: 40 },
  intro: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: '#F0F8FF', borderRadius: 12, padding: 12, marginBottom: 16 },
  introText: { flex: 1, fontSize: 12, color: '#0a5dff', lineHeight: 17, fontWeight: '600' },
  bodyText: { fontSize: 13, color: '#333', lineHeight: 20 },
  footnote: { fontSize: 11, color: '#BBB', textAlign: 'center', marginTop: 24, fontWeight: '600' },
});
