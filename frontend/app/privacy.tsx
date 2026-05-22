import { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BACKEND_URL } from '../src/config';
import { PRIVACY_POLICY_TEXT, PRIVACY_UPDATED_AT } from '../src/privacy';

export default function PrivacyScreen() {
  const router = useRouter();
  const [text, setText] = useState<string>('');
  const [updated, setUpdated] = useState<string>(PRIVACY_UPDATED_AT);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let aborted = false;
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/settings/privacy-policy`);
        if (r.ok) {
          const data = await r.json();
          if (!aborted) {
            setText(data?.text || PRIVACY_POLICY_TEXT);
            if (data?.updated_at) {
              try { setUpdated(new Date(data.updated_at).toLocaleDateString()); } catch {}
            }
          }
        } else {
          if (!aborted) setText(PRIVACY_POLICY_TEXT);
        }
      } catch {
        if (!aborted) setText(PRIVACY_POLICY_TEXT);
      }
      if (!aborted) setLoading(false);
    })();
    return () => { aborted = true; };
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="privacy-back-btn" onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
        </TouchableOpacity>
        <Text style={styles.title}>🔒 Privacy Policy</Text>
        <View style={{ width: 44 }} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#FF3B30" />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={true}>
          <View style={styles.intro}>
            <Ionicons name="shield-checkmark" size={18} color="#0a5d2b" />
            <View style={{ flex: 1 }}>
              <Text style={styles.introTitle}>Your privacy matters to us</Text>
              <Text style={styles.introSub}>Last updated: {updated}</Text>
            </View>
          </View>
          <Text style={styles.bodyText} testID="privacy-text">{text}</Text>
          <Text style={styles.footnote}>© Dams Rent a Car · info@damsrentacar.com</Text>
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
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  body: { padding: 20, paddingBottom: 40 },
  intro: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: '#e6f9ed', borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: '#bce7c8' },
  introTitle: { fontSize: 13, fontWeight: '800', color: '#0a5d2b' },
  introSub: { fontSize: 11, color: '#1e7a3e', marginTop: 2, fontWeight: '600' },
  bodyText: { fontSize: 13, color: '#333', lineHeight: 20 },
  footnote: { fontSize: 11, color: '#BBB', textAlign: 'center', marginTop: 24, fontWeight: '600' },
});
