import { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, FlatList, TextInput, Modal, ScrollView, Alert, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const EMPTY_LOC = { name: '', address: '', city: '', country: '', lat: '', lng: '', type: 'both' };

export default function AdminLocationsScreen() {
  const [locations, setLocations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editLoc, setEditLoc] = useState<any>(null);
  const [form, setForm] = useState({ ...EMPTY_LOC });
  const [saving, setSaving] = useState(false);
  const [filterCity, setFilterCity] = useState('');
  const router = useRouter();

  const fetchLocations = useCallback(async () => {
    try {
      let url = `${BACKEND_URL}/api/locations`;
      if (filterCity) url += `?city=${filterCity}`;
      const res = await fetch(url);
      if (res.ok) setLocations(await res.json());
    } catch (e) { console.log(e); }
    setLoading(false);
  }, [filterCity]);

  useEffect(() => { fetchLocations(); }, [fetchLocations]);

  const openAdd = () => { setEditLoc(null); setForm({ ...EMPTY_LOC }); setShowModal(true); };
  const openEdit = (loc: any) => {
    setEditLoc(loc);
    setForm({
      name: loc.name, address: loc.address, city: loc.city, country: loc.country,
      lat: String(loc.lat), lng: String(loc.lng), type: loc.type || 'both',
    });
    setShowModal(true);
  };

  const saveLoc = async () => {
    if (!form.name || !form.city || !form.lat || !form.lng) {
      if (Platform.OS === 'web') { window.alert('Name, city, latitude, and longitude are required'); }
      else { Alert.alert('Error', 'Name, city, latitude, and longitude are required'); }
      return;
    }
    setSaving(true);
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const url = editLoc ? `${BACKEND_URL}/api/locations/${editLoc.id}` : `${BACKEND_URL}/api/locations`;
      const body = { ...form, lat: parseFloat(form.lat), lng: parseFloat(form.lng) };
      const res = await fetch(url, {
        method: editLoc ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (res.ok) { setShowModal(false); fetchLocations(); }
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

  const deleteLoc = (loc: any) => {
    const doDelete = async () => {
      const token = await AsyncStorage.getItem('auth_token');
      await fetch(`${BACKEND_URL}/api/locations/${loc.id}`, {
        method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` },
      });
      fetchLocations();
    };
    if (Platform.OS === 'web') {
      if (window.confirm(`Delete ${loc.name}?`)) doDelete();
    } else {
      Alert.alert('Delete Location', `Delete ${loc.name}?`, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: doDelete },
      ]);
    }
  };

  const cities = [...new Set(locations.map(l => l.city))];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.topBar}>
        <TouchableOpacity testID="loc-back-btn" style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
        </TouchableOpacity>
        <Text style={styles.topTitle}>Locations</Text>
        <TouchableOpacity testID="add-location-btn" style={styles.addBtn} onPress={openAdd}>
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </View>

      {/* City filter */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
        <TouchableOpacity
          style={[styles.filterPill, !filterCity && styles.filterPillActive]}
          onPress={() => setFilterCity('')}
        >
          <Text style={[styles.filterText, !filterCity && styles.filterTextActive]}>All</Text>
        </TouchableOpacity>
        {cities.map(c => (
          <TouchableOpacity
            key={c}
            style={[styles.filterPill, filterCity === c && styles.filterPillActive]}
            onPress={() => setFilterCity(filterCity === c ? '' : c)}
          >
            <Text style={[styles.filterText, filterCity === c && styles.filterTextActive]}>{c}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color="#FF3B30" /></View>
      ) : locations.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="location-outline" size={64} color="#E5E5E5" />
          <Text style={styles.emptyText}>No locations yet</Text>
        </View>
      ) : (
        <FlatList
          testID="locations-list"
          data={locations}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.locCard}>
              <View style={styles.locIconWrap}>
                <Ionicons name="location" size={24} color="#FF3B30" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.locName}>{item.name}</Text>
                <Text style={styles.locAddress} numberOfLines={1}>{item.address}</Text>
                <View style={styles.locMeta}>
                  <View style={styles.locTag}><Text style={styles.locTagText}>{item.city}</Text></View>
                  <View style={styles.locTag}><Text style={styles.locTagText}>{item.country}</Text></View>
                  <Text style={styles.locCoords}>{item.lat.toFixed(4)}, {item.lng.toFixed(4)}</Text>
                </View>
              </View>
              <View style={styles.locActions}>
                <TouchableOpacity testID={`edit-loc-${item.id}`} style={styles.actionBtn} onPress={() => openEdit(item)}>
                  <Ionicons name="create-outline" size={18} color="#007AFF" />
                </TouchableOpacity>
                <TouchableOpacity testID={`delete-loc-${item.id}`} style={styles.actionBtn} onPress={() => deleteLoc(item)}>
                  <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            </View>
          )}
        />
      )}

      {/* Add/Edit Modal */}
      <Modal visible={showModal} animationType="slide" transparent>
        <KeyboardAvoidingView style={styles.modalOverlay} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{editLoc ? 'Edit Location' : 'Add Location'}</Text>
              <TouchableOpacity testID="close-loc-modal" onPress={() => setShowModal(false)}>
                <Ionicons name="close" size={24} color="#0A0A0A" />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalScroll} keyboardShouldPersistTaps="handled">
              <Text style={styles.label}>Name *</Text>
              <TextInput testID="loc-name-input" style={styles.input} value={form.name} onChangeText={v => setForm({...form, name: v})} placeholder="e.g. Punta Cana Airport" />

              <Text style={styles.label}>Address</Text>
              <TextInput testID="loc-address-input" style={styles.input} value={form.address} onChangeText={v => setForm({...form, address: v})} placeholder="Full address" />

              <Text style={styles.label}>City *</Text>
              <TextInput testID="loc-city-input" style={styles.input} value={form.city} onChangeText={v => setForm({...form, city: v})} placeholder="e.g. Punta Cana" />

              <Text style={styles.label}>Country</Text>
              <TextInput testID="loc-country-input" style={styles.input} value={form.country} onChangeText={v => setForm({...form, country: v})} placeholder="e.g. Dominican Republic" />

              <View style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.label}>Latitude *</Text>
                  <TextInput testID="loc-lat-input" style={styles.input} value={form.lat} onChangeText={v => setForm({...form, lat: v})} keyboardType="decimal-pad" placeholder="18.5670" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.label}>Longitude *</Text>
                  <TextInput testID="loc-lng-input" style={styles.input} value={form.lng} onChangeText={v => setForm({...form, lng: v})} keyboardType="decimal-pad" placeholder="-68.3634" />
                </View>
              </View>

              <Text style={styles.label}>Type</Text>
              <View style={styles.typeRow}>
                {['both', 'pickup', 'dropoff'].map(t => (
                  <TouchableOpacity key={t} style={[styles.typePill, form.type === t && styles.typePillActive]} onPress={() => setForm({...form, type: t})}>
                    <Text style={[styles.typeText, form.type === t && styles.typeTextActive]}>{t === 'both' ? 'Pickup & Dropoff' : t.charAt(0).toUpperCase() + t.slice(1)}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity testID="save-loc-btn" style={styles.saveBtn} onPress={saveLoc} disabled={saving}>
                {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>{editLoc ? 'Update' : 'Add Location'}</Text>}
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
  filterRow: { paddingHorizontal: 16, paddingBottom: 12, gap: 8 },
  filterPill: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 50, backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5' },
  filterPillActive: { backgroundColor: '#0A0A0A', borderColor: '#0A0A0A' },
  filterText: { fontSize: 13, fontWeight: '600', color: '#666' },
  filterTextActive: { color: '#FFF' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyText: { fontSize: 16, color: '#999' },
  list: { paddingHorizontal: 16, paddingBottom: 24 },
  locCard: { flexDirection: 'row', alignItems: 'center', padding: 14, backgroundColor: '#FFF', borderRadius: 16, marginBottom: 10, borderWidth: 1, borderColor: '#E5E5E5', gap: 12 },
  locIconWrap: { width: 48, height: 48, borderRadius: 14, backgroundColor: '#FFF0F0', justifyContent: 'center', alignItems: 'center' },
  locName: { fontSize: 15, fontWeight: '700', color: '#0A0A0A' },
  locAddress: { fontSize: 12, color: '#666', marginTop: 2 },
  locMeta: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 },
  locTag: { backgroundColor: '#F5F5F5', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  locTagText: { fontSize: 10, fontWeight: '700', color: '#666', textTransform: 'uppercase' },
  locCoords: { fontSize: 10, color: '#999' },
  locActions: { gap: 6 },
  actionBtn: { width: 36, height: 36, borderRadius: 8, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20, borderBottomWidth: 1, borderBottomColor: '#E5E5E5' },
  modalTitle: { fontSize: 20, fontWeight: '800', color: '#0A0A0A' },
  modalScroll: { padding: 20 },
  label: { fontSize: 12, fontWeight: '700', color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6, marginTop: 14 },
  input: { backgroundColor: '#F5F5F5', borderRadius: 12, padding: 14, fontSize: 15, color: '#0A0A0A', borderWidth: 1, borderColor: '#E5E5E5' },
  row: { flexDirection: 'row', gap: 12 },
  typeRow: { flexDirection: 'row', gap: 8 },
  typePill: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 50, backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5' },
  typePillActive: { backgroundColor: '#FF3B30', borderColor: '#FF3B30' },
  typeText: { fontSize: 12, fontWeight: '600', color: '#666' },
  typeTextActive: { color: '#FFF' },
  saveBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', marginTop: 24, marginBottom: 40 },
  saveBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
});
