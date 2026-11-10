import { getFolderDisplayName } from '../../folders';
import { ETIQUETA_ACCION, ETIQUETA_CAMPO, ETIQUETA_OPERADOR, type AccionRegla, type CondicionRegla, type Regla } from './tipos';

/* Texto de una regla para el listado: «Si De contiene "x" y Asunto contiene "y" → Mover a Z; detener». */

export function textoCondicion(c: CondicionRegla): string {
  const campo = c.field === 'header' ? `Encabezado ${c.header || ''}` : ETIQUETA_CAMPO[c.field];
  const op = ETIQUETA_OPERADOR[c.operator];
  if (c.operator === 'exists' || c.operator === 'not_exists') return `${campo} ${op}`;
  if (c.field === 'size') return `${campo} ${op.replace(' (KB)', '')} ${c.value} KB`;
  return `${campo} ${op} «${c.value}»`;
}

export function textoAccion(a: AccionRegla): string {
  const base = ETIQUETA_ACCION[a.type];
  if (a.type === 'move' || a.type === 'copy') return `${base} ${getFolderDisplayName(a.value || '')}`;
  if (a.type === 'forward' || a.type === 'forward_copy') return `${base} ${a.value || ''}`;
  return base;
}

export function resumenRegla(r: Regla): { condiciones: string; acciones: string } {
  const nexo = r.match === 'anyof' ? ' o ' : ' y ';
  const condiciones = 'Si ' + r.conditions.map(textoCondicion).join(nexo);
  const acciones = r.actions.map(textoAccion).join(', ') + (r.stop ? ' · detener las demás reglas' : '');
  return { condiciones, acciones };
}
