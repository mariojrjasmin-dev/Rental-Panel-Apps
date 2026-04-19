import { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Dimensions, ActivityIndicator } from 'react-native';
import * as Location from 'expo-location';

let MapView: any = null;
let Marker: any = null;

try {
  const maps = require('react-native-maps');
  MapView = maps.default;
  Marker = maps.Marker;
} catch (e) {
  console.log('react-native-maps not available');
}

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
  const [hasLocationPermission, setHasLocationPermission] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        setHasLocationPermission(status === 'granted');
      } catch (e) {
        console.log('Location permission error:', e);
      }
    })();
  }, []);

  // Validate coordinates
  const pLat = isNaN(pickupLat) ? 40.7128 : pickupLat;
  const pLng = isNaN(pickupLng) ? -74.006 : pickupLng;
  const dLat = isNaN(dropoffLat) ? 40.6413 : dropoffLat;
  const dLng = isNaN(dropoffLng) ? -73.7781 : dropoffLng;

  const centerLat = (pLat + dLat) / 2;
  const centerLng = (pLng + dLng) / 2;
  const latDelta = Math.max(Math.abs(pLat - dLat) * 1.8, 0.02);
  const lngDelta = Math.max(Math.abs(pLng - dLng) * 1.8, 0.02);

  if (!MapView || mapError) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.fallbackText}>Map unavailable</Text>
      </View>
    );
  }

  return (
    <View style={styles.mapContainer}>
      {!mapReady && (
        <View style={styles.loading}>
          <ActivityIndicator size="large" color="#FF3B30" />
          <Text style={styles.loadingText}>Loading map...</Text>
        </View>
      )}
      <MapView
        style={styles.map}
        initialRegion={{
          latitude: centerLat,
          longitude: centerLng,
          latitudeDelta: latDelta,
          longitudeDelta: lngDelta,
        }}
        showsUserLocation={hasLocationPermission}
        showsMyLocationButton={hasLocationPermission}
        onMapReady={() => setMapReady(true)}
        onError={() => setMapError(true)}
      >
        {Marker && (
          <>
            <Marker
              coordinate={{ latitude: pLat, longitude: pLng }}
              title={pickupName || 'Pickup'}
              description="Pickup Location"
              pinColor="#34C759"
            />
            <Marker
              coordinate={{ latitude: dLat, longitude: dLng }}
              title={dropoffName || 'Drop-off'}
              description="Drop-off Location"
              pinColor="#FF3B30"
            />
          </>
        )}
      </MapView>
    </View>
  );
}

const styles = StyleSheet.create({
  mapContainer: { width, height: height * 0.6, backgroundColor: '#F5F5F5' },
  map: { width: '100%', height: '100%' },
  loading: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, justifyContent: 'center', alignItems: 'center', zIndex: 1, backgroundColor: '#F5F5F5' },
  loadingText: { marginTop: 8, fontSize: 14, color: '#666' },
  fallback: { width, height: height * 0.5, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  fallbackText: { fontSize: 16, color: '#999' },
});
