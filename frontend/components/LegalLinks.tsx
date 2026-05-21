import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

/**
 * Small "Legal" card section with icon links to:
 *  - /terms   (rental Terms & Conditions, fetched from /api/settings/rental-terms)
 *  - /privacy (Privacy Policy, static text under /src/privacy.ts)
 *
 * Re-used on Home tab footer and Profile tab.
 */
export default function LegalLinks() {
  const router = useRouter();
  return (
    <View style={styles.section}>
      <Text style={styles.sectionLabel}>Legal</Text>
      <View style={styles.row}>
        <TouchableOpacity
          testID="legal-terms-link"
          style={styles.card}
          activeOpacity={0.7}
          onPress={() => router.push('/terms')}
        >
          <View style={[styles.iconWrap, { backgroundColor: '#F0F8FF' }]}>
            <Ionicons name="document-text-outline" size={20} color="#007AFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Terms</Text>
            <Text style={styles.cardSub}>Rental Terms &amp; Conditions</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#999" />
        </TouchableOpacity>

        <TouchableOpacity
          testID="legal-privacy-link"
          style={styles.card}
          activeOpacity={0.7}
          onPress={() => router.push('/privacy')}
        >
          <View style={[styles.iconWrap, { backgroundColor: '#FFF0F0' }]}>
            <Ionicons name="shield-checkmark-outline" size={20} color="#FF3B30" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Privacy</Text>
            <Text style={styles.cardSub}>How we handle your data</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#999" />
        </TouchableOpacity>
      </View>
      <Text style={styles.footnote}>© Dams Rent a Car · v1.0</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 24 },
  sectionLabel: { fontSize: 11, fontWeight: '800', color: '#999', letterSpacing: 1.4, marginBottom: 10, textTransform: 'uppercase' },
  row: { gap: 10 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FAFAFA', borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12, borderWidth: 1, borderColor: '#F0F0F0' },
  iconWrap: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#0A0A0A' },
  cardSub: { fontSize: 12, color: '#888', marginTop: 2 },
  footnote: { fontSize: 11, color: '#BBB', textAlign: 'center', marginTop: 14, fontWeight: '600' },
});
