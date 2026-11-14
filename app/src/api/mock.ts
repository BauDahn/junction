import type { Card, Profile, Recommendations } from './index';
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
