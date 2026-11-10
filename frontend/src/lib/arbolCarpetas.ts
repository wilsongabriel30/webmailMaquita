import type { Folder } from '../types';

/* Árbol de carpetas IMAP a partir de la lista plana («Padre.Hija.Nieta»).
   Lo usan los menús «Mover a…» para mostrar madre e hijas en cascada. */

export interface NodoCarpeta {
  nombre: string;
  carpeta: Folder | null;
  hijas: NodoCarpeta[];
  nivel: number;
}

const ORDEN_SISTEMA: Record<string, number> = { inbox: 0, drafts: 1, sent: 2, junk: 3, trash: 4, archive: 5 };

function nombreDe(f: Folder | string): string {
  return typeof f === 'string' ? f : f.name;
}

function tipoDe(f: Folder | string): string {
  return typeof f === 'string' ? 'folder' : f.type;
}

export function construirArbolCarpetas(lista: (Folder | string)[]): NodoCarpeta[] {
  const raices: NodoCarpeta[] = [];
  const porNombre = new Map<string, NodoCarpeta>();
  const ordenadas = [...(lista || [])].filter(f => nombreDe(f)).sort((a, b) => {
    const oa = ORDEN_SISTEMA[tipoDe(a)] ?? 6, ob = ORDEN_SISTEMA[tipoDe(b)] ?? 6;
    if (oa !== ob) return oa - ob;
    return nombreDe(a).localeCompare(nombreDe(b), 'es', { numeric: true, sensitivity: 'base' });
  });
  for (const f of ordenadas) {
    const nombre = nombreDe(f);
    const punto = nombre.lastIndexOf('.');
    const madre = punto > 0 ? porNombre.get(nombre.substring(0, punto)) : undefined;
    const nodo: NodoCarpeta = { nombre, carpeta: typeof f === 'string' ? null : f, hijas: [], nivel: madre ? madre.nivel + 1 : 0 };
    porNombre.set(nombre, nodo);
    if (madre) madre.hijas.push(nodo); else raices.push(nodo);
  }
  return raices;
}

/** Nombre completo legible: «Territorios › Napo › WWF». */
export function rutaLegible(nombre: string, legible: (n: string) => string): string {
  return nombre.split('.').map((_, i, partes) => legible(partes.slice(0, i + 1).join('.'))).join(' › ');
}
