import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { getProfile, getRecommendations, type Profile, type Recommendations } from '../src/api';
import { mockProfile, mockRecommendations } from '../src/api/mock';
import CardView from '../src/components/CardView';
import { getSessionId } from '../src/session';
import { font, space, useTheme } from '../src/theme';
import { Card, Screen, ScreenHeader, StateView } from '../src/ui';
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';
export default function PerfilScreen() {
  const { colors } = useTheme();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendations | null>(null);
  const [loading, setLoading] = useState(true);
  const [empty, setEmpty] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    getSessionId()
      .then((sessionId) => {
        if (!alive) return;
        if (!sessionId) {
          if (mockEnabled) {
            setProfile(mockProfile);
            setRecommendations(mockRecommendations);
          } else setEmpty(true);
          setLoading(false);
          return;
        }
        Promise.all([getProfile(sessionId), getRecommendations(sessionId)])
          .then(([p, r]) => {
            if (alive) {
              setProfile(p);
              setRecommendations(r);
            }
          })
          .catch((e: unknown) => {
            if (!alive) return;
            if ((e as { status?: number })?.status === 404) {
              if (mockEnabled) {
                setProfile(mockProfile);
                setRecommendations(mockRecommendations);
              } else setEmpty(true);
            } else setError(e instanceof Error ? e.message : 'No se pudo cargar el perfil.');
          })
          .finally(() => {
            if (alive) setLoading(false);
          });
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setError(e instanceof Error ? e.message : 'No se pudo leer la sesión.');
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  const sections = [
    ['investors', 'Inversores'],
    ['competitors', 'Competidores'],
    ['prospects', 'Clientes potenciales'],
  ] as const;
  return (
    <Screen>
      <ScreenHeader title="Perfil" subtitle="Tu startup y las recomendaciones de Cala, con fuentes." />
      {loading ? <StateView kind="loading" title="Cargando perfil…" /> : null}
      {error ? <StateView kind="error" title="No se pudo cargar" message={error} /> : null}
      {empty ? (
        <StateView
          kind="empty"
          title="Tu perfil todavía no está listo"
          message="El perfil se arma cuando hables con el chat."
        />
      ) : null}
      {profile ? (
        <>
          <Card raised>
            <Text style={{ color: colors.text, fontSize: font.h2, fontWeight: '800' }}>
              {profile.startup_name || 'Tu startup'}
            </Text>
            {profile.one_liner ? (
              <Text style={{ color: colors.textMuted, fontSize: font.body, lineHeight: 22, marginTop: space.xs, marginBottom: space.md }}>
                {profile.one_liner}
              </Text>
            ) : null}
            <Info label="Sector" value={profile.sector} />
            <Info label="Etapa" value={profile.stage} />
            <Info label="Ciudad" value={profile.location} />
            <Info label="Clientes objetivo" value={profile.target_customers} />
            <Info label="Competidores" value={profile.competitors?.join(', ')} />
          </Card>
          {recommendations
            ? sections.map(([key, label]) => (
                <View key={key} style={{ marginTop: space.xl }}>
                  <Text
                    accessibilityRole="header"
                    style={{ color: colors.text, fontSize: font.h2, fontWeight: '700' }}
                  >
                    {label}
                  </Text>
                  {recommendations[key].length ? (
                    recommendations[key].map((card, i) => (
                      <CardView key={`${card.title}-${i}`} card={card} />
                    ))
                  ) : (
                    <Text style={{ color: colors.textMuted, fontSize: font.body, marginTop: space.sm }}>
                      Aún no hay recomendaciones.
                    </Text>
                  )}
                </View>
              ))
            : null}
        </>
      ) : null}
    </Screen>
  );
}

function Info({ label, value }: { label: string; value?: string }) {
  const { colors } = useTheme();
  if (!value) return null;
  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        gap: space.md,
        borderTopWidth: 1,
        borderTopColor: colors.border,
        paddingVertical: space.md,
      }}
    >
      <Text style={{ color: colors.textMuted, fontSize: font.small }}>{label}</Text>
      <Text style={{ color: colors.text, fontSize: font.small, fontWeight: '600', textAlign: 'right', flexShrink: 1 }}>
        {value}
      </Text>
    </View>
  );
}
