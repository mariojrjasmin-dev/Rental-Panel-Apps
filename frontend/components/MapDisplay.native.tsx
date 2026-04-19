import { View, Text, TouchableOpacity, StyleSheet, Dimensions, Linking, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const { width, height } = Dimensions.get('window');

type Props = {
  pickupLat: number;
  pickupLng: number;
  pickupName: string;
  dropoffLat: number;
  dropoffLng: number;
  dropoffName: string;
};

export default function MapComponent({ pickupLat, pickupLng, pickupName, dropoffLat, dropoffLng, dropoffName }: Props) {
  const pLat = isNaN(pickupLat) ? 0 : pickupLat;
  const pLng = isNaN(pickupLng) ? 0 : pickupLng;
  const dLat = isNaN(dropoffLat) ? 0 : dropoffLat;
  const dLng = isNaN(dropoffLng) ? 0 : dropoffLng;

  const openRoute = () => {
    const url = Platform.select({
      ios: `maps:0,0?saddr=${pLat},${pLng}&daddr=${dLat},${dLng}`,
      android: `google.navigation:q=${dLat},${dLng}&waypoints=${pLat},${pLng}`,
      default: `https://www.google.com/maps/dir/${pLat},${pLng}/${dLat},${dLng}`,
    });
    if (url) {
      Linking.openURL(url).catch(() => {
        Linking.openURL(`https://www.google.com/maps/dir/${pLat},${pLng}/${dLat},${dLng}`);
      });
    }
  };

  const openLocation = (lat: number, lng: number, label: string) => {
    const url = Platform.select({
      ios: `maps:0,0?q=${encodeURIComponent(label)}&ll=${lat},${lng}`,
      android: `geo:0,0?q=${lat},${lng}(${encodeURIComponent(label)})`,
      default: `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`,
    });
    if (url) {
      Linking.openURL(url).catch(() => {
        Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`);
      });
    }
  };

  return (
    <View style={styles.container}>
      {/* Visual map representation */}
      <View style={styles.mapVisual}>
        <View style={styles.routeLine} />

        <View style={styles.pinRow}>
          <TouchableOpacity style={styles.pinCard} onPress={() => openLocation(pLat, pLng, pickupName)} activeOpacity={0.7}>
            <View style={styles.pinDotGreen} />
            <Text style={styles.pinLabel}>PICKUP</Text>
            <Text style={styles.pinName} numberOfLines={2}>{pickupName}</Text>
            <Text style={styles.pinCoords}>{pLat.toFixed(4)}, {pLng.toFixed(4)}</Text>
          </TouchableOpacity>

          <View style={styles.pinArrow}>
            <Ionicons name="arrow-forward" size={24} color="#999" />
          </View>

          <TouchableOpacity style={styles.pinCard} onPress={() => openLocation(dLat, dLng, dropoffName)} activeOpacity={0.7}>
            <View style={styles.pinDotRed} />
            <Text style={styles.pinLabel}>DROP-OFF</Text>
            <Text style={styles.pinName} numberOfLines={2}>{dropoffName}</Text>
            <Text style={styles.pinCoords}>{dLat.toFixed(4)}, {dLng.toFixed(4)}</Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity
          testID="open-full-route-btn"
          style={styles.routeBtn}
          onPress={openRoute}
          activeOpacity={0.7}
        >
          <Ionicons name="navigate" size={22} color="#FFF" />
          <Text style={styles.routeBtnText}>Open Full Route in Maps</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: '100%', height: height * 0.55, backgroundColor: '#F5F5F5' },
  mapVisual: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 24, paddingVertical: 20 },
  routeLine: { position: 'absolute', top: '35%', left: '50%', width: 2, height: '20%', backgroundColor: '#E5E5E5', marginLeft: -1 },
  pinRow: { flexDirection: 'row', alignItems: 'center', gap: 12, width: '100%', marginBottom: 24 },
  pinCard: { flex: 1, backgroundColor: '#FFF', borderRadius: 16, padding: 16, alignItems: 'center', shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 8, elevation: 2 },
  pinArrow: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  pinDotGreen: { width: 14, height: 14, borderRadius: 7, backgroundColor: '#34C759', marginBottom: 8 },
  pinDotRed: { width: 14, height: 14, borderRadius: 7, backgroundColor: '#FF3B30', marginBottom: 8 },
  pinLabel: { fontSize: 10, fontWeight: '800', color: '#999', letterSpacing: 1, marginBottom: 4 },
  pinName: { fontSize: 14, fontWeight: '700', color: '#0A0A0A', textAlign: 'center' },
  pinCoords: { fontSize: 10, color: '#BBB', marginTop: 4 },
  routeBtn: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#007AFF', paddingHorizontal: 28, paddingVertical: 16, borderRadius: 50, shadowColor: '#007AFF', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8, elevation: 4 },
  routeBtnText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
});
