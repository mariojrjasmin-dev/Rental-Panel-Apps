import { useState, useEffect, useCallback, useContext } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, FlatList, Image, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BottomTabBarHeightContext } from '@react-navigation/bottom-tabs';
import { useAuth } from '../_layout';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { t as tr } from '../../src/i18n';

import { BACKEND_URL } from '../../src/config';

type Booking = {
  id: string;
  car_name: string;
  car_image: string;
  pickup_date: string;
  dropoff_date: string;
  subtotal?: number;
  tax_rate?: number;
  tax_amount?: number;
  total_price: number;
  status: string;
  payment_method: string;
  payment_status: string;
  days: number;
  // Booking workflow upgrades
  deposit?: number;
  extra_mileage_fee?: number;
};

const PAYMENT_BADGE: Record<string, { color: string; key: string }> = {
  paid: { color: '#34C759', key: 'paidStatus' },
  succeeded: { color: '#34C759', key: 'paidStatus' },
  cash_paid: { color: '#34C759', key: 'paidStatus' },
  pending: { color: '#FF9500', key: 'unpaidStatus' },
  unpaid: { color: '#FF9500', key: 'unpaidStatus' },
  refunded: { color: '#8E8E93', key: 'refundedStatus' },
  failed: { color: '#FF3B30', key: 'unpaidStatus' },
};

const STATUS_COLORS: Record<string, string> = {
  confirmed: '#34C759',
  pending_payment: '#FFCC00',
  cancelled: '#FF3B30',
  completed: '#007AFF',
};

