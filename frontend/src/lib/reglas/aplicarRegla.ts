import { api } from '../../api/client';
import type { Regla } from './tipos';
import { cuerpoParaGuardar } from './tipos';

/* Aplicar una regla a los correos que YA están en una carpeta (por defecto la Bandeja de entrada).
   Las reglas Sieve solo actúan sobre lo que llega; este servicio pide al servidor que ordene lo anterior. */

export interface ResultadoAplicar {
  folder: string;
  revisados: number;
  coinciden: number;
  parcial: boolean;
  movidos: number;
  copiados: number;
  marcados: number;
  leidos: number;
  papelera: number;
  destino?: string | null;
  omitidas: string[];
}

export function aplicarReglaAExistentes(regla: Regla, carpeta = 'INBOX'): Promise<ResultadoAplicar> {
  return api.post<ResultadoAplicar>('/sieve/filters/aplicar', { rule: cuerpoParaGuardar(regla), folder: carpeta });
}

/** Nombre corto de una carpeta IMAP para los avisos («INBOX.Facturas» → «Facturas»). */
export function nombreCorto(carpeta?: string | null): string {
  if (!carpeta) return '';
  if (carpeta === 'INBOX') return 'Bandeja de entrada';
  if (carpeta === 'Trash') return 'Papelera';
  if (carpeta === 'Archive') return 'Archivo';
  return carpeta.replace(/^INBOX\./, '').split('.').pop() || carpeta;
}

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

/** Texto del aviso con lo que se hizo. */
export function textoResultado(r: ResultadoAplicar): string {
  if (!r.coinciden) {
    return r.parcial
      ? `Ningún correo de los últimos ${r.revisados} de la Bandeja de entrada cumple la regla`
      : 'Ningún correo anterior de la Bandeja de entrada cumple la regla';
  }
  const partes: string[] = [];
  if (r.movidos) partes.push(`${plural(r.movidos, 'movido', 'movidos')} a «${nombreCorto(r.destino)}»`);
  if (r.papelera) partes.push(`${plural(r.papelera, 'enviado', 'enviados')} a la Papelera`);
  if (r.copiados) partes.push(`${plural(r.copiados, 'copiado', 'copiados')}`);
  if (r.marcados) partes.push(`${plural(r.marcados, 'marcado', 'marcados')} con bandera`);
  if (r.leidos) partes.push(`${plural(r.leidos, 'marcado', 'marcados')} como leído`);
  let texto = `${plural(r.coinciden, 'correo anterior cumple', 'correos anteriores cumplen')} la regla` + (partes.length ? `: ${partes.join(', ')}` : '');
  if (r.omitidas.length) texto += ` (no se aplica hacia atrás: ${r.omitidas.join(', ')})`;
  if (r.parcial) texto += `. Se revisaron solo los últimos ${r.revisados} correos`;
  return texto;
}
