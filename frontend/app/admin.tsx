import { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, FlatList, TextInput, Modal, ScrollView, Alert, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from './_layout';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const EMPTY_CAR = {
  name: '', brand: '', model: '', year: 2024, category: 'Sedan', price_per_day: 0,
  seats: 5, transmission: 'Automatic', fuel_type: 'Gasoline', description: '', image_url: '',
  pickup_location: { name: '', lat: 0, lng: 0 },
  dropoff_location: { name: '', lat: 0, lng: 0 },
  available: true,
};

export default function AdminScreen() {
  const [cars, setCars] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editCar, setEditCar] = useState<any>(null);
  const [form, setForm] = useState({ ...EMPTY_CAR });
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const { user } = useAuth();
  const router = useRouter();

  const fetchData = useCallback(async () => {
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const headers = { 'Authorization': `Bearer ${token}` };
      const [carsRes, statsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/cars/all`, { headers }),
        fetch(`${BACKEND_URL}/api/admin/stats`, { headers }),
      ]);
      if (carsRes.ok) setCars(await carsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (e) { console.log(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openAdd = () => { setEditCar(null); setForm({ ...EMPTY_CAR }); setShowModal(true); };
  const openEdit = (car: any) => {
    setEditCar(car);
    setForm({
      name: car.name, brand: car.brand, model: car.model, year: car.year,
      category: car.category, price_per_day: car.price_per_day, seats: car.seats,
      transmission: car.transmission, fuel_type: car.fuel_type, description: car.description || '',
      image_url: car.image_url || '', available: car.available,
      pickup_location: car.pickup_location || { name: '', lat: 0, lng: 0 },
      dropoff_location: car.dropoff_location || { name: '', lat: 0, lng: 0 },
    });
    setShowModal(true);
  };

  const saveCar = async () => {
    if (!form.name || !form.brand || !form.price_per_day) {
      Alert.alert('Error', 'Name, brand, and price are required');
      return;
    }
    setSaving(true);
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const url = editCar ? `${BACKEND_URL}/api/cars/${editCar.id}` : `${BACKEND_URL}/api/cars`;
      const res = await fetch(url, {
        method: editCar ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ ...form, price_per_day: parseFloat(String(form.price_per_day)), year: parseInt(String(form.year)), seats: parseInt(String(form.seats)) }),
      });
      if (res.ok) {
        setShowModal(false);
        fetchData();
      } else {
        const err = await res.json();
        Alert.alert('Error', typeof err.detail === 'string' ? err.detail : 'Save failed');
      }
    } catch (e: any) { Alert.alert('Error', e.message); }
    setSaving(false);
  };

  const deleteCar = (car: any) => {
    Alert.alert('Delete Car', `Delete ${car.name}?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        const token = await AsyncStorage.getItem('auth_token');
        await fetch(`${BACKEND_URL}/api/cars/${car.id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        });
        fetchData();
      }},
    ]);
  };

  const CATEGORIES = ['Sedan', 'SUV', 'Luxury', 'Electric', 'Sports', 'Compact'];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.topBar}>
        <TouchableOpacity testID="admin-back-btn" style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
        </TouchableOpacity>
        <Text style={styles.topTitle}>Admin Panel</Text>
        <TouchableOpacity testID="add-car-btn" style={styles.addBtn} onPress={openAdd}>
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </View>

      {stats && (
        <View style={styles.statsGrid}>
          <View style={styles.statCard}><Text style={styles.statNum}>{stats.total_cars}</Text><Text style={styles.statLabel}>Cars</Text></View>
          <View style={styles.statCard}><Text style={styles.statNum}>{stats.total_bookings}</Text><Text style={styles.statLabel}>Bookings</Text></View>
          <View style={styles.statCard}><Text style={styles.statNum}>{stats.total_users}</Text><Text style={styles.statLabel}>Users</Text></View>
          <View style={styles.statCard}><Text style={styles.statNum}>{stats.active_bookings}</Text><Text style={styles.statLabel}>Active</Text></View>
        </View>
      )}

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color="#FF3B30" /></View>
      ) : (
        <FlatList
          testID="admin-car-list"
          data={cars}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.carRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.carName}>{item.name}</Text>
                <Text style={styles.carSub}>{item.category} - ${item.price_per_day}/day</Text>
              </View>
              <View style={styles.carActions}>
                <TouchableOpacity testID={`edit-car-${item.id}`} style={styles.actionBtn} onPress={() => openEdit(item)}>
                  <Ionicons name="create-outline" size={20} color="#007AFF" />
                </TouchableOpacity>
                <TouchableOpacity testID={`delete-car-${item.id}`} style={styles.actionBtn} onPress={() => deleteCar(item)}>
                  <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            </View>
          )}
        />
      )}

      <Modal visible={showModal} animationType="slide" transparent>
        <KeyboardAvoidingView style={styles.modalOverlay} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{editCar ? 'Edit Car' : 'Add New Car'}</Text>
              <TouchableOpacity testID="close-modal-btn" onPress={() => setShowModal(false)}>
                <Ionicons name="close" size={24} color="#0A0A0A" />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalScroll} keyboardShouldPersistTaps="handled">
              <Text style={styles.label}>Name</Text>
              <TextInput testID="car-name-input" style={styles.input} value={form.name} onChangeText={(v) => setForm({ ...form, name: v })} placeholder="e.g. Tesla Model 3" />
              
              <Text style={styles.label}>Brand</Text>
              <TextInput testID="car-brand-input" style={styles.input} value={form.brand} onChangeText={(v) => setForm({ ...form, brand: v })} placeholder="e.g. Tesla" />
              
              <Text style={styles.label}>Model</Text>
              <TextInput testID="car-model-input" style={styles.input} value={form.model} onChangeText={(v) => setForm({ ...form, model: v })} placeholder="e.g. Model 3" />
              
              <Text style={styles.label}>Year</Text>
              <TextInput testID="car-year-input" style={styles.input} value={String(form.year)} onChangeText={(v) => setForm({ ...form, year: parseInt(v) || 2024 })} keyboardType="numeric" />
              
              <Text style={styles.label}>Category</Text>
              <View style={styles.catRow}>
                {CATEGORIES.map(c => (
                  <TouchableOpacity key={c} style={[styles.catPill, form.category === c && styles.catPillActive]} onPress={() => setForm({ ...form, category: c })}>
                    <Text style={[styles.catPillText, form.category === c && styles.catPillTextActive]}>{c}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              
              <Text style={styles.label}>Price per day ($)</Text>
              <TextInput testID="car-price-input" style={styles.input} value={String(form.price_per_day)} onChangeText={(v) => setForm({ ...form, price_per_day: parseFloat(v) || 0 })} keyboardType="decimal-pad" />
              
              <Text style={styles.label}>Seats</Text>
              <TextInput style={styles.input} value={String(form.seats)} onChangeText={(v) => setForm({ ...form, seats: parseInt(v) || 5 })} keyboardType="numeric" />
              
              <Text style={styles.label}>Image URL</Text>
              <TextInput testID="car-image-input" style={styles.input} value={form.image_url} onChangeText={(v) => setForm({ ...form, image_url: v })} placeholder="https://..." />

              <Text style={styles.label}>Description</Text>
              <TextInput style={[styles.input, { height: 80 }]} value={form.description} onChangeText={(v) => setForm({ ...form, description: v })} multiline placeholder="Brief description..." />

              <TouchableOpacity testID="save-car-btn" style={styles.saveBtn} onPress={saveCar} disabled={saving}>
                {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>{editCar ? 'Update Car' : 'Add Car'}</Text>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  topTitle: { fontSize: 18, fontWeight: '800', color: '#0A0A0A' },
  addBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FF3B30', justifyContent: 'center', alignItems: 'center' },
  statsGrid: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 16 },
  statCard: { flex: 1, backgroundColor: '#F5F5F5', borderRadius: 14, padding: 14, alignItems: 'center' },
  statNum: { fontSize: 22, fontWeight: '900', color: '#0A0A0A' },
  statLabel: { fontSize: 11, color: '#999', fontWeight: '600', textTransform: 'uppercase', marginTop: 2 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  list: { paddingHorizontal: 16 },
  carRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: '#F5F5F5' },
  carName: { fontSize: 16, fontWeight: '700', color: '#0A0A0A' },
  carSub: { fontSize: 13, color: '#666', marginTop: 2 },
  carActions: { flexDirection: 'row', gap: 8 },
  actionBtn: { width: 40, height: 40, borderRadius: 10, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20, borderBottomWidth: 1, borderBottomColor: '#E5E5E5' },
  modalTitle: { fontSize: 20, fontWeight: '800', color: '#0A0A0A' },
  modalScroll: { padding: 20 },
  label: { fontSize: 13, fontWeight: '700', color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6, marginTop: 12 },
  input: { backgroundColor: '#F5F5F5', borderRadius: 12, padding: 14, fontSize: 16, color: '#0A0A0A', borderWidth: 1, borderColor: '#E5E5E5' },
  catRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  catPill: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 50, backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5' },
  catPillActive: { backgroundColor: '#0A0A0A', borderColor: '#0A0A0A' },
  catPillText: { fontSize: 13, fontWeight: '600', color: '#666' },
  catPillTextActive: { color: '#FFF' },
  saveBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', marginTop: 24, marginBottom: 40 },
  saveBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
});
