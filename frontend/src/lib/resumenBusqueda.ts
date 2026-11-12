// La búsqueda avanzada, dicha en una frase (12/11/2026).
//
// El panel mostraba la consulta tal como la entiende la caja («de:daniel asunto:factura entre:…»):
// útil para quien conoce los operadores, ruido para el resto. Aquí se dice lo mismo en palabras:
// «Correos de «daniel», con «factura» en el asunto, de esta semana, con archivo adjunto».

export interface CamposBusqueda {
  de: string; para: string; asunto: string; texto: string; dominio: string;
  desde: string; hasta: string; atajo: string;
  conAdjunto: boolean; adjuntoNombre: string; soloNoLeidos: boolean; soloMarcados: boolean;
  tamMin: string; enContenido: boolean;
}

export const ATAJOS_FECHA = [
  { etiqueta: 'Hoy', valor: 'hoy', frase: 'de hoy' },
  { etiqueta: 'Ayer', valor: 'ayer', frase: 'de ayer' },
  { etiqueta: 'Esta semana', valor: 'semana', frase: 'de esta semana' },
  { etiqueta: 'Este mes', valor: 'mes', frase: 'de este mes' },
  { etiqueta: 'Últimos 3 meses', valor: 'trimestre', frase: 'de los últimos 3 meses' },
];

export const TAMANOS = [
  { valor: '', etiqueta: 'Cualquier tamaño', frase: '' },
  { valor: '1M', etiqueta: 'Más de 1 MB', frase: 'de más de 1 MB' },
  { valor: '5M', etiqueta: 'Más de 5 MB (pesado)', frase: 'de más de 5 MB' },
  { valor: '10M', etiqueta: 'Más de 10 MB (muy pesado)', frase: 'de más de 10 MB' },
  { valor: '25M', etiqueta: 'Más de 25 MB', frase: 'de más de 25 MB' },
];

function fechaLegible(iso: string): string {
  const [a, m, d] = iso.split('-');
  return a && m && d ? `${d}/${m}/${a}` : iso;
}

/** Frase que describe lo que se va a buscar; '' si no hay nada escrito. */
export function resumirBusqueda(c: CamposBusqueda, incluyeReenviados = false): string {
  const p: string[] = [];
  if (c.de.trim()) p.push(`de «${c.de.trim()}»${incluyeReenviados ? ' (y los que otra persona le reenvió)' : ''}`);
  if (c.para.trim()) p.push(`enviados a «${c.para.trim()}»`);
  if (c.dominio.trim()) p.push(`de o para alguien de «${c.dominio.trim().replace(/^@/, '')}»`);
  if (c.asunto.trim()) p.push(`con «${c.asunto.trim()}» en el asunto`);
  if (c.texto.trim()) p.push(c.enContenido ? `que contengan «${c.texto.trim()}»` : `con «${c.texto.trim()}» en el remitente, el destinatario o el asunto`);
  if (c.desde && c.hasta) p.push(`entre el ${fechaLegible(c.desde)} y el ${fechaLegible(c.hasta)}`);
  else if (c.desde) p.push(`desde el ${fechaLegible(c.desde)}`);
  else if (c.hasta) p.push(`hasta el ${fechaLegible(c.hasta)}`);
  else if (c.atajo) p.push(ATAJOS_FECHA.find((a) => a.valor === c.atajo)?.frase || '');
  if (c.adjuntoNombre.trim()) p.push(`con un archivo adjunto llamado «${c.adjuntoNombre.trim()}»`);
  else if (c.conAdjunto) p.push('con archivo adjunto');
  if (c.soloNoLeidos) p.push('que aún no ha leído');
  if (c.soloMarcados) p.push('que marcó con bandera');
  const tam = TAMANOS.find((t) => t.valor && t.valor === c.tamMin.trim());
  if (tam) p.push(tam.frase);
  const partes = p.filter(Boolean);
  if (!partes.length) return '';
  return `Correos ${partes.join(', ')}.`;
}
