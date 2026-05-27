import { Image, StyleSheet, View } from 'react-native';
import type { ImageStyle, StyleProp, ViewStyle } from 'react-native';
import { useTheme } from '../src/theme';

/**
 * DAMS Rent A Car brand logo.
 * Automatically swaps between light & dark variants based on the current theme.
 *
 * - `size="large"` for auth screens / splash-like usage (260×80)
 * - `size="medium"` for in-app headers (160×50)
 * - `size="small"` for compact bars (120×38)
 *
 * Source PNGs have a transparent background, so the logo looks clean
 * over any surface color (light OR dark).
 */
type Props = {
  size?: 'small' | 'medium' | 'large';
  containerStyle?: StyleProp<ViewStyle>;
  imageStyle?: StyleProp<ImageStyle>;
  testID?: string;
  /** Force a specific variant regardless of current theme (rarely needed). */
  variant?: 'light' | 'dark';
};

// Logo source aspect ratio is ~3.36:1, so heights are tuned to that.
const DIMENSIONS = {
  small: { width: 120, height: 38 },
  medium: { width: 160, height: 50 },
  large: { width: 260, height: 80 },
} as const;

export default function BrandLogo({ size = 'medium', containerStyle, imageStyle, testID, variant }: Props) {
  const { isDark } = useTheme();
  const dim = DIMENSIONS[size];
  const useDark = variant ? variant === 'dark' : isDark;
  const source = useDark
    ? require('../assets/images/dams-logo-dark.png')
    : require('../assets/images/dams-logo.png');
  return (
    <View style={[styles.wrap, containerStyle]} testID={testID || 'brand-logo'}>
      <Image
        source={source}
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
