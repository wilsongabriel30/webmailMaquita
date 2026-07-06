/* Tipos compartidos del módulo de contactos */

export interface Contact {
  id: number;
  owner: string;
  first_name: string;
  last_name: string;
  display_name: string;
  nickname: string;
  email: string;
  email2: string;
  email3: string;
  phone: string;
  phone_mobile: string;
  phone_work: string;
  phone_home: string;
  fax: string;
  organization: string;
  company: string;
  job_title: string;
  department: string;
  address_street: string;
  address_city: string;
  address_state: string;
  address_zip: string;
  address_country: string;
  birthday: string | null;
  website: string;
  im_address: string;
  photo_url: string;
  notes: string;
  is_favorite: boolean;
  deleted_at: string | null;
  source: string;
  last_contacted_at: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
  categories: ContactCategory[];
}

export interface ContactCategory {
  id: number;
  name: string;
  color: string;
  contact_count?: number;
}

export interface ContactList {
  id: number;
  name: string;
  description: string;
  member_count: number;
}

export interface ContactsResponse {
  contacts: Contact[];
  total: number;
  page: number;
  per_page: number;
}

export type SidebarFilter = 'all' | 'favorites' | 'deleted' | `category:${number}` | `list:${number}`;

/* Colores de avatar */
export const AVATAR_COLORS = [
  '#0078d4', '#498205', '#8764b8', '#ca5010', '#038387',
  '#da3b01', '#8e562e', '#647c64', '#7160e8', '#c239b3',
  '#e3008c', '#9c0027', '#004e8c', '#4f6bed', '#881798',
];

/* Colores de categoría predefinidos (estilo Outlook) */
export const CATEGORY_COLORS = [
  { name: 'Rojo', value: '#d13438' },
  { name: 'Naranja', value: '#ca5010' },
  { name: 'Amarillo', value: '#eaa300' },
  { name: 'Verde', value: '#498205' },
  { name: 'Azul', value: '#0078d4' },
  { name: 'Morado', value: '#881798' },
  { name: 'Rosa', value: '#e3008c' },
  { name: 'Gris', value: '#69797e' },
];

/* Helpers */
export function getInitials(name: string): string {
  if (!name || !name.trim()) return '?';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  // Primer nombre + primer apellido. En nombres completos (2 nombres + 2
  // apellidos) el primer apellido esta a la mitad; en "Nombre Apellido" es el 2do.
  const nombre = parts[0];
  const apellido = parts[Math.floor(parts.length / 2)];
  return (nombre[0] + apellido[0]).toUpperCase();
}

export function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('es-EC', { day: '2-digit', month: 'short', year: 'numeric' });
}
