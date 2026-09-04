/* =============================================================================
   T-49 · Cifrado del caché local del correo
   -----------------------------------------------------------------------------
   QUE HACE: la llave (protegida por Windows a través de la aplicación, o por el
   navegador cuando no la hay) y las funciones para cifrar y descifrar lo que se
   guarda en el equipo.
   POR QUE:  los correos guardados para leer sin conexión no pueden quedar
   legibles para quien copie los archivos del equipo.
   DONDE SE USA: offlineStore.ts. Es el mismo criterio y el mismo formato que en
   el chat (chat-cache-llave.js / chat-cache-cifrado.js), para no tener dos
   maneras distintas de hacer lo mismo.
   ============================================================================= */

const BD_LLAVE = 'maquita-cache-llave';
const ALMACEN_LLAVE = 'llaves';
const TAM_IV = 12;

export interface Paquete {
  v: number;
  iv: Uint8Array;
  ct: Uint8Array;
}

declare global {
  interface Window {
    maquitaApp?: {
      protegerLlave(bytesBase64: string): Promise<string>;
      recuperarLlave(envueltaBase64: string): Promise<string>;
    };
  }
}

let llaveEnMemoria: CryptoKey | null = null;
let pendiente: Promise<CryptoKey> | null = null;

function hayApp(): boolean {
  return !!(window.maquitaApp
    && typeof window.maquitaApp.protegerLlave === 'function'
    && typeof window.maquitaApp.recuperarLlave === 'function');
}

function abrirBD(): Promise<IDBDatabase> {
  return new Promise((ok, mal) => {
    const p = indexedDB.open(BD_LLAVE, 1);
    p.onupgradeneeded = () => { p.result.createObjectStore(ALMACEN_LLAVE); };
    p.onsuccess = () => ok(p.result);
    p.onerror = () => mal(p.error);
  });
}

function leer(clave: string): Promise<any> {
  return abrirBD().then(db => new Promise((ok, mal) => {
    const p = db.transaction(ALMACEN_LLAVE, 'readonly').objectStore(ALMACEN_LLAVE).get(clave);
    p.onsuccess = () => ok(p.result);
    p.onerror = () => mal(p.error);
  }));
}

function escribir(clave: string, valor: any): Promise<void> {
  return abrirBD().then(db => new Promise((ok, mal) => {
    const p = db.transaction(ALMACEN_LLAVE, 'readwrite').objectStore(ALMACEN_LLAVE).put(valor, clave);
    p.onsuccess = () => ok();
    p.onerror = () => mal(p.error);
  }));
}

const aBase64 = (b: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(b)));
const deBase64 = (t: string) => Uint8Array.from(atob(t), c => c.charCodeAt(0));

/** Opción C: la aplicación protege la llave con DPAPI, atada a esa cuenta de Windows. */
async function conApp(): Promise<CryptoKey> {
  const envuelta = await leer('dpapi');
  if (envuelta) {
    try {
      const bytes = deBase64(await window.maquitaApp!.recuperarLlave(envuelta));
      return crypto.subtle.importKey('raw', bytes, 'AES-GCM', false, ['encrypt', 'decrypt']);
    } catch {
      // envoltura de otro usuario u otro equipo: se descarta y se empieza de cero.
      // Lo guardado con la anterior queda ilegible, que es exactamente lo que se busca.
    }
  }
  const material = crypto.getRandomValues(new Uint8Array(32));
  await escribir('dpapi', await window.maquitaApp!.protegerLlave(aBase64(material.buffer)));
  const llave = await crypto.subtle.importKey('raw', material, 'AES-GCM', false,
                                              ['encrypt', 'decrypt']);
  material.fill(0);
  return llave;
}

/** Opción A: sin aplicación, la llave la guarda el navegador y no es exportable. */
async function sinApp(): Promise<CryptoKey> {
  const guardada = await leer('principal');
  if (guardada) return guardada as CryptoKey;
  const llave = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false,
                                                ['encrypt', 'decrypt']);
  await escribir('principal', llave);
  return llave;
}

export function llaveProtegidaPorElEquipo(): boolean {
  return hayApp();
}

export function obtenerLlave(): Promise<CryptoKey> {
  if (llaveEnMemoria) return Promise.resolve(llaveEnMemoria);
  if (pendiente) return pendiente;
  pendiente = (hayApp() ? conApp() : sinApp()).then(k => {
    llaveEnMemoria = k;
    pendiente = null;
    return k;
  }, e => { pendiente = null; throw e; });
  return pendiente;
}

export async function cifrar(valor: unknown): Promise<Paquete> {
  const llave = await obtenerLlave();
  const iv = crypto.getRandomValues(new Uint8Array(TAM_IV));   // nunca se repite
  const claro = new TextEncoder().encode(JSON.stringify(valor));
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, llave, claro);
  return { v: 1, iv, ct: new Uint8Array(ct) };
}

export async function descifrar<T = any>(p: Paquete | null | undefined): Promise<T | null> {
  if (!p || !p.ct) return null;
  try {
    const llave = await obtenerLlave();
    const claro = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: new Uint8Array(p.iv) }, llave, new Uint8Array(p.ct));
    return JSON.parse(new TextDecoder().decode(claro)) as T;
  } catch {
    // Si no se puede descifrar se trata como si no estuviera. Nunca se devuelve
    // algo a medias: es preferible volver a pedirlo al servidor.
    return null;
  }
}

export function esPaquete(x: any): x is Paquete {
  return !!(x && typeof x === 'object' && x.ct && x.iv && typeof x.v === 'number');
}

export async function olvidarLlave(): Promise<void> {
  llaveEnMemoria = null;
  const db = await abrirBD();
  db.transaction(ALMACEN_LLAVE, 'readwrite').objectStore(ALMACEN_LLAVE).clear();
}
