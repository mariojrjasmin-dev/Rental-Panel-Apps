import { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Image, ActivityIndicator, Dimensions, TextInput, Alert, Platform, KeyboardAvoidingView } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import StarRating from '../components/StarRating';
import { useAuth } from './_layout';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const { width } = Dimensions.get('window');

type Review = {
  id: string;
  user_name: string;
  rating: number;
  comment: string;
  created_at: string;
  user_id: string;
};

export default function CarDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [car, setCar] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [reviewRating, setReviewRating] = useState(0);
  const [reviewComment, setReviewComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showReviewForm, setShowReviewForm] = useState(false);
  const { user } = useAuth();
  const router = useRouter();

  const fetchCar = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/cars/${id}`);
      if (res.ok) setCar(await res.json());
    } catch (e) {
      console.log('Fetch car error:', e);
    }
    setLoading(false);
  }, [id]);

  useEffect(() => { if (id) fetchCar(); }, [fetchCar]);

  const submitReview = async () => {
    if (reviewRating === 0) {
      Platform.OS === 'web' ? window.alert('Please select a rating') : Alert.alert('Error', 'Please select a rating');
      return;
    }
    setSubmitting(true);
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const res = await fetch(`${BACKEND_URL}/api/reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ car_id: id, rating: reviewRating, comment: reviewComment }),
      });
      if (res.ok) {
        setReviewRating(0);
        setReviewComment('');
        setShowReviewForm(false);
        fetchCar(); // Refresh to show updated reviews
      } else {
        const err = await res.json();
        const msg = typeof err.detail === 'string' ? err.detail : 'Failed to submit review';
        Platform.OS === 'web' ? window.alert(msg) : Alert.alert('Error', msg);
      }
    } catch (e: any) {
      Platform.OS === 'web' ? window.alert(e.message) : Alert.alert('Error', e.message);
    }
    setSubmitting(false);
  };

  const deleteReview = async (reviewId: string) => {
    const doDelete = async () => {
      const token = await AsyncStorage.getItem('auth_token');
      await fetch(`${BACKEND_URL}/api/reviews/${reviewId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      fetchCar();
    };
    if (Platform.OS === 'web') {
      if (window.confirm('Delete your review?')) doDelete();
    } else {
      Alert.alert('Delete Review', 'Delete your review?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: doDelete },
      ]);
    }
  };

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#FF3B30" /></View>;
  if (!car) return (
    <SafeAreaView style={styles.center}>
      <Text style={styles.errorText}>Car not found</Text>
      <TouchableOpacity onPress={() => router.back()}><Text style={styles.backLink}>Go Back</Text></TouchableOpacity>
    </SafeAreaView>
  );

  const reviews: Review[] = car.reviews || [];
  const userId = user?.id || user?.user_id || '';
  const userReview = reviews.find(r => r.user_id === userId);

  return (
    <View style={styles.container}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
          <View style={styles.heroContainer}>
            <Image source={{ uri: car.image_url }} style={styles.heroImage} resizeMode="cover" />
            <SafeAreaView style={styles.heroOverlay} edges={['top']}>
              <TouchableOpacity testID="back-button" style={styles.backBtn} onPress={() => router.back()}>
                <Ionicons name="arrow-back" size={24} color="#0A0A0A" />
              </TouchableOpacity>
            </SafeAreaView>
          </View>

          <View style={styles.content}>
            <View style={styles.titleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.carName}>{car.name}</Text>
                <View style={styles.categoryTag}>
                  <Text style={styles.categoryTagText}>Or Similar | {car.category}</Text>
                </View>
                <Text style={styles.carYear}>{car.year} {car.brand}</Text>
                {car.avg_rating > 0 && (
                  <View style={styles.ratingRow}>
                    <StarRating rating={car.avg_rating} size={16} showValue count={car.review_count} />
                  </View>
                )}
              </View>
            </View>

            <View style={styles.specsGrid}>
              <View style={styles.specCard}>
                <Ionicons name="people-outline" size={24} color="#FF3B30" />
                <Text style={styles.specValue}>{car.seats}</Text>
                <Text style={styles.specLabel}>Seats</Text>
              </View>
              <View style={styles.specCard}>
                <Ionicons name="cog-outline" size={24} color="#FF3B30" />
                <Text style={styles.specValue}>{car.transmission}</Text>
                <Text style={styles.specLabel}>Transmission</Text>
              </View>
              <View style={styles.specCard}>
                <Ionicons name="flash-outline" size={24} color="#FF3B30" />
                <Text style={styles.specValue}>{car.fuel_type}</Text>
                <Text style={styles.specLabel}>Fuel</Text>
              </View>
            </View>

            {/* Mileage policy banner */}
            <View style={styles.mileageBanner}>
              <Ionicons name="speedometer-outline" size={22} color="#FF3B30" />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.mileageTitle}>
                  {car.unlimited_mileage === false && car.mileage_limit
                    ? `${car.mileage_limit} km/day included`
                    : 'Unlimited mileage'}
                </Text>
                <Text style={styles.mileageSub}>
                  {car.unlimited_mileage === false && car.mileage_limit
                    ? 'Extra kilometers may incur additional charges'
                    : 'Drive as far as you want — no limits'}
                </Text>
              </View>
            </View>

            {/* Vehicle Features */}
            {(() => {
              const features = [
                { key: 'android_auto', label: 'Android Auto', icon: 'logo-android' },
                { key: 'apple_carplay', label: 'Apple CarPlay', icon: 'logo-apple' },
                { key: 'blind_spot_warning', label: 'Blind Spot Warning', icon: 'warning-outline' },
                { key: 'gps', label: 'GPS Navigation', icon: 'navigate-outline' },
                { key: 'keyless_entry', label: 'Keyless Entry', icon: 'key-outline' },
                { key: 'sunroof', label: 'Sunroof', icon: 'sunny-outline' },
              ].filter((f) => !!car[f.key]);
              if (features.length === 0) return null;
              return (
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Features</Text>
                  <View style={styles.featuresGrid}>
                    {features.map((f) => (
                      <View key={f.key} style={styles.featureChip}>
                        <Ionicons name={f.icon as any} size={16} color="#FF3B30" />
                        <Text style={styles.featureLabel}>{f.label}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              );
            })()}

            {car.description ? (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>About</Text>
                <Text style={styles.description}>{car.description}</Text>
              </View>
            ) : null}

            {(car.pickup_location || car.dropoff_location) && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Locations</Text>
                {car.pickup_location && (
                  <TouchableOpacity testID="pickup-location-btn" style={styles.locationRow}
                    onPress={() => router.push({ pathname: '/map-view', params: { pickupLat: String(car.pickup_location?.lat || 0), pickupLng: String(car.pickup_location?.lng || 0), pickupName: String(car.pickup_location?.name || 'Pickup'), dropoffLat: String(car.dropoff_location?.lat || 0), dropoffLng: String(car.dropoff_location?.lng || 0), dropoffName: String(car.dropoff_location?.name || 'Drop-off') } })}>
                    <View style={styles.locationIcon}><Ionicons name="location" size={18} color="#34C759" /></View>
                    <View style={{ flex: 1 }}><Text style={styles.locationLabel}>Pickup</Text><Text style={styles.locationName}>{car.pickup_location.name}</Text></View>
                    <Ionicons name="map-outline" size={20} color="#007AFF" />
                  </TouchableOpacity>
                )}
                {car.dropoff_location && (
                  <TouchableOpacity testID="dropoff-location-btn" style={styles.locationRow}
                    onPress={() => router.push({ pathname: '/map-view', params: { pickupLat: String(car.pickup_location?.lat || 0), pickupLng: String(car.pickup_location?.lng || 0), pickupName: String(car.pickup_location?.name || 'Pickup'), dropoffLat: String(car.dropoff_location?.lat || 0), dropoffLng: String(car.dropoff_location?.lng || 0), dropoffName: String(car.dropoff_location?.name || 'Drop-off') } })}>
                    <View style={[styles.locationIcon, { backgroundColor: '#FFF0F0' }]}><Ionicons name="location" size={18} color="#FF3B30" /></View>
                    <View style={{ flex: 1 }}><Text style={styles.locationLabel}>Drop-off</Text><Text style={styles.locationName}>{car.dropoff_location.name}</Text></View>
                    <Ionicons name="map-outline" size={20} color="#007AFF" />
                  </TouchableOpacity>
                )}
              </View>
            )}

            {/* Reviews Section */}
            <View style={styles.section}>
              <View style={styles.reviewsHeader}>
                <Text style={styles.sectionTitle}>Reviews</Text>
                {user && !userReview && (
                  <TouchableOpacity testID="write-review-btn" style={styles.writeReviewBtn} onPress={() => setShowReviewForm(!showReviewForm)}>
                    <Ionicons name="create-outline" size={16} color="#FF3B30" />
                    <Text style={styles.writeReviewText}>Write Review</Text>
                  </TouchableOpacity>
                )}
              </View>

              {/* Review Form */}
              {showReviewForm && (
                <View testID="review-form" style={styles.reviewForm}>
                  <Text style={styles.formLabel}>Your Rating</Text>
                  <StarRating rating={reviewRating} size={32} onRate={setReviewRating} />
                  <Text style={styles.formLabel}>Comment (optional)</Text>
                  <TextInput
                    testID="review-comment-input"
                    style={styles.commentInput}
                    value={reviewComment}
                    onChangeText={setReviewComment}
                    placeholder="Share your experience..."
                    placeholderTextColor="#999"
                    multiline
                    numberOfLines={3}
                  />
                  <View style={styles.formActions}>
                    <TouchableOpacity style={styles.cancelFormBtn} onPress={() => { setShowReviewForm(false); setReviewRating(0); setReviewComment(''); }}>
                      <Text style={styles.cancelFormText}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity testID="submit-review-btn" style={styles.submitReviewBtn} onPress={submitReview} disabled={submitting}>
                      {submitting ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.submitReviewText}>Submit</Text>}
                    </TouchableOpacity>
                  </View>
                </View>
              )}

              {reviews.length === 0 && !showReviewForm ? (
                <View style={styles.noReviews}>
                  <Ionicons name="chatbubble-outline" size={32} color="#E5E5E5" />
                  <Text style={styles.noReviewsText}>No reviews yet. Be the first!</Text>
                </View>
              ) : (
                reviews.map((r) => (
                  <View key={r.id} testID={`review-${r.id}`} style={styles.reviewCard}>
                    <View style={styles.reviewTop}>
                      <View style={styles.reviewerInfo}>
                        <View style={styles.reviewerAvatar}>
                          <Text style={styles.reviewerInitial}>{(r.user_name || 'A')[0].toUpperCase()}</Text>
                        </View>
                        <View>
                          <Text style={styles.reviewerName}>{r.user_name}</Text>
                          <Text style={styles.reviewDate}>{formatDate(r.created_at)}</Text>
                        </View>
                      </View>
                      <View style={styles.reviewRightCol}>
                        <StarRating rating={r.rating} size={14} />
                        {(r.user_id === userId || user?.role === 'admin') && (
                          <TouchableOpacity testID={`delete-review-${r.id}`} onPress={() => deleteReview(r.id)} style={styles.deleteReviewBtn}>
                            <Ionicons name="trash-outline" size={14} color="#FF3B30" />
                          </TouchableOpacity>
                        )}
                      </View>
                    </View>
                    {r.comment ? <Text style={styles.reviewComment}>{r.comment}</Text> : null}
                  </View>
                ))
              )}
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      <View style={styles.bottomBar}>
        <View>
          <Text style={styles.bottomPrice}>${car.price_per_day}</Text>
          <Text style={styles.bottomPriceUnit}>per day</Text>
        </View>
        <TouchableOpacity testID="book-now-button" style={styles.bookBtn} activeOpacity={0.7}
          onPress={() => router.push({ pathname: '/booking', params: { carId: car.id } })}>
          <Text style={styles.bookBtnText}>Book Now</Text>
          <Ionicons name="arrow-forward" size={20} color="#FFF" />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFF' },
  errorText: { fontSize: 18, color: '#666' },
  backLink: { fontSize: 16, color: '#FF3B30', marginTop: 8 },
  scrollContent: { paddingBottom: 110 },
  heroContainer: { width, height: 280, backgroundColor: '#F5F5F5' },
  heroImage: { width: '100%', height: '100%' },
  heroOverlay: { position: 'absolute', top: 0, left: 0, right: 0 },
  backBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF', justifyContent: 'center', alignItems: 'center', marginLeft: 16, marginTop: 8, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4, elevation: 3 },
  content: { paddingHorizontal: 24, paddingTop: 20 },
  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 },
  carName: { fontSize: 28, fontWeight: '900', color: '#0A0A0A', letterSpacing: -0.5 },
  carYear: { fontSize: 15, color: '#666', marginTop: 2 },
  ratingRow: { marginTop: 6 },
  categoryTag: { backgroundColor: '#0A0A0A', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 50, alignSelf: 'flex-start', marginTop: 6, marginBottom: 4 },
  categoryTagText: { color: '#FFF', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1 },
  specsGrid: { flexDirection: 'row', gap: 12, marginBottom: 24 },
  specCard: { flex: 1, backgroundColor: '#F5F5F5', borderRadius: 16, padding: 16, alignItems: 'center', gap: 6 },
  specValue: { fontSize: 15, fontWeight: '700', color: '#0A0A0A' },
  specLabel: { fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5 },
  mileageBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF5F5', borderRadius: 14, padding: 14, marginBottom: 20, borderWidth: 1, borderColor: '#FFE5E5' },
  mileageTitle: { fontSize: 15, fontWeight: '800', color: '#0A0A0A' },
  mileageSub: { fontSize: 12, color: '#666', marginTop: 2 },
  featuresGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 4 },
  featureChip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F5F5F5', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 50 },
  featureLabel: { fontSize: 13, fontWeight: '600', color: '#0A0A0A' },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: '#0A0A0A', marginBottom: 12 },
  description: { fontSize: 15, color: '#666', lineHeight: 24 },
  locationRow: { flexDirection: 'row', alignItems: 'center', padding: 14, backgroundColor: '#F5F5F5', borderRadius: 14, marginBottom: 8, gap: 12 },
  locationIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#F0FFF4', justifyContent: 'center', alignItems: 'center' },
  locationLabel: { fontSize: 11, color: '#999', textTransform: 'uppercase', fontWeight: '700', letterSpacing: 0.5 },
  locationName: { fontSize: 15, fontWeight: '600', color: '#0A0A0A' },
  // Reviews
  reviewsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  writeReviewBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 50, backgroundColor: '#FFF0F0' },
  writeReviewText: { fontSize: 13, fontWeight: '700', color: '#FF3B30' },
  reviewForm: { backgroundColor: '#F5F5F5', borderRadius: 16, padding: 16, marginBottom: 16, gap: 12 },
  formLabel: { fontSize: 12, fontWeight: '700', color: '#999', textTransform: 'uppercase', letterSpacing: 0.5 },
  commentInput: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, fontSize: 15, color: '#0A0A0A', minHeight: 80, textAlignVertical: 'top', borderWidth: 1, borderColor: '#E5E5E5' },
  formActions: { flexDirection: 'row', gap: 10, justifyContent: 'flex-end' },
  cancelFormBtn: { paddingHorizontal: 20, paddingVertical: 12, borderRadius: 50, backgroundColor: '#E5E5E5' },
  cancelFormText: { fontSize: 14, fontWeight: '700', color: '#666' },
  submitReviewBtn: { paddingHorizontal: 24, paddingVertical: 12, borderRadius: 50, backgroundColor: '#FF3B30', minWidth: 90, alignItems: 'center' },
  submitReviewText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  noReviews: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  noReviewsText: { fontSize: 14, color: '#999' },
  reviewCard: { backgroundColor: '#F5F5F5', borderRadius: 14, padding: 14, marginBottom: 10 },
  reviewTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  reviewerInfo: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  reviewerAvatar: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#0A0A0A', justifyContent: 'center', alignItems: 'center' },
  reviewerInitial: { fontSize: 16, fontWeight: '800', color: '#FFF' },
  reviewerName: { fontSize: 14, fontWeight: '700', color: '#0A0A0A' },
  reviewDate: { fontSize: 11, color: '#999' },
  reviewRightCol: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  deleteReviewBtn: { padding: 6 },
  reviewComment: { fontSize: 14, color: '#666', marginTop: 10, lineHeight: 20 },
  // Bottom bar
  bottomBar: { position: 'absolute', bottom: 0, left: 0, right: 0, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 24, paddingVertical: 16, paddingBottom: 32, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#E5E5E5' },
  bottomPrice: { fontSize: 26, fontWeight: '900', color: '#0A0A0A' },
  bottomPriceUnit: { fontSize: 13, color: '#999' },
  bookBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FF3B30', paddingHorizontal: 28, paddingVertical: 16, borderRadius: 50 },
  bookBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
});
