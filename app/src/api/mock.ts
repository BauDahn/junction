import type { Card, Message, Profile, Recommendations, SendTextResponse } from './index';
export const mockProfile: Profile = {
  startup_name: 'Nordleaf',
  one_liner: 'Herramientas de eficiencia energética para edificios',
  sector: 'ClimateTech',
  stage: 'Pre-seed',
  location: 'Helsinki',
  competitors: ['GreenBuild'],
  target_customers: 'Propietarios de edificios',
  facts: [],
  updated_at: new Date().toISOString(),
};
const card = (type: Card['type'], title: string, subtitle: string, reason: string): Card => ({
  type,
  title,
  subtitle,
  reason,
  sources: [{ name: 'Cala · ejemplo', url: 'https://cala.ai' }],
});
export const mockRecommendations: Recommendations = {
  status: 'ready',
  updated_at: new Date().toISOString(),
  investors: [
    card(
      'investor',
      'Polar Ventures',
      'Climate · Finlandia',
      'Invierte en soluciones de descarbonización.',
    ),
    card(
      'investor',
      'Northstar Capital',
      'Pre-seed · Europa',
      'Apoya equipos early-stage nórdicos.',
    ),
    card('investor', 'Arctic Seed', 'Impacto · Helsinki', 'Busca startups con impacto medible.'),
  ],
  competitors: [
    card(
      'competitor',
      'GreenBuild',
      'Software · Suecia',
      'Solución cercana para eficiencia de edificios.',
    ),
    card(
      'competitor',
      'Wattwise',
      'ClimateTech · Dinamarca',
      'Optimización de consumo energético.',
    ),
    card('competitor', 'BuildingOS', 'PropTech · Europa', 'Plataforma de datos para edificios.'),
  ],
  prospects: [
    card(
      'prospect',
      'Helsinki Housing',
      'Gestión inmobiliaria',
      'Posible cliente con cartera de edificios.',
    ),
    card(
      'prospect',
      'Nordic Estates',
      'Propietario · Finlandia',
      'Perfil compatible con el producto.',
    ),
    card(
      'prospect',
      'City of Espoo',
      'Sector público',
      'Iniciativas locales de eficiencia energética.',
    ),
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
    text: 'Por lo que me cuentas, estas referencias pueden encajar con tu startup.',
    created_at: now,
    sources: [{ name: 'Cala · ejemplo', url: 'https://cala.ai' }],
    cards: [mockRecommendations.investors[0], mockRecommendations.competitors[0]],
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
    'Busco inversores para mi startup de energía en Helsinki.',
    'Busco inversores para mi startup de energía en Helsinki.',
  );
}
