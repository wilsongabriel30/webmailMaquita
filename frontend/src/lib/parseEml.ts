/**
 * Lectura básica de un archivo .eml en el navegador (09/11/2026).
 *
 * Sirve para la vista previa de un correo adjunto que NO salió de nuestro buzón (por ejemplo un
 * .eml traído del equipo): se extraen asunto, remitente, destinatarios, fecha y el cuerpo
 * (texto o HTML). No pretende ser un lector MIME completo: cubre cabeceras plegadas, palabras
 * codificadas RFC 2047, multipart anidado, base64 y quoted-printable. Lo que no entiende lo
 * deja como texto. El HTML resultante SIEMPRE debe pasar por sanitizeHtml antes de mostrarse.
 */

export interface CorreoEml {
  subject: string;
  from: string;
  to: string;
  date: string;
  /** Cuerpo HTML (sin sanear) si el correo lo traía. */
  html: string;
  /** Cuerpo en texto plano si lo traía. */
  texto: string;
  /** Nombres de los adjuntos declarados en el correo. */
  adjuntos: string[];
}

interface Parte { cabeceras: Record<string, string>; cuerpo: string }

function decodificarBytes(bytes: Uint8Array, charset: string): string {
  try {
    return new TextDecoder(charset || 'utf-8').decode(bytes);
  } catch {
    return new TextDecoder('utf-8').decode(bytes);
  }
}

function base64ABytes(b64: string): Uint8Array {
  const limpio = b64.replace(/[^A-Za-z0-9+/=]/g, '');
  try {
    const bin = atob(limpio);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  } catch {
    return new Uint8Array();
  }
}

function quotedPrintableABytes(qp: string): Uint8Array {
  const sinSaltos = qp.replace(/=\r?\n/g, '');
  const out: number[] = [];
  for (let i = 0; i < sinSaltos.length; i++) {
    const c = sinSaltos[i];
    if (c === '=' && /^[0-9A-Fa-f]{2}$/.test(sinSaltos.substr(i + 1, 2))) {
      out.push(parseInt(sinSaltos.substr(i + 1, 2), 16));
      i += 2;
    } else {
      // Caracteres ya decodificados por TextDecoder latin1: su código es el byte.
      out.push(c.charCodeAt(0) & 0xff);
    }
  }
  return new Uint8Array(out);
}

/** Decodifica «=?utf-8?B?...?=» y «=?iso-8859-1?Q?...?=» dentro de una cabecera. */
export function decodificarPalabrasCodificadas(valor: string): string {
  return valor
    .replace(/\?=\s+=\?/g, '?==?')
    .replace(/=\?([^?]+)\?([BbQq])\?([^?]*)\?=/g, (_m, charset: string, tipo: string, dato: string) => {
      const bytes = tipo.toUpperCase() === 'B'
        ? base64ABytes(dato)
        : quotedPrintableABytes(dato.replace(/_/g, ' '));
      return decodificarBytes(bytes, charset);
    });
}

function separarCabecerasYCuerpo(crudo: string): Parte {
  const idx = crudo.search(/\r?\n\r?\n/);
  const bloque = idx >= 0 ? crudo.slice(0, idx) : crudo;
  const cuerpo = idx >= 0 ? crudo.slice(idx).replace(/^\r?\n\r?\n/, '') : '';
  const cabeceras: Record<string, string> = {};
  // Las cabeceras plegadas (línea siguiente con espacio) se unen a la anterior.
  const lineas = bloque.replace(/\r?\n[ \t]+/g, ' ').split(/\r?\n/);
  for (const l of lineas) {
    const p = l.indexOf(':');
    if (p <= 0) continue;
    const nombre = l.slice(0, p).trim().toLowerCase();
    const valor = l.slice(p + 1).trim();
    if (!(nombre in cabeceras)) cabeceras[nombre] = valor;
  }
  return { cabeceras, cuerpo };
}

function parametro(cabecera: string, nombre: string): string {
  const m = cabecera.match(new RegExp(nombre + '\\s*=\\s*"?([^";]+)"?', 'i'));
  return m ? m[1].trim() : '';
}

function decodificarCuerpo(parte: Parte): string {
  const ct = parte.cabeceras['content-type'] || '';
  const charset = parametro(ct, 'charset') || 'utf-8';
  const cte = (parte.cabeceras['content-transfer-encoding'] || '').toLowerCase();
  if (cte.includes('base64')) return decodificarBytes(base64ABytes(parte.cuerpo), charset);
  if (cte.includes('quoted-printable')) return decodificarBytes(quotedPrintableABytes(parte.cuerpo), charset);
  // 7bit/8bit: el texto llegó leído como latin1 (un carácter por byte); se vuelve a bytes y se
  // decodifica con el juego de caracteres declarado (normalmente utf-8).
  const bytes = new Uint8Array(parte.cuerpo.length);
  for (let i = 0; i < parte.cuerpo.length; i++) bytes[i] = parte.cuerpo.charCodeAt(i) & 0xff;
  return decodificarBytes(bytes, charset);
}

function recorrer(parte: Parte, acumulado: CorreoEml): void {
  const ct = (parte.cabeceras['content-type'] || 'text/plain').toLowerCase();
  const disposicion = parte.cabeceras['content-disposition'] || '';
  const nombre = parametro(disposicion, 'filename') || parametro(ct, 'name');
  if (/attachment/i.test(disposicion) || (nombre && !ct.startsWith('text/'))) {
    acumulado.adjuntos.push(decodificarPalabrasCodificadas(nombre || 'adjunto'));
    return;
  }
  if (ct.startsWith('multipart/')) {
    const frontera = parametro(parte.cabeceras['content-type'] || '', 'boundary');
    if (!frontera) return;
    const trozos = parte.cuerpo.split('--' + frontera);
    // El primero (preámbulo) y el último (tras «--») no son partes.
    for (const t of trozos.slice(1)) {
      if (t.startsWith('--')) break;
      recorrer(separarCabecerasYCuerpo(t.replace(/^\r?\n/, '')), acumulado);
    }
    return;
  }
  if (ct.startsWith('message/rfc822')) {
    recorrer(separarCabecerasYCuerpo(parte.cuerpo), acumulado);
    return;
  }
  if (ct.startsWith('text/html') && !acumulado.html) acumulado.html = decodificarCuerpo(parte);
  else if (ct.startsWith('text/plain') && !acumulado.texto) acumulado.texto = decodificarCuerpo(parte);
}

/** Lee el .eml (como texto latin1, para no perder bytes) y devuelve sus datos principales. */
export function parsearEml(crudo: string): CorreoEml {
  const raiz = separarCabecerasYCuerpo(crudo);
  const c = raiz.cabeceras;
  const resultado: CorreoEml = {
    subject: decodificarPalabrasCodificadas(c['subject'] || ''),
    from: decodificarPalabrasCodificadas(c['from'] || ''),
    to: decodificarPalabrasCodificadas(c['to'] || ''),
    date: c['date'] || '',
    html: '',
    texto: '',
    adjuntos: [],
  };
  recorrer(raiz, resultado);
  return resultado;
}

/** Lee un File .eml del navegador. Se decodifica como latin1 para conservar cada byte. */
export async function leerEml(archivo: File): Promise<CorreoEml> {
  const bytes = new Uint8Array(await archivo.arrayBuffer());
  return parsearEml(new TextDecoder('latin1').decode(bytes));
}
