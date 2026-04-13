import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Alert, Platform } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export default function BookingScreen() {
  const { carId } = useLocalSearchParams<{ carId: string }>();
  const [car, setCar] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'stripe'>('cash');
  const router = useRouter();

  // Default dates: tomorrow pickup, day after dropoff
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const dayAfter = new Date();
  dayAfter.setDate(dayAfter.getDate() + 3);

  const [pickupDate] = useState(tomorrow.toISOString().split('T')[0]);
  const [dropoffDate] = useState(dayAfter.toISOString().split('T')[0]);

  const days = Math.max(1, Math.ceil((dayAfter.getTime() - tomorrow.getTime()) / (1000 * 60 * 60 * 24)));

  useEffect(() => {
    const fetchCar = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/cars/${carId}`);
        if (res.ok) setCar(await res.json());
      } catch (e) { console.log(e); }
      setLoading(false);
    };
    if (carId) fetchCar();
  }, [carId]);

  const handleBooking = async () => {
    if (!car) return;
    setBooking(true);
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const res = await fetch(`${BACKEND_URL}/api/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          car_id: carId,
          pickup_date: pickupDate,
          dropoff_date: dropoffDate,
          pickup_location: car.pickup_location || { name: 'TBD', lat: 0, lng: 0 },
          dropoff_location: car.dropoff_location || { name: 'TBD', lat: 0, lng: 0 },
          payment_method: paymentMethod,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        Alert.alert('Error', typeof err.detail === 'string' ? err.detail : 'Booking failed');
        setBooking(false);
        return;
      }

      const bookingData = await res.json();

      if (paymentMethod === 'stripe') {
        // Create Stripe checkout
        const originUrl = typeof window !== 'undefined' ? window.location.origin : BACKEND_URL;
        const checkoutRes = await fetch(`${BACKEND_URL}/api/payments/checkout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ booking_id: bookingData.id, origin_url: originUrl }),
        });

        if (checkoutRes.ok) {
          const checkoutData = await checkoutRes.json();
          if (typeof window !== 'undefined' && checkoutData.url) {
            window.location.href = checkoutData.url;
            return;
          }
        }
        Alert.alert('Payment', 'Unable to start payment. Booking created as pending.');
      } else {
        router.replace({ pathname: '/booking-success', params: { bookingId: bookingData.id } });
      }
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Something went wrong');
    }
    setBooking(false);
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color="#FF3B30" /></View>;
  }

  if (!car) {
    return <SafeAreaView style={styles.center}><Text>Car not found</Text></SafeAreaView>;
  }

  const total = (days * car.price_per_day).toFixed(2);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.topBar}>
        <TouchableOpacity testID="booking-back-btn" onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
        </TouchableOpacity>
        <Text style={styles.topTitle}>Book Vehicle</Text>
        <View style={{ width: 44 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.carSummary}>
          <View style={{ flex: 1 }}>
            <Text style={styles.carName}>{car.name}</Text>
            <Text style={styles.carSub}>{car.year} {car.brand}</Text>
          </View>
          <Text style={styles.priceTag}>${car.price_per_day}<Text style={styles.priceUnit}>/day</Text></Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Rental Period</Text>
          <View style={styles.dateCards}>
            <View style={styles.dateCard}>
              <Ionicons name="calendar-outline" size={20} color="#34C759" />
              <View>
                <Text style={styles.dateLabel}>PICK UP</Text>
                <Text style={styles.dateValue}>{new Date(pickupDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</Text>
              </View>
            </View>
            <View style={styles.dateSep}><Ionicons name="arrow-forward" size={16} color="#999" /></View>
            <View style={styles.dateCard}>
              <Ionicons name="calendar-outline" size={20} color="#FF3B30" />
              <View>
                <Text style={styles.dateLabel}>DROP OFF</Text>
                <Text style={styles.dateValue}>{new Date(dropoffDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</Text>
              </View>
            </View>
          </View>
        </View>

        {(car.pickup_location || car.dropoff_location) && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Locations</Text>
            {car.pickup_location && (
              <TouchableOpacity
                testID="booking-map-btn"
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
                <Ionicons name="navigate-outline" size={20} color="#007AFF" />
                <Text style={styles.locationText}>View Map & Directions</Text>
                <Ionicons name="chevron-forward" size={16} color="#007AFF" />
              </TouchableOpacity>
            )}
          </View>
        )}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Payment Method</Text>
          <View style={styles.paymentOptions}>
            <TouchableOpacity
              testID="payment-cash-btn"
              style={[styles.paymentOption, paymentMethod === 'cash' && styles.paymentOptionActive]}
              onPress={() => setPaymentMethod('cash')}
            >
              <Ionicons name="cash-outline" size={24} color={paymentMethod === 'cash' ? '#FF3B30' : '#666'} />
              <Text style={[styles.paymentLabel, paymentMethod === 'cash' && styles.paymentLabelActive]}>Cash</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="payment-stripe-btn"
              style={[styles.paymentOption, paymentMethod === 'stripe' && styles.paymentOptionActive]}
              onPress={() => setPaymentMethod('stripe')}
            >
              <Ionicons name="card-outline" size={24} color={paymentMethod === 'stripe' ? '#FF3B30' : '#666'} />
              <Text style={[styles.paymentLabel, paymentMethod === 'stripe' && styles.paymentLabelActive]}>Card</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.summary}>
          <Text style={styles.summaryTitle}>Order Summary</Text>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{car.name}</Text>
            <Text style={styles.summaryValue}>${car.price_per_day}/day</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Duration</Text>
            <Text style={styles.summaryValue}>{days} day{days > 1 ? 's' : ''}</Text>
          </View>
          <View style={[styles.summaryRow, styles.totalRow]}>
            <Text style={styles.totalLabel}>Total</Text>
            <Text style={styles.totalValue}>${total}</Text>
          </View>
        </View>
      </ScrollView>

      <View style={styles.bottomBar}>
        <TouchableOpacity
          testID="confirm-booking-btn"
          style={styles.confirmBtn}
          onPress={handleBooking}
          disabled={booking}
          activeOpacity={0.7}
        >
          {booking ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <Text style={styles.confirmBtnText}>
              {paymentMethod === 'stripe' ? `Pay $${total}` : `Confirm Booking`}
            </Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFF' },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  topTitle: { fontSize: 18, fontWeight: '800', color: '#0A0A0A' },
  scroll: { paddingHorizontal: 24, paddingBottom: 120 },
  carSummary: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: '#E5E5E5', marginBottom: 24 },
  carName: { fontSize: 20, fontWeight: '900', color: '#0A0A0A' },
  carSub: { fontSize: 14, color: '#666', marginTop: 2 },
  priceTag: { fontSize: 22, fontWeight: '900', color: '#FF3B30' },
  priceUnit: { fontSize: 13, fontWeight: '400', color: '#999' },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: '#0A0A0A', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 },
  dateCards: { flexDirection: 'row', alignItems: 'center' },
  dateCard: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#F5F5F5', padding: 14, borderRadius: 14 },
  dateSep: { marginHorizontal: 8 },
  dateLabel: { fontSize: 10, color: '#999', fontWeight: '700', letterSpacing: 0.5 },
  dateValue: { fontSize: 14, fontWeight: '700', color: '#0A0A0A' },
  locationRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#F0F8FF', padding: 16, borderRadius: 14 },
  locationText: { flex: 1, fontSize: 15, fontWeight: '600', color: '#007AFF' },
  paymentOptions: { flexDirection: 'row', gap: 12 },
  paymentOption: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 20, borderRadius: 16, backgroundColor: '#F5F5F5', borderWidth: 2, borderColor: 'transparent' },
  paymentOptionActive: { borderColor: '#FF3B30', backgroundColor: '#FFF0F0' },
  paymentLabel: { fontSize: 15, fontWeight: '700', color: '#666' },
  paymentLabelActive: { color: '#FF3B30' },
  summary: { backgroundColor: '#F5F5F5', borderRadius: 20, padding: 20, gap: 12 },
  summaryTitle: { fontSize: 16, fontWeight: '800', color: '#0A0A0A', marginBottom: 4 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between' },
  summaryLabel: { fontSize: 14, color: '#666' },
  summaryValue: { fontSize: 14, fontWeight: '600', color: '#0A0A0A' },
  totalRow: { borderTopWidth: 1, borderTopColor: '#E5E5E5', paddingTop: 12, marginTop: 4 },
  totalLabel: { fontSize: 18, fontWeight: '800', color: '#0A0A0A' },
  totalValue: { fontSize: 24, fontWeight: '900', color: '#FF3B30' },
  bottomBar: { position: 'absolute', bottom: 0, left: 0, right: 0, paddingHorizontal: 24, paddingVertical: 16, paddingBottom: 32, backgroundColor: '#FFF', borderTopWidth: 1, borderTopColor: '#E5E5E5' },
  confirmBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', justifyContent: 'center' },
  confirmBtnText: { color: '#FFF', fontSize: 18, fontWeight: '700' },
});
