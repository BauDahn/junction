import { useMemo, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { Block, CalaCall, ClaimVerdict, Source } from '../api';
import { font, radius, space, tabularNums, useTheme, type Colors } from '../theme';

const SOURCE_RANKS = ['FILING', 'PRIMARY', 'PRESS', 'AGGREGATOR'] as const;

const VERDICT_LABELS: Record<ClaimVerdict, string> = {
  confirmed: 'Confirmed',
  partially_confirmed: 'Partially confirmed',
  contradicted: 'Contradicted',
  no_data: 'No data',
};

const FIELD_LABELS: Record<string, string> = {
  startup_name: 'Startup',
  one_liner: 'One-liner',
  sector: 'Sector',
  stage: 'Stage',
  location: 'Location',
  target_customers: 'Target customers',
  raising_amount: 'Raising amount',
  raising_round: 'Round',
  competitors: 'Competitors',
  interests: 'Interests',
  role: 'Role',
};

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function formatFieldLabel(key: string): string {
  return FIELD_LABELS[key] ?? key.replace(/_/g, ' ').replace(/^\w/, (ch) => ch.toUpperCase());
}

function formatFieldValue(value: unknown): string {
  if (value == null || value === '') return '—';
  if (Array.isArray(value)) return value.map((item) => String(item)).join(', ') || '—';
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v != null && v !== '' && (!Array.isArray(v) || v.length > 0))
      .map(([k, v]) => `${formatFieldLabel(k)}: ${formatFieldValue(v)}`);
    return entries.length ? entries.join(' · ') : '—';
  }
  return String(value);
}

type Styles = ReturnType<typeof makeStyles>;

