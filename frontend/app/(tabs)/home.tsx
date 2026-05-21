import { useState, useEffect, useCallback } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList, Image, ActivityIndicator, RefreshControl, ScrollView } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';
import StarRating from '../../components/StarRating';
import { t as tr } from '../../src/i18n';

import { BACKEND_URL } from '../../src/config';

type Car = {
  id: string;
  name: string;
  brand: string;
  model: string;
  year: number;
  category: string;
  price_per_day: number;
  seats: number;
  transmission: string;
  fuel_type: string;
  image_url: string;
  pickup_location?: { name: string; address?: string };
  dropoff_location?: { name: string; address?: string };
  avg_rating?: number;
  review_count?: number;
};

type Location = {
  id: string;
  name: string;
  city: string;
  country: string;
  address: string;
};

const CATEGORIES = ['All', 'SUV', 'Sedan', 'Luxury', 'Electric', 'Sports'];

export default function HomeScreen() {
  const [cars, setCars] = useState<Car[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [activeCity, setActiveCity] = useState('');
  const { user } = useAuth();
  const router = useRouter();

  // Derive unique cities from locations
  const cities = [...new Set(locations.map(l => l.city))];

  const fetchLocations = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/locations`);
      if (res.ok) setLocations(await res.json());
    } catch (e) { console.log('Fetch locations error:', e); }
  }, []);

  const fetchCars = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (activeCategory !== 'All') params.append('category', activeCategory);
      if (search) params.append('search', search);
      if (activeCity) params.append('city', activeCity);
      const res = await fetch(`${BACKEND_URL}/api/cars?${params.toString()}`);
      if (res.ok) setCars(await res.json());
    } catch (e) { console.log('Fetch cars error:', e); }
    setLoading(false);
    setRefreshing(false);
  }, [activeCategory, search, activeCity]);

  useEffect(() => { fetchLocations(); }, [fetchLocations]);

  // Refetch cars every time the tab is focused (not just on mount)
  useFocusEffect(
    useCallback(() => {
      fetchCars();
    }, [fetchCars])
  );

  const onRefresh = () => { setRefreshing(true); fetchCars(); };

  const clearFilters = () => {
    setActiveCity('');
    setActiveCategory('All');
    setSearch('');
  };

  const hasFilters = activeCity || activeCategory !== 'All' || search;

  const renderCar = ({ item }: { item: Car }) => (
    <TouchableOpacity
      testID={`car-card-${item.id}`}
      style={styles.carCard}
      activeOpacity={0.7}
      onPress={() => router.push({ pathname: '/car-detail', params: { id: item.id } })}
    >
      <Image source={{ uri: item.image_url }} style={styles.carImage} resizeMode="cover" />
      <View style={styles.carInfo}>
        <Text style={styles.carName} numberOfLines={1}>{item.name}</Text>
        <View style={styles.categoryBadgeSolo}>
          <Text style={styles.categoryText}>Or Similar | {item.category}</Text>
        </View>
        {item.pickup_location && (
          <View style={styles.locationRow}>
            <Ionicons name="location-outline" size={13} color="#007AFF" />
            <Text style={styles.locationText} numberOfLines={1}>{item.pickup_location.name}</Text>
          </View>
        )}
        {(item.avg_rating !== undefined && item.avg_rating > 0) && (
          <View style={styles.ratingRow}>
            <StarRating rating={item.avg_rating} size={14} showValue count={item.review_count} />
          </View>
        )}
        <View style={styles.carSpecs}>
          <View style={styles.specItem}>
            <Ionicons name="people-outline" size={14} color="#666" />
            <Text style={styles.specText}>{item.seats} seats</Text>
          </View>
          <View style={styles.specItem}>
            <Ionicons name="bag-handle-outline" size={14} color="#666" />
            <Text style={styles.specText}>{item.bags ?? 2} bags</Text>
          </View>
          <View style={styles.specItem}>
            <Ionicons name="cog-outline" size={14} color="#666" />
            <Text style={styles.specText}>{item.transmission}</Text>
          </View>
          <View style={styles.specItem}>
            <Ionicons name="flash-outline" size={14} color="#666" />
            <Text style={styles.specText}>{item.fuel_type}</Text>
          </View>
        </View>
        <View style={styles.carFooter}>
          <Text style={styles.price}>${item.price_per_day}</Text>
          <Text style={styles.priceUnit}>/day</Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.topBar}>
        <View>
          <Text style={styles.greeting}>{tr('welcomeNew')}{user?.name ? `, ${user.name}` : ''}</Text>
          <Text style={styles.title}>DAMS CAR RENTAL</Text>
        </View>
        <TouchableOpacity testID="profile-avatar" style={styles.avatar} onPress={() => router.push('/(tabs)/profile')}>
          <Ionicons name="person-circle" size={40} color="#0A0A0A" />
        </TouchableOpacity>
      </View>

      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#999" />
        <TextInput
          testID="car-search-input"
          style={styles.searchInput}
          placeholder={tr('findCar')}
          placeholderTextColor="#999"
          value={search}
          onChangeText={setSearch}
          onSubmitEditing={fetchCars}
          returnKeyType="search"
        />
        {search ? (
          <TouchableOpacity onPress={() => setSearch('')}>
            <Ionicons name="close-circle" size={20} color="#999" />
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Location filter */}
      {cities.length > 0 && (
        <View>
          <View style={styles.sectionHeader}>
            <Ionicons name="location" size={16} color="#FF3B30" />
            <Text style={styles.sectionLabel}>Location</Text>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterList}>
            <TouchableOpacity
              testID="location-all"
              style={[styles.locationPill, !activeCity && styles.locationPillActive]}
              onPress={() => setActiveCity('')}
            >
              <Ionicons name="globe-outline" size={14} color={!activeCity ? '#FFF' : '#FF3B30'} />
              <Text style={[styles.locationPillText, !activeCity && styles.locationPillTextActive]}>All Locations</Text>
            </TouchableOpacity>
            {cities.map(c => (
              <TouchableOpacity
                key={c}
                testID={`location-${c.replace(/\s/g, '-')}`}
                style={[styles.locationPill, activeCity === c && styles.locationPillActive]}
                onPress={() => setActiveCity(activeCity === c ? '' : c)}
              >
                <Ionicons name="location-outline" size={14} color={activeCity === c ? '#FFF' : '#FF3B30'} />
                <Text style={[styles.locationPillText, activeCity === c && styles.locationPillTextActive]}>{c}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      )}

      {/* Category filter */}
      <View>
        <View style={styles.sectionHeader}>
          <Ionicons name="car-sport" size={16} color="#FF3B30" />
          <Text style={styles.sectionLabel}>Vehicle Type</Text>
        </View>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.categoriesList}
        >
          {CATEGORIES.map(item => (
            <TouchableOpacity
              key={item}
              testID={`category-${item}`}
              style={[styles.categoryPill, activeCategory === item && styles.categoryPillActive]}
              onPress={() => setActiveCategory(item)}
            >
              <Text style={[styles.categoryPillText, activeCategory === item && styles.categoryPillTextActive]}>{item}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Active filters bar */}
      {hasFilters ? (
        <View style={styles.activeFiltersBar}>
          <Text style={styles.resultCount}>{cars.length} car{cars.length !== 1 ? 's' : ''} found</Text>
          <TouchableOpacity testID="clear-filters-btn" onPress={clearFilters} style={styles.clearBtn}>
            <Ionicons name="close-circle" size={16} color="#FF3B30" />
            <Text style={styles.clearBtnText}>Clear</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {loading ? (
        <View style={styles.centerContent}>
          <ActivityIndicator size="large" color="#FF3B30" />
        </View>
      ) : cars.length === 0 ? (
        <View style={styles.centerContent}>
          <Ionicons name="car-outline" size={64} color="#E5E5E5" />
          <Text style={styles.emptyText}>No cars found</Text>
          {hasFilters ? (
            <TouchableOpacity testID="clear-filters-empty-btn" style={styles.clearFiltersBtn} onPress={clearFilters}>
              <Text style={styles.clearFiltersBtnText}>Clear Filters</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : (
        <FlatList
          testID="car-list"
          data={cars}
          keyExtractor={(item) => item.id}
          renderItem={renderCar}
          contentContainerStyle={styles.carList}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FF3B30" />}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 24, paddingTop: 8, paddingBottom: 4 },
  greeting: { fontSize: 14, color: '#666' },
  title: { fontSize: 22, fontWeight: '900', color: '#0A0A0A', letterSpacing: -0.5 },
  avatar: { width: 44, height: 44, borderRadius: 22, justifyContent: 'center', alignItems: 'center' },
  searchContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 16, paddingHorizontal: 16, marginHorizontal: 24, marginTop: 16, marginBottom: 8, borderWidth: 1, borderColor: '#E5E5E5' },
  searchInput: { flex: 1, fontSize: 16, color: '#0A0A0A', paddingVertical: 14, marginLeft: 10 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 24, paddingTop: 8, paddingBottom: 4 },
  sectionLabel: { fontSize: 12, fontWeight: '800', color: '#0A0A0A', textTransform: 'uppercase', letterSpacing: 1 },
  filterList: { paddingHorizontal: 24, paddingVertical: 8, gap: 8 },
  locationPill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 50, backgroundColor: '#FFF0F0', borderWidth: 1, borderColor: '#FFD5D5' },
  locationPillActive: { backgroundColor: '#FF3B30', borderColor: '#FF3B30' },
  locationPillText: { fontSize: 13, fontWeight: '700', color: '#FF3B30' },
  locationPillTextActive: { color: '#FFFFFF' },
  categoriesList: { paddingHorizontal: 24, paddingVertical: 6, gap: 8 },
  categoryPill: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 50, backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5' },
  categoryPillActive: { backgroundColor: '#0A0A0A', borderColor: '#0A0A0A' },
  categoryPillText: { fontSize: 14, fontWeight: '600', color: '#666' },
  categoryPillTextActive: { color: '#FFFFFF' },
  activeFiltersBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 24, paddingVertical: 6 },
  resultCount: { fontSize: 13, fontWeight: '700', color: '#666' },
  clearBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  clearBtnText: { fontSize: 13, fontWeight: '700', color: '#FF3B30' },
  carList: { paddingHorizontal: 24, paddingBottom: 24 },
  carCard: { backgroundColor: '#FFFFFF', borderRadius: 24, overflow: 'hidden', marginBottom: 20, borderWidth: 1, borderColor: '#E5E5E5', shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 8, elevation: 2 },
  carImage: { width: '100%', height: 180, backgroundColor: '#F5F5F5' },
  carInfo: { padding: 16 },
  carHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  carName: { fontSize: 18, fontWeight: '800', color: '#0A0A0A', flex: 1 },
  categoryBadge: { backgroundColor: '#F5F5F5', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  categoryBadgeSolo: { backgroundColor: '#F5F5F5', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, alignSelf: 'flex-start', marginTop: 4 },
  categoryText: { fontSize: 11, fontWeight: '700', color: '#666', textTransform: 'uppercase', letterSpacing: 1 },
  locationRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 4 },
  locationText: { fontSize: 12, color: '#007AFF', fontWeight: '600' },
  ratingRow: { marginBottom: 4 },
  carSpecs: { flexDirection: 'row', gap: 16, marginBottom: 12 },
  specItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  specText: { fontSize: 13, color: '#666' },
  carFooter: { flexDirection: 'row', alignItems: 'baseline' },
  price: { fontSize: 24, fontWeight: '900', color: '#FF3B30' },
  priceUnit: { fontSize: 14, color: '#999', marginLeft: 2 },
  centerContent: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyText: { fontSize: 16, color: '#999' },
  clearFiltersBtn: { backgroundColor: '#FF3B30', paddingHorizontal: 20, paddingVertical: 12, borderRadius: 50, marginTop: 8 },
  clearFiltersBtnText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
});
