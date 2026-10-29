// ─── Microsoft To Do Types ───────────────────────────────────────

export interface TaskList {
  id: string;
  name: string;
  list_type: 'smart' | 'custom' | 'default';
  icon?: string;
  task_count: number;
  color?: string;
  sort_by?: Orden;
  group_id?: string | null;
  position?: number;
  role?: 'owner' | 'member';
  miembros?: number;
}

/** Grupo de listas de la barra lateral (cada persona arma los suyos). */
export interface TaskGroup {
  id: string;
  name: string;
  position: number;
}

/** Cómo se ordenan las tareas de una lista: manual es el orden en que se arrastraron. */
export type Orden = 'manual' | 'date' | 'important' | 'alpha' | 'created';

export interface Task {
  id: string;
  title: string;
  description?: string;
  completed: boolean;
  important: boolean;
  my_day: boolean;
  due_date?: string | null;
  reminder?: string | null;
  recurrence?: string | null;  // daily, weekdays, weekly, monthly, yearly o cada:N:unidad[:días] (repeticion.ts)
  note?: string;
  list_id?: string;
  position?: number;
  assigned_to?: string;
  created_by?: string;
  created_at?: string;
  completed_at?: string;
  // Listas inteligentes: lista de origen, personas asignadas y correo marcado del que salió.
  list_name?: string;
  asignados?: string[];
  correo?: CorreoTarea | null;
  // Pasos (hechos y en total) y archivos adjuntos, para mostrarlos en la fila (F3).
  pasos?: number;
  pasos_hechos?: number;
  adjuntos?: number;
  // Categorías de color (como en Outlook, F5): nombres de categorias.ts.
  labels?: string[];
}

/** Persona de una lista compartida (la propietaria o un miembro). */
export interface MiembroLista {
  email: string;
  nombre: string;
  role: 'owner' | 'member';
  added_by: string;
  joined_at?: string | null;
}

/** Un evento del registro de actividad de una lista o de una tarea. */
export interface EventoActividad {
  user_email: string;
  nombre: string;
  action: string;
  details: string;
  created_at: string;
}

/** Archivo adjunto de una tarea. */
export interface AdjuntoTarea {
  id: string;
  card_id: string;
  nombre: string;
  content_type: string;
  tamano: number;
  subido_por: string;
  creado_en: string;
}

export interface CorreoTarea {
  carpeta: string;
  uid: number;
  asunto?: string;
  remitente?: string;
}

export type SmartView = 'my-day' | 'important' | 'planned' | 'assigned' | 'flagged' | 'tasks' | 'seguimiento';
export type ActiveView = SmartView | string; // string = list UUID

export interface SmartListDef {
  id: SmartView;
  name: string;
  icon: string;
  color?: string;
}

export const SMART_LISTS: SmartListDef[] = [
  { id: 'my-day', name: 'Mi día', icon: 'sun', color: '#0078d4' },
  { id: 'important', name: 'Importante', icon: 'star' },
  { id: 'planned', name: 'Planeado', icon: 'calendar' },
  { id: 'assigned', name: 'Asignado a mí', icon: 'person' },
  { id: 'flagged', name: 'Correo electrónico marcado', icon: 'flag' },
  { id: 'tasks', name: 'Tareas', icon: 'home' },
  { id: 'seguimiento', name: 'Seguimiento de tareas asignadas', icon: 'flag', color: '#d13438' },
];

export const COLORS = {
  primary: '#0078d4',
  text: '#323130',
  secondary: '#605e5c',
  muted: '#a19f9d',
  border: '#edebe9',
  hoverBg: '#faf9f8',
  activeBg: '#eff6fc',
  sidebarBg: '#f3f2f1',
} as const;

// Legacy constants (backward compatibility while migrating)
export const PRIORITY_COLORS: Record<string, string> = {
  urgent: '#d13438', high: '#ff8c00', medium: '#ffb900', low: '#107c10',
};
export const PRIORITY_LABELS: Record<string, string> = {
  urgent: 'Urgente', high: 'Alta', medium: 'Media', low: 'Baja',
};
export const BOARD_COLORS = ['#0078d4','#d13438','#107c10','#ff8c00','#5c2d91','#008272','#ca5010','#69797e'];
