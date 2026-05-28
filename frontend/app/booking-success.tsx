import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { BACKEND_URL } from '../src/config';
import { taxLabel } from '../src/tax';
import { useTheme } from '../src/theme';

export default function BookingSuccessScreen() {
  const { bookingId, session_id } = useLocalSearchParams<{ bookingId?: string; session_id?: string }>();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [booking, setBooking] = useState<any>(null);
  const router = useRouter();
  const { colors } = useTheme();

  useEffect(() => {
    const process = async () => {
      try {
        // If coming from Stripe, poll payment status
        if (session_id) {
          let paid = false;
          for (let i = 0; i < 5; i++) {
            const res = await fetch(`${BACKEND_URL}/api/payments/status/${session_id}`);
            if (res.ok) {
              const data = await res.json();
              if (data.payment_status === 'paid') {
                paid = true;
                break;
              }
            }
            await new Promise(r => setTimeout(r, 2000));
          }
          setStatus(paid ? 'success' : 'error');
          return;
        }
        
        if (bookingId) {
          const token = await AsyncStorage.getItem('auth_token');
          const res = await fetch(`${BACKEND_URL}/api/bookings/${bookingId}`, {
            headers: { 'Authorization': `Bearer ${token}` },
          });
          if (res.ok) {
            setBooking(await res.json());
            setStatus('success');
          } else {
            setStatus('error');
          }
        } else {
          setStatus('success');
        }
      } catch (e) {
        setStatus('error');
      }
    };
    process();
  }, [bookingId, session_id]);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]}>
      <View style={styles.content}>
        {status === 'loading' ? (
          <>
            <ActivityIndicator size="large" color={colors.brand} />
            <Text style={[styles.loadingText, { color: colors.textMuted }]}>Processing your booking...</Text>
          </>
        ) : status === 'success' ? (
          <>
            <View style={[styles.successCircle, { backgroundColor: colors.success }]}>
              <Ionicons name="checkmark" size={48} color="#FFF" />
            </View>
            <Text style={[styles.title, { color: colors.text }]}>Booking Confirmed!</Text>
            <Text style={[styles.subtitle, { color: colors.textMuted }]}>Your vehicle has been reserved successfully</Text>
            {booking && (
              <View style={[styles.detailCard, { backgroundColor: colors.bgElevated, borderColor: colors.border, borderWidth: 1 }]}>
                <Text style={[styles.detailName, { color: colors.text }]}>{booking.car_name}</Text>
                <Text style={[styles.detailDate, { color: colors.textMuted }]}>{booking.pickup_date} - {booking.dropoff_date}</Text>
                {(booking.total_price != null) && (
                  <View style={[styles.breakdown, { borderTopColor: colors.border }]}>
                    <View style={styles.breakdownRow}>
                      <Text style={[styles.breakdownLabel, { color: colors.textMuted }]}>Subtotal</Text>
                      <Text style={[styles.breakdownValue, { color: colors.text }]}>${(booking.subtotal ?? booking.total_price).toFixed(2)}</Text>
                    </View>
                    <View style={styles.breakdownRow}>
                      <Text style={[styles.breakdownLabel, { color: colors.textMuted }]}>{taxLabel(booking?.pickup_location?.country)} ({booking.tax_rate ?? 0}%)</Text>
                      <Text style={[styles.breakdownValue, { color: colors.text }]}>${(booking.tax_amount ?? 0).toFixed(2)}</Text>
                    </View>
                  </View>
                )}
                <View style={[styles.totalRow, { borderTopColor: colors.border }]}>
                  <Text style={[styles.totalLabel, { color: colors.text }]}>Total</Text>
                  <Text style={[styles.detailTotal, { color: colors.brand }]}>${booking.total_price}</Text>
                </View>
              </View>
            )}
          </>
        ) : (
          <>
            <View style={[styles.successCircle, { backgroundColor: colors.brand }]}>
              <Ionicons name="alert" size={48} color="#FFF" />
            </View>
            <Text style={[styles.title, { color: colors.text }]}>Something went wrong</Text>
            <Text style={[styles.subtitle, { color: colors.textMuted }]}>Please check your bookings for status</Text>
          </>
        )}

        <View style={styles.actions}>
          {status === 'success' && booking?.id && (
            <TouchableOpacity testID="view-receipt-btn" style={[styles.primaryBtn, { backgroundColor: colors.brand }]} onPress={() => router.replace({ pathname: '/receipt', params: { bookingId: booking.id } })} activeOpacity={0.7}>
              <Text style={styles.primaryBtnText}>View Receipt</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity testID="view-bookings-btn" style={booking?.id ? [styles.secondaryBtn, { backgroundColor: colors.bgSubtle, borderColor: colors.border, borderWidth: 1 }] : [styles.primaryBtn, { backgroundColor: colors.brand }]} onPress={() => router.replace('/(tabs)/bookings')} activeOpacity={0.7}>
            <Text style={booking?.id ? [styles.secondaryBtnText, { color: colors.text }] : styles.primaryBtnText}>View My Bookings</Text>
          </TouchableOpacity>
          <TouchableOpacity testID="browse-more-btn" style={[styles.secondaryBtn, { backgroundColor: colors.bgSubtle, borderColor: colors.border, borderWidth: 1 }]} onPress={() => router.replace('/(tabs)/home')} activeOpacity={0.7}>
            <Text style={[styles.secondaryBtnText, { color: colors.text }]}>Browse More Cars</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 24 },
  loadingText: { fontSize: 16, marginTop: 16 },
  successCircle: { width: 96, height: 96, borderRadius: 48, justifyContent: 'center', alignItems: 'center', marginBottom: 24 },
  title: { fontSize: 28, fontWeight: '900', textAlign: 'center' },
  subtitle: { fontSize: 16, marginTop: 8, textAlign: 'center' },
  detailCard: { borderRadius: 20, padding: 20, marginTop: 24, width: '100%', gap: 4 },
  detailName: { fontSize: 18, fontWeight: '800', textAlign: 'center' },
  detailDate: { fontSize: 14, textAlign: 'center' },
  detailTotal: { fontSize: 22, fontWeight: '900' },
  breakdown: { marginTop: 16, paddingTop: 12, borderTopWidth: 1, gap: 4 },
  breakdownRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  breakdownLabel: { fontSize: 13 },
  breakdownValue: { fontSize: 14, fontWeight: '700' },
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 10, borderTopWidth: 1 },
  totalLabel: { fontSize: 14, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  actions: { width: '100%', marginTop: 32, gap: 12 },
  primaryBtn: { borderRadius: 50, paddingVertical: 18, alignItems: 'center' },
  primaryBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  secondaryBtn: { borderRadius: 50, paddingVertical: 18, alignItems: 'center' },
  secondaryBtnText: { fontSize: 17, fontWeight: '700' },
});