function Sources({
  sources,
  numbered = false,
  s,
}: {
  sources: Source[];
  numbered?: boolean;
  s: Styles;
}) {
  if (!sources?.length) return null;
  return (
    <View style={s.sources}>
      <Text style={s.sectionMicro}>Sources</Text>
      {sources.map((source, index) => {
        const domain = source.url ? host(source.url) : '';
        const rank =
          source.source_rank && SOURCE_RANKS.includes(source.source_rank)
            ? source.source_rank
            : undefined;
        return (
          <Pressable
            key={`${source.url}-${index}`}
            accessibilityRole="link"
            accessibilityLabel={`Source: ${source.name}`}
            onPress={() => {
              if (source.url) void Linking.openURL(source.url);
            }}
          >
              <Text style={s.sourceRow}>
              {numbered ? <Text style={s.sourceMeta}>[{index + 1}] </Text> : null}
              <Text style={s.link}>{source.name}</Text>
              {domain && domain.toLowerCase() !== source.name.toLowerCase() ? (
                <Text style={s.sourceMeta}> · {domain}</Text>
              ) : null}
              {source.date ? <Text style={s.sourceMeta}> · {source.date}</Text> : null}
              {rank ? <Text style={s.sourceRank}> · {rank}</Text> : null}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function QueryCall({ call, s }: { call: CalaCall; s: Styles }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={s.query}>
      <Pressable accessibilityRole="button" onPress={() => setOpen((prev) => !prev)}>
        <Text style={s.queryToggle}>{open ? 'Hide Cala query' : 'Show Cala query'}</Text>
      </Pressable>
      {open ? (
        <Text selectable style={s.queryText}>
          {call.tool}: {call.query}
        </Text>
      ) : null}
    </View>
  );
}

function Markdown({ text, s }: { text: string; s: Styles }) {
  const lines = (text ?? '')
    .split('\n')
    .filter((line, idx, arr) => line.trim() !== '' || (idx > 0 && arr[idx - 1].trim() !== ''));
  return (
    <View style={s.markdown}>
      {lines.map((line, i) => {
        const bullet = line.startsWith('- ') || line.startsWith('* ');
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

function TableBlock({
  block,
  s,
}: {
  block: Extract<Block, { type: 'cala_table' }>;
  s: Styles;
}) {
  const [all, setAll] = useState(false);
  const focus = block.focus_rows?.filter((i) => i >= 0 && i < block.rows.length) ?? [];
  const visible = all || !focus.length ? block.rows.map((_, i) => i) : focus;
  const hasRowSources = Boolean(block.row_sources?.some((rs) => rs && rs.length > 0));
  const columns = hasRowSources ? [...block.columns, 'Sources'] : block.columns;
  const title = block.title === 'Datos de Cala' ? 'Cala data' : block.title;

  return (
    <>
      <Text style={s.title}>{title}</Text>
      {block.summary ? (
        <Text style={s.body}>{block.summary}</Text>
      ) : block.answer ? (
        <Text style={s.body}>{block.answer}</Text>
      ) : null}
      {block.rows.length && block.columns.length ? (
        <View style={s.tableWrap}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={{ flexGrow: 1 }}>
              <View style={s.tableHeaderRow}>
                {columns.map((col, idx) => (
                  <Text key={`${col}-${idx}`} style={[s.cell, s.headerCell]}>
                    {col.replace(/_/g, ' ').replace(/^\w/, (letter) => letter.toUpperCase())}
                  </Text>
                ))}
              </View>
              {visible.map((rowIndex) => (
                <View key={rowIndex} style={s.tableRow}>
                  {columns.map((_, colIndex) => {
                    const isSourceCol = hasRowSources && colIndex === block.columns.length;
                    const raw = isSourceCol
                      ? (block.row_sources?.[rowIndex] ?? [])
                          .map((sourceIdx) => `[${sourceIdx + 1}]`)
                          .join(' ')
                      : block.rows[rowIndex]?.[colIndex];
                    const cellText = raw == null || raw === '' ? '—' : String(raw);
                    return (
                      <Text
                        key={colIndex}
                        selectable
                        style={[
                          s.cell,
                          colIndex === 0 && s.primaryCell,
                          isSourceCol && s.sourceCell,
                        ]}
                      >
                        {cellText}
                      </Text>
                    );
                  })}
                </View>
              ))}
            </View>
          </ScrollView>
        </View>
      ) : (
        <Text style={s.muted}>No rows returned.</Text>
      )}
      {focus.length > 0 && focus.length < block.rows.length ? (
        <Pressable accessibilityRole="button" onPress={() => setAll((prev) => !prev)}>
          <Text style={s.more}>
            {all ? 'Show less' : `Show all (${block.rows.length})`}
          </Text>
        </Pressable>
      ) : null}
      <Sources sources={block.sources} numbered={hasRowSources} s={s} />
      <QueryCall call={block.call} s={s} />
    </>
  );
}

function DataBlock({
  block,
  s,
}: {
  block: Extract<Block, { type: 'cala_table' | 'cala_answer' }>;
  s: Styles;
}) {
  if (block.type === 'cala_answer') {
    return (
      <>
        <Text style={s.title}>{block.title}</Text>
        <Markdown text={block.markdown} s={s} />
        <Sources sources={block.sources} s={s} />
        <QueryCall call={block.call} s={s} />
      </>
    );
  }
  return <TableBlock block={block} s={s} />;
}

/** Structured Cala data block (table, answer, claim verification, profile update, or not-found). */
export default function BlockView({
  block,
  nested = false,
}: {
  block: Block;
  nested?: boolean;
}) {
  const { colors } = useTheme();
  const s = useMemo(() => makeStyles(colors), [colors]);

  if (!block || typeof block !== 'object') return null;

  return (
    <View style={nested ? s.nestedContainer : s.container}>
      {block.type === 'cala_table' || block.type === 'cala_answer' ? (
        <DataBlock block={block} s={s} />
      ) : block.type === 'claim_check' ? (
        <>
          <View
            style={[
              s.verdictRow,
              {
                borderLeftColor:
                  block.verdict === 'confirmed'
                    ? colors.accent
                    : block.verdict === 'contradicted'
                      ? colors.danger
                      : colors.border,
              },
            ]}
          >
            <Text
              style={[
                s.verdictLabel,
                {
                  color:
                    block.verdict === 'confirmed'
                      ? colors.accent
                      : block.verdict === 'contradicted'
                        ? colors.danger
                        : colors.textMuted,
                },
              ]}
            >
              Verdict · {VERDICT_LABELS[block.verdict] ?? block.verdict}
            </Text>
          </View>
          <Text style={s.quote}>“{block.claim}”</Text>
          <Text style={s.body}>{block.explanation}</Text>
          <BlockView block={block.evidence} nested />
          <Sources sources={block.sources} s={s} />
        </>
      ) : block.type === 'profile_update' ? (
        <>
          <Text style={s.title}>Profile updated</Text>
          <View style={s.kvList}>
            {Object.entries(block.changes).map(([key, value]) => (
              <View key={key} style={s.kvRow}>
                <Text style={s.kvKey}>{formatFieldLabel(key)}</Text>
                <Text style={s.kvVal}>{formatFieldValue(value)}</Text>
              </View>
            ))}
          </View>
        </>
      ) : block.type === 'not_found' ? (
        <>
          <Text style={s.title}>{block.title || 'No data found in Cala'}</Text>
          <Text style={s.sectionMicro}>Checked in Cala</Text>
          <View style={s.kvList}>
            {block.tried.map((call, i) => (
              <View key={`${call.tool}-${i}`} style={s.triedRow}>
                <Text style={s.triedTool}>{call.tool}</Text>
                <Text selectable style={s.triedQuery}>
                  {call.query}
                </Text>
              </View>
            ))}
          </View>
          {block.closest ? <BlockView block={block.closest} nested /> : null}
        </>
      ) : block.type === 'text' ? (
        <Text style={s.body}>{block.text}</Text>
      ) : null}
    </View>
  );
}

function makeStyles(c: Colors) {
  return StyleSheet.create({
    container: {
      borderBottomWidth: 1,
      borderBottomColor: c.border,
      paddingVertical: space.md,
      gap: space.sm,
    },
    nestedContainer: {
      gap: space.sm,
    },
    title: {
      color: c.text,
      fontWeight: '600',
      fontSize: font.body,
      lineHeight: 22,
    },
    body: {
      color: c.textMuted,
      fontSize: font.small,
      lineHeight: 20,
    },
    bold: {
      fontWeight: '600',
      color: c.text,
    },
    markdown: {
      gap: space.xs,
    },
    tableWrap: {
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: c.border,
    },
    tableHeaderRow: {
      flexDirection: 'row',
      backgroundColor: c.surfaceAlt,
    },
    tableRow: {
      flexDirection: 'row',
      borderTopWidth: 1,
      borderTopColor: c.border,
    },
    cell: {
      flex: 1,
      minWidth: 96,
      maxWidth: 220,
      color: c.textMuted,
      fontSize: font.small,
      lineHeight: 18,
      paddingHorizontal: space.md,
      paddingVertical: space.sm,
      fontVariant: ['tabular-nums'],
    },
    headerCell: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
      paddingVertical: space.sm,
    },
    primaryCell: {
      color: c.text,
      fontWeight: '500',
    },
    sourceCell: {
      color: c.accent,
      fontSize: font.caption,
    },
    more: {
      color: c.accent,
      fontSize: font.small,
      fontWeight: '600',
    },
    sources: {
      gap: space.xs,
      paddingTop: space.xs,
    },
    sectionMicro: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
    },
    sourceRow: {
      fontSize: font.small,
      lineHeight: 18,
    },
    link: {
      color: c.accent,
      textDecorationLine: 'underline',
    },
    sourceMeta: {
      color: c.textFaint,
      fontSize: font.caption,
    },
    sourceRank: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
    },
    query: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingTop: space.sm,
    },
    queryToggle: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '500',
    },
    queryText: {
      color: c.textMuted,
      fontSize: font.caption,
      lineHeight: 18,
      marginTop: space.xs,
    },
    muted: {
      color: c.textMuted,
      fontSize: font.small,
    },
    verdictRow: {
      borderLeftWidth: 2,
      paddingLeft: space.sm,
    },
    verdictLabel: {
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
    },
    quote: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '600',
      lineHeight: 22,
    },
    kvList: {
      borderBottomWidth: 1,
      borderBottomColor: c.border,
    },
    kvRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      gap: space.md,
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: space.sm,
    },
    kvKey: {
      color: c.textMuted,
      fontSize: font.small,
    },
    kvVal: {
      color: c.text,
      fontSize: font.small,
      fontWeight: '500',
      textAlign: 'right',
      flexShrink: 1,
    },
    triedRow: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: space.sm,
      gap: space.xs,
    },
    triedTool: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
    },
    triedQuery: {
      color: c.textMuted,
      fontSize: font.small,
      lineHeight: 18,
    },
  });
}
