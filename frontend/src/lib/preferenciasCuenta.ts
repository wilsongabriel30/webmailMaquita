/**
 * Preferencias de la persona guardadas en su cuenta (11/11/2026, pedido de la dirección).
 *
 * «Lo que una persona personaliza en cualquier parte debe quedarse así»: muchas preferencias vivían solo en
 * el navegador (tema, favoritos, orden de la lista, chinchetas, secciones plegadas, vistas de Tareas y de la
 * Nube, zoom…) y se perdían al cambiar de navegador, de equipo o de dirección del webmail.
 *
 * Mecanismo único: las claves de CLAVES_DE_CUENTA se copian al servidor cada vez que cambian
 * (`PUT /api/settings {vista: {local: {...}}}`) y, al entrar, lo guardado en la cuenta se vuelca al navegador.
 * Si al entrar había diferencias, la página se recarga UNA vez para que todo arranque con los valores de la
 * cuenta. Lo que es propio del equipo (cachés, cifrado, descargas sin conexión, sesión) no se sincroniza.
 */
import { api } from '../api/client';

export const CLAVES_DE_CUENTA: string[] = [
  'theme',
  // «maquita_escala» (la calcula cada pantalla) no va: solo la escala que la persona ELIGE.
  'maquita_cinta_contraida', 'maquita_buscar_en_todo', 'maquita_escala_elegida',
  'maquita_mi_dia', 'maquita_pinned_msgs', 'maquita_sig_settings', 'maquita_dictado_modo',
  'webmail.carpetasFavoritas.v2', 'webmail.ordenLista',
  'sidebar_secciones_plegadas', 'sidebar.etiquetas.plegado',
  'ortografia-por-mensaje',
  'almacen_modo_vista', 'almacen_vista_dividida',
  'seguimiento.modo', 'tareas.modo', 'tareas-modo-vista',
];

const MARCA_RECARGA = 'maquita_prefs_recargado';
const MAX_VALOR = 20000;
const permitidas = new Set(CLAVES_DE_CUENTA);
let aplicando = false;
let temporizador: number | undefined;
let vigilando = false;

/** Lo que este navegador tiene ahora para las claves de la cuenta. */
export function preferenciasLocales(): Record<string, string> {
  const datos: Record<string, string> = {};
  for (const clave of CLAVES_DE_CUENTA) {
    try {
      const v = localStorage.getItem(clave);
      if (v !== null && v.length <= MAX_VALOR) datos[clave] = v;
    } catch { /* almacenamiento bloqueado */ }
  }
  return datos;
}

function guardarEnCuenta() {
  api.put('/settings', { vista: { local: preferenciasLocales() } }).catch(() => { /* queda en este navegador */ });
}

function programarGuardado() {
  window.clearTimeout(temporizador);
  temporizador = window.setTimeout(guardarEnCuenta, 2000);
}

/** Desde ahora, cada cambio de una preferencia de la lista se guarda en la cuenta. */
export function vigilarPreferencias() {
  if (vigilando) return;
  vigilando = true;
  const ponerOriginal = Storage.prototype.setItem;
  const quitarOriginal = Storage.prototype.removeItem;
  Storage.prototype.setItem = function (clave: string, valor: string) {
    ponerOriginal.call(this, clave, valor);
    if (!aplicando && this === window.localStorage && permitidas.has(clave)) programarGuardado();
  };
  Storage.prototype.removeItem = function (clave: string) {
    quitarOriginal.call(this, clave);
    if (!aplicando && this === window.localStorage && permitidas.has(clave)) programarGuardado();
  };
}

/**
 * Vuelca al navegador lo guardado en la cuenta. Devuelve true si cambió algo (hay que recargar).
 * `guardadas` es `vista.local` tal como lo devuelve `GET /api/settings`.
 */
export function aplicarPreferenciasDeCuenta(guardadas: unknown): boolean {
  if (!guardadas || typeof guardadas !== 'object') return false;
  let cambio = false;
  aplicando = true;
  try {
    for (const [clave, valor] of Object.entries(guardadas as Record<string, unknown>)) {
      if (!permitidas.has(clave) || typeof valor !== 'string') continue;
      if (localStorage.getItem(clave) !== valor) { localStorage.setItem(clave, valor); cambio = true; }
    }
  } catch { /* almacenamiento bloqueado */ } finally { aplicando = false; }
  return cambio;
}

/** Al entrar: aplica lo de la cuenta; si no había nada guardado, sube lo de este navegador. */
export function sincronizarAlEntrar(guardadas: unknown) {
  vigilarPreferencias();
  const hayGuardadas = !!guardadas && typeof guardadas === 'object' && Object.keys(guardadas as object).length > 0;
  if (!hayGuardadas) { if (Object.keys(preferenciasLocales()).length > 0) guardarEnCuenta(); return; }
  const cambio = aplicarPreferenciasDeCuenta(guardadas);
  let yaRecargo = false;
  try { yaRecargo = sessionStorage.getItem(MARCA_RECARGA) === '1'; } catch { yaRecargo = true; }
  if (cambio && !yaRecargo) {
    try { sessionStorage.setItem(MARCA_RECARGA, '1'); } catch { return; }
    window.location.reload();   // una sola vez por sesión: todo arranca con lo de la cuenta
  }
}
