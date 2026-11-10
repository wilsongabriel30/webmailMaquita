/* Tipos y etiquetas de las reglas de correo (Sieve) del webmail.
   Espejo de backend/app/sieve/modelos.py. Equipo de Tecnología Maquita. */

export type CampoCondicion = 'from' | 'to' | 'cc' | 'recipients' | 'subject' | 'body' | 'header' | 'size' | 'list';
export type OperadorCondicion =
  | 'contains' | 'is' | 'matches' | 'regex'
  | 'not_contains' | 'not_is' | 'not_matches' | 'not_regex'
  | 'exists' | 'not_exists' | 'over' | 'under';
export type TipoAccion = 'move' | 'copy' | 'flag' | 'read' | 'delete' | 'forward' | 'forward_copy';

export interface CondicionRegla {
  field: CampoCondicion;
  operator: OperadorCondicion;
  value: string;
  /** Nombre del encabezado cuando field === 'header'. */
  header?: string | null;
}

export interface AccionRegla {
  type: TipoAccion;
  value?: string | null;
}

export interface Regla {
  index?: number;
  name: string;
  match: 'allof' | 'anyof';
  conditions: CondicionRegla[];
  actions: AccionRegla[];
  stop: boolean;
  enabled: boolean;
  /** Forma antigua (primera condición y primera acción): la manda el servidor por compatibilidad. */
  condition?: CondicionRegla;
  action?: AccionRegla;
}

export const ETIQUETA_CAMPO: Record<CampoCondicion, string> = {
  from: 'De (remitente)',
  to: 'Para',
  cc: 'Cc',
  recipients: 'Para o Cc',
  subject: 'Asunto',
  body: 'Cuerpo del mensaje',
  header: 'Encabezado…',
  size: 'Tamaño',
  list: 'Lista de correo (List-Id)',
};

export const ETIQUETA_OPERADOR: Record<OperadorCondicion, string> = {
  contains: 'contiene',
  is: 'es exactamente',
  matches: 'coincide con el patrón',
  regex: 'cumple la expresión regular',
  not_contains: 'no contiene',
  not_is: 'no es',
  not_matches: 'no coincide con el patrón',
  not_regex: 'no cumple la expresión regular',
  exists: 'está presente',
  not_exists: 'no está presente',
  over: 'es mayor que (KB)',
  under: 'es menor que (KB)',
};

export const ETIQUETA_ACCION: Record<TipoAccion, string> = {
  move: 'Mover a la carpeta',
  copy: 'Copiar a la carpeta',
  flag: 'Marcar con bandera',
  read: 'Marcar como leído',
  delete: 'Eliminar',
  forward: 'Reenviar a',
  forward_copy: 'Reenviar una copia a',
};

const OPERADORES_TEXTO: OperadorCondicion[] = ['contains', 'not_contains', 'is', 'not_is', 'matches', 'not_matches', 'regex', 'not_regex', 'exists', 'not_exists'];

/** Operadores válidos para cada campo (el servidor rechaza los demás). */
export function operadoresDe(campo: CampoCondicion): OperadorCondicion[] {
  if (campo === 'size') return ['over', 'under'];
  if (campo === 'body') return ['contains', 'not_contains', 'regex', 'not_regex'];
  return OPERADORES_TEXTO;
}

/** Acciones que llevan carpeta. */
export const ACCIONES_CON_CARPETA: TipoAccion[] = ['move', 'copy'];
/** Acciones que llevan dirección de correo. */
export const ACCIONES_CON_CORREO: TipoAccion[] = ['forward', 'forward_copy'];

export function condicionVacia(): CondicionRegla {
  return { field: 'from', operator: 'contains', value: '' };
}

export function accionVacia(): AccionRegla {
  return { type: 'move', value: '' };
}

export function reglaVacia(): Regla {
  return { name: '', match: 'allof', conditions: [condicionVacia()], actions: [accionVacia()], stop: true, enabled: true };
}

/** La regla tal como viene del servidor (puede traer solo condition/action) en la forma de listas. */
export function normalizarRegla(r: Partial<Regla>): Regla {
  const conditions = r.conditions?.length ? r.conditions : r.condition ? [r.condition] : [condicionVacia()];
  const actions = r.actions?.length ? r.actions : r.action ? [r.action] : [accionVacia()];
  return {
    index: r.index,
    name: r.name || '',
    match: r.match === 'anyof' ? 'anyof' : 'allof',
    conditions,
    actions,
    stop: r.stop ?? actions.some(a => a.type !== 'flag' && a.type !== 'read'),
    enabled: r.enabled ?? true,
  };
}

/** Motivo por el que la regla no se puede guardar, o '' si está completa. */
export function faltaEnRegla(r: Regla): string {
  if (!r.name.trim()) return 'Ponga un nombre a la regla';
  if (!r.conditions.length) return 'Añada al menos una condición';
  for (const c of r.conditions) {
    if (c.field === 'header' && !(c.header || '').trim()) return 'Indique el nombre del encabezado';
    if (c.field === 'size' && !/^\d+$/.test(c.value.trim())) return 'El tamaño debe ser un número de KB';
    if (!['exists', 'not_exists'].includes(c.operator) && c.field !== 'size' && !c.value.trim()) return 'Falta el valor de una condición';
  }
  if (!r.actions.length) return 'Añada al menos una acción';
  for (const a of r.actions) {
    if (ACCIONES_CON_CARPETA.includes(a.type) && !(a.value || '').trim()) return 'Elija la carpeta de destino';
    if (ACCIONES_CON_CORREO.includes(a.type) && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test((a.value || '').trim())) return 'Escriba una dirección de correo válida para el reenvío';
  }
  return '';
}

/** Lo que se manda al servidor (sin index ni campos antiguos). */
export function cuerpoParaGuardar(r: Regla) {
  return {
    name: r.name.trim(),
    match: r.match,
    conditions: r.conditions.map(c => ({
      field: c.field,
      operator: c.operator,
      value: c.field === 'size' ? c.value.trim() : c.value,
      header: c.field === 'header' ? (c.header || '').trim() : null,
    })),
    actions: r.actions.map(a => ({ type: a.type, value: a.value ?? null })),
    stop: r.stop,
    enabled: r.enabled,
  };
}
