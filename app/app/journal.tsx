import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import {
  getEcosystemJournal,
  getSessionJournal,
  regenerateEcosystemJournal,
  regenerateSessionJournal,
  type Journal,
} from '../src/api';
import BlockView from '../src/components/BlockView';
import { getSessionId } from '../src/session';
import { useTheme } from '../src/theme';
import { Button, Card, Screen, ScreenHeader, StateView } from '../src/ui';

export default function JournalScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const s = journalStyles(colors);
  const [edition, setEdition] = useState<'ecosistema' | 'founders'>('ecosistema');
  const [journal, setJournal] = useState<Journal | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const date = new Date().toISOString().slice(0, 10);
  const load = useCallback(async () => {
    setError('');
    try {
      const session = await getSessionId();
      setSessionId(session);
      if (edition === 'founders' && !session) {
        setJournal(null);
        return;
      }
      setJournal(
        edition === 'ecosistema'
          ? await getEcosystemJournal(date)
          : await getSessionJournal(session!, date),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar el journal.');
    }
  }, [date, edition]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (journal?.status !== 'generating') return;
    const timer = setInterval(() => {
      void load();
    }, 2000);
    return () => clearInterval(timer);
  }, [journal?.status, load]);
  async function regenerate() {
    setError('');
    try {
      if (edition === 'ecosistema') await regenerateEcosystemJournal();
      else if (sessionId) await regenerateSessionJournal(sessionId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo regenerar.');
    }
  }
  return (
    <Screen>
      <ScreenHeader title="Journal" subtitle="Ediciones diarias del ecosistema y para founders." />
      <View style={s.switcher}>
        {(['ecosistema', 'founders'] as const).map((value) => (
          <Pressable
            key={value}
            accessibilityRole="button"
            onPress={() => setEdition(value)}
            style={[s.tab, edition === value && s.active]}
          >
            <Text style={s.tabText}>{value === 'ecosistema' ? 'Ecosistema' : 'Para ti'}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={s.date}>{date}</Text>
      <Pressable accessibilityRole="button" style={s.button} onPress={() => void regenerate()}>
        <Text style={s.buttonText}>Regenerar</Text>
      </Pressable>
      {edition === 'founders' && !sessionId ? (
        <View style={s.card}>
          <Text style={s.body}>
            Empieza una conversación en el chat para crear tu edición personalizada.
          </Text>
          <Pressable onPress={() => router.push('/chat')}>
            <Text style={s.link}>Ir al chat</Text>
          </Pressable>
        </View>
      ) : null}
      {error ? (
        <View style={s.card}>
          <Text accessibilityRole="alert" style={s.error}>
            {error}
          </Text>
          <Pressable onPress={() => void load()}>
            <Text style={s.link}>Reintentar</Text>
          </Pressable>
        </View>
      ) : null}
      {journal?.status === 'generating' ? (
        <View style={s.card}>
          <ActivityIndicator color={colors.accent} />
          <Text style={s.body}>
            Generando journal… {journal.progress?.done ?? 0}/{journal.progress?.total ?? 0}
          </Text>
        </View>
      ) : null}
      {journal?.status === 'error' ? (
        <View style={s.card}>
          <Text style={s.error}>{journal.error || 'No se pudo generar el journal.'}</Text>
          <Pressable onPress={() => void load()}>
            <Text style={s.link}>Reintentar</Text>
          </Pressable>
        </View>
      ) : null}
      {journal?.status === 'ready'
        ? journal.sections.map((section) => (
            <View key={section.id} style={s.section}>
              <Text style={s.sectionTitle}>{section.title}</Text>
              <Text style={s.body}>{section.description}</Text>
              {section.items.map((item) => (
                <View key={item.id} style={s.item}>
                  {item.is_new ? <Text style={s.new}>Nuevo</Text> : null}
                  <BlockView block={item.block} />
                  <Pressable
                    accessibilityRole="button"
                    style={s.ask}
                    onPress={() =>
                      router.push({
                        pathname: '/chat',
                        params: { journal_item_id: item.id, journal_title: section.title },
                      })
                    }
                  >
                    <Text style={s.buttonText}>Preguntar</Text>
                  </Pressable>
                </View>
              ))}
            </View>
          ))
        : null}
    </Screen>
  );
}
function journalStyles(c: import('../src/theme').Colors) {
  return StyleSheet.create({
    screen: { flex: 1, backgroundColor: c.bg },
    content: { padding: 20, paddingBottom: 40, maxWidth: 820, width: '100%', alignSelf: 'center' },
    eyebrow: { color: c.accent, fontSize: 11, fontWeight: '700', letterSpacing: 1.5 },
    title: { color: c.text, fontSize: 30, fontWeight: '800', marginTop: 5 },
    switcher: { flexDirection: 'row', gap: 8, marginTop: 18 },
    tab: { padding: 10, borderRadius: 10, borderWidth: 1, borderColor: c.surfaceAlt },
    active: { backgroundColor: c.accent },
    tabText: { color: c.text, fontWeight: '700' },
    date: { color: c.textMuted, marginTop: 14 },
    button: {
      alignSelf: 'flex-start',
      marginTop: 10,
      backgroundColor: c.accent,
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderRadius: 10,
    },
    buttonText: { color: c.accentText, fontWeight: '700' },
    card: {
      backgroundColor: c.surface,
      borderColor: c.surfaceAlt,
      borderWidth: 1,
      borderRadius: 14,
      padding: 16,
      marginTop: 14,
      gap: 8,
    },
    body: { color: c.textMuted, fontSize: 14, lineHeight: 21 },
    link: { color: c.accent, textDecorationLine: 'underline', fontWeight: '700' },
    error: { color: c.danger },
    section: { marginTop: 24 },
    sectionTitle: { color: c.text, fontWeight: '800', fontSize: 20 },
    item: { marginTop: 10 },
    new: {
      color: c.bg,
      backgroundColor: c.confirmed,
      overflow: 'hidden',
      borderRadius: 10,
      paddingHorizontal: 8,
      paddingVertical: 4,
      alignSelf: 'flex-start',
      fontSize: 11,
      fontWeight: '800',
    },
    ask: {
      alignSelf: 'flex-start',
      backgroundColor: c.surfaceAlt,
      paddingHorizontal: 14,
      paddingVertical: 9,
      borderRadius: 10,
      marginTop: 8,
    },
  });
}
