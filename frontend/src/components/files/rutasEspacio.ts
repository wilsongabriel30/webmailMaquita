/* Rutas por ESPACIO del Drive: el propio («Mis archivos», raíz «/») o una unidad
   compartida («/unidades/<id>/…»). Lógica pura, sin React ni red: la usan el
   diálogo «Mover a…», el aviso de espacio compartido y la vista dividida, y se
   prueba con `node --test` (frontend/tests/rutasEspacio.test.ts).

   Por qué existe (22/10/2026): el diálogo «Mover a…» arrancaba SIEMPRE en la raíz
   propia y sus destinos no llevaban el prefijo «/unidades/<id>». Al reorganizar
   dentro de una unidad, el destino salía como «/B/…» y el servidor lo tomaba como
   un movimiento al espacio personal: el archivo desaparecía de la unidad para
   todo el equipo, sin ningún error. */

export interface Espacio {
  tipo: 'propio' | 'unidad';
  /** Raíz del espacio: «/» o «/unidades/<id>». Nunca se sube por encima de ella. */
  raiz: string;
  unidadId?: string;
}

export interface Miga {
  ruta: string;
  /** Nombre del tramo tal cual; la raíz de una unidad lleva su id (la etiqueta la pone la vista). */
  parte: string;
  esRaiz: boolean;
}

const RE_UNIDAD = /^\/unidades\/(\d+)(?=\/|$)/;

/** «a//b/» → «/a/b»; vacío → «/». */
export function normalizarRuta(ruta: string): string {
  const partes = String(ruta || '').split('/').filter(p => p && p !== '.');
  return '/' + partes.join('/');
}

export function espacioDeRuta(ruta: string): Espacio {
  const limpia = normalizarRuta(ruta);
  const m = RE_UNIDAD.exec(limpia);
  if (m) return { tipo: 'unidad', raiz: `/unidades/${m[1]}`, unidadId: m[1] };
  return { tipo: 'propio', raiz: '/' };
}

export function mismoEspacio(a: string, b: string): boolean {
  return espacioDeRuta(a).raiz === espacioDeRuta(b).raiz;
}

/** «/unidades» a secas es la lista virtual de unidades: no es una carpeta donde guardar. */
export function esListaDeUnidades(ruta: string): boolean {
  return normalizarRuta(ruta) === '/unidades';
}

/** Carpeta donde arranca el diálogo «Mover a…» / «Copiar a…».
    Dentro de una unidad: la carpeta ACTUAL, con su prefijo, para reorganizar ahí
    mismo. En el espacio propio se mantiene la raíz, como siempre. */
export function carpetaInicialSelector(rutaActual: string, enListado: boolean): string {
  if (!enListado) return '/';
  const limpia = normalizarRuta(rutaActual);
  return espacioDeRuta(limpia).tipo === 'unidad' ? limpia : '/';
}

/** Ruta completa del elemento al soltarlo en `carpeta`. */
export function rutaDestino(carpeta: string, nombre: string): string {
  const c = normalizarRuta(carpeta);
  return (c === '/' ? '' : c) + '/' + nombre;
}

/** Carpeta que contiene a `ruta`, sin salir de la raíz de su espacio (null si ya está en ella). */
export function padreDentroDelEspacio(ruta: string): string | null {
  const limpia = normalizarRuta(ruta);
  const { raiz } = espacioDeRuta(limpia);
  if (limpia === raiz) return null;
  const i = limpia.lastIndexOf('/');
  const padre = i <= 0 ? '/' : limpia.slice(0, i);
  return padre.length < raiz.length ? raiz : padre;
}

/** Migas desde la raíz del espacio hasta `ruta` (la primera siempre es la raíz). */
export function migasDelEspacio(ruta: string): Miga[] {
  const limpia = normalizarRuta(ruta);
  const { raiz, unidadId } = espacioDeRuta(limpia);
  const migas: Miga[] = [{ ruta: raiz, parte: unidadId || '', esRaiz: true }];
  const resto = limpia.slice(raiz === '/' ? 0 : raiz.length).split('/').filter(Boolean);
  let acumulada = raiz === '/' ? '' : raiz;
  for (const parte of resto) {
    acumulada += '/' + parte;
    migas.push({ ruta: acumulada, parte, esRaiz: false });
  }
  return migas;
}

/** ¿Se puede mover/copiar `origen` a `carpeta`? Devuelve el motivo si no se puede. */
export function motivoDestinoInvalido(origen: string, carpeta: string, nombre: string): string | null {
  const o = normalizarRuta(origen);
  const c = normalizarRuta(carpeta);
  if (esListaDeUnidades(c)) return 'Elige una carpeta dentro de la unidad';
  if (rutaDestino(c, nombre) === o) return 'Ya está en esa carpeta';
  if (c === o || c.startsWith(o + '/')) return 'No se puede poner una carpeta dentro de sí misma';
  return null;
}
