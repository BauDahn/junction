import { useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { Block, CalaCall, Source } from '../api';
import { verdictColors, verdictLabels } from '../verdict';

const ranks = ['FILING', 'PRIMARY', 'PRESS', 'AGGREGATOR'] as const;
function Sources({ sources }: { sources: Source[] }) {
  return (
    <View style={s.sources}>
      {sources.map((source, i) => (
        <Pressable
          key={`${source.url}-${i}`}
          accessibilityRole="link"
          onPress={() => Linking.openURL(source.url)}
        >
          <Text style={s.link}>
            ↗ {source.name}
            {source.date ? ` · ${source.date}` : ''}
            {source.source_rank && ranks.includes(source.source_rank) ? (
              <Text style={s.rank}> {source.source_rank}</Text>
            ) : null}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}
function Query({ call }: { call: CalaCall }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={s.query}>
      <Pressable accessibilityRole="button" onPress={() => setOpen(!open)}>
        <Text style={s.muted}>{open ? '⌄' : '›'} Consulta</Text>
      </Pressable>
      {open ? (
        <Text style={s.queryText}>
          {call.tool}: {call.query}
        </Text>
      ) : null}
    </View>
  );
}
function DataBlock({ block }: { block: Extract<Block, { type: 'cala_table' | 'cala_answer' }> }) {
  if (block.type === 'cala_answer')
    return (
      <>
        <Text style={s.title}>{block.title}</Text>
        <Markdown text={block.markdown} />
        <Sources sources={block.sources} />
        <Query call={block.call} />
      </>
    );
  return (
    <>
      <Text style={s.title}>{block.title}</Text>
      {block.summary ? <Text style={s.body}>{block.summary}</Text> : null}
      <ScrollView horizontal showsHorizontalScrollIndicator>
        <View>
          <View style={s.tableRow}>
            {block.columns.map((c, i) => (
              <Text key={i} style={[s.cell, s.headerCell]}>
                {c}
              </Text>
            ))}
          </View>
          {block.rows.map((row, ri) => (
            <View key={ri} style={s.tableRow}>
              {row.map((value, ci) => (
                <Text key={ci} style={s.cell}>
                  {value == null ? '—' : String(value)}
                </Text>
              ))}
              <Text style={s.rowSources}>
                {(block.row_sources?.[ri] ?? [])
                  .map((sourceIndex) => `[${sourceIndex + 1}]`)
                  .join(' ')}
              </Text>
            </View>
          ))}
        </View>
      </ScrollView>
      <Sources sources={block.sources} />
      <Query call={block.call} />
    </>
  );
}
function Markdown({ text }: { text: string }) {
  return (
    <View style={s.markdown}>
      {text.split('\n').map((line, i) => {
        const bullet = line.startsWith('- ');
        const content = bullet ? line.slice(2) : line;
        const parts = content.split(/(\*\*[^*]+\*\*)/g);
        return (
          <Text key={i} style={s.body}>
            {bullet ? '• ' : ''}
            {parts.map((part, j) =>
              part.startsWith('**') && part.endsWith('**') ? (
                <Text key={j} style={s.bold}>
                  {part.slice(2, -2)}
                </Text>
              ) : (
                part
              ),
            )}
          </Text>
        );
      })}
    </View>
  );
}
export default function BlockView({ block }: { block: Block }) {
  if (!block || typeof block !== 'object') return null;
  return (
    <View style={s.card}>
      {block.type === 'cala_table' || block.type === 'cala_answer' ? (
        <DataBlock block={block as Extract<Block, { type: 'cala_table' | 'cala_answer' }>} />
      ) : block.type === 'claim_check' ? (
        <>
          <Text style={s.quote}>“{block.claim}”</Text>
          <Text
            style={[
              s.badge,
              { color: verdictColors[block.verdict], borderColor: verdictColors[block.verdict] },
            ]}
          >
            {verdictLabels[block.verdict]}
          </Text>
          <Text style={s.body}>{block.explanation}</Text>
          <BlockView block={block.evidence} />
          <Sources sources={block.sources} />
        </>
      ) : block.type === 'profile_update' ? (
        <>
          <Text style={s.title}>Perfil actualizado</Text>
          {Object.entries(block.changes).map(([key, value]) => (
            <Text key={key} style={s.body}>
              {key} → {String(value)}
            </Text>
          ))}
        </>
      ) : block.type === 'not_found' ? (
        <>
          <Text style={s.title}>{block.title}</Text>
          <Text style={s.body}>Se buscó en Cala:</Text>
          {block.tried.map((call, i) => (
            <Text key={i} style={s.muted}>
              {call.tool}: {call.query}
            </Text>
          ))}
          {block.closest ? <BlockView block={block.closest} /> : null}
        </>
      ) : block.type === 'text' ? (
        <Text style={s.body}>{block.text}</Text>
      ) : null}
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
    gap: 8,
  },
  title: { color: '#f8fafc', fontWeight: '700', fontSize: 16 },
  body: { color: '#cbd5e1', fontSize: 14, lineHeight: 21 },
  bold: { fontWeight: '700', color: '#f8fafc' },
  markdown: { gap: 4 },
  tableRow: { flexDirection: 'row', alignItems: 'stretch' },
  cell: {
    minWidth: 100,
    maxWidth: 220,
    color: '#cbd5e1',
    fontSize: 12,
    padding: 9,
    borderBottomWidth: 1,
    borderColor: '#29324b',
  },
  headerCell: { color: '#f8fafc', fontWeight: '700', backgroundColor: '#202943' },
  rowSources: { color: '#c4b5fd', padding: 9 },
  sources: { gap: 5 },
  link: { color: '#c4b5fd', fontSize: 12, textDecorationLine: 'underline' },
  rank: {
    color: '#0b1020',
    backgroundColor: '#c4b5fd',
    overflow: 'hidden',
    borderRadius: 5,
    fontSize: 10,
  },
  query: { borderTopWidth: 1, borderColor: '#29324b', paddingTop: 7, marginTop: 4 },
  queryText: { color: '#9aa6bf', fontSize: 11, marginTop: 5 },
  muted: { color: '#9aa6bf', fontSize: 12 },
  quote: { color: '#f8fafc', fontSize: 16, fontWeight: '600' },
  badge: {
    alignSelf: 'flex-start',
    fontSize: 11,
    fontWeight: '700',
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 9,
    paddingVertical: 5,
    overflow: 'hidden',
  },
});
