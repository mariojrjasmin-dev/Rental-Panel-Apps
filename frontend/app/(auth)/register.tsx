import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../_layout';

export default function RegisterScreen() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  const handleRegister = async () => {
    if (!name || !email || !password) { setError('Please fill all fields'); return; }
    if (password.length < 6) { setError('Password must be at least 6 characters'); return; }
    setLoading(true);
    setError('');
    try {
      await register(name, email, password);
      router.replace('/(tabs)/home');
    } catch (e: any) {
      setError(e.message || 'Registration failed');
    }
    setLoading(false);
  };

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={styles.brand}>DAMS</Text>
          <Text style={styles.brandSub}>CAR RENTAL</Text>
          <Text style={styles.subtitle}>Create your account</Text>
        </View>

        <View style={styles.form}>
          {error ? <Text testID="register-error" style={styles.error}>{error}</Text> : null}
          
          <View style={styles.inputContainer}>
            <Ionicons name="person-outline" size={20} color="#666" style={styles.inputIcon} />
            <TextInput testID="register-name-input" style={styles.input} placeholder="Full Name" placeholderTextColor="#999" value={name} onChangeText={setName} />
          </View>

          <View style={styles.inputContainer}>
            <Ionicons name="mail-outline" size={20} color="#666" style={styles.inputIcon} />
            <TextInput testID="register-email-input" style={styles.input} placeholder="Email" placeholderTextColor="#999" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
          </View>

          <View style={styles.inputContainer}>
            <Ionicons name="lock-closed-outline" size={20} color="#666" style={styles.inputIcon} />
            <TextInput testID="register-password-input" style={styles.input} placeholder="Password (min 6 chars)" placeholderTextColor="#999" value={password} onChangeText={setPassword} secureTextEntry />
          </View>

          <TouchableOpacity testID="register-submit-button" style={styles.primaryBtn} onPress={handleRegister} disabled={loading} activeOpacity={0.7}>
            {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>Create Account</Text>}
          </TouchableOpacity>

          <TouchableOpacity testID="go-to-login" onPress={() => router.push('/(auth)/login')} style={styles.linkBtn}>
            <Text style={styles.linkText}>Already have an account? <Text style={styles.linkBold}>Sign In</Text></Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 24 },
  header: { marginBottom: 40 },
  brand: { fontSize: 48, fontWeight: '900', color: '#0A0A0A', letterSpacing: -2 },
  brandSub: { fontSize: 16, fontWeight: '700', color: '#FF3B30', letterSpacing: 6, marginTop: -4 },
  subtitle: { fontSize: 16, color: '#666', marginTop: 12 },
  form: { gap: 16 },
  error: { color: '#FF3B30', fontSize: 14, textAlign: 'center', backgroundColor: '#FFF0F0', padding: 12, borderRadius: 12 },
  inputContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F5F5', borderRadius: 16, paddingHorizontal: 16, borderWidth: 1, borderColor: '#E5E5E5' },
  inputIcon: { marginRight: 12 },
  input: { flex: 1, fontSize: 16, color: '#0A0A0A', paddingVertical: 16 },
  primaryBtn: { backgroundColor: '#FF3B30', borderRadius: 50, paddingVertical: 18, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  primaryBtnText: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  linkBtn: { alignItems: 'center', marginTop: 8 },
  linkText: { fontSize: 15, color: '#666' },
  linkBold: { color: '#FF3B30', fontWeight: '700' },
});
