// ─── Microsoft To Do Types ───────────────────────────────────────

export interface TaskList {
  id: string;
  name: string;
  list_type: 'smart' | 'custom' | 'default';
  icon?: string;
  task_count: number;
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  completed: boolean;
  important: boolean;
  my_day: boolean;
  due_date?: string;
  reminder?: string;
  recurrence?: string;  // daily, weekdays, weekly, monthly, yearly
  note?: string;
  list_id?: string;
  assigned_to?: string;
  created_by?: string;
  created_at?: string;
  completed_at?: string;
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
