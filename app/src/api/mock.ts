import type {
  Block,
  Card,
  Journal,
  Message,
  Profile,
  Recommendations,
  SendTextResponse,
} from './index';

export const mockProfile: Profile = {
  startup_name: 'Nordleaf',
  one_liner: 'Energy efficiency tools for buildings',
  sector: 'ClimateTech',
  stage: 'Pre-seed',
  location: 'Helsinki',
  competitors: ['GreenBuild'],
  target_customers: 'Building owners',
  facts: [],
  updated_at: new Date().toISOString(),
};

const card = (type: Card['type'], title: string, subtitle: string, reason: string): Card => ({
  type,
  title,
  subtitle,
  reason,
  sources: [{ name: 'Cala · example', url: 'https://cala.ai' }],
});

export const mockRecommendations: Recommendations = {
  status: 'ready',
  updated_at: new Date().toISOString(),
  investors: [
    card('investor', 'Polar Ventures', 'Climate · Finland', 'Invests in decarbonization solutions.'),
    card('investor', 'Northstar Capital', 'Pre-seed · Europe', 'Backs Nordic early-stage teams.'),
    card('investor', 'Arctic Seed', 'Impact · Helsinki', 'Looks for startups with measurable impact.'),
  ],
  competitors: [
    card('competitor', 'GreenBuild', 'Software · Sweden', 'An adjacent solution for building efficiency.'),
    card('competitor', 'Wattwise', 'ClimateTech · Denmark', 'Optimizes energy consumption.'),
    card('competitor', 'BuildingOS', 'PropTech · Europe', 'A data platform for buildings.'),
  ],
  prospects: [
    card('prospect', 'Helsinki Housing', 'Property management', 'Potential customer with a portfolio of buildings.'),
    card('prospect', 'Nordic Estates', 'Property owner · Finland', 'A profile that fits the product.'),
    card('prospect', 'City of Espoo', 'Public sector', 'Local energy efficiency initiatives.'),
  ],
};

const histories = new Map<string, Message[]>();
const wait = () => new Promise((resolve) => setTimeout(resolve, 800));

export async function createMockSession(): Promise<string> {
  await wait();
  const id = 'mock-session';
  if (!histories.has(id)) histories.set(id, []);
  return id;
}

export async function listMockMessages(sessionId: string): Promise<Message[]> {
  await wait();
  return [...(histories.get(sessionId) ?? [])];
}

function exampleTable() {
  return {
    type: 'cala_table' as const,
    title: 'Sample data: Amenitiz Series B round',
    summary: 'Demo data; this does not represent real information.',
    call: { tool: 'knowledge_query' as const, query: 'DEMO: Amenitiz Series B round' },
    columns: ['Company', 'Round', 'Amount'],
    rows: [['Amenitiz (example)', 'Series B (example)', null]],
    sources: [
      {
        name: 'Example source',
        url: 'https://example.com',
        date: '2026-11-14',
        source_rank: 'PRESS' as const,
      },
    ],
    row_sources: [[0]],
  };
}

function exampleBlocks(text: string): Block[] {
  const lower = text.toLowerCase();
  if (lower.includes('xyz'))
    return [
      {
        type: 'not_found',
        title: 'Example: no information found',
        tried: [
          { tool: 'knowledge_query', query: 'DEMO: canonical query XYZ' },
          { tool: 'entity', query: 'DEMO: XYZ entities' },
          { tool: 'knowledge_search', query: 'DEMO: XYZ search' },
        ],
      },
    ];
  if (lower.includes('raised'))
    return [
      {
        type: 'claim_check',
        claim: text,
        verdict: 'partially_confirmed',
        explanation: 'Sample result to demonstrate this block.',
        evidence: exampleTable(),
        sources: [{ name: 'Example source', url: 'https://example.com', source_rank: 'PRESS' }],
      },
    ];
  if (lower.includes('we are') || lower.includes('interested'))
    return [{ type: 'profile_update', changes: { interests: 'Example: Nordic fintech' } }];
  if (text.includes('?') || lower.includes('who')) return [exampleTable()];
  return [
    {
      type: 'cala_answer',
      title: 'Sample answer',
      call: { tool: 'knowledge_search', query: `DEMO: ${text}` },
      markdown: '**Sample data.** Cala would show its response here as returned.\n- Demo point',
      sources: [{ name: 'Example source', url: 'https://example.com', source_rank: 'PRIMARY' }],
    },
  ];
}

