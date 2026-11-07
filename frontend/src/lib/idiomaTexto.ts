/**
 * Detección ligera y local del idioma de un texto: español o inglés (o «no se sabe»).
 *
 * Sirve al corrector ortográfico del redactor (cambia a inglés si la persona escribe en
 * inglés) y se envía como pista al autocompletado con IA. No usa servicios externos: cuenta
 * palabras muy frecuentes de cada idioma. Es la misma lógica que `backend/app/ai/idioma.py`;
 * si se cambia una lista aquí, conviene cambiarla allá.
 */

export type IdiomaTexto = 'es' | 'en';

const ES = new Set(`
  de la que el en y los las del se por un una para con su al lo como más mas pero sus le ya
  o este esta estos estas ese esa eso esto porque entre cuando muy sin sobre también tambien
  hasta hay donde desde todo todos todas nos durante uno les ni otros otras otro otra ante
  ellos ellas antes algunos qué unos yo él tanto mucho muchos nada algo nosotros mi mis tu tus
  usted ustedes es está están estan gracias saludos estimado estimada estimados
  estimadas buenos buenas días dias tardes noches favor adjunto adjunta reunión reunion hola
  querido querida queridos queridas cordial atentamente cual cuál quien quién dónde
  cómo señor señora compañeros compañeras equipo informe semana mañana hoy
`.split(/\s+/).filter(Boolean));

const EN = new Set(`
  the and of to in is you that it for on with as are this be at have from or by we your
  will can our not but they all would there their what so if about which when do please
  thank thanks dear regards best hello hi meeting attached could should let know i my an
  was were been has had any us these those kind sincerely looking forward team colleagues
  attend schedule report week today tomorrow morning afternoon hope well find following
  send sent here how who where why yes need also just more some into than then them
`.split(/\s+/).filter(Boolean));

const INICIO_EN = /^\s*(?:dear|hello|hi|good (?:morning|afternoon|evening)|greetings)\b/i;
const INICIO_ES = /^\s*(?:estimad|querid|apreciad|buen[oa]s (?:d[ií]as|tardes|noches)|hola(?![a-z])|se[ñn]or|distinguid|reciba|por medio)/i;
const RUIDO = /^>.*$|https?:\/\/\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+/gm;
const PALABRA = /[a-záéíóúüñ']+/gi;
const DIACRITICOS_ES = /[ñáéíóú¿¡]/gi;
const MAX = 4000;

function puntos(texto: string): [number, number] {
  const palabras = (texto.toLowerCase().match(PALABRA) || []).map(p => p.replace(/^'+|'+$/g, ''));
  let es = 0, en = 0;
  for (const p of palabras) { if (ES.has(p)) es++; if (EN.has(p)) en++; }
  es += Math.min(3, (texto.match(DIACRITICOS_ES) || []).length);
  return [es, en];
}

/** 'es', 'en' o null si el texto es corto o ambiguo. Ignora citas («>»), enlaces y direcciones. */
export function detectarIdioma(texto: string | null | undefined): IdiomaTexto | null {
  if (!texto) return null;
  const t = texto.slice(0, MAX).replace(RUIDO, ' ');
  const [es, en] = puntos(t);
  if (en >= 2 && en > 1.5 * es) return 'en';
  if (es >= 2 && es > 1.5 * en) return 'es';
  if (es + en <= 2) {
    if (INICIO_EN.test(t)) return 'en';
    if (INICIO_ES.test(t)) return 'es';
  }
  return null;
}

/** Texto visible de un HTML (para detectar el idioma del correo al que se responde). */
export function textoDeHtml(html: string): string {
  return html
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<blockquote[\s\S]*?<\/blockquote>/gi, ' ')  // citas anidadas: correos anteriores
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&[a-z]+;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
