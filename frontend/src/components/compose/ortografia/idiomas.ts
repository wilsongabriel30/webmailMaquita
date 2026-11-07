/**
 * Idiomas del corrector ortográfico del redactor y elección recordada por mensaje.
 *
 * El corrector es el del navegador: se activa con `spellcheck` y el idioma sale del atributo
 * `lang` del cuerpo (Firefox y Safari lo respetan; Chrome revisa con los idiomas activados en
 * su configuración, por eso conviene tener activados Español e Inglés).
 */
import type { IdiomaTexto } from '../../../lib/idiomaTexto';

export type IdiomaOrtografia = 'es-EC' | 'en';

export const POR_DEFECTO: IdiomaOrtografia = 'es-EC';

export const NOMBRE: Record<IdiomaOrtografia, string> = {
  'es-EC': 'Español (Ecuador)',
  en: 'Inglés',
};

export const deTexto = (i: IdiomaTexto): IdiomaOrtografia => (i === 'en' ? 'en' : 'es-EC');
export const aTexto = (i: IdiomaOrtografia): IdiomaTexto => (i === 'en' ? 'en' : 'es');
export const otro = (i: IdiomaOrtografia): IdiomaOrtografia => (i === 'en' ? 'es-EC' : 'en');

// Elección a mano, recordada por mensaje:
// - «ventana:<id>»: en memoria de la página (el id de la ventana es un contador que se repite
//   tras recargar, así que no se guarda en el navegador: otro mensaje la heredaría);
// - «borrador:<uid>»: en localStorage (identifica el mensaje aunque se recargue o se reabra).
const CLAVE = 'ortografia-por-mensaje';
const MAXIMO = 100;
const enMemoria = new Map<string, IdiomaOrtografia>();
const duradera = (c: string) => c.startsWith('borrador:');

type Mapa = Record<string, IdiomaOrtografia>;

function leerMapa(): Mapa {
  try {
    const crudo = localStorage.getItem(CLAVE);
    const mapa = crudo ? JSON.parse(crudo) : {};
    return mapa && typeof mapa === 'object' ? mapa : {};
  } catch { return {}; }
}

export function eleccionGuardada(claves: string[]): IdiomaOrtografia | null {
  for (const c of claves) {
    const v = enMemoria.get(c);
    if (v) return v;
  }
  const mapa = leerMapa();
  for (const c of claves.filter(duradera)) {
    const v = mapa[c];
    if (v === 'es-EC' || v === 'en') return v;
  }
  return null;
}

export function guardarEleccion(claves: string[], idioma: IdiomaOrtografia) {
  for (const c of claves) enMemoria.set(c, idioma);
  const persistentes = claves.filter(duradera);
  if (!persistentes.length) return;
  try {
    const mapa = leerMapa();
    for (const c of persistentes) { delete mapa[c]; mapa[c] = idioma; }
    const llaves = Object.keys(mapa);
    for (const viejo of llaves.slice(0, Math.max(0, llaves.length - MAXIMO))) delete mapa[viejo];
    localStorage.setItem(CLAVE, JSON.stringify(mapa));
  } catch { /* sin almacenamiento (ventana privada): vale mientras la página siga abierta */ }
}
