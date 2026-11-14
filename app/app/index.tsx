import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { health, type HealthStatus } from '../src/api';

export default function HomeScreen() {
  const [status, setStatus] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    health().then(setStatus).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'No se pudo conectar con la API.');
    });
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>JUNCTION · STARTUP INTELLIGENCE</Text>
      <Text style={styles.title}>Conexión con el backend</Text>
      {status ? (
        <View style={styles.card} accessibilityLiveRegion="polite">
          <StatusRow label="Provider" value={status.provider} />
          <StatusRow label="Model" value={status.model} />
          <StatusRow label="Cala" value={status.cala ? 'Disponible' : 'No disponible'} />
          <StatusRow label="Transcription" value={status.transcription} />
        </View>
      ) : error ? (
        <Text accessibilityRole="alert" style={styles.error}>{error}</Text>
      ) : (
        <View style={styles.loading} accessibilityLiveRegion="polite">
          <ActivityIndicator color="#8b5cf6" />
          <Text style={styles.muted}>Comprobando /api/health…</Text>
        </View>
      )}
    </View>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#0b1020' },
  eyebrow: { color: '#a78bfa', fontSize: 12, fontWeight: '700', letterSpacing: 1.5, marginBottom: 12 },
  title: { color: '#f8fafc', fontSize: 28, fontWeight: '700', marginBottom: 24 },
  card: { maxWidth: 560, width: '100%', padding: 20, borderRadius: 16, backgroundColor: '#151c30', borderWidth: 1, borderColor: '#29324b' },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#29324b' },
  label: { color: '#9aa6bf', fontSize: 15 },
  value: { color: '#f8fafc', fontSize: 15, fontWeight: '600', flexShrink: 1, textAlign: 'right' },
  error: { maxWidth: 560, color: '#fecaca', backgroundColor: '#3a1d2a', borderRadius: 12, padding: 16, fontSize: 15 },
  loading: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  muted: { color: '#9aa6bf', fontSize: 15 }
});
