import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, TouchableOpacity, Image, Platform, Alert, Linking, Modal } from 'react-native';
import { useLocalSearchParams, useRouter, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import BrandLogo from '../components/BrandLogo';
import { taxLabel } from '../src/tax';
import { useTheme } from '../src/theme';
import { t as tr } from '../src/i18n';

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
  // Booking workflow upgrades
  deposit?: number;
  odometer_in?: number;
  odometer_out?: number;
  extra_mileage_fee?: number;
  extra_mileage_km?: number;
  extra_mileage_rate?: number;
};

export default function ReceiptScreen() {
  const { bookingId } = useLocalSearchParams<{ bookingId: string }>();
  const router = useRouter();
  const [booking, setBooking] = useState<Booking | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  // Cancel-booking flow state. The customer cancels via a confirm modal;
  // the actual POST hits /api/bookings/{id}/cancel which restocks the car
  // and emails a confirmation. Eligibility (≥24h before pickup) is enforced
  // by the backend — we mirror the rule here only to show/hide the button.
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const { colors, isDark } = useTheme();

  // The cancel button is rendered ONLY when:
  //  • booking exists
  //  • status is one of pending / pending_payment / confirmed
  //  • pickup_date is at least 24h in the future
  const canCancel = (() => {
    if (!booking) return false;
    const ok = ['pending', 'pending_payment', 'confirmed'].includes((booking.status || '').toLowerCase());
    if (!ok) return false;
    if (!booking.pickup_date) return ok; // server will decide
    const t = Date.parse(booking.pickup_date);
    if (Number.isNaN(t)) return ok;
    const hoursLeft = (t - Date.now()) / 36e5;
    return hoursLeft >= 24;
  })();

  const handleCancelBooking = async () => {
    if (!booking || cancelling) return;
    setCancelling(true);
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const res = await fetch(`${BACKEND_URL}/api/bookings/${booking.id}/cancel`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = (data && typeof data.detail === 'string') ? data.detail : tr('cancelBookingFailed');
        if (Platform.OS === 'web') {
          // eslint-disable-next-line no-alert
          window.alert(detail);
        } else {
          Alert.alert(tr('cancelBooking'), detail);
        }
        setCancelling(false);
        setCancelModalVisible(false);
        return;
      }
      // Success — close the modal, refresh the booking display, and confirm.
      setCancelModalVisible(false);
      if (data?.booking) {
        setBooking(data.booking);
      } else {
        // Optimistic update.
        setBooking({ ...booking, status: 'cancelled' });
      }
      if (Platform.OS === 'web') {
        // eslint-disable-next-line no-alert
        window.alert(tr('bookingCancelled'));
      } else {
        Alert.alert(tr('bookingCancelled'));
      }
    } catch (e: any) {
      if (Platform.OS === 'web') {
        // eslint-disable-next-line no-alert
        window.alert(e?.message || tr('cancelBookingFailed'));
      } else {
        Alert.alert(tr('cancelBooking'), e?.message || tr('cancelBookingFailed'));
      }
    } finally {
      setCancelling(false);
    }
  };

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

      // Fetch the PDF (works on all platforms; properly handles auth headers)
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        throw new Error(`Server returned ${res.status} ${res.statusText}`);
      }

      if (Platform.OS === 'web') {
        // On web: open the PDF in a new tab
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        window.open(blobUrl, '_blank');
        setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
      } else {
        // On native: save bytes to cache, then open the share sheet.
        // Uses the new File API from expo-file-system v19+.
        const bytes = new Uint8Array(await res.arrayBuffer());
        const fileName = `dams-receipt-${bookingId.slice(-8)}.pdf`;
        const file = new File(Paths.cache, fileName);
        try { if (file.exists) file.delete(); } catch {}
        file.create();
        file.write(bytes);

        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(file.uri, {
            mimeType: 'application/pdf',
            dialogTitle: 'DAMS Car Rental Receipt',
            UTI: 'com.adobe.pdf',
          });
        } else {
          await Linking.openURL(file.uri);
        }
      }
    } catch (e: any) {
      Alert.alert('Download failed', e?.message || 'Could not download the receipt. Please try again.');
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
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top', 'bottom']}>
      <Stack.Screen options={{ headerShown: false }} />

      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.bgElevated, borderBottomColor: colors.border }]}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()} activeOpacity={0.6}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <View style={styles.headerTitle}>
          <BrandLogo size="small" testID="receipt-header-logo" imageStyle={{ width: 110, height: 33 }} />
          <Text style={styles.headerSub}>RECEIPT</Text>
        </View>
        <TouchableOpacity style={styles.downloadIconBtn} onPress={downloadPdf} disabled={downloading} activeOpacity={0.6}>
          {downloading ? <ActivityIndicator size="small" color={colors.brand} /> : <Ionicons name="share-outline" size={22} color={colors.brand} />}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Receipt header card — intentionally always dark for paper-receipt feel */}
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
        <View style={[styles.vehicleCard, { backgroundColor: colors.bgElevated }]}>
          {!!booking.car_image && (
            <Image source={{ uri: booking.car_image }} style={[styles.vehicleImage, { backgroundColor: colors.bgSubtle }]} resizeMode="cover" />
          )}
          <View style={styles.vehicleInfo}>
            <Text style={[styles.sectionLabel, { color: colors.textSubtle }]}>VEHICLE</Text>
            <Text style={[styles.vehicleName, { color: colors.text }]}>{booking.car_name}</Text>
          </View>
        </View>

        {/* Customer */}
        <View style={[styles.section, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.sectionLabel, { color: colors.textSubtle }]}>BILLED TO</Text>
          <Text style={[styles.value, { color: colors.text }]}>{booking.user_name || 'Customer'}</Text>
          <Text style={[styles.muted, { color: colors.textMuted }]}>{booking.user_email || ''}</Text>
        </View>

        {/* Rental details */}
        <View style={[styles.section, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.sectionLabel, { color: colors.textSubtle }]}>RENTAL DETAILS</Text>
          <Row colors={colors} label="Pickup" value={fmt(booking.pickup_date)} />
          <Row colors={colors} label="Drop-off" value={fmt(booking.dropoff_date)} />
          {!!booking.pickup_location?.name && <Row colors={colors} label="Pickup Location" value={booking.pickup_location.name} />}
          {!!booking.dropoff_location?.name && <Row colors={colors} label="Drop-off Location" value={booking.dropoff_location.name} />}
          <Row colors={colors} label="Duration" value={`${booking.days} day${booking.days === 1 ? '' : 's'}`} />
          <Row colors={colors} label="Payment" value={(booking.payment_method || 'cash').toUpperCase()} />
          {booking.odometer_in != null && (
            <Row colors={colors} label="Odometer (Pickup)" value={`${Number(booking.odometer_in).toLocaleString()} km`} />
          )}
          {booking.odometer_out != null && (
            <Row colors={colors} label="Odometer (Drop-off)" value={`${Number(booking.odometer_out).toLocaleString()} km`} />
          )}
        </View>

        {/* Cost breakdown */}
        <View style={[styles.section, { backgroundColor: colors.bgElevated }]}>
          <Text style={[styles.sectionLabel, { color: colors.textSubtle }]}>COST BREAKDOWN</Text>
          <Row
            colors={colors}
            label={`Daily Rate × ${booking.days}`}
            value={`$${(booking.days ? (booking.subtotal || 0) / booking.days : 0).toFixed(2)} × ${booking.days}`}
          />
          <Row colors={colors} label="Subtotal" value={`$${(booking.subtotal || 0).toFixed(2)}`} bold />
          {(booking as any).promo_code && (booking as any).discount_amount > 0 && (
            <Row
              colors={colors}
              label={`Promo (${(booking as any).promo_code})`}
              value={`−$${((booking as any).discount_amount || 0).toFixed(2)}`}
            />
          )}
          {!!booking.extra_mileage_fee && booking.extra_mileage_fee > 0 && (
            <Row
              colors={colors}
              label={`Extra Mileage (${booking.extra_mileage_km || 0} km × $${(booking.extra_mileage_rate || 0).toFixed(2)})`}
              value={`$${booking.extra_mileage_fee.toFixed(2)}`}
            />
          )}
          <Row
            colors={colors}
            label={`${taxLabel((booking.pickup_location as any)?.country)} (${booking.tax_rate || 0}%)`}
            value={`$${(booking.tax_amount || 0).toFixed(2)}`}
            hint={booking.pickup_location?.name}
          />
        </View>

        {/* Grand total — intentionally always brand-red */}
        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>GRAND TOTAL</Text>
          <Text style={styles.totalValue}>${(booking.total_price || 0).toFixed(2)}</Text>
          <Text style={styles.totalCurrency}>USD</Text>
        </View>

        {/* Refundable security deposit */}
        {!!booking.deposit && booking.deposit > 0 && (
          <View style={styles.depositCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons name="shield-half" size={20} color="#FFFFFF" />
              <Text style={styles.depositLabel}>REFUNDABLE SECURITY DEPOSIT</Text>
            </View>
            <Text style={styles.depositValue}>${booking.deposit.toFixed(2)} USD</Text>
            <Text style={styles.depositHint}>
              Collected at pickup. Refunded at drop-off if no damages or extras are owed. Not included in the grand total.
            </Text>
          </View>
        )}

        {/* Actions */}
        <TouchableOpacity style={[styles.downloadBtn, { backgroundColor: isDark ? colors.bgElevated : '#0A0A0A', borderWidth: isDark ? 1 : 0, borderColor: colors.border }]} onPress={downloadPdf} disabled={downloading} activeOpacity={0.7}>
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

        {/* Cancel Booking button — only shown when cancellation is allowed.
            Backend enforces the actual 24h policy; this is a UI guard. */}
        {canCancel && (
          <TouchableOpacity
            testID="cancel-booking-btn"
            style={styles.cancelBtn}
            onPress={() => setCancelModalVisible(true)}
            disabled={cancelling}
            activeOpacity={0.7}
          >
            <Ionicons name="close-circle-outline" size={20} color="#FF3B30" />
            <Text style={styles.cancelBtnText}>{tr('cancelBooking')}</Text>
          </TouchableOpacity>
        )}

        <Text style={[styles.footer, { color: colors.textMuted }]}>Thank you for choosing DAMS Car Rental.</Text>
        <Text style={[styles.footerSmall, { color: colors.textSubtle }]}>support@damscarrental.com</Text>
      </ScrollView>

      {/* Cancel-confirmation modal */}
      <Modal
        visible={cancelModalVisible}
        animationType="fade"
        transparent
        onRequestClose={() => !cancelling && setCancelModalVisible(false)}
      >
        <View style={styles.cancelModalOverlay}>
          <View style={styles.cancelModalCard}>
            <View style={styles.cancelModalHeader}>
              <Ionicons name="alert-circle" size={28} color="#FF9500" />
              <Text style={styles.cancelModalTitle}>{tr('cancelBookingTitle')}</Text>
            </View>
            <Text style={styles.cancelModalSub}>{tr('cancelBookingSub')}</Text>
            <View style={styles.cancelPolicyBox}>
              <Ionicons name="information-circle-outline" size={16} color="#0a5d2b" />
              <Text style={styles.cancelPolicyText}>{tr('cancellationPolicy')}</Text>
            </View>
            <View style={styles.cancelActions}>
              <TouchableOpacity
                testID="cancel-modal-keep"
                style={styles.cancelKeepBtn}
                onPress={() => setCancelModalVisible(false)}
                disabled={cancelling}
                activeOpacity={0.7}
              >
                <Text style={styles.cancelKeepBtnText}>{tr('keepBooking')}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="cancel-modal-confirm"
                style={[styles.cancelConfirmBtn, cancelling && { opacity: 0.6 }]}
                onPress={handleCancelBooking}
                disabled={cancelling}
                activeOpacity={0.7}
              >
                {cancelling ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.cancelConfirmBtnText}>{tr('confirmCancelBooking')}</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function Row({ label, value, bold, hint, colors }: { label: string; value: string; bold?: boolean; hint?: string; colors: any }) {
  return (
    <View style={styles.row}>
      <Text style={[styles.rowLabel, { color: colors.textMuted }]}>
        {label}
        {hint ? <Text style={[styles.rowHint, { color: colors.textSubtle }]}>  · {hint}</Text> : null}
      </Text>
      <Text style={[styles.rowValue, { color: colors.text }, bold && { fontWeight: '800' }]}>{value}</Text>
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
  headerTitle: { flex: 1, alignItems: 'center', gap: 2 },
  headerSub: { fontSize: 9, color: '#FF3B30', fontWeight: '800', letterSpacing: 3, marginTop: -2 },
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
  depositCard: { backgroundColor: '#0a3d80', borderRadius: 16, padding: 16, marginTop: 12, marginBottom: 4 },
  depositLabel: { color: '#FFF', fontSize: 12, fontWeight: '800', letterSpacing: 0.8 },
  depositValue: { color: '#FFF', fontSize: 22, fontWeight: '900', marginTop: 8 },
  depositHint: { color: '#cfe0ff', fontSize: 11, fontWeight: '600', marginTop: 6, lineHeight: 15 },

  downloadBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#0A0A0A', borderRadius: 50, paddingVertical: 16, marginTop: 4,
  },
  downloadBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },

  footer: { textAlign: 'center', fontSize: 13, color: '#666', marginTop: 20 },
  footerSmall: { textAlign: 'center', fontSize: 11, color: '#999', marginTop: 4 },

  primaryBtn: { backgroundColor: '#FF3B30', paddingHorizontal: 24, paddingVertical: 14, borderRadius: 50, marginTop: 8 },
  primaryBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },

  // ---- Cancel Booking button ----
  cancelBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, marginTop: 10, borderRadius: 50, backgroundColor: '#FFF', borderWidth: 1.5, borderColor: '#FFD2CE' },
  cancelBtnText: { color: '#FF3B30', fontWeight: '800', fontSize: 15 },

  // ---- Cancel-confirmation modal ----
  cancelModalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  cancelModalCard: { width: '100%', maxWidth: 420, backgroundColor: '#FFFFFF', borderRadius: 20, padding: 22 },
  cancelModalHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 },
  cancelModalTitle: { fontSize: 19, fontWeight: '900', color: '#0A0A0A', flex: 1 },
  cancelModalSub: { fontSize: 14, color: '#444', marginBottom: 14, lineHeight: 20 },
  cancelPolicyBox: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: '#e6f9ed', borderWidth: 1, borderColor: '#a4e1be', borderRadius: 10, padding: 10, marginBottom: 14 },
  cancelPolicyText: { flex: 1, fontSize: 12, color: '#0a5d2b', fontWeight: '700' },
  cancelActions: { flexDirection: 'row', gap: 10 },
  cancelKeepBtn: { flex: 1, paddingVertical: 14, borderRadius: 50, backgroundColor: '#F5F5F5', alignItems: 'center', justifyContent: 'center' },
  cancelKeepBtnText: { fontSize: 15, fontWeight: '800', color: '#0A0A0A' },
  cancelConfirmBtn: { flex: 1.3, paddingVertical: 14, borderRadius: 50, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center' },
  cancelConfirmBtnText: { fontSize: 15, fontWeight: '800', color: '#FFFFFF' },
});
