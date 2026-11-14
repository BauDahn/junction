import { ApiError, type Source } from './index';

export type EntityMode = 'raising' | 'investing';

export type EntityMatchSignal = {
  signal: string;
  text: string;
  sources: Source[];
};

export type EntityFact = {
  label: string;
  value: string | number;
  sources: Source[];
};

export type EntityRound = {
  round_type?: string;
  amount?: string;
  date?: string;
  leads: string[];
  investors: string[];
  sources: Source[];
};

export type EntityPortfolioItem = {
  id: string;
  name: string;
};

export type EntityPerson = {
  id: string;
  name: string;
  role: string;
  since?: string;
};

export type EntityDetail = {
  id: string;
  type: 'investor' | 'startup';
  name: string;
  description?: string;
  score?: number;
  confidence?: number;
  why_match: EntityMatchSignal[];
  facts: EntityFact[];
  rounds: EntityRound[];
  portfolio: EntityPortfolioItem[];
  people: EntityPerson[];
  loaded_at: string;
};

export type EntityDetailResult = {
  detail: EntityDetail | null;
  isSample: boolean;
};

const REQUEST_TIMEOUT_MS = 8000;

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';

const CALA_SOURCE: Source = {
  name: 'Cala Knowledge Graph',
  url: 'https://cala.ai',
  source_rank: 'PRIMARY',
};

const EIGHT_ROADS_SOURCE: Source = {
  name: 'Eight Roads Ventures',
  url: 'https://eightroads.com',
  source_rank: 'PRIMARY',
};

const CHALFEN_SOURCE: Source = {
  name: 'Chalfen Ventures',
  url: 'https://chalfen.vc',
  source_rank: 'PRIMARY',
};

const NORTHZONE_SOURCE: Source = {
  name: 'Northzone',
  url: 'https://northzone.com',
  source_rank: 'PRIMARY',
};

const POINT_NINE_SOURCE: Source = {
  name: 'Point Nine',
  url: 'https://pointnine.com',
  source_rank: 'PRIMARY',
};

const AMENITIZ_SOURCE: Source = {
  name: 'Amenitiz',
  url: 'https://amenitiz.com',
  source_rank: 'PRIMARY',
};

const PRESS_SERIES_A_SOURCE: Source = {
  name: 'Cala Press Archive',
  url: 'https://cala.ai',
  date: '2022',
  source_rank: 'PRESS',
};

const PRESS_SERIES_B_SOURCE: Source = {
  name: 'Cala Press Archive',
  url: 'https://cala.ai',
  date: '2025',
  source_rank: 'PRESS',
};

type MockSeed = Omit<EntityDetail, 'score' | 'confidence' | 'why_match'> & {
  matchScore: number;
  matchConfidence: number;
  matchSignals: EntityMatchSignal[];
};

