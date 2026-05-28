import { useEffect, useState, useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Linking, Platform, ActivityIndicator, Alert } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import { useTheme } from '../src/theme';

type Coords = { latitude: number; longitude: number };

// Haversine distance in kilometres
function haversineKm(a: Coords, b: { lat: number; lng: number }): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const R = 6371; // km
  const dLat = toRad(b.lat - a.latitude);
  const dLng = toRad(b.lng - a.longitude);
  const lat1 = toRad(a.latitude);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

function formatDistance(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km)} km`;
}

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

  const [userLocation, setUserLocation] = useState<Coords | null>(null);
  const [permissionStatus, setPermissionStatus] = useState<'idle' | 'requesting' | 'granted' | 'denied' | 'unavailable'>('idle');
  const [locating, setLocating] = useState(false);
  const { colors, isDark } = useTheme();

  // Request location permission + fetch position
  const requestAndFetchLocation = async (silent = false) => {
    try {
      setPermissionStatus('requesting');
      setLocating(true);
      const services = await Location.hasServicesEnabledAsync();
      if (!services) {
        setPermissionStatus('unavailable');
        setLocating(false);
        if (!silent) Alert.alert('Location services off', 'Please enable location services in your device settings to get directions from your current location.');
        return;
      }
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setPermissionStatus('denied');
        setLocating(false);
        if (!silent) {
          Alert.alert(
            'Location permission denied',
            'We use your location only to give directions from where you are to the pickup/drop-off. You can still navigate without it.',
            [{ text: 'OK' }]
          );
        }
        return;
      }
      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setUserLocation({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
      setPermissionStatus('granted');
    } catch (e: any) {
      console.log('Location error:', e?.message || e);
      setPermissionStatus('denied');
    }
    setLocating(false);
  };

  useEffect(() => {
    // Auto-request on mount (so the permission dialog pops once).
    requestAndFetchLocation(true);
  }, []);

  const distanceToPickup = useMemo(() => {
    if (!userLocation || !pickupLat || !pickupLng) return null;
    return haversineKm(userLocation, { lat: pickupLat, lng: pickupLng });
  }, [userLocation, pickupLat, pickupLng]);

  const distanceToDropoff = useMemo(() => {
    if (!userLocation || !dropoffLat || !dropoffLng) return null;
    return haversineKm(userLocation, { lat: dropoffLat, lng: dropoffLng });
  }, [userLocation, dropoffLat, dropoffLng]);

  // Build a Google-Maps directions URL.
  // If we have userLocation -> use it as origin so the route starts from where the user is.
  // Otherwise fall back to "Current Location" which Google Maps resolves at run time on iOS/Android.
  const directionsUrl = (destLat: number, destLng: number, destLabel: string) => {
    const dest = `${destLat},${destLng}`;
    if (userLocation) {
      const origin = `${userLocation.latitude},${userLocation.longitude}`;
      return `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${dest}&travelmode=driving`;
    }
    // "Current Location" is recognised by the iOS Maps & Google Maps apps as the device location.
    return `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent('Current Location')}&destination=${dest}&travelmode=driving`;
  };

  const navigateTo = (lat: number, lng: number, label: string) => {
    const url = directionsUrl(lat, lng, label);
    Linking.openURL(url).catch((err) => {
      console.log('Could not open maps:', err);
      Alert.alert('Maps unavailable', 'Could not open Google Maps on this device.');
    });
  };

  const openFullRoute = () => {
    // Three-leg trip: customer location → pickup → drop-off (when location available)
    let url: string;
    const pickup = `${pickupLat},${pickupLng}`;
    const dropoff = `${dropoffLat},${dropoffLng}`;
    if (userLocation) {
      const origin = `${userLocation.latitude},${userLocation.longitude}`;
      url = `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${dropoff}&waypoints=${pickup}&travelmode=driving`;
    } else {
      url = `https://www.google.com/maps/dir/?api=1&origin=${pickup}&destination=${dropoff}&travelmode=driving`;
    }
    Linking.openURL(url).catch((err) => {
      console.log('Could not open maps:', err);
    });
  };

  const renderPermissionBanner = () => {
    if (permissionStatus === 'granted' && userLocation) {
      return (
        <View style={styles.locOk}>
          <Ionicons name="location" size={16} color="#0a5d2b" />
          <Text style={styles.locOkText}>
            Your location: {userLocation.latitude.toFixed(4)}, {userLocation.longitude.toFixed(4)}
          </Text>
        </View>
      );
    }
    if (locating) {
      return (
        <View style={styles.locLoading}>
          <ActivityIndicator size="small" color="#007AFF" />
          <Text style={styles.locLoadingText}>Getting your location…</Text>
        </View>
      );
    }
    if (permissionStatus === 'denied' || permissionStatus === 'unavailable') {
      return (
        <TouchableOpacity
          testID="enable-location-btn"
          style={styles.locDenied}
          onPress={() => requestAndFetchLocation(false)}
          activeOpacity={0.8}
        >
          <Ionicons name="location-outline" size={18} color="#a05a00" />
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={styles.locDeniedTitle}>Enable location to get personalised directions</Text>
            <Text style={styles.locDeniedSub}>Tap to retry. We only use it to navigate to pickup/drop-off.</Text>
          </View>
          <Ionicons name="refresh" size={18} color="#a05a00" />
        </TouchableOpacity>
      );
    }
    return null;
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity testID="map-back-btn" style={[styles.backBtn, { backgroundColor: colors.bgSubtle }]} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Directions</Text>
        <View style={{ width: 44 }} />
      </View>

      {/* Permission banner */}
      <View style={styles.bannerWrap}>{renderPermissionBanner()}</View>

      {/* Route visual */}
      <View style={styles.routeVisual}>
        {/* User "You are here" card — only when we have location */}
        {userLocation && (
          <>
            <View style={[styles.locationCardSelf, { backgroundColor: isDark ? 'rgba(59,130,246,0.15)' : '#F0F8FF', borderColor: isDark ? 'rgba(59,130,246,0.35)' : '#cfe3ff' }]}>
              <View style={styles.pinLineWrap}>
                <View style={[styles.pinDot, { backgroundColor: colors.info }]} />
                <View style={[styles.pinLine, { backgroundColor: colors.border }]} />
              </View>
              <View style={styles.locationInfo}>
                <Text style={[styles.locationLabel, { color: colors.textSubtle }]}>YOU ARE HERE</Text>
                <Text style={[styles.locationName, { color: colors.text }]}>Your current location</Text>
                <Text style={[styles.locationCoords, { color: colors.textSubtle }]}>
                  {userLocation.latitude.toFixed(4)}, {userLocation.longitude.toFixed(4)}
                </Text>
              </View>
              <Ionicons name="locate" size={22} color={colors.info} />
            </View>

            <View style={styles.connector}>
              <View style={[styles.connectorLine, { backgroundColor: colors.border }]} />
              <View style={[styles.connectorBadge, { backgroundColor: colors.text }]}>
                <Ionicons name="walk" size={14} color={colors.bg} />
              </View>
              <View style={[styles.connectorLine, { backgroundColor: colors.border }]} />
            </View>
          </>
        )}

        {/* Pickup card */}
        <TouchableOpacity
          testID="directions-pickup-btn"
          style={[styles.locationCard, { backgroundColor: colors.bgElevated, borderColor: colors.border, borderWidth: 1 }]}
          activeOpacity={0.7}
          onPress={() => navigateTo(pickupLat, pickupLng, pickupName)}
        >
          <View style={styles.pinLineWrap}>
            <View style={[styles.pinDot, { backgroundColor: colors.success }]} />
            <View style={[styles.pinLine, { backgroundColor: colors.border }]} />
          </View>
          <View style={styles.locationInfo}>
            <Text style={[styles.locationLabel, { color: colors.textSubtle }]}>PICKUP LOCATION</Text>
            <Text style={[styles.locationName, { color: colors.text }]}>{pickupName}</Text>
            <Text style={[styles.locationCoords, { color: colors.textSubtle }]}>
              {pickupLat.toFixed(4)}, {pickupLng.toFixed(4)}
              {distanceToPickup !== null && (
                <Text style={[styles.distanceText, { color: colors.info }]}>{`  ·  ${formatDistance(distanceToPickup)} away`}</Text>
              )}
            </Text>
          </View>
          <View style={[styles.goBtn, { backgroundColor: colors.success }]}>
            <Ionicons name="navigate" size={18} color="#FFF" />
          </View>
        </TouchableOpacity>

        {/* Route connector */}
        <View style={styles.connector}>
          <View style={[styles.connectorLine, { backgroundColor: colors.border }]} />
          <View style={[styles.connectorBadge, { backgroundColor: colors.text }]}>
            <Ionicons name="car-sport" size={16} color={colors.bg} />
          </View>
          <View style={[styles.connectorLine, { backgroundColor: colors.border }]} />
        </View>

        {/* Dropoff card */}
        <TouchableOpacity
          testID="directions-dropoff-btn"
          style={[styles.locationCard, { backgroundColor: colors.bgElevated, borderColor: colors.border, borderWidth: 1 }]}
          activeOpacity={0.7}
          onPress={() => navigateTo(dropoffLat, dropoffLng, dropoffName)}
        >
          <View style={styles.pinLineWrap}>
            <View style={[styles.pinDot, { backgroundColor: colors.brand }]} />
          </View>
          <View style={styles.locationInfo}>
            <Text style={[styles.locationLabel, { color: colors.textSubtle }]}>DROP-OFF LOCATION</Text>
            <Text style={[styles.locationName, { color: colors.text }]}>{dropoffName}</Text>
            <Text style={[styles.locationCoords, { color: colors.textSubtle }]}>
              {dropoffLat.toFixed(4)}, {dropoffLng.toFixed(4)}
              {distanceToDropoff !== null && (
                <Text style={[styles.distanceText, { color: colors.info }]}>{`  ·  ${formatDistance(distanceToDropoff)} away`}</Text>
              )}
            </Text>
          </View>
          <View style={[styles.goBtn, { backgroundColor: colors.brand }]}>
            <Ionicons name="navigate" size={18} color="#FFF" />
          </View>
        </TouchableOpacity>
      </View>

      {/* Action buttons */}
      <View style={styles.actions}>
        <TouchableOpacity
          testID="open-full-route-btn"
          style={[styles.primaryBtn, { backgroundColor: colors.info }]}
          onPress={openFullRoute}
          activeOpacity={0.7}
        >
          <Ionicons name="map-outline" size={22} color="#FFF" />
          <Text style={styles.primaryBtnText}>
            {userLocation ? 'Open Full Route in Google Maps' : 'Get Directions in Google Maps'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          testID="pickup-navigate-btn"
          style={[styles.secondaryBtn, { backgroundColor: colors.bgElevated, borderColor: colors.border, borderWidth: 1 }]}
          onPress={() => navigateTo(pickupLat, pickupLng, pickupName)}
          activeOpacity={0.7}
        >
          <View style={[styles.miniDot, { backgroundColor: colors.success }]} />
          <Text style={[styles.secondaryBtnText, { color: colors.text }]}>
            {userLocation ? 'Navigate from here → Pickup' : 'Navigate to Pickup'}
          </Text>
          <Ionicons name="open-outline" size={16} color={colors.textMuted} />
        </TouchableOpacity>

        <TouchableOpacity
          testID="dropoff-navigate-btn"
          style={[styles.secondaryBtn, { backgroundColor: colors.bgElevated, borderColor: colors.border, borderWidth: 1 }]}
          onPress={() => navigateTo(dropoffLat, dropoffLng, dropoffName)}
          activeOpacity={0.7}
        >
          <View style={[styles.miniDot, { backgroundColor: colors.brand }]} />
          <Text style={[styles.secondaryBtnText, { color: colors.text }]}>
            {userLocation ? 'Navigate from here → Drop-off' : 'Navigate to Drop-off'}
          </Text>
          <Ionicons name="open-outline" size={16} color={colors.textMuted} />
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
  bannerWrap: { paddingHorizontal: 24, paddingTop: 4, paddingBottom: 8 },
  locOk: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#e6f9ed', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  locOkText: { fontSize: 12, fontWeight: '600', color: '#0a5d2b' },
  locLoading: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#f0f8ff', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  locLoadingText: { fontSize: 12, fontWeight: '600', color: '#0a5dff' },
  locDenied: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff5e6', borderWidth: 1, borderColor: '#ffd48a', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10 },
  locDeniedTitle: { fontSize: 13, fontWeight: '800', color: '#a05a00' },
  locDeniedSub: { fontSize: 11, color: '#b87600', marginTop: 2 },
  routeVisual: { paddingHorizontal: 24, paddingTop: 8 },
  locationCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 16, padding: 16, gap: 14 },
  locationCardSelf: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F0F8FF', borderRadius: 16, padding: 16, gap: 14, borderWidth: 1, borderColor: '#cfe3ff' },
  pinLineWrap: { alignItems: 'center', width: 20 },
  pinDot: { width: 16, height: 16, borderRadius: 8 },
  pinLine: { width: 2, height: 20, backgroundColor: '#E5E5E5', marginTop: 4 },
  locationInfo: { flex: 1 },
  locationLabel: { fontSize: 10, fontWeight: '800', color: '#999', letterSpacing: 1, marginBottom: 4 },
  locationName: { fontSize: 16, fontWeight: '700', color: '#0A0A0A' },
  locationCoords: { fontSize: 11, color: '#BBB', marginTop: 3 },
  distanceText: { fontSize: 11, color: '#007AFF', fontWeight: '700' },
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
