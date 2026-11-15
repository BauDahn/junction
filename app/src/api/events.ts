export type CalaEvent = {
  id: string; name: string; slogan: string; date: string; city: string; venue: string; imageUrl: string;
  participantData: 'cala' | 'none';
};

const eventImages: Record<string, string> = {
  'slush-2026': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1200&q=85',
  'arctic15-helsinki': 'https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=1200&q=85',
  'techarena-stockholm': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=85',
  'sifted-summit-london': 'https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=1200&q=85',
  'bits-pretzels-munich': 'https://images.unsplash.com/photo-1521737711867-e3b97375f902?auto=format&fit=crop&w=1200&q=85',
  'south-summit-madrid': 'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&q=85',
};
const makeEvent = (id: string, name: string, slogan: string, date: string, city: string, venue: string): CalaEvent => ({
  id, name, slogan, date, city, venue, imageUrl: eventImages[id], participantData: id === 'slush-2026' ? 'cala' : 'none',
});
// The real events endpoint (PR #114 contract) does not exist yet.
export const EVENTS_CATALOG: CalaEvent[] = [
  makeEvent('slush-2026', 'Slush 2026', 'Founder-focused venture gathering in the Nordics', 'Nov 18–19, 2026', 'Helsinki', 'Messukeskus Helsinki'),
  makeEvent('arctic15-helsinki', 'Arctic15 Helsinki', 'Deal-making summit built around pre-booked 1-on-1s', 'Jun 4–5, 2026', 'Helsinki', 'Cable Factory'),
  makeEvent('techarena-stockholm', 'Techarena Stockholm', 'Nordic growth & climate capital forum', 'Feb 19–20, 2026', 'Stockholm', 'Strawberry Arena'),
  makeEvent('sifted-summit-london', 'Sifted Summit', 'European B2B SaaS & seed-to-scaleup briefing', 'Oct 7–8, 2026', 'London', 'Magazine London'),
  makeEvent('bits-pretzels-munich', 'Bits & Pretzels', 'Founders & B2B software leads table sessions', 'Sep 28–30, 2026', 'Munich', 'ICM Munich'),
  makeEvent('south-summit-madrid', 'South Summit Madrid', 'Southern European hospitality, fintech & SaaS arena', 'Jun 3–5, 2026', 'Madrid', 'La Nave'),
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
