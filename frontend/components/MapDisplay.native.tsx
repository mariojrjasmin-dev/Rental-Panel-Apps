import { View, StyleSheet, Dimensions } from 'react-native';
import MapView, { Marker } from 'react-native-maps';

const { width, height } = Dimensions.get('window');

type Props = {
  pickupLat: number;
  pickupLng: number;
  pickupName: string;
  dropoffLat: number;
  dropoffLng: number;
  dropoffName: string;
};

export default function MapComponent({ pickupLat, pickupLng, pickupName, dropoffLat, dropoffLng, dropoffName }: Props) {
  const centerLat = (pickupLat + dropoffLat) / 2;
  const centerLng = (pickupLng + dropoffLng) / 2;
  const latDelta = Math.abs(pickupLat - dropoffLat) * 1.8 + 0.02;
  const lngDelta = Math.abs(pickupLng - dropoffLng) * 1.8 + 0.02;

  return (
    <MapView
      style={styles.map}
      initialRegion={{
        latitude: centerLat,
        longitude: centerLng,
        latitudeDelta: latDelta,
        longitudeDelta: lngDelta,
      }}
      showsUserLocation
      showsMyLocationButton
    >
      <Marker
        coordinate={{ latitude: pickupLat, longitude: pickupLng }}
        title={pickupName}
        description="Pickup Location"
        pinColor="#34C759"
      />
      <Marker
        coordinate={{ latitude: dropoffLat, longitude: dropoffLng }}
        title={dropoffName}
        description="Drop-off Location"
        pinColor="#FF3B30"
      />
    </MapView>
  );
}

const styles = StyleSheet.create({
  map: { width, height: height * 0.6 },
});
