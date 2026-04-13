import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

type Props = {
  rating: number;
  size?: number;
  onRate?: (rating: number) => void;
  showValue?: boolean;
  count?: number;
};

export default function StarRating({ rating, size = 18, onRate, showValue = false, count }: Props) {
  const stars = [1, 2, 3, 4, 5];

  return (
    <View style={styles.container}>
      {stars.map((s) => (
        <TouchableOpacity
          key={s}
          testID={`star-${s}`}
          disabled={!onRate}
          onPress={() => onRate?.(s)}
          activeOpacity={onRate ? 0.7 : 1}
          style={{ padding: onRate ? 4 : 0 }}
        >
          <Ionicons
            name={rating >= s ? 'star' : rating >= s - 0.5 ? 'star-half' : 'star-outline'}
            size={size}
            color="#FFCC00"
          />
        </TouchableOpacity>
      ))}
      {showValue && rating > 0 && (
        <Text style={[styles.value, { fontSize: size * 0.78 }]}>{rating.toFixed(1)}</Text>
      )}
      {count !== undefined && count > 0 && (
        <Text style={[styles.count, { fontSize: size * 0.67 }]}>({count})</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  value: { fontWeight: '800', color: '#0A0A0A', marginLeft: 4 },
  count: { color: '#999', marginLeft: 2 },
});