function response(sessionId: string, text: string, transcript?: string): SendTextResponse {
  const now = new Date().toISOString();
  const user: Message = {
    id: `mock-user-${Date.now()}`,
    role: 'user',
    text,
    ...(transcript ? { transcript, audio: true } : {}),
    created_at: now,
  };
  const reply: Message = {
    id: `mock-assistant-${Date.now()}`,
    role: 'assistant',
    text: 'Sample demo data; these are not real Cala results.',
    created_at: now,
    blocks: exampleBlocks(text),
    sources: [{ name: 'Cala · example', url: 'https://cala.ai' }],
  };
  const history = histories.get(sessionId) ?? [];
  histories.set(sessionId, [...history, user, reply]);
  return { message: user, reply, profile_updated: true, recommendations_status: 'ready' };
}

export async function sendMockText(sessionId: string, text: string): Promise<SendTextResponse> {
  await wait();
  return response(sessionId, text);
}

export async function sendMockAudio(sessionId: string): Promise<SendTextResponse> {
  await wait();
  return response(
    sessionId,
    'Looking for energy and climate investors for my startup in Helsinki.',
    'Looking for energy and climate investors for my startup in Helsinki.',
  );
}

const journalStates = new Map<string, { started: number; done: number }>();
function mockJournal(edition: Journal['edition'], date: string): Journal {
  const key = `${edition}:${date}`;
  const state = journalStates.get(key);
  const generating = !!state && Date.now() - state.started < 3000;
  const table = exampleTable();
  const answer: Block = {
    type: 'cala_answer',
    title: 'Sample data: ecosystem activity',
    call: { tool: 'knowledge_search', query: 'DEMO: recent ecosystem activity' },
    markdown: '**Sample data.** This section shows how a Cala response would look.',
    sources: [{ name: 'Example source', url: 'https://example.com' }],
  };
  const section = (
    id: string,
    title: string,
    description: string,
    block: Block,
    isNew: boolean,
  ) => ({ id, title, description, items: [{ id: `${id}-item`, is_new: isNew, block }] });
  const sections =
    edition === 'ecosistema'
      ? [
          section('rounds', 'Recent rounds', 'Notable rounds by region.', table, true),
          section('funds', 'Active funds', 'Investors with recent activity.', answer, false),
          section('slush', 'Slush 2026', 'Companies and people across the ecosystem.', table, true),
        ]
      : [
          section('sectors', 'Rounds in your sectors', 'Recent activity across your sectors and regions of interest.', table, true),
          section('investors', 'Investors leading rounds', 'Funds with activity as lead investors.', answer, false),
          section('competitors', 'Competitors raising funds', 'Recent rounds from similar companies.', table, true),
        ];
  return {
    edition,
    date,
    status: generating ? 'generating' : 'ready',
    generated_at: generating ? undefined : new Date().toISOString(),
    progress: generating
      ? { done: Math.min(2, Math.floor((Date.now() - state!.started) / 1000)), total: 3 }
      : undefined,
    sections,
  };
}

export async function getMockJournal(
  edition: Journal['edition'],
  date = new Date().toISOString().slice(0, 10),
  _sessionId?: string,
): Promise<Journal> {
  await wait();
  return mockJournal(edition, date);
}

export async function regenerateMockJournal(
  edition: Journal['edition'],
  sessionId?: string,
): Promise<{ status: 'generating' }> {
  const date = new Date().toISOString().slice(0, 10);
  journalStates.set(`${edition}:${date}`, { started: Date.now(), done: 0 });
  void sessionId;
  return { status: 'generating' };
}
