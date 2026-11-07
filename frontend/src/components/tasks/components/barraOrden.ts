// Orden de la barra lateral de Tareas: grupos (con sus listas) y listas sueltas, en un solo orden.
// Arrastrar cambia esta estructura y se guarda entera con PUT /tasks/sidebar/orden.
import type { TaskGroup, TaskList } from '../types';

export type Elemento = { tipo: 'grupo'; id: string; listas: string[] } | { tipo: 'lista'; id: string };

export type Destino =
  | { tipo: 'antesDeLista'; id: string }
  | { tipo: 'enGrupo'; id: string }
  | { tipo: 'antesDeGrupo'; id: string }
  | { tipo: 'alFinal' };

/** Listas propias o compartidas que van en la barra («Tareas» tiene su lugar fijo arriba). */
export function listasDeBarra(listas: TaskList[]): TaskList[] {
  return listas.filter(l => l.list_type === 'custom');
}

export function armarBarra(listas: TaskList[], grupos: TaskGroup[]): Elemento[] {
  const propias = listasDeBarra(listas);
  const idsGrupos = new Set(grupos.map(g => g.id));
  const pos = (l: TaskList) => l.position ?? 0;
  const arriba: { pos: number; el: Elemento }[] = [
    ...grupos.map(g => ({
      pos: g.position,
      el: {
        tipo: 'grupo' as const, id: g.id,
        listas: propias.filter(l => l.group_id === g.id).sort((a, b) => pos(a) - pos(b)).map(l => l.id),
      },
    })),
    ...propias
      .filter(l => !l.group_id || !idsGrupos.has(l.group_id))
      .map(l => ({ pos: pos(l), el: { tipo: 'lista' as const, id: l.id } })),
  ];
  return arriba.sort((a, b) => a.pos - b.pos).map(x => x.el);
}

function quitar(barra: Elemento[], tipo: 'grupo' | 'lista', id: string): { barra: Elemento[]; grupo?: Elemento } {
  if (tipo === 'grupo') {
    const grupo = barra.find(e => e.tipo === 'grupo' && e.id === id);
    return { barra: barra.filter(e => e !== grupo), grupo };
  }
  return {
    barra: barra
      .filter(e => !(e.tipo === 'lista' && e.id === id))
      .map(e => (e.tipo === 'grupo' ? { ...e, listas: e.listas.filter(l => l !== id) } : e)),
  };
}

/** Nueva barra tras soltar un elemento. Un grupo no entra en otro grupo: se coloca antes de él. */
export function mover(barra: Elemento[], arrastrado: { tipo: 'grupo' | 'lista'; id: string }, destino: Destino): Elemento[] {
  if (destino.tipo !== 'alFinal' && destino.id === arrastrado.id) return barra;
  const { barra: sin, grupo } = quitar(barra, arrastrado.tipo, arrastrado.id);
  const nuevo: Elemento = grupo ?? { tipo: 'lista', id: arrastrado.id };

  if (destino.tipo === 'alFinal') return [...sin, nuevo];

  if (destino.tipo === 'enGrupo' && arrastrado.tipo === 'lista') {
    return sin.map(e => (e.tipo === 'grupo' && e.id === destino.id ? { ...e, listas: [...e.listas, arrastrado.id] } : e));
  }

  if (destino.tipo === 'enGrupo' || destino.tipo === 'antesDeGrupo') {
    const i = sin.findIndex(e => e.tipo === 'grupo' && e.id === destino.id);
    return i < 0 ? barra : [...sin.slice(0, i), nuevo, ...sin.slice(i)];
  }

  // Antes de una lista: suelta arriba, o dentro del grupo que la contiene.
  const i = sin.findIndex(e => e.tipo === 'lista' && e.id === destino.id);
  if (i >= 0) return [...sin.slice(0, i), nuevo, ...sin.slice(i)];
  if (arrastrado.tipo === 'grupo') {
    const g = sin.findIndex(e => e.tipo === 'grupo' && e.listas.includes(destino.id));
    return g < 0 ? barra : [...sin.slice(0, g), nuevo, ...sin.slice(g)];
  }
  return sin.map(e => {
    if (e.tipo !== 'grupo' || !e.listas.includes(destino.id)) return e;
    const j = e.listas.indexOf(destino.id);
    return { ...e, listas: [...e.listas.slice(0, j), arrastrado.id, ...e.listas.slice(j)] };
  });
}

/** Mover una lista a un grupo (o sacarla, con null) desde el menú, sin arrastrar. */
export function moverAGrupo(barra: Elemento[], listaId: string, grupoId: string | null): Elemento[] {
  return mover(barra, { tipo: 'lista', id: listaId }, grupoId ? { tipo: 'enGrupo', id: grupoId } : { tipo: 'alFinal' });
}

/** Dónde está una lista: en qué grupo (o arriba, null) y en qué lugar entre sus vecinas. */
function lugar(barra: Elemento[], listaId: string): { grupo: string | null; i: number; total: number } | null {
  const arriba = barra.findIndex(e => e.tipo === 'lista' && e.id === listaId);
  if (arriba >= 0) return { grupo: null, i: arriba, total: barra.length };
  for (const e of barra) {
    if (e.tipo === 'grupo' && e.listas.includes(listaId)) return { grupo: e.id, i: e.listas.indexOf(listaId), total: e.listas.length };
  }
  return null;
}

/** «Mover arriba» (-1) o «Mover abajo» (+1) desde el menú: cambia de lugar con su vecina, dentro de su grupo. */
export function puedeDesplazar(barra: Elemento[], listaId: string, delta: -1 | 1): boolean {
  const l = lugar(barra, listaId);
  return !!l && l.i + delta >= 0 && l.i + delta < l.total;
}

export function desplazar(barra: Elemento[], listaId: string, delta: -1 | 1): Elemento[] {
  const l = lugar(barra, listaId);
  if (!l || !puedeDesplazar(barra, listaId, delta)) return barra;
  const cambiar = <T,>(xs: T[]): T[] => {
    const ys = [...xs];
    [ys[l.i], ys[l.i + delta]] = [ys[l.i + delta], ys[l.i]];
    return ys;
  };
  if (l.grupo === null) return cambiar(barra);
  return barra.map(e => (e.tipo === 'grupo' && e.id === l.grupo ? { ...e, listas: cambiar(e.listas) } : e));
}
