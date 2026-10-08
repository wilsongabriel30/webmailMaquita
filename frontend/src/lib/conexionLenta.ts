// Aviso de conexión lenta (08/10/2026). Separa lo que tarda el SERVIDOR (cabecera Server-Timing «app;dur=»,
// la pone el backend) de lo que tarda la RED hasta el equipo de la persona. Con conexiones rurales o por
// satélite el servidor responde en 1 s y la respuesta tarda 10 s en llegar: la pantalla «se quedaba pensando»
// sin explicar nada y la persona refrescaba a mitad de una acción. Ahora se le dice que es su conexión.
// También vigila las peticiones que llevan mucho rato sin respuesta (red trabada).
export type EstadoRed = 'normal' | 'lenta' | 'esperando';

const UMBRAL_RED_LENTA_MS = 3000;   // tiempo de red (sin contar el servidor) que ya se nota
const UMBRAL_ESPERA_MS = 10000;     // una petición sin respuesta tanto rato = red trabada
const MUESTRAS = 6;                 // se miran las últimas N peticiones...
const MIN_LENTAS = 2;               // ...y con estas lentas se avisa (una sola puede ser casualidad)
const VIGENCIA_MUESTRA_MS = 120000; // una medida de hace más de 2 min ya no dice nada de la red actual

// Peticiones que tardan por naturaleza (subir adjuntos, enviar, buscar en el texto, IA, descargas): no se vigilan
const NO_VIGILAR = /\/(send|upload|adjunt|attach|ai|copiloto|search|buscar|export|descarg|download)/i;

export interface Medida { t0: number; vigilar: boolean; servidorMs: number | null; descartar: boolean }

const muestras: { t: number; redMs: number }[] = [];
const enCurso = new Set<Medida>();
let estado: EstadoRed = 'normal';
let esperandoDesde = 0;

function tipoConexionLento(): boolean {
  const c = (navigator as Navigator & { connection?: { effectiveType?: string } }).connection;
  return !!c && (c.effectiveType === 'slow-2g' || c.effectiveType === '2g');
}

function calcular(): EstadoRed {
  const ahora = performance.now();
  for (const m of enCurso) if (m.vigilar && ahora - m.t0 > UMBRAL_ESPERA_MS) return 'esperando';
  while (muestras.length && ahora - muestras[0].t > VIGENCIA_MUESTRA_MS) muestras.shift();
  if (muestras.filter(m => m.redMs > UMBRAL_RED_LENTA_MS).length >= MIN_LENTAS) return 'lenta';
  return tipoConexionLento() ? 'lenta' : 'normal';
}

function actualizar(): void {
  const nuevo = calcular();
  if (nuevo === estado) return;
  if (nuevo === 'esperando') esperandoDesde = Date.now();
  estado = nuevo;
  window.dispatchEvent(new CustomEvent('red-lenta-cambio', { detail: nuevo }));
}

export function estadoRed(): { estado: EstadoRed; esperandoDesde: number } {
  return { estado, esperandoDesde };
}

export function inicioPeticion(path: string): Medida {
  const m: Medida = { t0: performance.now(), vigilar: !NO_VIGILAR.test(path), servidorMs: null, descartar: false };
  enCurso.add(m);
  return m;
}

/** Lee «app;dur=123» de Server-Timing. Sin cabecera (caché del service worker, error de nginx) = null. */
export function tiempoServidor(res: Response): number | null {
  const v = res.headers.get('Server-Timing') || '';
  const r = /(?:^|,)\s*app;dur=([\d.]+)/.exec(v);
  return r ? parseFloat(r[1]) : null;
}

/** Al terminar (con el cuerpo ya leído): red = total − servidor. */
export function finPeticion(m: Medida): void {
  enCurso.delete(m);
  if (m.vigilar && !m.descartar && m.servidorMs !== null) {
    const redMs = Math.max(0, performance.now() - m.t0 - m.servidorMs);
    muestras.push({ t: performance.now(), redMs });
    if (muestras.length > MUESTRAS) muestras.shift();
  }
  actualizar();
}

if (typeof window !== 'undefined') {
  // Revisión cada 2 s solo mientras haya algo que vigilar (peticiones abiertas o aviso a la vista)
  setInterval(() => { if (enCurso.size || estado !== 'normal') actualizar(); }, 2000);
}
