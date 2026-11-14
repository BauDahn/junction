import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { health, type HealthStatus } from '../src/api';
export default function EstadoScreen() {
  const [status, setStatus] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    health()
      .then(setStatus)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : 'No se pudo conectar con la API.'),
      );
  }, []);
  return (
    <View style={s.container}>
      <Text style={s.eyebrow}>JUNCTION · STARTUP INTELLIGENCE</Text>
      <Text style={s.title}>Estado del sistema</Text>
      {status ? (
        <View style={s.card}>
          <Row label="Proveedor" value={status.provider} />
          <Row label="Modelo" value={status.model} />
          <Row label="Cala" value={status.cala ? 'Disponible' : 'No disponible'} />
          {status.transcription ? <Row label="Transcripción" value={status.transcription} /> : null}
        </View>
      ) : error ? (
        <Text accessibilityRole="alert" style={s.error}>
          {error}
        </Text>
      ) : (
        <View style={s.loading}>
          <ActivityIndicator color="#8b5cf6" />
          <Text style={s.muted}>Comprobando conexión…</Text>
        </View>
      )}
    </View>
  );
}
function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.row}>
      <Text style={s.label}>{label}</Text>
      <Text style={s.value}>{value}</Text>
    </View>
  );
}
const s = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#0b1020' },
  eyebrow: {
    color: '#a78bfa',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.5,
    marginBottom: 12,
  },
  title: { color: '#f8fafc', fontSize: 28, fontWeight: '700', marginBottom: 24 },
  card: {
    maxWidth: 560,
    width: '100%',
    padding: 20,
    borderRadius: 16,
    backgroundColor: '#151c30',
    borderWidth: 1,
    borderColor: '#29324b',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#29324b',
  },
  label: { color: '#9aa6bf', fontSize: 15 },
  value: { color: '#f8fafc', fontSize: 15, fontWeight: '600', flexShrink: 1, textAlign: 'right' },
  error: {
    maxWidth: 560,
    color: '#fecaca',
    backgroundColor: '#3a1d2a',
    borderRadius: 12,
    padding: 16,
    fontSize: 15,
  },
  loading: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  muted: { color: '#9aa6bf', fontSize: 15 },
});
