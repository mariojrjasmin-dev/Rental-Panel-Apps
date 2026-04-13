import { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, FlatList, Image, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';
import AsyncStorage from '@react-native-async-storage/async-storage';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type Booking = {
  id: string;
  car_name: string;
  car_image: string;
  pickup_date: string;
  dropoff_date: string;
  total_price: number;
  status: string;
  payment_method: string;
  payment_status: string;
  days: number;
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

  useEffect(() => { fetchBookings(); }, [fetchBookings]);

  const onRefresh = () => { setRefreshing(true); fetchBookings(); };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const renderBooking = ({ item }: { item: Booking }) => (
    <TouchableOpacity testID={`booking-card-${item.id}`} style={styles.card} activeOpacity={0.7}>
      <Image source={{ uri: item.car_image }} style={styles.carImage} resizeMode="cover" />
      <View style={styles.cardContent}>
        <View style={styles.cardHeader}>
          <Text style={styles.carName} numberOfLines={1}>{item.car_name}</Text>
          <View style={[styles.statusBadge, { backgroundColor: (STATUS_COLORS[item.status] || '#999') + '20' }]}>
            <Text style={[styles.statusText, { color: STATUS_COLORS[item.status] || '#999' }]}>
              {item.status.replace('_', ' ')}
            </Text>
          </View>
        </View>
        <View style={styles.dateRow}>
          <Ionicons name="calendar-outline" size={14} color="#666" />
          <Text style={styles.dateText}>{formatDate(item.pickup_date)} - {formatDate(item.dropoff_date)}</Text>
        </View>
        <View style={styles.cardFooter}>
          <View style={styles.paymentInfo}>
            <Ionicons name={item.payment_method === 'stripe' ? 'card-outline' : 'cash-outline'} size={14} color="#666" />
            <Text style={styles.paymentText}>{item.payment_method === 'stripe' ? 'Card' : 'Cash'}</Text>
          </View>
          <Text style={styles.totalPrice}>${item.total_price}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>My Bookings</Text>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color="#FF3B30" /></View>
      ) : bookings.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="calendar-outline" size={64} color="#E5E5E5" />
          <Text style={styles.emptyText}>No bookings yet</Text>
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
          contentContainerStyle={styles.list}
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
  carName: { fontSize: 17, fontWeight: '800', color: '#0A0A0A', flex: 1, marginRight: 8 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusText: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  dateRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dateText: { fontSize: 13, color: '#666' },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 },
  paymentInfo: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  paymentText: { fontSize: 13, color: '#666' },
  totalPrice: { fontSize: 20, fontWeight: '900', color: '#FF3B30' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyText: { fontSize: 16, color: '#999' },
  browseBtn: { backgroundColor: '#FF3B30', paddingHorizontal: 24, paddingVertical: 14, borderRadius: 50, marginTop: 8 },
  browseBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
});
