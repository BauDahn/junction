import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getProfile, getRecommendations, type Profile, type Recommendations } from '../src/api';
import { mockProfile, mockRecommendations } from '../src/api/mock';
import CardView from '../src/components/CardView';
import { getSessionId } from '../src/session';
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';
export default function PerfilScreen() {
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
  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <Text style={s.eyebrow}>JUNCTION · STARTUP INTELLIGENCE</Text>
      <Text style={s.title}>Perfil</Text>
      {loading ? (
        <View style={s.loading}>
          <ActivityIndicator color="#a78bfa" />
          <Text style={s.muted}>Cargando perfil…</Text>
        </View>
      ) : null}
      {error ? (
        <Text accessibilityRole="alert" style={s.error}>
          {error}
        </Text>
      ) : null}
      {empty ? (
        <View style={s.empty}>
          <Text style={s.emptyTitle}>Tu perfil todavía no está listo</Text>
          <Text style={s.muted}>El perfil se arma cuando hables con el chat.</Text>
        </View>
      ) : null}
      {profile ? (
        <>
          <View style={s.profile}>
            <Text style={s.name}>{profile.startup_name || 'Tu startup'}</Text>
            {profile.one_liner ? <Text style={s.one}>{profile.one_liner}</Text> : null}
            <Info label="Sector" value={profile.sector} />
            <Info label="Etapa" value={profile.stage} />
            <Info label="Ciudad" value={profile.location} />
            <Info label="Clientes objetivo" value={profile.target_customers} />
            <Info label="Competidores" value={profile.competitors?.join(', ')} />
          </View>
          {recommendations ? (
            <>
              {(['investors', 'competitors', 'prospects'] as const).map((key) => (
                <View key={key}>
                  <Text style={s.section}>
                    {key === 'investors'
                      ? 'Inversores'
                      : key === 'competitors'
                        ? 'Competidores'
                        : 'Clientes potenciales'}
                  </Text>
                  {recommendations[key].length ? (
                    recommendations[key].map((card, i) => (
                      <CardView key={`${card.title}-${i}`} card={card} />
                    ))
                  ) : (
                    <Text style={s.muted}>Aún no hay recomendaciones.</Text>
                  )}
                </View>
              ))}
            </>
          ) : null}
        </>
      ) : null}
    </ScrollView>
  );
}
function Info({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <View style={s.info}>
      <Text style={s.label}>{label}</Text>
      <Text style={s.value}>{value}</Text>
    </View>
  );
}
const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#0b1020' },
  content: { padding: 22, paddingBottom: 40, maxWidth: 820, width: '100%', alignSelf: 'center' },
  eyebrow: {
    color: '#a78bfa',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.5,
    marginBottom: 10,
  },
  title: { color: '#f8fafc', fontSize: 32, fontWeight: '800', marginBottom: 18 },
  loading: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  muted: { color: '#9aa6bf', fontSize: 14, lineHeight: 21 },
  empty: {
    backgroundColor: '#151c30',
    padding: 20,
    borderColor: '#29324b',
    borderWidth: 1,
    borderRadius: 16,
  },
  emptyTitle: { color: '#f8fafc', fontSize: 17, fontWeight: '700', marginBottom: 8 },
  profile: {
    backgroundColor: '#151c30',
    padding: 18,
    borderColor: '#29324b',
    borderWidth: 1,
    borderRadius: 16,
  },
  name: { color: '#f8fafc', fontSize: 23, fontWeight: '800' },
  one: { color: '#cbd5e1', fontSize: 14, marginTop: 6, marginBottom: 12 },
  info: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
    borderTopWidth: 1,
    borderTopColor: '#29324b',
    paddingVertical: 11,
  },
  label: { color: '#9aa6bf', fontSize: 13 },
  value: { color: '#f8fafc', fontSize: 13, fontWeight: '600', textAlign: 'right', flexShrink: 1 },
  section: { color: '#f8fafc', fontSize: 19, fontWeight: '700', marginTop: 24 },
  error: { color: '#fecaca', backgroundColor: '#3a1d2a', padding: 14, borderRadius: 12 },
});
