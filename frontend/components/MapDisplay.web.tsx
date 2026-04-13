import { View, Text, TouchableOpacity, StyleSheet, Dimensions, Linking } from 'react-native';
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
  const openFullMap = () => {
    const url = `https://www.google.com/maps/dir/${pickupLat},${pickupLng}/${dropoffLat},${dropoffLng}`;
    Linking.openURL(url);
  };

  return (
    <View style={styles.webMapFallback}>
      <View style={styles.webMapContent}>
        <Ionicons name="map" size={64} color="#FF3B30" />
        <Text style={styles.webMapTitle}>Map View</Text>
        <Text style={styles.webMapSubtitle}>Interactive maps available on mobile</Text>
        <TouchableOpacity testID="open-google-maps-btn" style={styles.openMapBtn} onPress={openFullMap}>
          <Ionicons name="navigate" size={20} color="#FFF" />
          <Text style={styles.openMapBtnText}>Open in Google Maps</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  webMapFallback: { width: '100%', height: height * 0.5, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  webMapContent: { alignItems: 'center', gap: 12 },
  webMapTitle: { fontSize: 24, fontWeight: '900', color: '#0A0A0A' },
  webMapSubtitle: { fontSize: 14, color: '#666' },
  openMapBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#007AFF', paddingHorizontal: 24, paddingVertical: 14, borderRadius: 50, marginTop: 8 },
  openMapBtnText: { color: '#FFF', fontWeight: '700', fontSize: 16 },
});