const MOCK_RECORDS: Record<string, MockSeed> = {
  'eight-roads-ventures': {
    id: 'eight-roads-ventures',
    type: 'investor',
    name: 'Eight Roads Ventures',
    description:
      'Global venture capital firm backing enterprise software, fintech, and healthcare technology companies across Europe, Asia, and North America.',
    matchScore: 88,
    matchConfidence: 0.91,
    matchSignals: [
      {
        signal: 'sector',
        text: 'Active B2B SaaS and fintech investor across European software companies (AI-tagged).',
        sources: [CALA_SOURCE, EIGHT_ROADS_SOURCE],
      },
      {
        signal: 'stage',
        text: 'Leads and co-leads Series A and Series B financings in scaling software platforms.',
        sources: [PRESS_SERIES_A_SOURCE, EIGHT_ROADS_SOURCE],
      },
      {
        signal: 'region',
        text: 'European team invests across UK, Spain, France, and the Nordics.',
        sources: [EIGHT_ROADS_SOURCE, CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Sectors (AI-tagged)',
        value: 'B2B SaaS, Fintech, Enterprise Software',
        sources: [CALA_SOURCE, EIGHT_ROADS_SOURCE],
      },
      {
        label: 'Stages (AI-tagged)',
        value: 'Series A, Series B',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Headquarters',
        value: 'London, United Kingdom',
        sources: [EIGHT_ROADS_SOURCE],
      },
      {
        label: 'Typical round size',
        value: '$10M–$40M',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Rounds in the last 24 months',
        value: 14,
        sources: [CALA_SOURCE],
      },
    ],
    rounds: [
      {
        round_type: 'Series A',
        amount: '$30M',
        date: '2022',
        leads: ['Eight Roads Ventures', 'Chalfen Ventures'],
        investors: ['Eight Roads Ventures', 'Chalfen Ventures', 'Point Nine'],
        sources: [PRESS_SERIES_A_SOURCE, CALA_SOURCE],
      },
      {
        round_type: 'Series B',
        amount: '€38.9M',
        date: '2025',
        leads: ['Kfund'],
        investors: ['Kfund', 'Eight Roads Ventures', 'Chalfen Ventures', 'Point Nine'],
        sources: [PRESS_SERIES_B_SOURCE, CALA_SOURCE],
      },
    ],
    portfolio: [
      { id: 'amenitiz', name: 'Amenitiz' },
      { id: 'spendesk', name: 'Spendesk' },
    ],
    people: [{ id: 'lucile-cornet', name: 'Lucile Cornet', role: 'Partner', since: '2022' }],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'chalfen-ventures': {
    id: 'chalfen-ventures',
    type: 'investor',
    name: 'Chalfen Ventures',
    description:
      'London-based solo-GP venture firm partnering with software founders across Europe from Seed through Series A.',
    matchScore: 79,
    matchConfidence: 0.44,
    matchSignals: [
      {
        signal: 'stage',
        text: 'Focuses on Seed and Series A rounds alongside European lead funds.',
        sources: [CHALFEN_SOURCE, PRESS_SERIES_A_SOURCE],
      },
      {
        signal: 'sector',
        text: 'Backs vertical SaaS and workflow infrastructure startups (AI-tagged).',
        sources: [CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Sectors (AI-tagged)',
        value: 'B2B SaaS, Vertical Software',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Stages (AI-tagged)',
        value: 'Seed, Series A',
        sources: [CHALFEN_SOURCE],
      },
      {
        label: 'Headquarters',
        value: 'London, United Kingdom',
        sources: [CHALFEN_SOURCE],
      },
    ],
    rounds: [
      {
        round_type: 'Series A',
        amount: '$30M',
        date: '2022',
        leads: ['Eight Roads Ventures', 'Chalfen Ventures'],
        investors: ['Eight Roads Ventures', 'Chalfen Ventures', 'Point Nine'],
        sources: [PRESS_SERIES_A_SOURCE, CALA_SOURCE],
      },
      {
        amount: '€38.9M',
        date: '2025',
        leads: ['Kfund'],
        investors: ['Kfund', 'Chalfen Ventures', 'Eight Roads Ventures'],
        sources: [PRESS_SERIES_B_SOURCE],
      },
    ],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [{ id: 'mike-chalfen', name: 'Mike Chalfen', role: 'Founder & Partner' }],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  northzone: {
    id: 'northzone',
    type: 'investor',
    name: 'Northzone',
    description:
      'Multi-stage European venture capital firm investing from Seed to Growth out of Stockholm, London, Amsterdam, and New York.',
    matchScore: 84,
    matchConfidence: 0.86,
    matchSignals: [
      {
        signal: 'region',
        text: 'Strong Nordic and pan-European coverage with an active Stockholm office.',
        sources: [NORTHZONE_SOURCE, CALA_SOURCE],
      },
      {
        signal: 'sector',
        text: 'Invests across fintech, climate tech, and B2B SaaS (AI-tagged).',
        sources: [CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Sectors (AI-tagged)',
        value: 'Fintech, B2B SaaS, ClimateTech',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Stages (AI-tagged)',
        value: 'Seed, Series A, Series B',
        sources: [NORTHZONE_SOURCE],
      },
      {
        label: 'Headquarters',
        value: 'Stockholm & London',
        sources: [NORTHZONE_SOURCE],
      },
      {
        label: 'Rounds in the last 24 months',
        value: 11,
        sources: [CALA_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [{ id: 'spendesk', name: 'Spendesk' }],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'point-nine': {
    id: 'point-nine',
    type: 'investor',
    name: 'Point Nine',
    description:
      'Berlin-based early-stage venture fund focused exclusively on B2B SaaS and digital marketplaces.',
    matchScore: 82,
    matchConfidence: 0.84,
    matchSignals: [
      {
        signal: 'stage',
        text: 'Leads Seed rounds for European B2B SaaS teams.',
        sources: [POINT_NINE_SOURCE, CALA_SOURCE],
      },
      {
        signal: 'sector',
        text: 'Deep focus on SaaS metrics and horizontal/vertical software (AI-tagged).',
        sources: [CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Sectors (AI-tagged)',
        value: 'B2B SaaS, Marketplaces',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Stages (AI-tagged)',
        value: 'Pre-seed, Seed',
        sources: [POINT_NINE_SOURCE],
      },
      {
        label: 'Headquarters',
        value: 'Berlin, Germany',
        sources: [POINT_NINE_SOURCE],
      },
    ],
    rounds: [
      {
        round_type: 'Series A',
        amount: '$30M',
        date: '2022',
        leads: ['Eight Roads Ventures', 'Chalfen Ventures'],
        investors: ['Eight Roads Ventures', 'Chalfen Ventures', 'Point Nine'],
        sources: [PRESS_SERIES_A_SOURCE],
      },
    ],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [{ id: 'louis-coppey', name: 'Louis Coppey', role: 'Partner' }],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  amenitiz: {
    id: 'amenitiz',
    type: 'startup',
    name: 'Amenitiz',
    description:
      'Barcelona-based all-in-one hospitality management software platform (PMS, channel manager, and direct booking engine) built for independent hotels.',
    matchScore: 86,
    matchConfidence: 0.9,
    matchSignals: [
      {
        signal: 'sector',
        text: 'Vertical B2B SaaS platform serving European SMB hospitality operators (AI-tagged).',
        sources: [AMENITIZ_SOURCE, CALA_SOURCE],
      },
      {
        signal: 'activity',
        text: 'Backed across Seed, Series A, and Series B by tier-one European software funds.',
        sources: [PRESS_SERIES_B_SOURCE, CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Sectors (AI-tagged)',
        value: 'Hospitality SaaS, B2B Software',
        sources: [CALA_SOURCE, AMENITIZ_SOURCE],
      },
      {
        label: 'Stages (AI-tagged)',
        value: 'Series B',
        sources: [PRESS_SERIES_B_SOURCE],
      },
      {
        label: 'Headquarters',
        value: 'Barcelona, Spain',
        sources: [AMENITIZ_SOURCE],
      },
      {
        label: 'Country',
        value: 'Spain',
        sources: [CALA_SOURCE],
      },
    ],
    rounds: [
      {
        round_type: 'Series B',
        amount: '€38.9M',
        date: '2025',
        leads: ['Kfund'],
        investors: ['Kfund', 'Eight Roads Ventures', 'Chalfen Ventures', 'Point Nine'],
        sources: [PRESS_SERIES_B_SOURCE, CALA_SOURCE],
      },
      {
        round_type: 'Series A',
        amount: '$30M',
        date: '2022',
        leads: ['Eight Roads Ventures', 'Chalfen Ventures'],
        investors: ['Eight Roads Ventures', 'Chalfen Ventures', 'Point Nine'],
        sources: [PRESS_SERIES_A_SOURCE, CALA_SOURCE],
      },
    ],
    portfolio: [],
    people: [
      { id: 'alexandre-guinefolleau', name: 'Alexandre Guinefolleau', role: 'Founder', since: '2018' },
      { id: 'frederic-cadet', name: 'Frédéric Cadet', role: 'Founder', since: '2018' },
      { id: 'emmanuelle-sanchez', name: 'Emmanuelle Sanchez', role: 'Founder', since: '2018' },
    ],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  nordleaf: {
    id: 'nordleaf',
    type: 'startup',
    name: 'Nordleaf',
    description:
      'Energy efficiency analytics and automated building operations software for commercial property owners in the Nordics.',
    matchScore: 76,
    matchConfidence: 0.45,
    matchSignals: [
      {
        signal: 'sector',
        text: 'ClimateTech and PropTech B2B software aligned with Nordic decarbonization mandates.',
        sources: [CALA_SOURCE],
      },
      {
        signal: 'region',
        text: 'Headquartered in Helsinki with early commercial building deployments.',
        sources: [CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Sectors (AI-tagged)',
        value: 'ClimateTech, PropTech',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Stages (AI-tagged)',
        value: 'Pre-seed',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Headquarters',
        value: 'Helsinki, Finland',
        sources: [CALA_SOURCE],
      },
    ],
    rounds: [
      {
        amount: '€750K',
        date: '2025',
        leads: ['Arctic Seed'],
        investors: ['Arctic Seed'],
        sources: [CALA_SOURCE],
      },
    ],
    portfolio: [],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  spendesk: {
    id: 'spendesk',
    type: 'startup',
    name: 'Spendesk',
    description:
      'Spend management and procurement platform combining corporate cards, invoice workflows, and expense automation for finance teams.',
    matchScore: 81,
    matchConfidence: 0.85,
    matchSignals: [
      {
        signal: 'sector',
        text: 'European B2B fintech and SaaS spend management category leader (AI-tagged).',
        sources: [CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Sectors (AI-tagged)',
        value: 'Fintech, B2B SaaS',
        sources: [CALA_SOURCE],
      },
      {
        label: 'Headquarters',
        value: 'Paris, France',
        sources: [CALA_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'lucile-cornet': {
    id: 'lucile-cornet',
    type: 'investor',
    name: 'Lucile Cornet',
    description: 'Partner at Eight Roads Ventures focusing on European enterprise software and vertical SaaS.',
    matchScore: 80,
    matchConfidence: 0.78,
    matchSignals: [
      {
        signal: 'closeness',
        text: 'Led Eight Roads Ventures Series A investment in Amenitiz.',
        sources: [PRESS_SERIES_A_SOURCE, EIGHT_ROADS_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Role',
        value: 'Partner at Eight Roads Ventures',
        sources: [EIGHT_ROADS_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'mike-chalfen': {
    id: 'mike-chalfen',
    type: 'investor',
    name: 'Mike Chalfen',
    description: 'Founder and Partner at Chalfen Ventures, investing in early-stage European software companies.',
    matchScore: 78,
    matchConfidence: 0.44,
    matchSignals: [
      {
        signal: 'closeness',
        text: 'Co-led Amenitiz Series A through Chalfen Ventures.',
        sources: [CHALFEN_SOURCE, PRESS_SERIES_A_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Role',
        value: 'Founder & Partner at Chalfen Ventures',
        sources: [CHALFEN_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'louis-coppey': {
    id: 'louis-coppey',
    type: 'investor',
    name: 'Louis Coppey',
    description: 'Partner at Point Nine focusing on B2B SaaS and software infrastructure.',
    matchScore: 79,
    matchConfidence: 0.8,
    matchSignals: [
      {
        signal: 'closeness',
        text: 'Led Point Nine Seed investment in Amenitiz.',
        sources: [POINT_NINE_SOURCE, CALA_SOURCE],
      },
    ],
    facts: [
      {
        label: 'Role',
        value: 'Partner at Point Nine',
        sources: [POINT_NINE_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'alexandre-guinefolleau': {
    id: 'alexandre-guinefolleau',
    type: 'startup',
    name: 'Alexandre Guinefolleau',
    description: 'Co-founder and CEO of Amenitiz.',
    matchScore: 74,
    matchConfidence: 0.82,
    matchSignals: [],
    facts: [
      {
        label: 'Role',
        value: 'Co-founder & CEO at Amenitiz',
        sources: [AMENITIZ_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'frederic-cadet': {
    id: 'frederic-cadet',
    type: 'startup',
    name: 'Frédéric Cadet',
    description: 'Co-founder and CTO of Amenitiz.',
    matchScore: 74,
    matchConfidence: 0.82,
    matchSignals: [],
    facts: [
      {
        label: 'Role',
        value: 'Co-founder & CTO at Amenitiz',
        sources: [AMENITIZ_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },

  'emmanuelle-sanchez': {
    id: 'emmanuelle-sanchez',
    type: 'startup',
    name: 'Emmanuelle Sanchez',
    description: 'Co-founder and CRO of Amenitiz.',
    matchScore: 74,
    matchConfidence: 0.82,
    matchSignals: [],
    facts: [
      {
        label: 'Role',
        value: 'Co-founder & CRO at Amenitiz',
        sources: [AMENITIZ_SOURCE],
      },
    ],
    rounds: [],
    portfolio: [{ id: 'amenitiz', name: 'Amenitiz' }],
    people: [],
    loaded_at: '2026-11-14T18:30:00Z',
  },
};

const MOCK_ALIASES: Record<string, string> = {
  'eight-roads': 'eight-roads-ventures',
  eight_roads: 'eight-roads-ventures',
  eight_roads_ventures: 'eight-roads-ventures',
  'inv-1': 'eight-roads-ventures',
  'investor-1': 'eight-roads-ventures',
  '1': 'eight-roads-ventures',
  chalfen: 'chalfen-ventures',
  chalfen_ventures: 'chalfen-ventures',
  'inv-2': 'chalfen-ventures',
  'investor-2': 'chalfen-ventures',
  '2': 'chalfen-ventures',
  'northzone-ventures': 'northzone',
  'inv-3': 'northzone',
  'investor-3': 'northzone',
  '3': 'northzone',
  'point-nine-capital': 'point-nine',
  point_nine: 'point-nine',
  point9: 'point-nine',
  'inv-4': 'point-nine',
  'investor-4': 'point-nine',
  '4': 'point-nine',
  'db95edaa-058f-494d-a4f4-5f56bf81afd9': 'amenitiz',
  'startup-1': 'amenitiz',
  'company-1': 'amenitiz',
  'startup-2': 'nordleaf',
  'company-2': 'nordleaf',
};

function findMockEntity(id: string, mode: EntityMode): EntityDetail | null {
  const key = id.trim().toLowerCase();
  if (!key || key === 'missing' || key === 'empty' || key === 'not-found') return null;

  const resolvedKey = MOCK_ALIASES[key] ?? key;
  const seed = MOCK_RECORDS[resolvedKey];
  if (!seed) return null;

  const expectedType = mode === 'raising' ? 'investor' : 'startup';
  const showMatch = seed.type === expectedType && seed.matchSignals.length > 0;

  return {
    id: seed.id,
    type: seed.type,
    name: seed.name,
    description: seed.description,
    ...(showMatch
      ? {
          score: seed.matchScore,
          confidence: seed.matchConfidence,
          why_match: seed.matchSignals,
        }
      : { why_match: [] }),
    facts: seed.facts,
    rounds: seed.rounds,
    portfolio: seed.portfolio,
    people: seed.people,
    loaded_at: seed.loaded_at,
  };
}

function sanitizeSources(raw: unknown): Source[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (s): s is Source =>
      Boolean(s && typeof s === 'object' && typeof (s as Source).name === 'string' && typeof (s as Source).url === 'string'),
  );
}

function sanitizeStrings(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter((v): v is string => typeof v === 'string' && v.trim().length > 0);
}

function normalizeEntityDetail(raw: unknown): EntityDetail {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;

  const why_match: EntityMatchSignal[] = Array.isArray(obj.why_match)
    ? obj.why_match
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map((item) => ({
          signal: typeof item.signal === 'string' ? item.signal : 'signal',
          text: typeof item.text === 'string' ? item.text : '',
          sources: sanitizeSources(item.sources),
        }))
        .filter((item) => item.text.length > 0)
    : [];

  const facts: EntityFact[] = Array.isArray(obj.facts)
    ? obj.facts
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map((item) => ({
          label: typeof item.label === 'string' ? item.label : '',
          value:
            typeof item.value === 'string' || typeof item.value === 'number' ? item.value : '',
          sources: sanitizeSources(item.sources),
        }))
        .filter((item) => item.label.length > 0 && item.value !== '')
    : [];

  const rounds: EntityRound[] = Array.isArray(obj.rounds)
    ? obj.rounds
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map((item) => ({
          ...(typeof item.round_type === 'string' && item.round_type
            ? { round_type: item.round_type }
            : {}),
          ...(typeof item.amount === 'string' && item.amount ? { amount: item.amount } : {}),
          ...(typeof item.date === 'string' && item.date ? { date: item.date } : {}),
          leads: sanitizeStrings(item.leads),
          investors: sanitizeStrings(item.investors),
          sources: sanitizeSources(item.sources),
        }))
    : [];

  const portfolio: EntityPortfolioItem[] = Array.isArray(obj.portfolio)
    ? obj.portfolio
        .filter(
          (item): item is Record<string, unknown> =>
            Boolean(item && typeof item === 'object' && item.id != null && typeof item.name === 'string' && item.name),
        )
        .map((item) => ({ id: String(item.id), name: String(item.name) }))
    : [];

  const people: EntityPerson[] = Array.isArray(obj.people)
    ? obj.people
        .filter(
          (item): item is Record<string, unknown> =>
            Boolean(item && typeof item === 'object' && item.id != null && typeof item.name === 'string' && item.name),
        )
        .map((item) => ({
          id: String(item.id),
          name: String(item.name),
          role: typeof item.role === 'string' && item.role ? item.role : 'Member',
          ...(typeof item.since === 'string' && item.since ? { since: item.since } : {}),
        }))
    : [];

  return {
    id: String(obj.id ?? ''),
    type: obj.type === 'investor' ? 'investor' : 'startup',
    name: String(obj.name ?? ''),
    ...(typeof obj.description === 'string' && obj.description ? { description: obj.description } : {}),
    ...(typeof obj.score === 'number' ? { score: obj.score } : {}),
    ...(typeof obj.confidence === 'number' ? { confidence: obj.confidence } : {}),
    why_match,
    facts,
    rounds,
    portfolio,
    people,
    loaded_at: typeof obj.loaded_at === 'string' ? obj.loaded_at : '',
  };
}

export async function fetchEntityDetail(
  id: string,
  mode: EntityMode = 'raising',
  sessionId?: string | null,
): Promise<EntityDetailResult> {
  const cleanId = id.trim();
  if (!cleanId) return { detail: null, isSample: false };

  if (mockEnabled) {
    if (cleanId.toLowerCase() === 'error') {
      throw new ApiError('mock_error', 'Could not reach the backend. Check your connection and try again.', 503);
    }
    return { detail: findMockEntity(cleanId, mode), isSample: true };
  }

  const params = new URLSearchParams();
  params.set('mode', mode);
  if (sessionId) params.set('session_id', sessionId);
  const url = `${baseUrl}/api/entities/${encodeURIComponent(cleanId)}?${params.toString()}`;

  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS) : null;

  try {
    const response = await fetch(url, controller ? { signal: controller.signal } : undefined);
    const body: unknown = await response.json().catch(() => null);

    if (response.status === 404) {
      const payload = body as { error?: { code?: string; message?: string }; detail?: string } | null;
      const msg = payload?.error?.message ?? payload?.detail ?? 'Entity not found.';
      if (/session/i.test(msg)) {
        throw new ApiError('session_not_found', msg, 404);
      }
      return { detail: null, isSample: false };
    }

    if (!response.ok) {
      const payload = body as { error?: { code?: string; message?: string }; detail?: string } | null;
      throw new ApiError(
        payload?.error?.code ?? 'http_error',
        payload?.error?.message ?? payload?.detail ?? `Request failed with status ${response.status}.`,
        response.status,
      );
    }

    if (!body || typeof body !== 'object' || !('name' in body)) {
      throw new ApiError('invalid_response', 'Received an unexpected response from the server.', response.status);
    }

    return { detail: normalizeEntityDetail(body), isSample: false };
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;

    const fallback = findMockEntity(cleanId, mode);
    if (fallback) {
      return { detail: fallback, isSample: true };
    }

    throw new ApiError(
      'network_error',
      'Could not reach the backend. Check your connection and try again.',
      0,
    );
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function getEntityDetail(
  id: string,
  mode: EntityMode = 'raising',
  sessionId?: string | null,
): Promise<EntityDetail | null> {
  const { detail } = await fetchEntityDetail(id, mode, sessionId);
  return detail;
}
