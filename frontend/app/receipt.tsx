import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, TouchableOpacity, Image, Platform, Alert, Linking } from 'react-native';
import { useLocalSearchParams, useRouter, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

import { BACKEND_URL } from '../src/config';

type Booking = {
  id: string;
  user_name?: string;
  user_email?: string;
  car_name: string;
  car_image?: string;
  pickup_date: string;
  dropoff_date: string;
  pickup_location?: { name?: string };
  dropoff_location?: { name?: string };
  days: number;
  price_per_day: number;
  subtotal: number;
  tax_rate: number;
  tax_amount: number;
  total_price: number;
  status: string;
  payment_method: string;
  created_at?: string;
};

export default function ReceiptScreen() {
  const { bookingId } = useLocalSearchParams<{ bookingId: string }>();
  const router = useRouter();
  const [booking, setBooking] = useState<Booking | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!bookingId) { setLoading(false); return; }
      try {
        const token = await AsyncStorage.getItem('auth_token');
        const res = await fetch(`${BACKEND_URL}/api/bookings/${bookingId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setBooking(await res.json());
      } catch (e) {
        // ignore
      }
      setLoading(false);
    };
    load();
  }, [bookingId]);

  const downloadPdf = async () => {
    if (!bookingId || !booking) return;
    setDownloading(true);
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const url = `${BACKEND_URL}/api/bookings/${bookingId}/receipt.pdf`;

      if (Platform.OS === 'web') {
        // On web: fetch, create blob, open in new tab
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) throw new Error('Could not fetch receipt');
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        window.open(blobUrl, '_blank');
        setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
      } else {
        // On native: download to cache and share
        const fileUri = FileSystem.cacheDirectory + `dams-receipt-${bookingId.slice(-8)}.pdf`;
        const dl = await FileSystem.downloadAsync(url, fileUri, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(dl.uri, {
            mimeType: 'application/pdf',
            dialogTitle: 'DAMS Car Rental Receipt',
            UTI: 'com.adobe.pdf',
          });
        } else {
          await Linking.openURL(dl.uri);
        }
      }
    } catch (e: any) {
      Alert.alert('Download failed', e.message || 'Could not download the receipt. Please try again.');
    }
    setDownloading(false);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <Stack.Screen options={{ title: 'Receipt' }} />
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#FF3B30" />
        </View>
      </SafeAreaView>
    );
  }

  if (!booking) {
    return (
      <SafeAreaView style={styles.container}>
        <Stack.Screen options={{ title: 'Receipt' }} />
        <View style={styles.center}>
          <Ionicons name="document-outline" size={64} color="#E5E5E5" />
          <Text style={styles.emptyText}>Receipt not found</Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={() => router.back()}>
            <Text style={styles.primaryBtnText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const fmt = (d: string) => new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  const issued = booking.created_at ? fmt(booking.created_at) : '';
  const statusLabel = (booking.status || '').replace(/_/g, ' ').toUpperCase();
  const shortId = (booking.id || '').slice(-10).toUpperCase();

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <Stack.Screen options={{ headerShown: false }} />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()} activeOpacity={0.6}>
          <Ionicons name="arrow-back" size={22} color="#0A0A0A" />
        </TouchableOpacity>
        <View style={styles.headerTitle}>
          <Text style={styles.headerBrand}>DAMS</Text>
          <Text style={styles.headerSub}>RECEIPT</Text>
        </View>
        <TouchableOpacity style={styles.downloadIconBtn} onPress={downloadPdf} disabled={downloading} activeOpacity={0.6}>
          {downloading ? <ActivityIndicator size="small" color="#FF3B30" /> : <Ionicons name="share-outline" size={22} color="#FF3B30" />}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Receipt header card */}
        <View style={styles.receiptHeader}>
          <View style={styles.receiptHeaderRow}>
            <View>
              <Text style={styles.receiptLabel}>RECEIPT #</Text>
              <Text style={styles.receiptNumber}>{shortId}</Text>
            </View>
            <View style={styles.statusPill}>
              <View style={[styles.statusDot, { backgroundColor: statusColor(booking.status) }]} />
              <Text style={styles.statusText}>{statusLabel}</Text>
            </View>
          </View>
          {!!issued && (
            <View style={{ marginTop: 10 }}>
              <Text style={styles.receiptLabel}>ISSUED</Text>
              <Text style={styles.receiptValue}>{issued}</Text>
            </View>
          )}
        </View>

        {/* Vehicle card */}
        <View style={styles.vehicleCard}>
          {!!booking.car_image && (
            <Image source={{ uri: booking.car_image }} style={styles.vehicleImage} resizeMode="cover" />
          )}
          <View style={styles.vehicleInfo}>
            <Text style={styles.sectionLabel}>VEHICLE</Text>
            <Text style={styles.vehicleName}>{booking.car_name}</Text>
          </View>
        </View>

        {/* Customer */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>BILLED TO</Text>
          <Text style={styles.value}>{booking.user_name || 'Customer'}</Text>
          <Text style={styles.muted}>{booking.user_email || ''}</Text>
        </View>

        {/* Rental details */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>RENTAL DETAILS</Text>
          <Row label="Pickup" value={fmt(booking.pickup_date)} />
          <Row label="Drop-off" value={fmt(booking.dropoff_date)} />
          {!!booking.pickup_location?.name && <Row label="Pickup Location" value={booking.pickup_location.name} />}
          {!!booking.dropoff_location?.name && <Row label="Drop-off Location" value={booking.dropoff_location.name} />}
          <Row label="Duration" value={`${booking.days} day${booking.days === 1 ? '' : 's'}`} />
          <Row label="Payment" value={(booking.payment_method || 'cash').toUpperCase()} />
        </View>

        {/* Cost breakdown */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>COST BREAKDOWN</Text>
          <Row
            label={`Daily Rate × ${booking.days}`}
            value={`$${(booking.days ? (booking.subtotal || 0) / booking.days : 0).toFixed(2)} × ${booking.days}`}
          />
          <Row label="Subtotal" value={`$${(booking.subtotal || 0).toFixed(2)}`} bold />
          <Row
            label={`Tax (${booking.tax_rate || 0}%)`}
            value={`$${(booking.tax_amount || 0).toFixed(2)}`}
            hint={booking.pickup_location?.name}
          />
        </View>

        {/* Grand total */}
        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>GRAND TOTAL</Text>
          <Text style={styles.totalValue}>${(booking.total_price || 0).toFixed(2)}</Text>
          <Text style={styles.totalCurrency}>USD</Text>
        </View>

        {/* Actions */}
        <TouchableOpacity style={styles.downloadBtn} onPress={downloadPdf} disabled={downloading} activeOpacity={0.7}>
          {downloading ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <>
              <Ionicons name={Platform.OS === 'web' ? 'download-outline' : 'share-outline'} size={20} color="#FFF" />
              <Text style={styles.downloadBtnText}>
                {Platform.OS === 'web' ? 'Download PDF Receipt' : 'Share / Save PDF Receipt'}
              </Text>
            </>
          )}
        </TouchableOpacity>

        <Text style={styles.footer}>Thank you for choosing DAMS Car Rental.</Text>
        <Text style={styles.footerSmall}>support@damscarrental.com</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ label, value, bold, hint }: { label: string; value: string; bold?: boolean; hint?: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>
        {label}
        {hint ? <Text style={styles.rowHint}>  · {hint}</Text> : null}
      </Text>
      <Text style={[styles.rowValue, bold && { fontWeight: '800' }]}>{value}</Text>
    </View>
  );
}

function statusColor(s: string) {
  const map: Record<string, string> = {
    confirmed: '#34C759',
    active: '#34C759',
    pending_payment: '#FF9500',
    pending: '#FF9500',
    completed: '#5856D6',
    cancelled: '#FF3B30',
  };
  return map[s] || '#666';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  emptyText: { fontSize: 16, color: '#999' },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 12,
    backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E5E5E5',
  },
  backBtn: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { flex: 1, alignItems: 'center' },
  headerBrand: { fontSize: 18, fontWeight: '900', color: '#0A0A0A', letterSpacing: -0.5 },
  headerSub: { fontSize: 10, color: '#FF3B30', fontWeight: '700', letterSpacing: 2 },
  downloadIconBtn: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  scroll: { padding: 16, paddingBottom: 40 },

  receiptHeader: {
    backgroundColor: '#0A0A0A', borderRadius: 20, padding: 20, marginBottom: 12,
  },
  receiptHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  receiptLabel: { fontSize: 10, color: '#999', fontWeight: '700', letterSpacing: 1 },
  receiptNumber: { fontSize: 20, color: '#FFF', fontWeight: '900', marginTop: 4, letterSpacing: 1 },
  receiptValue: { fontSize: 14, color: '#FFF', fontWeight: '600', marginTop: 2 },
  statusPill: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(255,255,255,0.1)', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 50,
  },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { color: '#FFF', fontSize: 11, fontWeight: '800', letterSpacing: 0.5 },

  vehicleCard: { backgroundColor: '#FFF', borderRadius: 20, overflow: 'hidden', marginBottom: 12 },
  vehicleImage: { width: '100%', height: 160, backgroundColor: '#F0F0F0' },
  vehicleInfo: { padding: 16 },
  vehicleName: { fontSize: 20, fontWeight: '900', color: '#0A0A0A', marginTop: 4 },

  section: { backgroundColor: '#FFF', borderRadius: 20, padding: 16, marginBottom: 12 },
  sectionLabel: { fontSize: 10, color: '#999', fontWeight: '700', letterSpacing: 1, marginBottom: 10 },
  value: { fontSize: 16, color: '#0A0A0A', fontWeight: '700' },
  muted: { fontSize: 13, color: '#666', marginTop: 2 },

  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6 },
  rowLabel: { fontSize: 13, color: '#666', flex: 1 },
  rowHint: { fontSize: 12, color: '#999' },
  rowValue: { fontSize: 14, color: '#0A0A0A', fontWeight: '700' },

  totalCard: {
    backgroundColor: '#FF3B30', borderRadius: 20, padding: 20,
    flexDirection: 'row', alignItems: 'baseline', marginBottom: 16,
  },
  totalLabel: { flex: 1, color: '#FFF', fontSize: 14, fontWeight: '800', letterSpacing: 1 },
  totalValue: { color: '#FFF', fontSize: 28, fontWeight: '900' },
  totalCurrency: { color: '#FFF', fontSize: 12, fontWeight: '700', marginLeft: 6, opacity: 0.8 },

  downloadBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#0A0A0A', borderRadius: 50, paddingVertical: 16, marginTop: 4,
  },
  downloadBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },

  footer: { textAlign: 'center', fontSize: 13, color: '#666', marginTop: 20 },
  footerSmall: { textAlign: 'center', fontSize: 11, color: '#999', marginTop: 4 },

  primaryBtn: { backgroundColor: '#FF3B30', paddingHorizontal: 24, paddingVertical: 14, borderRadius: 50, marginTop: 8 },
  primaryBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
});