export default function BookingsScreen() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { user } = useAuth();
  const router = useRouter();
  // Pad list bottom by the actual tab bar height (incl. iOS home indicator)
  // so the last booking card is not hidden behind the bottom tab bar.
  // useContext is safer than useBottomTabBarHeight() (which throws on web /
  // non-tab screens). Falls back to 80px when context isn't present.
  const tabBarHeight = useContext(BottomTabBarHeightContext) ?? 80;

  const fetchBookings = useCallback(async () => {
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const res = await fetch(`${BACKEND_URL}/api/bookings`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setBookings(data);
      }
    } catch (e) {
      console.log('Fetch bookings error:', e);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  // Refetch bookings every time the tab is focused
  useFocusEffect(
    useCallback(() => {
      fetchBookings();
    }, [fetchBookings])
  );

  const onRefresh = () => { setRefreshing(true); fetchBookings(); };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const renderBooking = ({ item }: { item: Booking }) => (
    <TouchableOpacity
      testID={`booking-card-${item.id}`}
      style={styles.card}
      activeOpacity={0.7}
      onPress={() => router.push({ pathname: '/receipt', params: { bookingId: item.id } })}
    >
      <Image source={{ uri: item.car_image }} style={styles.carImage} resizeMode="cover" />
      <View style={styles.cardContent}>
        <View style={styles.cardHeader}>
          <Text style={styles.carName} numberOfLines={1}>{item.car_name}</Text>
          <View style={[styles.statusBadge, { backgroundColor: (STATUS_COLORS[item.status] || '#999') + '20' }]}>
            <Text style={[styles.statusText, { color: STATUS_COLORS[item.status] || '#999' }]}>
              {tr('status' + (item.status === 'pending_payment' ? 'Pending' : item.status.charAt(0).toUpperCase() + item.status.slice(1)))}
            </Text>
          </View>
        </View>
        {(() => {
          const pay = PAYMENT_BADGE[item.payment_status || 'pending'] || PAYMENT_BADGE.pending;
          // For cash bookings without explicit status, show "Cash" pill instead
          const isCashOnly = item.payment_method === 'cash' && (!item.payment_status || item.payment_status === 'pending');
          if (isCashOnly) {
            return (
              <View style={[styles.payBadge, { backgroundColor: '#F5F5F5' }]}>
                <Ionicons name="cash-outline" size={11} color="#666" />
                <Text style={[styles.payBadgeText, { color: '#666' }]}>{tr('cash')}</Text>
              </View>
            );
          }
          return (
            <View style={[styles.payBadge, { backgroundColor: pay.color + '18' }]}>
              <Ionicons name={pay.key === 'paidStatus' ? 'checkmark-circle' : pay.key === 'refundedStatus' ? 'arrow-undo-circle' : 'time-outline'} size={11} color={pay.color} />
              <Text style={[styles.payBadgeText, { color: pay.color }]}>{tr(pay.key)}</Text>
            </View>
          );
        })()}
        <View style={styles.dateRow}>
          <Ionicons name="calendar-outline" size={14} color="#666" />
          <Text style={styles.dateText}>{formatDate(item.pickup_date)} - {formatDate(item.dropoff_date)}</Text>
        </View>
        <View style={styles.cardFooter}>
          <View style={styles.paymentInfo}>
            <Ionicons name={item.payment_method === 'stripe' ? 'card-outline' : 'cash-outline'} size={14} color="#666" />
            <Text style={styles.paymentText}>{item.payment_method === 'stripe' ? tr('card') : tr('cash')}</Text>
            <Ionicons name="receipt-outline" size={14} color="#FF3B30" style={{ marginLeft: 8 }} />
            <Text style={[styles.paymentText, { color: '#FF3B30', fontWeight: '700' }]}>{tr('receipt')}</Text>
          </View>
          <Text style={styles.totalPrice}>${item.total_price}</Text>
        </View>
        {(item.subtotal != null || (item.tax_amount ?? 0) > 0) && (
          <View style={styles.taxRow}>
            <Text style={styles.taxText}>
              Subtotal ${(item.subtotal ?? 0).toFixed(2)} · Tax {item.tax_rate ?? 0}% ${(item.tax_amount ?? 0).toFixed(2)}
            </Text>
          </View>
        )}
        {!!item.extra_mileage_fee && item.extra_mileage_fee > 0 && (
          <View style={styles.taxRow}>
            <Text style={[styles.taxText, { color: '#a05a00', fontWeight: '700' }]}>
              ⚠️ Extra mileage charged: ${item.extra_mileage_fee.toFixed(2)}
            </Text>
          </View>
        )}
        {!!item.deposit && item.deposit > 0 && (
          <View style={[styles.taxRow, { backgroundColor: '#eaf3ff', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4, marginTop: 4, alignSelf: 'flex-start' }]}>
            <Ionicons name="shield-half" size={12} color="#0a3d80" />
            <Text style={[styles.taxText, { color: '#0a3d80', fontWeight: '700', marginLeft: 4 }]}>
              ${item.deposit.toFixed(2)} refundable deposit
            </Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>{tr('myBookings')}</Text>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color="#FF3B30" /></View>
      ) : bookings.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="calendar-outline" size={64} color="#E5E5E5" />
          <Text style={styles.emptyText}>{tr('noBookings')}</Text>
          <TouchableOpacity testID="browse-cars-btn" style={styles.browseBtn} onPress={() => router.push('/(tabs)/home')}>
            <Text style={styles.browseBtnText}>Browse Cars</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          testID="bookings-list"
          data={bookings}
          keyExtractor={(item) => item.id}
          renderItem={renderBooking}
          contentContainerStyle={[styles.list, { paddingBottom: tabBarHeight + 24 }]}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FF3B30" />}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  header: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 16 },
  title: { fontSize: 28, fontWeight: '900', color: '#0A0A0A', letterSpacing: -0.5 },
  list: { paddingHorizontal: 24, paddingBottom: 24 },
  card: { backgroundColor: '#FFF', borderRadius: 20, overflow: 'hidden', marginBottom: 16, borderWidth: 1, borderColor: '#E5E5E5' },
  carImage: { width: '100%', height: 140, backgroundColor: '#F5F5F5' },
  cardContent: { padding: 16, gap: 8 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  payBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 50, alignSelf: 'flex-start' },
  payBadgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  carName: { fontSize: 17, fontWeight: '800', color: '#0A0A0A', flex: 1, marginRight: 8 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusText: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  dateRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dateText: { fontSize: 13, color: '#666' },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 },
  taxRow: { marginTop: 6, paddingTop: 6, borderTopWidth: 1, borderTopColor: '#F0F0F0' },
  taxText: { fontSize: 11, color: '#999', fontWeight: '600' },
  paymentInfo: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  paymentText: { fontSize: 13, color: '#666' },
  totalPrice: { fontSize: 20, fontWeight: '900', color: '#FF3B30' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyText: { fontSize: 16, color: '#999' },
  browseBtn: { backgroundColor: '#FF3B30', paddingHorizontal: 24, paddingVertical: 14, borderRadius: 50, marginTop: 8 },
  browseBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
});
