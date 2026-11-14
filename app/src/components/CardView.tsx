import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import type { Card } from '../api';
export default function CardView({ card }: { card: Card }) {
  return (
    <View style={s.card}>
      <Text style={s.title}>{card.title}</Text>
      {card.subtitle ? <Text style={s.subtitle}>{card.subtitle}</Text> : null}
      <Text style={s.reason}>{card.reason}</Text>
      <Text style={s.sourceHeading}>Fuentes</Text>
      {card.sources.map((source, i) => (
        <Pressable
          key={`${source.url}-${i}`}
          accessibilityRole="link"
          onPress={() => Linking.openURL(source.url)}
        >
          <Text style={s.source}>↗ {source.name}</Text>
        </Pressable>
      ))}
    </View>
  );
}
const s = StyleSheet.create({
  card: {
    backgroundColor: '#151c30',
    borderColor: '#29324b',
    borderWidth: 1,
    borderRadius: 15,
    padding: 16,
    marginTop: 10,
  },
  title: { color: '#f8fafc', fontWeight: '700', fontSize: 16 },
  subtitle: { color: '#a78bfa', fontSize: 13, marginTop: 4 },
  reason: { color: '#cbd5e1', fontSize: 14, lineHeight: 21, marginTop: 10 },
  sourceHeading: { color: '#9aa6bf', fontSize: 11, fontWeight: '700', marginTop: 12 },
  source: { color: '#c4b5fd', fontSize: 13, textDecorationLine: 'underline', marginTop: 6 },
});
