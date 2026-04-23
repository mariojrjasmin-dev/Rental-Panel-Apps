import { useState, useEffect, useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Alert, Platform } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DatePickerField from '../components/DatePickerField';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export default function BookingScreen() {
  const { carId } = useLocalSearchParams<{ carId: string }>();
  const [car, setCar] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'stripe'>('cash');
  const [taxRate, setTaxRate] = useState(0);
  const router = useRouter();

  // Default dates: tomorrow pickup, 3 days later dropoff
  const [pickupDate, setPickupDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [dropoffDate, setDropoffDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 4);
    d.setHours(0, 0, 0, 0);
    return d;
  });

  // Minimum dates
  const minPickup = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const minDropoff = useMemo(() => {
    const d = new Date(pickupDate);
    d.setDate(d.getDate() + 1);
    return d;
  }, [pickupDate]);

  // Calculate days and total dynamically
  const days = useMemo(() => {
    const diff = dropoffDate.getTime() - pickupDate.getTime();
    return Math.max(1, Math.ceil(diff / (1000 * 60 * 60 * 24)));
  }, [pickupDate, dropoffDate]);

  const total = useMemo(() => {
    if (!car) return '0.00';
    return (days * car.price_per_day).toFixed(2);
  }, [days, car]);

  const taxAmount = useMemo(() => {
    if (!car || taxRate <= 0) return '0.00';
    return ((days * car.price_per_day) * (taxRate / 100)).toFixed(2);
  }, [days, car, taxRate]);

  const grandTotal = useMemo(() => {
    return (parseFloat(total) + parseFloat(taxAmount)).toFixed(2);
  }, [total, taxAmount]);

  // When pickup changes, ensure dropoff is after pickup
  const handlePickupChange = (newDate: Date) => {
    setPickupDate(newDate);
    const nextDay = new Date(newDate);
    nextDay.setDate(nextDay.getDate() + 1);
    if (dropoffDate <= newDate) {
      setDropoffDate(nextDay);
    }
  };

  const handleDropoffChange = (newDate: Date) => {
    if (newDate <= pickupDate) {
      Alert.alert('Invalid Date', 'Drop-off date must be after pickup date');
      return;
    }
    setDropoffDate(newDate);
  };

  useEffect(() => {
    const fetchCar = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/cars/${carId}`);
        if (res.ok) {
          const carData = await res.json();
          setCar(carData);
          // Fetch tax rate from pickup location
          if (carData.pickup_location?.name) {
            try {
              const taxRes = await fetch(`${BACKEND_URL}/api/locations/tax-by-name?name=${encodeURIComponent(carData.pickup_location.name)}`);
              if (taxRes.ok) {
                const taxData = await taxRes.json();
                setTaxRate(taxData.tax_rate || 0);
              }
            } catch (e) { console.log('Tax fetch error:', e); }
          }
        }
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
      const pickupStr = pickupDate.toISOString().split('T')[0];
      const dropoffStr = dropoffDate.toISOString().split('T')[0];

      const res = await fetch(`${BACKEND_URL}/api/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          car_id: carId,
          pickup_date: pickupStr,
          dropoff_date: dropoffStr,
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
        const originUrl = typeof window !== 'undefined' ? window.location.origin : '';
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
    return <SafeAreaView style={styles.center}><Text style={{ fontSize: 16, color: '#666' }}>Car not found</Text></SafeAreaView>;
  }

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
          <View style={styles.datePickerGroup}>
            <DatePickerField
              date={pickupDate}
              onDateChange={handlePickupChange}
              minimumDate={minPickup}
              label="Pick Up"
              accentColor="#34C759"
            />
            <View style={styles.dateArrow}>
              <Ionicons name="arrow-down" size={20} color="#999" />
              <Text style={styles.daysLabel}>{days} day{days !== 1 ? 's' : ''}</Text>
            </View>
            <DatePickerField
              date={dropoffDate}
              onDateChange={handleDropoffChange}
              minimumDate={minDropoff}
              label="Drop Off"
              accentColor="#FF3B30"
            />
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
            <Text style={styles.summaryValue}>{days} day{days !== 1 ? 's' : ''}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Pickup</Text>
            <Text style={styles.summaryValue}>{pickupDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Drop-off</Text>
            <Text style={styles.summaryValue}>{dropoffDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Subtotal</Text>
            <Text style={styles.summaryValue}>${total}</Text>
          </View>
          {taxRate > 0 && (
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Tax ({taxRate}%)</Text>
              <Text style={styles.summaryValue}>${taxAmount}</Text>
            </View>
          )}
          <View style={[styles.summaryRow, styles.totalRow]}>
            <Text style={styles.totalLabel}>Total</Text>
            <Text style={styles.totalValue}>${grandTotal}</Text>
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
              {paymentMethod === 'stripe' ? `Pay $${grandTotal}` : `Confirm Booking`}
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
  datePickerGroup: { gap: 8 },
  dateArrow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 4 },
  daysLabel: { fontSize: 13, fontWeight: '700', color: '#999' },
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
