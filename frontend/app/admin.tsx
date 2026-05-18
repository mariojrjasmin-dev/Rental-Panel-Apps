import { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, FlatList, TextInput, ScrollView, Alert, ActivityIndicator, KeyboardAvoidingView, Platform, Image, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as ImagePicker from 'expo-image-picker';
import { useAuth } from './_layout';

import { BACKEND_URL } from '../src/config';

const EMPTY_CAR = {
  name: '', brand: '', model: '', year: 2024, category: 'Sedan', price_per_day: 0,
  seats: 5, transmission: 'Automatic', fuel_type: 'Gasoline', description: '', image_url: '',
  pickup_location: { name: '', lat: 0, lng: 0, address: '' },
  dropoff_location: { name: '', lat: 0, lng: 0, address: '' },
  available: true,
};

const CATEGORIES = ['Sedan', 'SUV', 'Luxury', 'Electric', 'Sports', 'Compact'];

export default function AdminScreen() {
  const [cars, setCars] = useState<any[]>([]);
  const [locations, setLocations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editCar, setEditCar] = useState<any>(null);
  const [form, setForm] = useState({ ...EMPTY_CAR });
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [uploading, setUploading] = useState(false);
  const { user } = useAuth();
  const router = useRouter();

  const fetchData = useCallback(async () => {
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const headers = { 'Authorization': `Bearer ${token}` };
      const [carsRes, statsRes, locsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/cars/all`, { headers }),
        fetch(`${BACKEND_URL}/api/admin/stats`, { headers }),
        fetch(`${BACKEND_URL}/api/locations`),
      ]);
      if (carsRes.ok) setCars(await carsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      if (locsRes.ok) setLocations(await locsRes.json());
    } catch (e) { console.log(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openAdd = () => { setEditCar(null); setForm({ ...EMPTY_CAR }); setShowForm(true); };
  const openEdit = (car: any) => {
    setEditCar(car);
    setForm({
      name: car.name || '', brand: car.brand || '', model: car.model || '', year: car.year || 2024,
      category: car.category || 'Sedan', price_per_day: car.price_per_day || 0, seats: car.seats || 5,
      transmission: car.transmission || 'Automatic', fuel_type: car.fuel_type || 'Gasoline',
      description: car.description || '', image_url: car.image_url || '', available: car.available !== false,
      pickup_location: car.pickup_location || { name: '', lat: 0, lng: 0, address: '' },
      dropoff_location: car.dropoff_location || { name: '', lat: 0, lng: 0, address: '' },
    });
    setShowForm(true);
  };

  const selectLocation = (field: 'pickup_location' | 'dropoff_location', loc: any) => {
    setForm(prev => ({
      ...prev,
      [field]: { name: loc.name, lat: loc.lat, lng: loc.lng, address: loc.address || '' },
    }));
  };

  const pickImage = async () => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Platform.OS === 'web' ? window.alert('Permission to access photos is required') : Alert.alert('Permission needed', 'Permission to access photos is required');
        return;
      }
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [16, 9], quality: 0.7, base64: true });
      if (!result.canceled && result.assets?.[0]?.base64) {
        setUploading(true);
        try {
          const token = await AsyncStorage.getItem('auth_token');
          const ext = result.assets[0].uri?.split('.').pop() || 'jpg';
          const res = await fetch(`${BACKEND_URL}/api/upload/image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ image_data: result.assets[0].base64, filename: `car_${Date.now()}.${ext}` }),
          });
          if (res.ok) { const data = await res.json(); setForm(prev => ({ ...prev, image_url: data.url })); }
        } catch (e) { console.log('Upload error:', e); }
        setUploading(false);
      }
    } catch (e) { console.log('Image picker error:', e); }
  };

  const saveCar = async () => {
    if (!form.name || !form.brand || !form.price_per_day) {
      Platform.OS === 'web' ? window.alert('Name, brand, and price are required') : Alert.alert('Error', 'Name, brand, and price are required');
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
      if (res.ok) { setShowForm(false); fetchData(); }
      else {
        const err = await res.json();
        const msg = typeof err.detail === 'string' ? err.detail : 'Save failed';
        Platform.OS === 'web' ? window.alert(msg) : Alert.alert('Error', msg);
      }
    } catch (e: any) {
      Platform.OS === 'web' ? window.alert(e.message) : Alert.alert('Error', e.message);
    }
    setSaving(false);
  };

  const deleteCar = (car: any) => {
    const doDelete = async () => {
      const token = await AsyncStorage.getItem('auth_token');
      await fetch(`${BACKEND_URL}/api/cars/${car.id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
      fetchData();
    };
    if (Platform.OS === 'web') { if (window.confirm(`Delete ${car.name}?`)) doDelete(); }
    else { Alert.alert('Delete Car', `Delete ${car.name}?`, [{ text: 'Cancel', style: 'cancel' }, { text: 'Delete', style: 'destructive', onPress: doDelete }]); }
  };

  // ============ FORM VIEW ============
  if (showForm) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.topBar}>
          <TouchableOpacity testID="form-back-btn" style={styles.backBtn} onPress={() => setShowForm(false)}>
            <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
          </TouchableOpacity>
          <Text style={styles.topTitle}>{editCar ? 'Edit Car' : 'Add New Car'}</Text>
          <View style={{ width: 44 }} />
        </View>
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView style={styles.formScroll} keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: 60 }}>
            {/* Image */}
            <Text style={styles.label}>Car Photo</Text>
            {form.image_url ? (
              <View style={styles.imgPreviewWrap}>
                <Image source={{ uri: form.image_url }} style={styles.imgPreview} resizeMode="cover" />
                <TouchableOpacity testID="remove-image-btn" style={styles.removeImgBtn} onPress={() => setForm({ ...form, image_url: '' })}>
                  <Ionicons name="close-circle" size={28} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity testID="pick-image-btn" style={styles.imgPlaceholder} onPress={pickImage} disabled={uploading}>
                {uploading ? <ActivityIndicator color="#FF3B30" /> : (
                  <>
                    <Ionicons name="images-outline" size={36} color="#CCC" />
                    <Text style={styles.imgPlaceholderText}>Tap to select photo</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
            <TextInput testID="car-image-input" style={styles.input} value={form.image_url} onChangeText={v => setForm({...form, image_url: v})} placeholder="Or paste image URL" />

            {/* Basic info */}
            <Text style={styles.label}>Name *</Text>
            <TextInput testID="car-name-input" style={styles.input} value={form.name} onChangeText={v => setForm({...form, name: v})} placeholder="e.g. Tesla Model 3" />

            <Text style={styles.label}>Brand *</Text>
            <TextInput testID="car-brand-input" style={styles.input} value={form.brand} onChangeText={v => setForm({...form, brand: v})} placeholder="e.g. Tesla" />

            <Text style={styles.label}>Model</Text>
            <TextInput testID="car-model-input" style={styles.input} value={form.model} onChangeText={v => setForm({...form, model: v})} placeholder="e.g. Model 3" />

            <View style={styles.row}>
              <View style={{ flex: 1 }}><Text style={styles.label}>Year</Text>
                <TextInput testID="car-year-input" style={styles.input} value={String(form.year)} onChangeText={v => setForm({...form, year: parseInt(v) || 2024})} keyboardType="numeric" />
              </View>
              <View style={{ flex: 1 }}><Text style={styles.label}>Seats</Text>
                <TextInput style={styles.input} value={String(form.seats)} onChangeText={v => setForm({...form, seats: parseInt(v) || 5})} keyboardType="numeric" />
              </View>
            </View>

            <Text style={styles.label}>Category</Text>
            <View style={styles.catRow}>
              {CATEGORIES.map(c => (
                <TouchableOpacity key={c} style={[styles.catPill, form.category === c && styles.catPillActive]} onPress={() => setForm({...form, category: c})}>
                  <Text style={[styles.catPillText, form.category === c && styles.catPillTextActive]}>{c}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.label}>Price per day ($) *</Text>
            <TextInput testID="car-price-input" style={styles.input} value={String(form.price_per_day)} onChangeText={v => setForm({...form, price_per_day: parseFloat(v) || 0})} keyboardType="decimal-pad" />

            <Text style={styles.label}>Description</Text>
            <TextInput style={[styles.input, { minHeight: 80, textAlignVertical: 'top' }]} value={form.description} onChangeText={v => setForm({...form, description: v})} multiline placeholder="Brief description..." />

            {/* Pickup Location */}
            <Text style={styles.sectionHeader}>Pickup Location</Text>
            {form.pickup_location?.name ? (
              <View style={styles.selectedLoc}>
                <View style={[styles.locDot, { backgroundColor: '#34C759' }]} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.selectedLocName}>{form.pickup_location.name}</Text>
                  <Text style={styles.selectedLocCoords}>{form.pickup_location.lat}, {form.pickup_location.lng}</Text>
                </View>
                <TouchableOpacity onPress={() => setForm({...form, pickup_location: { name: '', lat: 0, lng: 0, address: '' }})}>
                  <Ionicons name="close-circle" size={22} color="#999" />
                </TouchableOpacity>
              </View>
            ) : null}
            <Text style={styles.subLabel}>Select from locations:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.locPills}>
              {locations.map(loc => (
                <TouchableOpacity
                  key={`pickup-${loc.id}`}
                  style={[styles.locPill, form.pickup_location?.name === loc.name && styles.locPillActive]}
                  onPress={() => selectLocation('pickup_location', loc)}
                >
                  <Ionicons name="location" size={12} color={form.pickup_location?.name === loc.name ? '#FFF' : '#34C759'} />
                  <Text style={[styles.locPillText, form.pickup_location?.name === loc.name && styles.locPillTextActive]} numberOfLines={1}>{loc.name}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Dropoff Location */}
            <Text style={styles.sectionHeader}>Drop-off Location</Text>
            {form.dropoff_location?.name ? (
              <View style={styles.selectedLoc}>
                <View style={[styles.locDot, { backgroundColor: '#FF3B30' }]} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.selectedLocName}>{form.dropoff_location.name}</Text>
                  <Text style={styles.selectedLocCoords}>{form.dropoff_location.lat}, {form.dropoff_location.lng}</Text>
                </View>
                <TouchableOpacity onPress={() => setForm({...form, dropoff_location: { name: '', lat: 0, lng: 0, address: '' }})}>
                  <Ionicons name="close-circle" size={22} color="#999" />
                </TouchableOpacity>
              </View>
            ) : null}
            <Text style={styles.subLabel}>Select from locations:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.locPills}>
              {locations.map(loc => (
                <TouchableOpacity
                  key={`dropoff-${loc.id}`}
                  style={[styles.locPill, form.dropoff_location?.name === loc.name && styles.locPillActiveRed]}
                  onPress={() => selectLocation('dropoff_location', loc)}
                >
                  <Ionicons name="location" size={12} color={form.dropoff_location?.name === loc.name ? '#FFF' : '#FF3B30'} />
                  <Text style={[styles.locPillText, form.dropoff_location?.name === loc.name && styles.locPillTextActive]} numberOfLines={1}>{loc.name}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TouchableOpacity testID="save-car-btn" style={styles.saveBtn} onPress={saveCar} disabled={saving}>
              {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>{editCar ? 'Update Car' : 'Add Car'}</Text>}
            </TouchableOpacity>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  // ============ LIST VIEW ============
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
          keyExtractor={item => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.carRow} onPress={() => openEdit(item)} activeOpacity={0.7}>
              {item.image_url ? (
                <Image source={{ uri: item.image_url }} style={styles.carThumb} resizeMode="cover" />
              ) : (
                <View style={[styles.carThumb, styles.carThumbPlaceholder]}><Ionicons name="car-outline" size={20} color="#999" /></View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={styles.carName}>{item.name}</Text>
                <Text style={styles.carSub}>{item.category} - ${item.price_per_day}/day</Text>
                {item.pickup_location?.name ? (
                  <Text style={styles.carLoc} numberOfLines={1}><Ionicons name="location-outline" size={11} color="#007AFF" /> {item.pickup_location.name}</Text>
                ) : null}
              </View>
              <View style={styles.carActions}>
                <TouchableOpacity testID={`edit-car-${item.id}`} style={styles.actionBtn} onPress={() => openEdit(item)}>
                  <Ionicons name="create-outline" size={20} color="#007AFF" />
                </TouchableOpacity>
                <TouchableOpacity testID={`delete-car-${item.id}`} style={styles.actionBtn} onPress={() => deleteCar(item)}>
                  <Ionicons name="trash-outline" size={20} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          )}
        />
      )}
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
  list: { paddingHorizontal: 16, paddingBottom: 24 },
  carRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F5F5F5', gap: 12 },
  carThumb: { width: 56, height: 42, borderRadius: 10, backgroundColor: '#F5F5F5' },
  carThumbPlaceholder: { justifyContent: 'center', alignItems: 'center' },
  carName: { fontSize: 16, fontWeight: '700', color: '#0A0A0A' },
  carSub: { fontSize: 13, color: '#666', marginTop: 2 },
  carLoc: { fontSize: 11, color: '#007AFF', marginTop: 2 },
  carActions: { flexDirection: 'row', gap: 8 },
  actionBtn: { width: 40, height: 40, borderRadius: 10, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  // Form
  formScroll: { flex: 1, paddingHorizontal: 24 },
  label: { fontSize: 12, fontWeight: '700', color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6, marginTop: 16 },
  subLabel: { fontSize: 11, color: '#BBB', marginBottom: 6, marginTop: 4 },
  sectionHeader: { fontSize: 14, fontWeight: '800', color: '#0A0A0A', marginTop: 24, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 },
  input: { backgroundColor: '#F5F5F5', borderRadius: 12, padding: 14, fontSize: 15, color: '#0A0A0A', borderWidth: 1, borderColor: '#E5E5E5' },
  row: { flexDirection: 'row', gap: 12 },
  imgPreviewWrap: { borderRadius: 16, overflow: 'hidden', marginBottom: 8 },
  imgPreview: { width: '100%', height: 160, borderRadius: 16, backgroundColor: '#F5F5F5' },
  removeImgBtn: { position: 'absolute', top: 8, right: 8, backgroundColor: '#FFF', borderRadius: 14 },
  imgPlaceholder: { width: '100%', height: 120, borderRadius: 16, backgroundColor: '#F5F5F5', borderWidth: 2, borderColor: '#E5E5E5', borderStyle: 'dashed', justifyContent: 'center', alignItems: 'center', gap: 8, marginBottom: 8 },
  imgPlaceholderText: { fontSize: 14, color: '#999' },
  catRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  catPill: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 50, backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5' },
  catPillActive: { backgroundColor: '#0A0A0A', borderColor: '#0A0A0A' },
  catPillText: { fontSize: 13, fontWeight: '600', color: '#666' },
  catPillTextActive: { color: '#FFF' },
  // Location selection
  selectedLoc: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#F5F5F5', padding: 12, borderRadius: 12, marginBottom: 6 },
  locDot: { width: 12, height: 12, borderRadius: 6 },
  selectedLocName: { fontSize: 14, fontWeight: '700', color: '#0A0A0A' },
  selectedLocCoords: { fontSize: 11, color: '#999' },
  locPills: { gap: 8, paddingBottom: 4 },
  locPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 50, backgroundColor: '#F0FFF4', borderWidth: 1, borderColor: '#D5F5E3' },
  locPillActive: { backgroundColor: '#34C759', borderColor: '#34C759' },
  locPillActiveRed: { backgroundColor: '#FF3B30', borderColor: '#FF3B30' },
  locPillText: { fontSize: 12, fontWeight: '600', color: '#333', maxWidth: 120 },
  locPillTextActive: { color: '#FFF' },
  saveBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', marginTop: 24 },
  saveBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
});
