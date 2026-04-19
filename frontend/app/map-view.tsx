import { View, Text, TouchableOpacity, StyleSheet, Linking, Platform, Dimensions } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';

const { height } = Dimensions.get('window');

export default function MapViewScreen() {
  const params = useLocalSearchParams<{
    pickupLat: string;
    pickupLng: string;
    pickupName: string;
    dropoffLat: string;
    dropoffLng: string;
    dropoffName: string;
  }>();
  const router = useRouter();

  const pickupLat = parseFloat(params.pickupLat ?? '') || 0;
  const pickupLng = parseFloat(params.pickupLng ?? '') || 0;
  const dropoffLat = parseFloat(params.dropoffLat ?? '') || 0;
  const dropoffLng = parseFloat(params.dropoffLng ?? '') || 0;
  const pickupName = params.pickupName || 'Pickup';
  const dropoffName = params.dropoffName || 'Drop-off';

  const openInMaps = (lat: number, lng: number, label: string) => {
    // Always use Google Maps HTTPS URL — works on all platforms and all Android devices
    const url = `https://www.google.com/maps/search/?api=1&query=${lat},${lng}&query_place_id=${encodeURIComponent(label)}`;
    Linking.openURL(url).catch((err) => {
      console.log('Could not open maps:', err);
    });
  };

  const openFullRoute = () => {
    const url = `https://www.google.com/maps/dir/?api=1&origin=${pickupLat},${pickupLng}&destination=${dropoffLat},${dropoffLng}`;
    Linking.openURL(url).catch((err) => {
      console.log('Could not open maps:', err);
    });
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity testID="map-back-btn" style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Directions</Text>
        <View style={{ width: 44 }} />
      </View>

      {/* Route visual */}
      <View style={styles.routeVisual}>
        {/* Pickup card */}
        <TouchableOpacity
          testID="directions-pickup-btn"
          style={styles.locationCard}
          activeOpacity={0.7}
          onPress={() => openInMaps(pickupLat, pickupLng, pickupName)}
        >
          <View style={styles.pinLineWrap}>
            <View style={[styles.pinDot, { backgroundColor: '#34C759' }]} />
            <View style={styles.pinLine} />
          </View>
          <View style={styles.locationInfo}>
            <Text style={styles.locationLabel}>PICKUP LOCATION</Text>
            <Text style={styles.locationName}>{pickupName}</Text>
            <Text style={styles.locationCoords}>{pickupLat.toFixed(4)}, {pickupLng.toFixed(4)}</Text>
          </View>
          <View style={[styles.goBtn, { backgroundColor: '#34C759' }]}>
            <Ionicons name="navigate" size={18} color="#FFF" />
          </View>
        </TouchableOpacity>

        {/* Route connector */}
        <View style={styles.connector}>
          <View style={styles.connectorLine} />
          <View style={styles.connectorBadge}>
            <Ionicons name="car-sport" size={16} color="#FFF" />
          </View>
          <View style={styles.connectorLine} />
        </View>

        {/* Dropoff card */}
        <TouchableOpacity
          testID="directions-dropoff-btn"
          style={styles.locationCard}
          activeOpacity={0.7}
          onPress={() => openInMaps(dropoffLat, dropoffLng, dropoffName)}
        >
          <View style={styles.pinLineWrap}>
            <View style={[styles.pinDot, { backgroundColor: '#FF3B30' }]} />
          </View>
          <View style={styles.locationInfo}>
            <Text style={styles.locationLabel}>DROP-OFF LOCATION</Text>
            <Text style={styles.locationName}>{dropoffName}</Text>
            <Text style={styles.locationCoords}>{dropoffLat.toFixed(4)}, {dropoffLng.toFixed(4)}</Text>
          </View>
          <View style={[styles.goBtn, { backgroundColor: '#FF3B30' }]}>
            <Ionicons name="navigate" size={18} color="#FFF" />
          </View>
        </TouchableOpacity>
      </View>

      {/* Action buttons */}
      <View style={styles.actions}>
        <TouchableOpacity
          testID="open-full-route-btn"
          style={styles.primaryBtn}
          onPress={openFullRoute}
          activeOpacity={0.7}
        >
          <Ionicons name="map-outline" size={22} color="#FFF" />
          <Text style={styles.primaryBtnText}>Get Directions in Google Maps</Text>
        </TouchableOpacity>

        <TouchableOpacity
          testID="pickup-navigate-btn"
          style={styles.secondaryBtn}
          onPress={() => openInMaps(pickupLat, pickupLng, pickupName)}
          activeOpacity={0.7}
        >
          <View style={[styles.miniDot, { backgroundColor: '#34C759' }]} />
          <Text style={styles.secondaryBtnText}>Navigate to Pickup</Text>
          <Ionicons name="open-outline" size={16} color="#666" />
        </TouchableOpacity>

        <TouchableOpacity
          testID="dropoff-navigate-btn"
          style={styles.secondaryBtn}
          onPress={() => openInMaps(dropoffLat, dropoffLng, dropoffName)}
          activeOpacity={0.7}
        >
          <View style={[styles.miniDot, { backgroundColor: '#FF3B30' }]} />
          <Text style={styles.secondaryBtnText}>Navigate to Drop-off</Text>
          <Ionicons name="open-outline" size={16} color="#666" />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '800', color: '#0A0A0A' },
  routeVisual: { paddingHorizontal: 24, paddingTop: 16 },
  locationCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 16, padding: 16, gap: 14 },
  pinLineWrap: { alignItems: 'center', width: 20 },
  pinDot: { width: 16, height: 16, borderRadius: 8 },
  pinLine: { width: 2, height: 20, backgroundColor: '#E5E5E5', marginTop: 4 },
  locationInfo: { flex: 1 },
  locationLabel: { fontSize: 10, fontWeight: '800', color: '#999', letterSpacing: 1, marginBottom: 4 },
  locationName: { fontSize: 16, fontWeight: '700', color: '#0A0A0A' },
  locationCoords: { fontSize: 11, color: '#BBB', marginTop: 3 },
  goBtn: { width: 44, height: 44, borderRadius: 22, justifyContent: 'center', alignItems: 'center' },
  connector: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, paddingHorizontal: 8 },
  connectorLine: { flex: 1, height: 2, backgroundColor: '#E5E5E5' },
  connectorBadge: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#0A0A0A', justifyContent: 'center', alignItems: 'center', marginHorizontal: 12 },
  actions: { flex: 1, justifyContent: 'flex-end', paddingHorizontal: 24, paddingBottom: 32, gap: 10 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#007AFF', paddingVertical: 18, borderRadius: 50 },
  primaryBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  secondaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#F5F5F5', paddingVertical: 16, paddingHorizontal: 20, borderRadius: 14 },
  secondaryBtnText: { flex: 1, fontSize: 15, fontWeight: '600', color: '#0A0A0A' },
  miniDot: { width: 10, height: 10, borderRadius: 5 },
});
