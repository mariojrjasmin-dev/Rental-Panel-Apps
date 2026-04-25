import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../_layout';
import { t } from '../../src/i18n';

export default function TabsLayout() {
  const { locale } = useAuth(); // re-render tab labels when locale changes
  return (
    <Tabs screenOptions={{
      headerShown: false,
      tabBarActiveTintColor: '#FF3B30',
      tabBarInactiveTintColor: '#999',
      tabBarStyle: {
        backgroundColor: '#FFFFFF',
        borderTopColor: '#E5E5E5',
        borderTopWidth: 1,
        paddingBottom: 8,
        paddingTop: 8,
        height: 64,
      },
      tabBarLabelStyle: { fontSize: 12, fontWeight: '600' },
    }}>
      <Tabs.Screen name="home" options={{
        title: t('tabHome'),
        tabBarIcon: ({ color, size }) => <Ionicons name="car-sport" size={size} color={color} />,
      }} />
      <Tabs.Screen name="bookings" options={{
        title: t('tabBookings'),
        tabBarIcon: ({ color, size }) => <Ionicons name="calendar" size={size} color={color} />,
      }} />
      <Tabs.Screen name="profile" options={{
        title: t('tabProfile'),
        tabBarIcon: ({ color, size }) => <Ionicons name="person" size={size} color={color} />,
      }} />
    </Tabs>
  );
}
