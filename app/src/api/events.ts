export type EventInvestorMatch = {
  id: string; name: string; one_liner: string; score: number; why_match: string; tags: string[];
  stage_focus: string; notable_round: string; partner_name?: string;
};
export type CalaEvent = {
  id: string; name: string; slogan: string; date: string; city: string; venue: string; imageUrl: string;
  attendingInvestorIds: string[]; scheduleWindows: string[]; investors: EventInvestorMatch[];
};

const investorRecords: Record<string, EventInvestorMatch> = {
  'eight-roads-ventures': {
    id: 'eight-roads-ventures', name: 'Eight Roads Ventures', one_liner: 'Global venture firm backing European software, fintech, and healthcare companies.', score: 92,
    why_match: 'Cala records European B2B SaaS activity and Series A and Series B investing, including Amenitiz.', tags: ['B2B SaaS', 'Fintech', 'Enterprise software'], stage_focus: 'Series A, Series B', notable_round: 'Amenitiz · $30M Series A; €38.9M Series B', partner_name: 'Lucile Cornet',
  },
  'chalfen-ventures': {
    id: 'chalfen-ventures', name: 'Chalfen Ventures', one_liner: 'Solo-GP fund partnering with European software founders.', score: 87,
    why_match: 'Cala records Seed and Series A focus in vertical SaaS and workflow software, including Amenitiz.', tags: ['B2B SaaS', 'Vertical software'], stage_focus: 'Seed, Series A', notable_round: 'Amenitiz · $30M Series A; €38.9M Series B', partner_name: 'Mike Chalfen',
  },
  northzone: {
    id: 'northzone', name: 'Northzone', one_liner: 'Multi-stage European venture firm with a strong Nordic presence.', score: 81,
    why_match: 'Cala records ClimateTech, fintech, and B2B SaaS investing with Nordic coverage, including Spendesk.', tags: ['ClimateTech', 'Fintech', 'B2B SaaS'], stage_focus: 'Seed, Series A, Series B', notable_round: 'Spendesk · portfolio company; 11 rounds in the last 24 months',
  },
  'point-nine': {
    id: 'point-nine', name: 'Point Nine', one_liner: 'European early-stage investor in software and SaaS businesses.', score: 76,
    why_match: 'Cala records Seed and Series A investing in European B2B software, including Amenitiz.', tags: ['B2B SaaS', 'Software'], stage_focus: 'Seed, Series A', notable_round: 'Amenitiz · $30M Series A; €38.9M Series B', partner_name: 'Louis Coppey',
  },
  'lifeline-ventures': {
    id: 'lifeline-ventures', name: 'Lifeline Ventures', one_liner: 'Finnish early-stage venture firm investing across the Nordics.', score: 64,
    why_match: 'Cala records Nordic early-stage activity and a Nordleaf €750K / €1.2M financing record.', tags: ['Nordics', 'Early stage', 'ClimateTech'], stage_focus: 'Pre-seed, Seed', notable_round: 'Nordleaf · €750K / €1.2M',
  },
};
const eventImages: Record<string, string> = {
  'slush-2026': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1200&q=85',
  'arctic15-helsinki': 'https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=1200&q=85',
  'techarena-stockholm': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=85',
  'sifted-summit-london': 'https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=1200&q=85',
  'bits-pretzels-munich': 'https://images.unsplash.com/photo-1521737711867-e3b97375f902?auto=format&fit=crop&w=1200&q=85',
  'south-summit-madrid': 'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&q=85',
};
const makeEvent = (id: string, name: string, slogan: string, date: string, city: string, venue: string, ids: string[], schedule: string[]): CalaEvent => ({
  id, name, slogan, date, city, venue, imageUrl: eventImages[id], attendingInvestorIds: ids, scheduleWindows: schedule,
  investors: ids.map((investorId) => investorRecords[investorId]).filter(Boolean),
});
export const EVENTS_CATALOG: CalaEvent[] = [
  makeEvent('slush-2026', 'Slush 2026', 'Founder-focused venture gathering in the Nordics', 'Nov 18–19, 2026', 'Helsinki', 'Messukeskus Helsinki', ['eight-roads-ventures', 'northzone', 'lifeline-ventures', 'chalfen-ventures', 'point-nine'], ['Day 1 · 10:00–12:00 Founder office hours']),
  makeEvent('arctic15-helsinki', 'Arctic15 Helsinki', 'Deal-making summit built around pre-booked 1-on-1s', 'Jun 4–5, 2026', 'Helsinki', 'Cable Factory', ['lifeline-ventures', 'northzone', 'point-nine'], ['Day 1 · 10:00–12:00 Meeting sessions']),
  makeEvent('techarena-stockholm', 'Techarena Stockholm', 'Nordic growth & climate capital forum', 'Feb 19–20, 2026', 'Stockholm', 'Strawberry Arena', ['northzone', 'eight-roads-ventures', 'lifeline-ventures'], ['Day 1 · 10:00–12:00 Investor meetings']),
  makeEvent('sifted-summit-london', 'Sifted Summit', 'European B2B SaaS & seed-to-scaleup briefing', 'Oct 7–8, 2026', 'London', 'Magazine London', ['eight-roads-ventures', 'chalfen-ventures', 'point-nine'], ['Day 1 · 10:00–12:00 Founder meetings']),
  makeEvent('bits-pretzels-munich', 'Bits & Pretzels', 'Founders & B2B software leads table sessions', 'Sep 28–30, 2026', 'Munich', 'ICM Munich', ['point-nine', 'eight-roads-ventures', 'chalfen-ventures'], ['Day 1 · 10:00–12:00 Table sessions']),
  makeEvent('south-summit-madrid', 'South Summit Madrid', 'Southern European hospitality, fintech & SaaS arena', 'Jun 3–5, 2026', 'Madrid', 'La Nave', ['eight-roads-ventures', 'chalfen-ventures', 'point-nine'], ['Day 1 · 10:00–12:00 Investor meetings']),
];
export function getEventById(id: string): CalaEvent | undefined { return EVENTS_CATALOG.find((event) => event.id === id); }
export function findEventByQuery(query: string): CalaEvent | undefined {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return undefined;
  const primaryTokens: Record<string, string[]> = {
    'slush-2026': ['slush'],
    'arctic15-helsinki': ['arctic15'],
    'techarena-stockholm': ['techarena'],
    'sifted-summit-london': ['sifted'],
    'bits-pretzels-munich': ['bits', 'pretzels'],
    'south-summit-madrid': ['south summit'],
  };
  return EVENTS_CATALOG.find((event) => {
    const searchableTerms = [event.id, event.name, event.city, ...(primaryTokens[event.id] ?? [])];
    return searchableTerms.some((term) => normalized.includes(term.toLowerCase()));
  });
}
export function buildOutreachBrief(event: CalaEvent, template: 'cold' | 'followup', startupName = 'Nordleaf', sector = 'ClimateTech', stage = 'Seed', roundSize = '€2.0M–€3.0M', senderName = 'Alex Lindqvist'): string {
  const investor = event.investors[0];
  const greeting = investor?.partner_name ? `Hello ${investor.partner_name},` : `Hello ${investor?.name ?? 'there'},`;
  const context = `${startupName} is a ${stage} ${sector} company preparing a ${roundSize} fundraise.`;
  const evidence = investor?.id === 'northzone'
    ? 'Cala records Northzone activity across Nordic ClimateTech and 11 rounds in the last 24 months, alongside portfolio company Spendesk.'
    : investor?.notable_round
      ? `Cala records your participation in ${investor.notable_round}.`
      : `Cala identifies a strong fit with your ${investor?.stage_focus ?? 'investment'} focus.`;
  if (template === 'followup') return `${greeting}\n\nThank you for the conversation at ${event.name}. ${context} I would welcome a follow-up to share our materials and explore fit. ${evidence}\n\nWould you be available for a short meeting?\n\nBest,\n${senderName}`;
  return `${greeting}\n\nI will be at ${event.name} in ${event.city}. ${context} We are building in ${sector} and are preparing to meet investors whose verified focus aligns with our plans. ${evidence}\n\nWould you be open to a short conversation during the event?\n\nBest,\n${senderName}`;
}
