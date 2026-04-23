import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export default function BookingSuccessScreen() {
  const { bookingId, session_id } = useLocalSearchParams<{ bookingId?: string; session_id?: string }>();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [booking, setBooking] = useState<any>(null);
  const router = useRouter();

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
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        {status === 'loading' ? (
          <>
            <ActivityIndicator size="large" color="#FF3B30" />
            <Text style={styles.loadingText}>Processing your booking...</Text>
          </>
        ) : status === 'success' ? (
          <>
            <View style={styles.successCircle}>
              <Ionicons name="checkmark" size={48} color="#FFF" />
            </View>
            <Text style={styles.title}>Booking Confirmed!</Text>
            <Text style={styles.subtitle}>Your vehicle has been reserved successfully</Text>
            {booking && (
              <View style={styles.detailCard}>
                <Text style={styles.detailName}>{booking.car_name}</Text>
                <Text style={styles.detailDate}>{booking.pickup_date} - {booking.dropoff_date}</Text>
                {(booking.subtotal != null || (booking.tax_amount ?? 0) > 0) && (
                  <View style={styles.breakdown}>
                    <View style={styles.breakdownRow}>
                      <Text style={styles.breakdownLabel}>Subtotal</Text>
                      <Text style={styles.breakdownValue}>${(booking.subtotal ?? 0).toFixed(2)}</Text>
                    </View>
                    <View style={styles.breakdownRow}>
                      <Text style={styles.breakdownLabel}>Tax ({booking.tax_rate ?? 0}%)</Text>
                      <Text style={styles.breakdownValue}>${(booking.tax_amount ?? 0).toFixed(2)}</Text>
                    </View>
                  </View>
                )}
                <View style={styles.totalRow}>
                  <Text style={styles.totalLabel}>Total</Text>
                  <Text style={styles.detailTotal}>${booking.total_price}</Text>
                </View>
              </View>
            )}
          </>
        ) : (
          <>
            <View style={[styles.successCircle, { backgroundColor: '#FF3B30' }]}>
              <Ionicons name="alert" size={48} color="#FFF" />
            </View>
            <Text style={styles.title}>Something went wrong</Text>
            <Text style={styles.subtitle}>Please check your bookings for status</Text>
          </>
        )}

        <View style={styles.actions}>
          {status === 'success' && booking?.id && (
            <TouchableOpacity testID="view-receipt-btn" style={styles.primaryBtn} onPress={() => router.replace({ pathname: '/receipt', params: { bookingId: booking.id } })} activeOpacity={0.7}>
              <Text style={styles.primaryBtnText}>View Receipt</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity testID="view-bookings-btn" style={booking?.id ? styles.secondaryBtn : styles.primaryBtn} onPress={() => router.replace('/(tabs)/bookings')} activeOpacity={0.7}>
            <Text style={booking?.id ? styles.secondaryBtnText : styles.primaryBtnText}>View My Bookings</Text>
          </TouchableOpacity>
          <TouchableOpacity testID="browse-more-btn" style={styles.secondaryBtn} onPress={() => router.replace('/(tabs)/home')} activeOpacity={0.7}>
            <Text style={styles.secondaryBtnText}>Browse More Cars</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 24 },
  loadingText: { fontSize: 16, color: '#666', marginTop: 16 },
  successCircle: { width: 96, height: 96, borderRadius: 48, backgroundColor: '#34C759', justifyContent: 'center', alignItems: 'center', marginBottom: 24 },
  title: { fontSize: 28, fontWeight: '900', color: '#0A0A0A', textAlign: 'center' },
  subtitle: { fontSize: 16, color: '#666', marginTop: 8, textAlign: 'center' },
  detailCard: { backgroundColor: '#F5F5F5', borderRadius: 20, padding: 20, marginTop: 24, width: '100%', gap: 4 },
  detailName: { fontSize: 18, fontWeight: '800', color: '#0A0A0A', textAlign: 'center' },
  detailDate: { fontSize: 14, color: '#666', textAlign: 'center' },
  detailTotal: { fontSize: 22, fontWeight: '900', color: '#FF3B30' },
  breakdown: { marginTop: 16, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#E5E5E5', gap: 4 },
  breakdownRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  breakdownLabel: { fontSize: 13, color: '#666' },
  breakdownValue: { fontSize: 14, color: '#0A0A0A', fontWeight: '700' },
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#E5E5E5' },
  totalLabel: { fontSize: 14, color: '#0A0A0A', fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  actions: { width: '100%', marginTop: 32, gap: 12 },
  primaryBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center' },
  primaryBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  secondaryBtn: { backgroundColor: '#F5F5F5', borderRadius: 50, paddingVertical: 18, alignItems: 'center' },
  secondaryBtnText: { color: '#0A0A0A', fontSize: 17, fontWeight: '700' },
});
