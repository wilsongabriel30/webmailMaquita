// Texto de los avisos de correo nuevo (06/11/2026): quién envía y el asunto, no solo cuántos.
//   un correo → título = remitente, texto = asunto
//   varios    → título = «N correos nuevos», texto = «Remitente: asunto» del más reciente
// Lo usan el aviso en tiempo real (useWebSocket) y el de respaldo (MessageList): MISMO texto en los dos.
import { nombreApp } from './marca';

/** «Carlos Ponce <contabilidadproductos@…>» → «Carlos Ponce»; sin nombre, la dirección. */
export function nombreRemitente(from: string | undefined | null): string {
  const t = (from || '').trim();
  if (!t) return '';
  const m = t.match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>/);
  if (m) return (m[1] || m[2]).trim();
  return t;
}

export function textoAvisoCorreo(nuevos: number, de?: string, asunto?: string): { titulo: string; cuerpo: string } {
  const n = Math.max(1, nuevos || 1);
  const a = (asunto || '').trim() || '(sin asunto)';
  // El nombre va también en el texto: hay pantallas que muestran solo el texto (06/11/2026).
  if (de && n === 1) return { titulo: de, cuerpo: `De: ${de}\nAsunto: ${a}` };
  if (de) return { titulo: `${n} correos nuevos`, cuerpo: `De: ${de}\nAsunto: ${a}` };
  return { titulo: nombreApp(), cuerpo: n === 1 ? 'Nuevo correo recibido' : `${n} correos nuevos` };
}

/** Cuentas delegadas (06/11/2026): lo mismo, diciendo además a qué cuenta llegó. Igual que el servidor
 *  (textos_aviso_cuenta en resumen_correo_nuevo.py). */
export function textoAvisoCuenta(nuevos: number, cuenta: string, de?: string, asunto?: string): { titulo: string; cuerpo: string } {
  const n = Math.max(1, nuevos || 1);
  const a = (asunto || '').trim() || '(sin asunto)';
  if (de && n === 1) return { titulo: de, cuerpo: `De: ${de}\nAsunto: ${a}\nCuenta: ${cuenta}` };
  if (de) return { titulo: `${n} correos nuevos en ${cuenta}`, cuerpo: `De: ${de}\nAsunto: ${a}` };
  return { titulo: cuenta, cuerpo: n === 1 ? `Correo nuevo en ${cuenta}` : `${n} correos nuevos en ${cuenta}` };
}
