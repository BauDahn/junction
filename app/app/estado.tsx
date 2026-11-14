import { useEffect, useState, type ReactNode } from 'react';
import { Text, View } from 'react-native';
import { health, type HealthStatus } from '../src/api';
import { font, space, useTheme } from '../src/theme';
import { Badge, Card, Screen, ScreenHeader, StateView } from '../src/ui';

export default function EstadoScreen() {
  const { colors } = useTheme();
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
    <Screen>
      <ScreenHeader
        title="Estado del sistema"
        subtitle="Conexión con el backend, Cala y el modelo."
      />
      {status ? (
        <Card raised>
          <Row
            label="Cala"
            right={
              <Badge
                label={status.cala ? 'Disponible' : 'No disponible'}
                tone={status.cala ? 'confirmed' : 'contradicted'}
              />
            }
          />
          <Row label="Proveedor LLM" value={status.provider} />
          <Row label="Modelo" value={status.model} />
          {status.transcription ? <Row label="Transcripción" value={status.transcription} /> : null}
        </Card>
      ) : error ? (
        <StateView kind="error" title="Sin conexión con la API" message={error} />
      ) : (
        <StateView kind="loading" title="Comprobando conexión…" />
      )}
      <Text style={{ color: colors.textFaint, fontSize: font.small, marginTop: space.lg }}>
        Todo dato de Cala se muestra con su fuente.
      </Text>
    </Screen>
  );

}

function Row({ label, value, right }: { label: string; value?: string; right?: ReactNode }) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: space.lg,
        paddingVertical: space.md,
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
      }}
    >
      <Text style={{ color: colors.textMuted, fontSize: font.body }}>{label}</Text>
      {right ?? (
        <Text
          style={{ color: colors.text, fontSize: font.body, fontWeight: '600', flexShrink: 1, textAlign: 'right' }}
        >
          {value}
        </Text>
      )}
    </View>
  );
}
