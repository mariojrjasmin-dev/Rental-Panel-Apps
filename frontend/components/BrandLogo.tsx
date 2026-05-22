import { Image, StyleSheet, View } from 'react-native';
import type { ImageStyle, StyleProp, ViewStyle } from 'react-native';

/**
 * DAMS Rent A Car brand logo.
 * - `size="large"` for auth screens / splash-like usage (260×100)
 * - `size="medium"` for in-app headers (160×62)
 * - `size="small"` for compact bars (120×46)
 */
type Props = {
  size?: 'small' | 'medium' | 'large';
  containerStyle?: StyleProp<ViewStyle>;
  imageStyle?: StyleProp<ImageStyle>;
  testID?: string;
};

const DIMENSIONS = {
  small: { width: 120, height: 46 },
  medium: { width: 160, height: 62 },
  large: { width: 260, height: 100 },
} as const;

export default function BrandLogo({ size = 'medium', containerStyle, imageStyle, testID }: Props) {
  const dim = DIMENSIONS[size];
  return (
    <View style={[styles.wrap, containerStyle]} testID={testID || 'brand-logo'}>
      <Image
        source={require('../assets/images/dams-logo.png')}
        style={[{ width: dim.width, height: dim.height }, imageStyle]}
        resizeMode="contain"
        accessibilityLabel="DAMS Rent a Car"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center' },
});
