import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Image, ActivityIndicator, Dimensions } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const { width } = Dimensions.get('window');

export default function CarDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [car, setCar] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const fetchCar = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/cars/${id}`);
        if (res.ok) setCar(await res.json());
      } catch (e) {
        console.log('Fetch car error:', e);
      }
      setLoading(false);
    };
    if (id) fetchCar();
  }, [id]);

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color="#FF3B30" /></View>;
  }

  if (!car) {
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.errorText}>Car not found</Text>
        <TouchableOpacity onPress={() => router.back()}><Text style={styles.backLink}>Go Back</Text></TouchableOpacity>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        <View style={styles.heroContainer}>
          <Image source={{ uri: car.image_url }} style={styles.heroImage} resizeMode="cover" />
          <SafeAreaView style={styles.heroOverlay} edges={['top']}>
            <TouchableOpacity testID="back-button" style={styles.backBtn} onPress={() => router.back()}>
              <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
            </TouchableOpacity>
          </SafeAreaView>
        </View>

        <View style={styles.content}>
          <View style={styles.titleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.carName}>{car.name}</Text>
              <Text style={styles.carYear}>{car.year} {car.brand}</Text>
            </View>
            <View style={styles.categoryTag}>
              <Text style={styles.categoryTagText}>{car.category}</Text>
            </View>
          </View>

          <View style={styles.specsGrid}>
            <View style={styles.specCard}>
              <Ionicons name="people-outline" size={24} color="#FF3B30" />
              <Text style={styles.specValue}>{car.seats}</Text>
              <Text style={styles.specLabel}>Seats</Text>
            </View>
            <View style={styles.specCard}>
              <Ionicons name="cog-outline" size={24} color="#FF3B30" />
              <Text style={styles.specValue}>{car.transmission}</Text>
              <Text style={styles.specLabel}>Transmission</Text>
            </View>
            <View style={styles.specCard}>
              <Ionicons name="flash-outline" size={24} color="#FF3B30" />
              <Text style={styles.specValue}>{car.fuel_type}</Text>
              <Text style={styles.specLabel}>Fuel</Text>
            </View>
          </View>

          {car.description ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>About</Text>
              <Text style={styles.description}>{car.description}</Text>
            </View>
          ) : null}

          {(car.pickup_location || car.dropoff_location) && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Locations</Text>
              {car.pickup_location && (
                <TouchableOpacity
                  testID="pickup-location-btn"
                  style={styles.locationRow}
                  onPress={() => router.push({
                    pathname: '/map-view',
                    params: {
                      pickupLat: car.pickup_location.lat,
                      pickupLng: car.pickup_location.lng,
                      pickupName: car.pickup_location.name,
                      dropoffLat: car.dropoff_location?.lat,
                      dropoffLng: car.dropoff_location?.lng,
                      dropoffName: car.dropoff_location?.name,
                    }
                  })}
                >
                  <View style={styles.locationIcon}>
                    <Ionicons name="location" size={18} color="#34C759" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.locationLabel}>Pickup</Text>
                    <Text style={styles.locationName}>{car.pickup_location.name}</Text>
                  </View>
                  <Ionicons name="map-outline" size={20} color="#007AFF" />
                </TouchableOpacity>
              )}
              {car.dropoff_location && (
                <TouchableOpacity
                  testID="dropoff-location-btn"
                  style={styles.locationRow}
                  onPress={() => router.push({
                    pathname: '/map-view',
                    params: {
                      pickupLat: car.pickup_location?.lat,
                      pickupLng: car.pickup_location?.lng,
                      pickupName: car.pickup_location?.name,
                      dropoffLat: car.dropoff_location.lat,
                      dropoffLng: car.dropoff_location.lng,
                      dropoffName: car.dropoff_location.name,
                    }
                  })}
                >
                  <View style={[styles.locationIcon, { backgroundColor: '#FFF0F0' }]}>
                    <Ionicons name="location" size={18} color="#FF3B30" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.locationLabel}>Drop-off</Text>
                    <Text style={styles.locationName}>{car.dropoff_location.name}</Text>
                  </View>
                  <Ionicons name="map-outline" size={20} color="#007AFF" />
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>
      </ScrollView>

      <View style={styles.bottomBar}>
        <View>
          <Text style={styles.bottomPrice}>${car.price_per_day}</Text>
          <Text style={styles.bottomPriceUnit}>per day</Text>
        </View>
        <TouchableOpacity
          testID="book-now-button"
          style={styles.bookBtn}
          activeOpacity={0.7}
          onPress={() => router.push({ pathname: '/booking', params: { carId: car.id } })}
        >
          <Text style={styles.bookBtnText}>Book Now</Text>
          <Ionicons name="arrow-forward" size={20} color="#FFF" />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFF' },
  errorText: { fontSize: 18, color: '#666' },
  backLink: { fontSize: 16, color: '#FF3B30', marginTop: 8 },
  scrollContent: { paddingBottom: 100 },
  heroContainer: { width, height: 280, backgroundColor: '#F5F5F5' },
  heroImage: { width: '100%', height: '100%' },
  heroOverlay: { position: 'absolute', top: 0, left: 0, right: 0 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF', justifyContent: 'center', alignItems: 'center', marginLeft: 16, marginTop: 8, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4, elevation: 3 },
  content: { paddingHorizontal: 24, paddingTop: 20 },
  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 },
  carName: { fontSize: 28, fontWeight: '900', color: '#0A0A0A', letterSpacing: -0.5 },
  carYear: { fontSize: 15, color: '#666', marginTop: 2 },
  categoryTag: { backgroundColor: '#0A0A0A', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 50 },
  categoryTagText: { color: '#FFF', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1 },
  specsGrid: { flexDirection: 'row', gap: 12, marginBottom: 24 },
  specCard: { flex: 1, backgroundColor: '#F5F5F5', borderRadius: 16, padding: 16, alignItems: 'center', gap: 6 },
  specValue: { fontSize: 15, fontWeight: '700', color: '#0A0A0A' },
  specLabel: { fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: '#0A0A0A', marginBottom: 12 },
  description: { fontSize: 15, color: '#666', lineHeight: 24 },
  locationRow: { flexDirection: 'row', alignItems: 'center', padding: 14, backgroundColor: '#F5F5F5', borderRadius: 14, marginBottom: 8, gap: 12 },
  locationIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#F0FFF4', justifyContent: 'center', alignItems: 'center' },
  locationLabel: { fontSize: 11, color: '#999', textTransform: 'uppercase', fontWeight: '700', letterSpacing: 0.5 },
  locationName: { fontSize: 15, fontWeight: '600', color: '#0A0A0A' },
  bottomBar: { position: 'absolute', bottom: 0, left: 0, right: 0, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 24, paddingVertical: 16, paddingBottom: 32, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#E5E5E5' },
  bottomPrice: { fontSize: 26, fontWeight: '900', color: '#0A0A0A' },
  bottomPriceUnit: { fontSize: 13, color: '#999' },
  bookBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FF3B30', paddingHorizontal: 28, paddingVertical: 16, borderRadius: 50 },
  bookBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
});
