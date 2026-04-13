import { View, Text, TouchableOpacity, StyleSheet, Linking, Platform } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import MapComponent from '../components/MapDisplay';

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

  const pickupLat = parseFloat(params.pickupLat || '40.7128');
  const pickupLng = parseFloat(params.pickupLng || '-74.006');
  const dropoffLat = parseFloat(params.dropoffLat || '40.6413');
  const dropoffLng = parseFloat(params.dropoffLng || '-73.7781');
  const pickupName = params.pickupName || 'Pickup';
  const dropoffName = params.dropoffName || 'Drop-off';

  const openDirections = (lat: number, lng: number, label: string) => {
    const url = Platform.select({
      ios: `maps:0,0?q=${label}&ll=${lat},${lng}`,
      android: `geo:0,0?q=${lat},${lng}(${label})`,
      default: `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`,
    });
    if (url) Linking.openURL(url);
  };

  return (
    <View style={styles.container}>
      <MapComponent
        pickupLat={pickupLat}
        pickupLng={pickupLng}
        pickupName={pickupName}
        dropoffLat={dropoffLat}
        dropoffLng={dropoffLng}
        dropoffName={dropoffName}
      />

      <SafeAreaView style={styles.overlay} edges={['top']}>
        <TouchableOpacity testID="map-back-btn" style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
        </TouchableOpacity>
      </SafeAreaView>

      <View style={styles.bottomSheet}>
        <View style={styles.handleBar} />
        <Text style={styles.sheetTitle}>Directions</Text>

        <TouchableOpacity
          testID="directions-pickup-btn"
          style={styles.directionRow}
          activeOpacity={0.7}
          onPress={() => openDirections(pickupLat, pickupLng, pickupName)}
        >
          <View style={[styles.dirIcon, { backgroundColor: '#F0FFF4' }]}>
            <Ionicons name="location" size={20} color="#34C759" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.dirLabel}>PICKUP</Text>
            <Text style={styles.dirName}>{pickupName}</Text>
          </View>
          <TouchableOpacity style={styles.navBtn} onPress={() => openDirections(pickupLat, pickupLng, pickupName)}>
            <Ionicons name="navigate" size={18} color="#FFF" />
            <Text style={styles.navBtnText}>Go</Text>
          </TouchableOpacity>
        </TouchableOpacity>

        <TouchableOpacity
          testID="directions-dropoff-btn"
          style={styles.directionRow}
          activeOpacity={0.7}
          onPress={() => openDirections(dropoffLat, dropoffLng, dropoffName)}
        >
          <View style={[styles.dirIcon, { backgroundColor: '#FFF0F0' }]}>
            <Ionicons name="location" size={20} color="#FF3B30" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.dirLabel}>DROP-OFF</Text>
            <Text style={styles.dirName}>{dropoffName}</Text>
          </View>
          <TouchableOpacity style={[styles.navBtn, { backgroundColor: '#FF3B30' }]} onPress={() => openDirections(dropoffLat, dropoffLng, dropoffName)}>
            <Ionicons name="navigate" size={18} color="#FFF" />
            <Text style={styles.navBtnText}>Go</Text>
          </TouchableOpacity>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFF' },
  overlay: { position: 'absolute', top: 0, left: 0, right: 0 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF', justifyContent: 'center', alignItems: 'center', marginLeft: 16, marginTop: 8, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4, elevation: 3 },
  bottomSheet: { flex: 1, backgroundColor: '#FFFFFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingHorizontal: 24, paddingTop: 12, marginTop: -24, shadowColor: '#000', shadowOffset: { width: 0, height: -2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 5 },
  handleBar: { width: 40, height: 4, borderRadius: 2, backgroundColor: '#E5E5E5', alignSelf: 'center', marginBottom: 16 },
  sheetTitle: { fontSize: 20, fontWeight: '900', color: '#0A0A0A', marginBottom: 16 },
  directionRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#F5F5F5' },
  dirIcon: { width: 44, height: 44, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  dirLabel: { fontSize: 10, color: '#999', fontWeight: '700', letterSpacing: 0.5 },
  dirName: { fontSize: 16, fontWeight: '700', color: '#0A0A0A', marginTop: 2 },
  navBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#34C759', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 50 },
  navBtnText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
});
