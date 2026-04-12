import React from 'react';
import type { ActiveView } from '../types';
import { COLORS } from '../types';

interface Props {
  view: ActiveView;
}

const MESSAGES: Record<string, { title: string; subtitle: string }> = {
  'my-day': { title: 'Concentra tu día', subtitle: 'Agrega tareas que quieras completar hoy.' },
  'important': { title: 'Sin tareas importantes', subtitle: 'Las tareas marcadas con estrella aparecerán aquí.' },
  'planned': { title: 'Sin tareas planeadas', subtitle: 'Las tareas con fecha de vencimiento aparecerán aquí.' },
  'assigned': { title: 'Sin tareas asignadas', subtitle: 'Las tareas asignadas a ti aparecerán aquí.' },
  'flagged': { title: 'Sin correos marcados', subtitle: 'Los correos que marques aparecerán aquí.' },
  'tasks': { title: 'Sin tareas pendientes', subtitle: 'Agrega una tarea para comenzar.' },
};

export function EmptyState({ view }: Props) {
  const msg = MESSAGES[view] || { title: 'Sin tareas', subtitle: 'Esta lista está vacía.' };

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 12,
      padding: 40, textAlign: 'center',
      fontFamily: "'Segoe UI', system-ui, sans-serif",
    }}>
      {/* Simple illustration */}
      <svg width={64} height={64} viewBox="0 0 24 24" fill="none" stroke={COLORS.border} strokeWidth={1}>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M8 10l2 2 4-4" stroke={COLORS.muted} strokeWidth={1.5} />
        <line x1="8" y1="16" x2="16" y2="16" stroke={COLORS.border} />
      </svg>
      <div style={{ fontSize: 16, fontWeight: 600, color: COLORS.text }}>{msg.title}</div>
      <div style={{ fontSize: 13, color: COLORS.secondary, maxWidth: 300 }}>{msg.subtitle}</div>
    </div>
  );
}
