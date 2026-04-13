import { useState, useEffect, useCallback } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList, Image, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../_layout';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

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
};

const CATEGORIES = ['All', 'SUV', 'Sedan', 'Luxury', 'Electric', 'Sports'];

export default function HomeScreen() {
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const { user } = useAuth();
  const router = useRouter();

  const fetchCars = useCallback(async () => {
    try {
      let url = `${BACKEND_URL}/api/cars?`;
      if (activeCategory !== 'All') url += `category=${activeCategory}&`;
      if (search) url += `search=${search}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setCars(data);
      }
    } catch (e) {
      console.log('Fetch cars error:', e);
    }
    setLoading(false);
    setRefreshing(false);
  }, [activeCategory, search]);

  useEffect(() => { fetchCars(); }, [fetchCars]);

  const onRefresh = () => { setRefreshing(true); fetchCars(); };

  const renderCar = ({ item }: { item: Car }) => (
    <TouchableOpacity
      testID={`car-card-${item.id}`}
      style={styles.carCard}
      activeOpacity={0.7}
      onPress={() => router.push({ pathname: '/car-detail', params: { id: item.id } })}
    >
      <Image source={{ uri: item.image_url }} style={styles.carImage} resizeMode="cover" />
      <View style={styles.carInfo}>
        <View style={styles.carHeader}>
          <Text style={styles.carName} numberOfLines={1}>{item.name}</Text>
          <View style={styles.categoryBadge}>
            <Text style={styles.categoryText}>{item.category}</Text>
          </View>
        </View>
        <View style={styles.carSpecs}>
          <View style={styles.specItem}>
            <Ionicons name="people-outline" size={14} color="#666" />
            <Text style={styles.specText}>{item.seats} seats</Text>
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
          <Text style={styles.greeting}>Hello, {user?.name || 'there'}</Text>
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
          placeholder="Find a vehicle..."
          placeholderTextColor="#999"
          value={search}
          onChangeText={setSearch}
          onSubmitEditing={fetchCars}
          returnKeyType="search"
        />
        {search ? (
          <TouchableOpacity onPress={() => { setSearch(''); }}>
            <Ionicons name="close-circle" size={20} color="#999" />
          </TouchableOpacity>
        ) : null}
      </View>

      <FlatList
        horizontal
        data={CATEGORIES}
        keyExtractor={(item) => item}
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.categoriesList}
        renderItem={({ item }) => (
          <TouchableOpacity
            testID={`category-${item}`}
            style={[styles.categoryPill, activeCategory === item && styles.categoryPillActive]}
            onPress={() => setActiveCategory(item)}
          >
            <Text style={[styles.categoryPillText, activeCategory === item && styles.categoryPillTextActive]}>{item}</Text>
          </TouchableOpacity>
        )}
      />

      {loading ? (
        <View style={styles.centerContent}>
          <ActivityIndicator size="large" color="#FF3B30" />
        </View>
      ) : cars.length === 0 ? (
        <View style={styles.centerContent}>
          <Ionicons name="car-outline" size={64} color="#E5E5E5" />
          <Text style={styles.emptyText}>No cars found</Text>
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
  categoriesList: { paddingHorizontal: 24, paddingVertical: 12, gap: 8 },
  categoryPill: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 50, backgroundColor: '#F5F5F5', borderWidth: 1, borderColor: '#E5E5E5' },
  categoryPillActive: { backgroundColor: '#0A0A0A', borderColor: '#0A0A0A' },
  categoryPillText: { fontSize: 14, fontWeight: '600', color: '#666' },
  categoryPillTextActive: { color: '#FFFFFF' },
  carList: { paddingHorizontal: 24, paddingBottom: 24 },
  carCard: { backgroundColor: '#FFFFFF', borderRadius: 24, overflow: 'hidden', marginBottom: 20, borderWidth: 1, borderColor: '#E5E5E5', shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 8, elevation: 2 },
  carImage: { width: '100%', height: 180, backgroundColor: '#F5F5F5' },
  carInfo: { padding: 16 },
  carHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  carName: { fontSize: 18, fontWeight: '800', color: '#0A0A0A', flex: 1 },
  categoryBadge: { backgroundColor: '#F5F5F5', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  categoryText: { fontSize: 11, fontWeight: '700', color: '#666', textTransform: 'uppercase', letterSpacing: 1 },
  carSpecs: { flexDirection: 'row', gap: 16, marginBottom: 12 },
  specItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  specText: { fontSize: 13, color: '#666' },
  carFooter: { flexDirection: 'row', alignItems: 'baseline' },
  price: { fontSize: 24, fontWeight: '900', color: '#FF3B30' },
  priceUnit: { fontSize: 14, color: '#999', marginLeft: 2 },
  centerContent: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyText: { fontSize: 16, color: '#999' },
});
