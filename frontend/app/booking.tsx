import { useState, useEffect, useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Alert, Platform, TextInput } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DatePickerField from '../components/DatePickerField';
import { t as tr } from '../src/i18n';

import { BACKEND_URL } from '../src/config';

export default function BookingScreen() {
  const { carId } = useLocalSearchParams<{ carId: string }>();
  const [car, setCar] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'stripe'>('cash');
  const [taxRate, setTaxRate] = useState(0);
  const [locMinDays, setLocMinDays] = useState(1);
  // Promo code state
  const [promoInput, setPromoInput] = useState('');
  const [appliedPromo, setAppliedPromo] = useState<{ code: string; discount: number; type: string; value: number } | null>(null);
  const [validatingPromo, setValidatingPromo] = useState(false);
  const router = useRouter();

  // Default dates: tomorrow pickup, dropoff respects min_booking_days when known
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

  // Min booking days now comes from the LOCATION (set in admin panel),
  // with a fallback to car's legacy field, then 1.
  const minDays = (locMinDays && locMinDays > 0)
    ? locMinDays
    : ((car?.min_booking_days && car.min_booking_days > 0) ? car.min_booking_days : 1);

  // When the car loads, auto-extend dropoff to satisfy min_booking_days if needed
  useEffect(() => {
    if (!car) return;
    const cur = Math.max(1, Math.ceil((dropoffDate.getTime() - pickupDate.getTime()) / 86400000));
    if (cur < minDays) {
      const d = new Date(pickupDate);
      d.setDate(d.getDate() + minDays);
      setDropoffDate(d);
    }
  }, [car?.id, minDays]);

  // Minimum dates
  const minPickup = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const minDropoff = useMemo(() => {
    const d = new Date(pickupDate);
    d.setDate(d.getDate() + minDays);
    return d;
  }, [pickupDate, minDays]);

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
    const sub = parseFloat(total);
    const disc = appliedPromo?.discount ? Number(appliedPromo.discount) : 0;
    const discountedSub = Math.max(sub - disc, 0);
    const tax = discountedSub * (taxRate / 100);
    return (discountedSub + tax).toFixed(2);
  }, [total, taxRate, appliedPromo]);

  const discountedSubtotal = useMemo(() => {
    const sub = parseFloat(total);
    const disc = appliedPromo?.discount ? Number(appliedPromo.discount) : 0;
    return Math.max(sub - disc, 0).toFixed(2);
  }, [total, appliedPromo]);

  const recomputedTax = useMemo(() => {
    return (parseFloat(discountedSubtotal) * (taxRate / 100)).toFixed(2);
  }, [discountedSubtotal, taxRate]);

  const applyPromo = async () => {
    const code = promoInput.trim().toUpperCase();
    if (!code) { Alert.alert('Promo code', 'Please enter a code.'); return; }
    setValidatingPromo(true);
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const res = await fetch(`${BACKEND_URL}/api/promo-codes/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ code, subtotal: parseFloat(total) }),
      });
      const data = await res.json();
      if (data.valid) {
        setAppliedPromo({
          code: data.code,
          discount: Number(data.discount) || 0,
          type: data.discount_type,
          value: Number(data.discount_value) || 0,
        });
      } else {
        setAppliedPromo(null);
        Alert.alert('Promo code', data.message || 'Invalid promo code');
      }
    } catch (e: any) {
      Alert.alert('Promo code', e?.message || 'Could not validate code');
    }
    setValidatingPromo(false);
  };

  const removePromo = () => { setAppliedPromo(null); setPromoInput(''); };

  // When pickup changes, ensure dropoff respects min_booking_days
  const handlePickupChange = (newDate: Date) => {
    setPickupDate(newDate);
    const minDrop = new Date(newDate);
    minDrop.setDate(minDrop.getDate() + minDays);
    if (dropoffDate < minDrop) {
      setDropoffDate(minDrop);
    }
  };

  const handleDropoffChange = (newDate: Date) => {
    const minDrop = new Date(pickupDate);
    minDrop.setDate(minDrop.getDate() + minDays);
    if (newDate < minDrop) {
      Alert.alert(
        tr('error'),
        minDays > 1
          ? `${tr('error')}: minimum ${minDays} ${minDays === 1 ? tr('day') : tr('days')}`
          : 'Drop-off date must be after pickup date'
      );
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
        }
      } catch (e) { console.log(e); }
      setLoading(false);
    };
    if (carId) fetchCar();
  }, [carId]);

  // Tax rate refreshes whenever the car's pickup location changes
  useEffect(() => {
    const locName = car?.pickup_location?.name;
    if (!locName) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        const taxRes = await fetch(
          `${BACKEND_URL}/api/locations/tax-by-name?name=${encodeURIComponent(locName)}`,
          { signal: ctrl.signal }
        );
        if (taxRes.ok) {
          const taxData = await taxRes.json();
          setTaxRate(Number(taxData.tax_rate) || 0);
          setLocMinDays(Number(taxData.min_booking_days) || 1);
        } else {
          setTaxRate(0);
          setLocMinDays(1);
        }
      } catch (e: any) {
        if (e?.name !== 'AbortError') console.log('Tax fetch error:', e);
      }
    })();
    return () => ctrl.abort();
  }, [car?.pickup_location?.name]);

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
          promo_code: appliedPromo?.code || null,
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
        <Text style={styles.topTitle}>{tr('confirmBooking')}</Text>
        <View style={{ width: 44 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.carSummary}>
          <View style={{ flex: 1 }}>
            <Text style={styles.carName}>{car.name}</Text>
            <Text style={styles.carSub}>{car.year} {car.brand}</Text>
          </View>
          <Text style={styles.priceTag}>${car.price_per_day}<Text style={styles.priceUnit}>{tr('perDay')}</Text></Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{tr('rentalDetails')}</Text>
          {minDays > 1 && (
            <View style={styles.minDaysBanner}>
              <Ionicons name="information-circle-outline" size={16} color="#FF9500" />
              <Text style={styles.minDaysText}>
                {tr('language') === 'Idioma'
                  ? `Reserva mínima: ${minDays} días`
                  : `Minimum rental: ${minDays} days`}
              </Text>
            </View>
          )}
          <View style={styles.datePickerGroup}>
            <DatePickerField
              date={pickupDate}
              onDateChange={handlePickupChange}
              minimumDate={minPickup}
              label={tr('pickup')}
              accentColor="#34C759"
            />
            <View style={styles.dateArrow}>
              <Ionicons name="arrow-down" size={20} color="#999" />
              <Text style={styles.daysLabel}>{days} {days !== 1 ? tr('days') : tr('day')}</Text>
            </View>
            <DatePickerField
              date={dropoffDate}
              onDateChange={handleDropoffChange}
              minimumDate={minDropoff}
              label={tr('dropoff')}
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
                <Text style={styles.locationText}>{tr('pickupLocation')} & GPS</Text>
                <Ionicons name="chevron-forward" size={16} color="#007AFF" />
              </TouchableOpacity>
            )}
          </View>
        )}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{tr('paymentMethod')}</Text>
          <View style={styles.paymentOptions}>
            <TouchableOpacity
              testID="payment-cash-btn"
              style={[styles.paymentOption, paymentMethod === 'cash' && styles.paymentOptionActive]}
              onPress={() => setPaymentMethod('cash')}
            >
              <Ionicons name="cash-outline" size={24} color={paymentMethod === 'cash' ? '#FF3B30' : '#666'} />
              <Text style={[styles.paymentLabel, paymentMethod === 'cash' && styles.paymentLabelActive]}>{tr('cash')}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="payment-stripe-btn"
              style={[styles.paymentOption, paymentMethod === 'stripe' && styles.paymentOptionActive]}
              onPress={() => setPaymentMethod('stripe')}
            >
              <Ionicons name="card-outline" size={24} color={paymentMethod === 'stripe' ? '#FF3B30' : '#666'} />
              <Text style={[styles.paymentLabel, paymentMethod === 'stripe' && styles.paymentLabelActive]}>{tr('card')}</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🎟️ Promo Code</Text>
          {appliedPromo ? (
            <View style={styles.promoApplied}>
              <Ionicons name="checkmark-circle" size={20} color="#34c759" />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.promoCode}>{appliedPromo.code}</Text>
                <Text style={styles.promoSub}>
                  {appliedPromo.type === 'percent' ? `${appliedPromo.value}% off` : `$${appliedPromo.value} off`} · You save ${appliedPromo.discount.toFixed(2)}
                </Text>
              </View>
              <TouchableOpacity onPress={removePromo} style={styles.promoRemoveBtn}>
                <Text style={styles.promoRemoveText}>Remove</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.promoRow}>
              <TextInput
                style={styles.promoInput}
                value={promoInput}
                onChangeText={(t) => setPromoInput(t.toUpperCase())}
                placeholder="Enter code"
                placeholderTextColor="#999"
                autoCapitalize="characters"
                autoCorrect={false}
              />
              <TouchableOpacity
                style={[styles.promoApplyBtn, validatingPromo && { opacity: 0.5 }]}
                onPress={applyPromo}
                disabled={validatingPromo}
              >
                {validatingPromo ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.promoApplyText}>Apply</Text>}
              </TouchableOpacity>
            </View>
          )}
        </View>

        <View style={styles.summary}>
          <Text style={styles.summaryTitle}>{tr('costBreakdown')}</Text>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{car.name}</Text>
            <Text style={styles.summaryValue}>${car.price_per_day}{tr('perDay')}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{tr('duration')}</Text>
            <Text style={styles.summaryValue}>{days} {days !== 1 ? tr('days') : tr('day')}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{tr('pickup')}</Text>
            <Text style={styles.summaryValue}>{pickupDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{tr('dropoff')}</Text>
            <Text style={styles.summaryValue}>{dropoffDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{tr('subtotal')}</Text>
            <Text style={styles.summaryValue}>${total}</Text>
          </View>
          {appliedPromo && (
            <View style={styles.summaryRow}>
              <Text style={[styles.summaryLabel, { color: '#ff2d92', fontWeight: '700' }]}>
                🎟️ {appliedPromo.code} ({appliedPromo.type === 'percent' ? `${appliedPromo.value}%` : `$${appliedPromo.value}`})
              </Text>
              <Text style={[styles.summaryValue, { color: '#ff2d92', fontWeight: '700' }]}>
                −${appliedPromo.discount.toFixed(2)}
              </Text>
            </View>
          )}
          {taxRate > 0 ? (
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>{tr('tax')} ({taxRate}%)</Text>
              <Text style={styles.summaryValue}>${appliedPromo ? recomputedTax : taxAmount}</Text>
            </View>
          ) : (
            <View style={styles.summaryRow}>
              <Text style={[styles.summaryLabel, { color: '#999' }]}>{tr('tax')} (0%)</Text>
              <Text style={[styles.summaryValue, { color: '#999' }]}>$0.00</Text>
            </View>
          )}
          <View style={[styles.summaryRow, styles.totalRow]}>
            <Text style={styles.totalLabel}>{tr('total')}</Text>
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
              {paymentMethod === 'stripe' ? `${tr('pay')} $${grandTotal}` : tr('confirmBooking')}
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
  minDaysBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FFF8E5', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginBottom: 12 },
  minDaysText: { fontSize: 13, color: '#8a6500', fontWeight: '600' },
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
  promoRow: { flexDirection: 'row', gap: 10 },
  promoInput: { flex: 1, backgroundColor: '#F5F5F5', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, fontWeight: '600', color: '#0A0A0A', letterSpacing: 1 },
  promoApplyBtn: { backgroundColor: '#ff2d92', paddingHorizontal: 20, justifyContent: 'center', borderRadius: 12, minWidth: 80, alignItems: 'center' },
  promoApplyText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  promoApplied: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#e6f9ed', borderRadius: 12, padding: 14 },
  promoCode: { fontWeight: '800', fontSize: 14, color: '#0A0A0A', letterSpacing: 1 },
  promoSub: { fontSize: 12, color: '#34c759', marginTop: 2, fontWeight: '600' },
  promoRemoveBtn: { paddingHorizontal: 10, paddingVertical: 6 },
  promoRemoveText: { color: '#FF3B30', fontWeight: '700', fontSize: 13 },
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
