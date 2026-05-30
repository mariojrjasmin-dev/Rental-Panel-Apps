import { useState, useEffect, useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Alert, Platform, TextInput, Modal, Switch } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DatePickerField from '../components/DatePickerField';
import { t as tr } from '../src/i18n';
import { useTheme } from '../src/theme';
import { taxLabel } from '../src/tax';

import { BACKEND_URL } from '../src/config';

export default function BookingScreen() {
  const { colors } = useTheme();
  const { carId } = useLocalSearchParams<{ carId: string }>();
  const [car, setCar] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  // 💳 Card payment via Stripe is currently HIDDEN on the customer app.
  // Flip this to `true` to re-enable the on-app card option.
  const SHOW_CARD_PAYMENT = false;
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'stripe'>('cash');
  const [taxRate, setTaxRate] = useState(0);
  const [locMinDays, setLocMinDays] = useState(1);
  const [insuranceIncluded, setInsuranceIncluded] = useState(false);
  const [refuelAmount, setRefuelAmount] = useState(0);
  const [refuelOptedIn, setRefuelOptedIn] = useState(false);
  // Per-location mileage policy (returned by /locations/tax-by-name)
  const [unlimitedMileage, setUnlimitedMileage] = useState(true);
  const [mileageLimitPerDay, setMileageLimitPerDay] = useState(0);
  const [extraMileageCharge, setExtraMileageCharge] = useState(0);
  // Multi-location: customer picks from the allowed pickup/dropoff lists.
  // Default to the first entry; resets when the car changes.
  type LocOpt = { name: string; lat: number; lng: number; country?: string; city?: string };
  const [selectedPickup, setSelectedPickup] = useState<LocOpt | null>(null);
  const [selectedDropoff, setSelectedDropoff] = useState<LocOpt | null>(null);
  // Country lookup: name → country (used to enforce same-country pickup/dropoff)
  const [pickupCountry, setPickupCountry] = useState<string>('');
  // Per-location metadata lookup, prefetched on mount, so we can hydrate
  // tax rate / country / mileage policy INSTANTLY when the user taps a chip
  // (no waiting for /tax-by-name to come back).
  const [countryByName, setCountryByName] = useState<Record<string, string>>({});
  const [locMetaByName, setLocMetaByName] = useState<Record<string, {
    tax_rate: number;
    country: string;
    min_booking_days: number;
    insurance_included: boolean;
    refuel_amount: number;
    unlimited_mileage: boolean;
    mileage_limit_per_day: number;
    extra_mileage_charge: number;
  }>>({});
  // Rental terms state
  const [termsText, setTermsText] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [termsModalVisible, setTermsModalVisible] = useState(false);
  // Final confirmation modal — shown right before the booking is actually
  // submitted so the customer gets one explicit chance to review the
  // reservation summary (car, dates, locations, price, payment method).
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
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
    const refuel = (refuelOptedIn && refuelAmount > 0) ? refuelAmount : 0;
    const taxable = discountedSub + refuel;
    const tax = taxable * (taxRate / 100);
    return (taxable + tax).toFixed(2);
  }, [total, taxRate, appliedPromo, refuelOptedIn, refuelAmount]);

  const discountedSubtotal = useMemo(() => {
    const sub = parseFloat(total);
    const disc = appliedPromo?.discount ? Number(appliedPromo.discount) : 0;
    return Math.max(sub - disc, 0).toFixed(2);
  }, [total, appliedPromo]);

  const recomputedTax = useMemo(() => {
    const refuel = (refuelOptedIn && refuelAmount > 0) ? refuelAmount : 0;
    const taxable = parseFloat(discountedSubtotal) + refuel;
    return (taxable * (taxRate / 100)).toFixed(2);
  }, [discountedSubtotal, taxRate, refuelOptedIn, refuelAmount]);

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

  // Fetch rental terms (global)
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/settings/rental-terms`);
        if (r.ok) {
          const data = await r.json();
          setTermsText(data.terms || '');
        }
      } catch (e) { /* ignore */ }
    })();
  }, []);

  // Fetch the locations catalogue once → build a {name: country} lookup so
  // we can enforce the "same country" rule on the booking screen without
  // making one network call per chip.
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/locations`);
        if (r.ok) {
          const list = await r.json();
          const countryMap: Record<string, string> = {};
          const metaMap: Record<string, any> = {};
          for (const l of (list || [])) {
            const nm = (l?.name || '').trim();
            const co = (l?.country || '').trim();
            if (!nm) continue;
            const key = nm.toLowerCase();
            countryMap[key] = co;
            metaMap[key] = {
              tax_rate: Number(l?.tax_rate) || 0,
              country: co,
              min_booking_days: Number(l?.min_booking_days) || 1,
              insurance_included: Boolean(l?.insurance_included),
              refuel_amount: Number(l?.refuel_amount) || 0,
              unlimited_mileage: l?.unlimited_mileage !== false,
              mileage_limit_per_day: Number(l?.mileage_limit_per_day) || 0,
              extra_mileage_charge: Number(l?.extra_mileage_charge) || 0,
            };
          }
          setCountryByName(countryMap);
          setLocMetaByName(metaMap);
        }
      } catch (e) { /* ignore */ }
    })();
  }, []);

  // When the car loads, default the picker selection to the first allowed
  // pickup/dropoff (or the legacy singular fields for old data). Prefer pickup
  // locations that actually have stock available — never default to a 0-stock one.
  //
  // RULE: drop-off defaults to the SAME location as pickup whenever a
  // matching-name entry exists in dropoff_locations. This reflects the
  // standard "return where you picked up" rental pattern. The customer can
  // still override the drop-off chip if a one-way return is offered.
  useEffect(() => {
    if (!car) return;
    const pickups: LocOpt[] = (car.pickup_locations && car.pickup_locations.length)
      ? car.pickup_locations
      : (car.pickup_location ? [car.pickup_location] : []);
    const dropoffs: LocOpt[] = (car.dropoff_locations && car.dropoff_locations.length)
      ? car.dropoff_locations
      : (car.dropoff_location ? [car.dropoff_location] : []);
    // Helper that reads car.stock without needing the closure-captured one
    const _stockOf = (n?: string) => {
      if (!n) return 0;
      const s = car?.stock;
      if (!s || typeof s !== 'object') return Number(car.units_available ?? 0) || 0;
      return Math.max(0, Number(s[n] ?? 0) || 0);
    };
    let nextPickup: LocOpt | null = selectedPickup;
    if (pickups.length && (!selectedPickup || !pickups.some(p => p.name === selectedPickup.name) || _stockOf(selectedPickup.name) <= 0)) {
      // Prefer the first pickup with stock > 0; fall back to first if none.
      const withStock = pickups.find(p => _stockOf(p.name) > 0);
      nextPickup = withStock || pickups[0];
      setSelectedPickup(nextPickup);
    }
    if (dropoffs.length) {
      // Try to match the pickup name first — same-location return is the default.
      const matchPickup = nextPickup ? dropoffs.find(d => d.name === nextPickup!.name) : undefined;
      if (matchPickup) {
        if (!selectedDropoff || selectedDropoff.name !== matchPickup.name) {
          setSelectedDropoff(matchPickup);
        }
      } else if (!selectedDropoff || !dropoffs.some(d => d.name === selectedDropoff.name)) {
        // No same-name entry available → fall back to the first valid dropoff.
        setSelectedDropoff(dropoffs[0]);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [car?.id]);

  // Keep drop-off in sync with pickup whenever the customer changes pickup.
  // If a same-name drop-off exists for the new pickup, switch to it. This is
  // a user-friendly "return to same location" auto-pair. The customer can
  // still tap a different drop-off chip to override afterwards.
  useEffect(() => {
    if (!car || !selectedPickup) return;
    const dropoffs: LocOpt[] = (car.dropoff_locations && car.dropoff_locations.length)
      ? car.dropoff_locations
      : (car.dropoff_location ? [car.dropoff_location] : []);
    if (!dropoffs.length) return;
    const match = dropoffs.find(d => d.name === selectedPickup.name);
    if (match && (!selectedDropoff || selectedDropoff.name !== match.name)) {
      setSelectedDropoff(match);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPickup?.name, car?.id]);

  // Helper: country for a given location-name (uses the prefetched map).
  const countryFor = (name?: string) => {
    if (!name) return '';
    return (countryByName[name.toLowerCase()] || '').trim();
  };

  // Helper: how many physical units of THIS car are available at the given pickup location.
  // Reads from car.stock (per-location map) returned by GET /api/cars/{id}. Returns 0 if unknown.
  const stockFor = (name?: string): number => {
    if (!name || !car) return 0;
    const s = car.stock;
    if (!s || typeof s !== 'object') {
      // Legacy car without stock map: fall back to the total `units_available`.
      return Number(car.units_available ?? 0) || 0;
    }
    return Math.max(0, Number(s[name] ?? 0) || 0);
  };

  // Low-stock threshold below which we show a warning banner on the booking screen.
  const LOW_STOCK_THRESHOLD = 2;

  // Whenever pickupCountry resolves (or changes), make sure the currently
  // selected dropoff is in the same country. If not, auto-fix to the first
  // compatible dropoff option from the car's allowed list. This prevents
  // the customer from ever ending up with a cross-country selection.
  useEffect(() => {
    if (!car || !pickupCountry) return;
    const dropoffs: LocOpt[] = (car.dropoff_locations && car.dropoff_locations.length)
      ? car.dropoff_locations
      : (car.dropoff_location ? [car.dropoff_location] : []);
    if (!dropoffs.length) return;
    const currentCountry = countryFor(selectedDropoff?.name);
    if (currentCountry && currentCountry.toLowerCase() === pickupCountry.toLowerCase()) return;
    // Find first dropoff in same country
    const sameCountry = dropoffs.find(d => {
      const c = countryFor(d.name);
      return c && c.toLowerCase() === pickupCountry.toLowerCase();
    });
    if (sameCountry) {
      setSelectedDropoff(sameCountry);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickupCountry, car?.id, countryByName]);

  // Tax rate refreshes whenever the *selected* pickup location changes.
  useEffect(() => {
    const locName = selectedPickup?.name;
    if (!locName) return;
    const key = locName.toLowerCase();

    // 🔑 STEP 1 — INSTANT hydration from the prefetched per-location map.
    // This guarantees the cost summary shows the correct tax rate + label in
    // the SAME render cycle as the chip tap, with zero flicker and no
    // "Tax (0%)" loading state.
    const cached = locMetaByName[key];
    if (cached) {
      setTaxRate(cached.tax_rate);
      setLocMinDays(cached.min_booking_days);
      setInsuranceIncluded(cached.insurance_included);
      setRefuelAmount(cached.refuel_amount);
      if (cached.refuel_amount <= 0) setRefuelOptedIn(false);
      setUnlimitedMileage(cached.unlimited_mileage);
      setMileageLimitPerDay(cached.mileage_limit_per_day);
      setExtraMileageCharge(cached.extra_mileage_charge);
      setPickupCountry(cached.country);
    } else if (Object.keys(locMetaByName).length === 0) {
      // 🛡 The locations prefetch hasn't completed yet (cold load race).
      // Do NOT zero-out the tax rate — keep whatever was loaded last so
      // the user never sees a transient "Tax (0%) $0.00" on the very
      // first render. We'll re-run automatically when locMetaByName
      // populates because it's a dependency below.
    } else {
      // Map IS loaded but doesn't contain this pickup name (admin renamed
      // the location or the car has a stale pickup_locations entry). Fall
      // back to the country name map and let the async tax-by-name call
      // below resolve the rate via tolerant matching on the backend.
      const eagerCountry = (countryByName[key] || '').trim();
      setPickupCountry(eagerCountry);
      setTaxRate(0);
    }

    // 🔑 STEP 2 — also do an async refresh from the source-of-truth endpoint
    // in case admin changed tax/refuel after the locations prefetch.
    const ctrl = new AbortController();
    (async () => {
      try {
        const taxRes = await fetch(
          `${BACKEND_URL}/api/locations/tax-by-name?name=${encodeURIComponent(locName)}`,
          { signal: ctrl.signal }
        );
        if (!taxRes.ok) return;
        const taxData = await taxRes.json();
        // Only apply if user hasn't switched away from this pickup yet.
        // (selectedPickup.name might have changed mid-flight; cleanup
        // aborts the request, so we'd never get here in that case.)
        setTaxRate(Number(taxData.tax_rate) || 0);
        setLocMinDays(Number(taxData.min_booking_days) || 1);
        setInsuranceIncluded(Boolean(taxData.insurance_included));
        const refuel = Number(taxData.refuel_amount) || 0;
        setRefuelAmount(refuel);
        if (refuel <= 0) setRefuelOptedIn(false);
        setUnlimitedMileage(taxData.unlimited_mileage !== false);
        setMileageLimitPerDay(Number(taxData.mileage_limit_per_day) || 0);
        setExtraMileageCharge(Number(taxData.extra_mileage_charge) || 0);
        const co = (taxData.country || '').trim();
        if (co) setPickupCountry(co);
      } catch (e: any) {
        if (e?.name !== 'AbortError') console.log('Tax fetch error:', e);
      }
    })();
    return () => ctrl.abort();
  }, [selectedPickup?.name, locMetaByName, countryByName]);

  const handleBooking = async () => {
    if (!car) return;
    if (!termsAccepted) {
      Alert.alert('Terms required', 'Please review and accept the rental terms before confirming.');
      return;
    }
    // Same-country guard (client-side; server enforces the same rule).
    const pCo = countryFor(selectedPickup?.name);
    const dCo = countryFor(selectedDropoff?.name);
    if (pCo && dCo && pCo.toLowerCase() !== dCo.toLowerCase()) {
      Alert.alert(
        'Different country',
        `Pick-up is in ${pCo} but drop-off is in ${dCo}. Rentals are only allowed within the same country.`
      );
      return;
    }
    // Per-location stock guard (client-side; server enforces the same rule).
    const stockLeft = stockFor(selectedPickup?.name);
    if (selectedPickup?.name && stockLeft <= 0) {
      Alert.alert(
        'Out of stock',
        `This vehicle is currently out of stock at ${selectedPickup.name}. Please choose a different pickup location.`
      );
      return;
    }
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
          pickup_location: selectedPickup || car.pickup_location || { name: 'TBD', lat: 0, lng: 0 },
          dropoff_location: selectedDropoff || car.dropoff_location || { name: 'TBD', lat: 0, lng: 0 },
          payment_method: paymentMethod,
          promo_code: appliedPromo?.code || null,
          refuel_opted_in: refuelOptedIn && refuelAmount > 0,
          terms_accepted: true,
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
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
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

        {(() => {
          const pickups: LocOpt[] = (car.pickup_locations && car.pickup_locations.length)
            ? car.pickup_locations
            : (car.pickup_location ? [car.pickup_location] : []);
          const dropoffs: LocOpt[] = (car.dropoff_locations && car.dropoff_locations.length)
            ? car.dropoff_locations
            : (car.dropoff_location ? [car.dropoff_location] : []);
          if (!pickups.length && !dropoffs.length) return null;
          return (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>📍 Locations</Text>
              {/* Same-country rule banner */}
              <View style={styles.sameCountryBanner}>
                <Ionicons name="globe-outline" size={14} color="#0a5d2b" />
                <Text style={styles.sameCountryBannerText}>
                  Pick-up and drop-off must be in the same country.
                </Text>
              </View>
              {/* Low-stock warning for the currently selected pickup */}
              {selectedPickup && (() => {
                const left = stockFor(selectedPickup.name);
                if (left === 0) {
                  return (
                    <View style={[styles.sameCountryBanner, { backgroundColor: '#ffe9e7', borderColor: '#ffb4ad' }]}>
                      <Ionicons name="alert-circle" size={14} color="#d70015" />
                      <Text style={[styles.sameCountryBannerText, { color: '#d70015' }]}>
                        This vehicle is out of stock at {selectedPickup.name}.
                      </Text>
                    </View>
                  );
                }
                if (left <= LOW_STOCK_THRESHOLD) {
                  return (
                    <View style={[styles.sameCountryBanner, { backgroundColor: '#fff5e6', borderColor: '#ffd48a' }]}>
                      <Ionicons name="flame" size={14} color="#a05a00" />
                      <Text style={[styles.sameCountryBannerText, { color: '#a05a00' }]}>
                        🔥 Only {left} {left === 1 ? 'unit' : 'units'} left at {selectedPickup.name} — book soon!
                      </Text>
                    </View>
                  );
                }
                return null;
              })()}
              {/* Pickup picker — visible only when there are 2+ options */}
              {pickups.length > 1 && (
                <View style={{ marginBottom: 8 }}>
                  <Text style={styles.locPickerLabel}>Pickup</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
                    {pickups.map((loc) => {
                      const active = selectedPickup?.name === loc.name;
                      const co = countryFor(loc.name);
                      const left = stockFor(loc.name);
                      const outOfStock = left <= 0;
                      const sublabelParts: string[] = [];
                      if (co) sublabelParts.push(co);
                      if (outOfStock) sublabelParts.push('out of stock');
                      else if (left <= LOW_STOCK_THRESHOLD) sublabelParts.push(`only ${left} left`);
                      else sublabelParts.push(`${left} left`);
                      return (
                        <TouchableOpacity
                          key={`pu-${loc.name}`}
                          testID={`pickup-option-${loc.name}`}
                          onPress={() => {
                            if (outOfStock) {
                              Alert.alert(
                                'Out of stock',
                                `This vehicle is currently out of stock at ${loc.name}. Please choose another pickup location.`
                              );
                              return;
                            }
                            setSelectedPickup(loc);
                          }}
                          activeOpacity={0.7}
                          style={[styles.locChip, active && !outOfStock && styles.locChipPickupActive, outOfStock && styles.locChipDisabled]}
                        >
                          <View style={[styles.locDot, { backgroundColor: outOfStock ? '#C7C7CC' : '#34C759' }]} />
                          <View style={styles.locChipBody}>
                            <Text style={[styles.locChipText, active && !outOfStock && styles.locChipTextActive, outOfStock && styles.locChipTextDisabled]} numberOfLines={1}>{loc.name}</Text>
                            <Text style={[styles.locChipCountry, outOfStock && styles.locChipCountryDisabled, !outOfStock && left <= LOW_STOCK_THRESHOLD && { color: '#a05a00', fontWeight: '800' }]} numberOfLines={1}>
                              {sublabelParts.join(' · ')}
                            </Text>
                          </View>
                          {active && !outOfStock && <Ionicons name="checkmark-circle" size={16} color="#34C759" />}
                          {outOfStock && <Ionicons name="lock-closed" size={14} color="#C7C7CC" />}
                        </TouchableOpacity>
                      );
                    })}
                  </ScrollView>
                </View>
              )}
              {/* Dropoff picker — visible only when there are 2+ options */}
              {dropoffs.length > 1 && (
                <View style={{ marginBottom: 8 }}>
                  <Text style={styles.locPickerLabel}>Drop-off</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
                    {dropoffs.map((loc) => {
                      const active = selectedDropoff?.name === loc.name;
                      const co = countryFor(loc.name);
                      const sameCountry = !pickupCountry || !co || co.toLowerCase() === pickupCountry.toLowerCase();
                      const disabled = !sameCountry;
                      return (
                        <TouchableOpacity
                          key={`do-${loc.name}`}
                          testID={`dropoff-option-${loc.name}`}
                          onPress={() => {
                            if (disabled) {
                              Alert.alert(
                                'Different country',
                                `This drop-off is in ${co} but your pick-up is in ${pickupCountry}. Rentals must stay in the same country.`
                              );
                              return;
                            }
                            setSelectedDropoff(loc);
                          }}
                          activeOpacity={0.7}
                          style={[styles.locChip, active && styles.locChipDropoffActive, disabled && styles.locChipDisabled]}
                        >
                          <View style={[styles.locDot, { backgroundColor: disabled ? '#C7C7CC' : '#FF3B30' }]} />
                          <View style={styles.locChipBody}>
                            <Text style={[styles.locChipText, active && styles.locChipTextActive, disabled && styles.locChipTextDisabled]} numberOfLines={1}>{loc.name}</Text>
                            {!!co && <Text style={[styles.locChipCountry, disabled && styles.locChipCountryDisabled]} numberOfLines={1}>{co}{disabled ? ' · unavailable' : ''}</Text>}
                          </View>
                          {active && !disabled && <Ionicons name="checkmark-circle" size={16} color="#FF3B30" />}
                          {disabled && <Ionicons name="lock-closed" size={14} color="#C7C7CC" />}
                        </TouchableOpacity>
                      );
                    })}
                  </ScrollView>
                </View>
              )}
              {/* Selected summary (always visible, even with single option) */}
              {(selectedPickup || selectedDropoff) && (
                <View style={[styles.locSummary, { borderTopColor: colors.border }]}>
                  {selectedPickup && (
                    <View style={styles.locSummaryRow}>
                      <View style={[styles.locDot, { backgroundColor: '#34C759' }]} />
                      <Text style={[styles.locSummaryText, { color: colors.textMuted }]} numberOfLines={1}>Pickup: <Text style={[styles.locSummaryBold, { color: colors.text }]}>{selectedPickup.name}</Text></Text>
                    </View>
                  )}
                  {selectedDropoff && (
                    <View style={styles.locSummaryRow}>
                      <View style={[styles.locDot, { backgroundColor: '#FF3B30' }]} />
                      <Text style={[styles.locSummaryText, { color: colors.textMuted }]} numberOfLines={1}>Drop-off: <Text style={[styles.locSummaryBold, { color: colors.text }]}>{selectedDropoff.name}</Text></Text>
                    </View>
                  )}
                </View>
              )}
              {/* GPS map button */}
              {selectedPickup && (
                <TouchableOpacity
                  testID="booking-map-btn"
                  style={styles.locationRow}
                  onPress={() => router.push({
                    pathname: '/map-view',
                    params: {
                      pickupLat: selectedPickup.lat,
                      pickupLng: selectedPickup.lng,
                      pickupName: selectedPickup.name,
                      dropoffLat: selectedDropoff?.lat,
                      dropoffLng: selectedDropoff?.lng,
                      dropoffName: selectedDropoff?.name,
                    }
                  })}
                >
                  <Ionicons name="navigate-outline" size={20} color="#007AFF" />
                  <Text style={styles.locationText}>{tr('pickupLocation')} & GPS</Text>
                  <Ionicons name="chevron-forward" size={16} color="#007AFF" />
                </TouchableOpacity>
              )}
            </View>
          );
        })()}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{tr('paymentMethod')}</Text>
          {SHOW_CARD_PAYMENT ? (
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
          ) : (
            <View style={styles.cashOnlyCard}>
              <Ionicons name="cash-outline" size={26} color="#FF3B30" />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cashOnlyTitle}>{tr('cash')}</Text>
                <Text style={styles.cashOnlySub}>Paid in cash or card at pickup. Our agent will provide a receipt.</Text>
              </View>
            </View>
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🛡️ Insurance</Text>
          <View style={insuranceIncluded ? styles.insuranceIncluded : styles.insuranceNotIncluded}>
            <Ionicons
              name={insuranceIncluded ? 'shield-checkmark' : 'shield-outline'}
              size={22}
              color={insuranceIncluded ? '#34c759' : '#ff9500'}
            />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={[styles.insuranceTitle, { color: insuranceIncluded ? '#0a5d2b' : '#a05a00' }]}>
                {insuranceIncluded ? 'Insurance included' : 'Insurance NOT included'}
              </Text>
              <Text style={[styles.insuranceSub, { color: insuranceIncluded ? '#1e7a3e' : '#b87600' }]}>
                {insuranceIncluded
                  ? 'Basic insurance is included with this rental at no extra cost.'
                  : 'This rental does not include insurance. You are responsible for any damage.'}
              </Text>
            </View>
          </View>
        </View>

        {refuelAmount > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>⛽ Pre-paid Refuel</Text>
            <TouchableOpacity
              testID="refuel-toggle"
              activeOpacity={0.8}
              onPress={() => setRefuelOptedIn(!refuelOptedIn)}
              style={refuelOptedIn ? styles.refuelOn : styles.refuelOff}
            >
              <Ionicons
                name={refuelOptedIn ? 'checkmark-circle' : 'flash-outline'}
                size={22}
                color={refuelOptedIn ? '#34c759' : '#666'}
              />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={[styles.refuelTitle, { color: refuelOptedIn ? '#0a5d2b' : '#0a0a0a' }]}>
                  {refuelOptedIn ? `Pre-paid refuel — $${refuelAmount.toFixed(2)} (added)` : `Add Pre-paid Refuel — $${refuelAmount.toFixed(2)}`}
                </Text>
                <Text style={styles.refuelSub}>
                  {refuelOptedIn
                    ? 'No need to refuel before return. Save time at drop-off.'
                    : 'Skip refueling at return — return the car empty. Tap to add.'}
                </Text>
              </View>
              <Switch
                value={refuelOptedIn}
                onValueChange={setRefuelOptedIn}
                trackColor={{ false: '#e5e5e5', true: '#34c759' }}
                thumbColor={Platform.OS === 'android' ? '#fff' : undefined}
              />
            </TouchableOpacity>
          </View>
        )}

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

        {/* Mileage policy (per pickup location) */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📏 Mileage Policy</Text>
          <View style={unlimitedMileage ? styles.mileageUnlimited : styles.mileageLimited}>
            <Ionicons
              name={unlimitedMileage ? 'infinite' : 'speedometer-outline'}
              size={22}
              color={unlimitedMileage ? '#0a5d2b' : '#a05a00'}
            />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={[styles.mileageTitle, { color: unlimitedMileage ? '#0a5d2b' : '#a05a00' }]}>
                {unlimitedMileage
                  ? 'Unlimited Mileage'
                  : `Extra Mileage: $${extraMileageCharge.toFixed(2)}/km`}
              </Text>
              <Text style={[styles.mileageSub, { color: unlimitedMileage ? '#1e7a3e' : '#b87600' }]}>
                {unlimitedMileage
                  ? 'Drive as much as you want — no per-km charges apply.'
                  : `Includes ${mileageLimitPerDay} km/day (${mileageLimitPerDay * days} km total). $${extraMileageCharge.toFixed(2)} per extra km billed at drop-off.`}
              </Text>
            </View>
          </View>
        </View>

        {/* Refundable Security Deposit (per vehicle) */}
        {car.deposit > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>💼 Security Deposit</Text>
            <View style={styles.depositCard}>
              <Ionicons name="shield-half" size={22} color="#0a3d80" />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.depositTitle}>
                  ${Number(car.deposit).toFixed(2)} refundable
                </Text>
                <Text style={styles.depositSub}>
                  Collected at pickup, refunded at drop-off if no damages or extras are owed. Not added to the total below.
                </Text>
              </View>
            </View>
          </View>
        )}

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
          {refuelOptedIn && refuelAmount > 0 && (
            <View style={styles.summaryRow}>
              <Text style={[styles.summaryLabel, { color: '#34c759', fontWeight: '700' }]}>⛽ Pre-paid Refuel</Text>
              <Text style={[styles.summaryValue, { color: '#34c759', fontWeight: '700' }]}>+${refuelAmount.toFixed(2)}</Text>
            </View>
          )}
          {taxRate > 0 ? (
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>{taxLabel(pickupCountry || selectedPickup?.country)} ({taxRate}%)</Text>
              <Text style={styles.summaryValue}>${appliedPromo ? recomputedTax : taxAmount}</Text>
            </View>
          ) : (
            <View style={styles.summaryRow}>
              <Text style={[styles.summaryLabel, { color: '#999' }]}>{taxLabel(pickupCountry || selectedPickup?.country)} (0%)</Text>
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
          testID="terms-toggle"
          activeOpacity={0.7}
          onPress={() => setTermsAccepted(!termsAccepted)}
          style={styles.termsRow}
        >
          <View style={[styles.termsBox, termsAccepted && styles.termsBoxChecked]}>
            {termsAccepted && <Ionicons name="checkmark" size={16} color="#FFF" />}
          </View>
          <Text style={styles.termsLabel}>
            I have read and accept the{' '}
            <Text
              style={styles.termsLink}
              onPress={(e: any) => { e?.stopPropagation && e.stopPropagation(); setTermsModalVisible(true); }}
            >
              Rental Terms &amp; Conditions
            </Text>
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          testID="confirm-booking-btn"
          style={[styles.confirmBtn, (!termsAccepted || booking) && styles.confirmBtnDisabled]}
          onPress={() => {
            // Show the review modal first. The actual booking submission runs
            // only after the customer taps "Confirm & Book" inside the modal.
            if (!termsAccepted || booking) return;
            setConfirmModalVisible(true);
          }}
          disabled={booking || !termsAccepted}
          activeOpacity={0.7}
        >
          {booking ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <Text style={styles.confirmBtnText}>
              {!termsAccepted
                ? 'Accept Terms to Continue'
                : (paymentMethod === 'stripe' ? `${tr('pay')} $${grandTotal}` : tr('confirmBooking'))}
            </Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Terms & Conditions Modal */}
      <Modal
        visible={termsModalVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setTermsModalVisible(false)}
      >
        <SafeAreaView style={styles.modalContainer} edges={['top']}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>📜 Rental Terms &amp; Conditions</Text>
            <TouchableOpacity onPress={() => setTermsModalVisible(false)} style={styles.modalCloseBtn}>
              <Ionicons name="close" size={24} color="#0A0A0A" />
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.modalScroll} contentContainerStyle={{ padding: 20 }}>
            <Text style={styles.modalBody}>
              {termsText || 'Loading rental terms…'}
            </Text>
          </ScrollView>
          <View style={styles.modalFooter}>
            <TouchableOpacity
              style={[styles.modalBtn, styles.modalBtnGhost]}
              onPress={() => setTermsModalVisible(false)}
            >
              <Text style={styles.modalBtnGhostText}>Close</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="terms-accept-btn"
              style={[styles.modalBtn, styles.modalBtnPrimary]}
              onPress={() => { setTermsAccepted(true); setTermsModalVisible(false); }}
            >
              <Text style={styles.modalBtnPrimaryText}>I Accept</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </Modal>

      {/* ===== Booking Confirmation Modal =====
          Shown AFTER the customer taps "Confirm Booking" / "Pay $X" on the
          form but BEFORE we actually POST /api/bookings. Last clear chance
          to review dates, locations, payment method and total. */}
      <Modal
        visible={confirmModalVisible}
        animationType="fade"
        transparent
        onRequestClose={() => setConfirmModalVisible(false)}
      >
        {/* Safe string conversion helpers — render NOTHING but strings.
            Defensive against the React error "Objects are not valid as a
            React child (found: [object Date])" that surfaced when raw
            Date objects (pickupDate/dropoffDate) leaked into <Text>. */}
        {(() => {
          const safe = (v: any) => {
            if (v == null) return '';
            if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v);
            if (v instanceof Date) {
              if (Number.isNaN(v.getTime())) return '';
              try { return v.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }); } catch { return v.toDateString(); }
            }
            if (typeof v === 'object' && 'name' in v) return String((v as any).name || '');
            return String(v);
          };
          const _carName = safe(car?.name);
          const _pickupStr = safe(pickupDate);
          const _dropoffStr = safe(dropoffDate);
          const _pickupLocStr = safe(selectedPickup?.name) || '—';
          const _dropoffLocStr = safe(selectedDropoff?.name) || '—';
          const _paymentStr = paymentMethod === 'stripe' ? String(tr('card') || 'Card') : String(tr('cash') || 'Cash');
          const _totalStr = `$${Number(grandTotal) || 0}`;
          const _titleStr = String(tr('confirmYourBooking') || 'Confirm your booking');
          const _subStr = String(tr('confirmYourBookingSub') || 'Please review your reservation details before confirming.');
          const _pickupLabelStr = String(tr('pickupDate') || 'Pickup Date');
          const _dropoffLabelStr = String(tr('dropoffDate') || 'Drop-off Date');
          const _pickupLocLabelStr = String(tr('pickupLocation') || 'Pickup Location');
          const _dropoffLocLabelStr = String(tr('dropoffLocation') || 'Drop-off Location');
          const _payLabelStr = String(tr('paymentMethod') || 'Payment');
          const _totalLabelStr = String(tr('total') || 'Total');
          const _backStr = String(tr('backToEdit') || 'Back to Edit');
          const _confirmStr = String(tr('confirmAndBook') || 'Confirm & Book');
          return (
            <View style={styles.confirmModalOverlay}>
              <View style={styles.confirmModalCard}>
                <View style={styles.confirmModalHeader}>
                  <Ionicons name="checkmark-circle" size={28} color="#34C759" />
                  <Text style={styles.confirmModalTitle}>{_titleStr}</Text>
                </View>
                <Text style={styles.confirmModalSub}>{_subStr}</Text>

                <View style={styles.confirmRow}>
                  <Text style={styles.confirmLabel}>🚗 Vehicle</Text>
                  <Text style={styles.confirmValue} numberOfLines={1}>{_carName}</Text>
                </View>
                <View style={styles.confirmRow}>
                  <Text style={styles.confirmLabel}>📅 {_pickupLabelStr}</Text>
                  <Text style={styles.confirmValue}>{_pickupStr}</Text>
                </View>
                <View style={styles.confirmRow}>
                  <Text style={styles.confirmLabel}>📅 {_dropoffLabelStr}</Text>
                  <Text style={styles.confirmValue}>{_dropoffStr}</Text>
                </View>
                <View style={styles.confirmRow}>
                  <Text style={styles.confirmLabel}>📍 {_pickupLocLabelStr}</Text>
                  <Text style={styles.confirmValue} numberOfLines={2}>{_pickupLocStr}</Text>
                </View>
                <View style={styles.confirmRow}>
                  <Text style={styles.confirmLabel}>🏁 {_dropoffLocLabelStr}</Text>
                  <Text style={styles.confirmValue} numberOfLines={2}>{_dropoffLocStr}</Text>
                </View>
                <View style={styles.confirmRow}>
                  <Text style={styles.confirmLabel}>💳 {_payLabelStr}</Text>
                  <Text style={styles.confirmValue}>{_paymentStr}</Text>
                </View>
                <View style={styles.confirmTotalRow}>
                  <Text style={styles.confirmTotalLabel}>{_totalLabelStr}</Text>
                  <Text style={styles.confirmTotalValue}>{_totalStr}</Text>
                </View>

                <View style={styles.confirmActions}>
                  <TouchableOpacity
                    testID="confirm-modal-back"
                    style={styles.confirmCancelBtn}
                    onPress={() => setConfirmModalVisible(false)}
                    disabled={booking}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.confirmCancelBtnText}>{_backStr}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    testID="confirm-modal-confirm"
                    style={[styles.confirmOkBtn, booking && { opacity: 0.6 }]}
                    onPress={async () => {
                      setConfirmModalVisible(false);
                      await handleBooking();
                    }}
                    disabled={booking}
                    activeOpacity={0.7}
                  >
                    {booking ? (
                      <ActivityIndicator color="#FFF" />
                    ) : (
                      <Text style={styles.confirmOkBtnText}>{_confirmStr}</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          );
        })()}
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFF' },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  topTitle: { fontSize: 18, fontWeight: '800', color: '#0A0A0A' },
  scroll: { paddingHorizontal: 24, paddingBottom: 180 },
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
  insuranceIncluded: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#e6f9ed', borderWidth: 1, borderColor: '#34c759', borderRadius: 12, padding: 14 },
  insuranceNotIncluded: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#fff5e6', borderWidth: 1, borderColor: '#ff9500', borderRadius: 12, padding: 14 },
  insuranceTitle: { fontSize: 14, fontWeight: '800' },
  insuranceSub: { fontSize: 12, marginTop: 4, lineHeight: 16 },
  mileageUnlimited: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#e6f9ed', borderWidth: 1, borderColor: '#34c759', borderRadius: 12, padding: 14 },
  mileageLimited: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#fff5e6', borderWidth: 1, borderColor: '#ff9500', borderRadius: 12, padding: 14 },
  mileageTitle: { fontSize: 14, fontWeight: '800' },
  mileageSub: { fontSize: 12, marginTop: 4, lineHeight: 16 },
  depositCard: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#eaf3ff', borderWidth: 1, borderColor: '#0a84ff', borderRadius: 12, padding: 14 },
  cashOnlyCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF5F4', borderWidth: 1, borderColor: '#FF3B30', borderRadius: 12, padding: 14 },
  cashOnlyTitle: { fontSize: 15, fontWeight: '800', color: '#0A0A0A' },
  cashOnlySub: { fontSize: 12, color: '#666', marginTop: 2, lineHeight: 16, fontWeight: '500' },
  depositTitle: { fontSize: 14, fontWeight: '800', color: '#0a3d80' },
  depositSub: { fontSize: 12, marginTop: 4, lineHeight: 16, color: '#1d4f8f' },
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
  confirmBtnDisabled: { backgroundColor: '#C7C7CC' },
  confirmBtnText: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  refuelOn: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#e6f9ed', borderWidth: 1, borderColor: '#34c759', borderRadius: 12, padding: 14 },
  refuelOff: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5', borderRadius: 12, padding: 14 },
  refuelTitle: { fontSize: 14, fontWeight: '800' },
  refuelSub: { fontSize: 12, color: '#666', marginTop: 4, lineHeight: 16 },
  termsRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 12, paddingHorizontal: 4 },
  termsBox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: '#999', alignItems: 'center', justifyContent: 'center', marginRight: 10, backgroundColor: '#FFF' },
  termsBoxChecked: { backgroundColor: '#FF3B30', borderColor: '#FF3B30' },
  termsLabel: { flex: 1, fontSize: 13, color: '#333', fontWeight: '600', lineHeight: 18 },
  termsLink: { color: '#007AFF', textDecorationLine: 'underline', fontWeight: '700' },
  modalContainer: { flex: 1, backgroundColor: '#FFF' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#E5E5E5' },
  modalTitle: { fontSize: 17, fontWeight: '800', color: '#0A0A0A', flex: 1 },
  modalCloseBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F5F5F5' },
  modalScroll: { flex: 1 },
  modalBody: { fontSize: 13, color: '#333', lineHeight: 20 },
  modalFooter: { flexDirection: 'row', gap: 10, padding: 16, borderTopWidth: 1, borderTopColor: '#E5E5E5', paddingBottom: 24 },
  modalBtn: { flex: 1, paddingVertical: 14, borderRadius: 50, alignItems: 'center', justifyContent: 'center' },
  modalBtnGhost: { backgroundColor: '#F5F5F5' },
  modalBtnGhostText: { color: '#0A0A0A', fontSize: 15, fontWeight: '700' },
  modalBtnPrimary: { backgroundColor: '#FF3B30' },
  modalBtnPrimaryText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
  // Multi-location picker chips
  locPickerLabel: { fontSize: 11, fontWeight: '800', color: '#666', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 6 },
  locChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 50, backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5', maxWidth: 260 },
  locChipBody: { flexShrink: 1, maxWidth: 200 },
  locChipPickupActive: { backgroundColor: '#e6f9ed', borderColor: '#34C759' },
  locChipDropoffActive: { backgroundColor: '#FFE9E7', borderColor: '#FF3B30' },
  locChipDisabled: { backgroundColor: '#FAFAFA', borderColor: '#EFEFEF', opacity: 0.6 },
  locChipText: { fontSize: 13, fontWeight: '700', color: '#444' },
  locChipTextActive: { color: '#0a0a0a' },
  locChipTextDisabled: { color: '#999', textDecorationLine: 'line-through' },
  locChipCountry: { fontSize: 10, color: '#888', fontWeight: '600', marginTop: 1 },
  locChipCountryDisabled: { color: '#bbb' },
  locDot: { width: 8, height: 8, borderRadius: 4 },
  locSummary: { gap: 4, paddingVertical: 8, marginVertical: 6, borderTopWidth: 1, borderTopColor: '#F0F0F0' },
  locSummaryRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  locSummaryText: { flex: 1, fontSize: 13, color: '#666', fontWeight: '600' },
  locSummaryBold: { color: '#0a0a0a', fontWeight: '800' },
  sameCountryBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#e6f9ed', borderWidth: 1, borderColor: '#a4e1be', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginBottom: 12 },
  sameCountryBannerText: { fontSize: 12, color: '#0a5d2b', fontWeight: '700', flex: 1 },
  // ===== Booking Confirmation Modal =====
  confirmModalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  confirmModalCard: { width: '100%', maxWidth: 420, backgroundColor: '#FFFFFF', borderRadius: 20, padding: 22, shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 20, shadowOffset: { width: 0, height: 8 }, elevation: 8 },
  confirmModalHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 },
  confirmModalTitle: { fontSize: 19, fontWeight: '900', color: '#0A0A0A', flex: 1 },
  confirmModalSub: { fontSize: 13, color: '#666', marginBottom: 16, lineHeight: 18 },
  confirmRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F0F0F0', gap: 12 },
  confirmLabel: { fontSize: 13, color: '#666', fontWeight: '700', flexShrink: 0 },
  confirmValue: { fontSize: 14, color: '#0A0A0A', fontWeight: '700', flex: 1, textAlign: 'right' },
  confirmTotalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12, marginTop: 4 },
  confirmTotalLabel: { fontSize: 16, fontWeight: '900', color: '#0A0A0A' },
  confirmTotalValue: { fontSize: 24, fontWeight: '900', color: '#FF3B30' },
  confirmActions: { flexDirection: 'row', gap: 10, marginTop: 8 },
  confirmCancelBtn: { flex: 1, paddingVertical: 14, borderRadius: 50, backgroundColor: '#F5F5F5', alignItems: 'center', justifyContent: 'center' },
  confirmCancelBtnText: { fontSize: 15, fontWeight: '800', color: '#0A0A0A' },
  confirmOkBtn: { flex: 1.4, paddingVertical: 14, borderRadius: 50, backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center' },
  confirmOkBtnText: { fontSize: 15, fontWeight: '800', color: '#FFFFFF' },
});
