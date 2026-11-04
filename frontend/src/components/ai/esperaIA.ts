/**
 * Esperas de la IA del correo: texto y duración aproximada de cada función (04/11/2026).
 * Tiempos medidos con qwen2.5:14b en la Tesla P40 (mediana caliente) más un margen; ver
 * COMPARATIVA-QWEN-7B-14B-P40-20261104. Si el modelo está en frío tarda más: el indicador
 * pasa a «Casi listo…» y luego avisa con calma de que está tardando.
 */
export type FuncionIA = 'responder' | 'resumir' | 'buscar';

export const ESPERA_IA: Record<FuncionIA, { texto: string; segundos: number }> = {
  responder: { texto: 'Redactando su respuesta…', segundos: 10 },
  resumir: { texto: 'Resumiendo la conversación…', segundos: 8 },
  buscar: { texto: 'Buscando en su correo…', segundos: 6 },
};

/** «unos 8 segundos», «un segundo»; null cuando ya se cumplió el tiempo estimado. */
export function textoRestante(segundosRestantes: number): string | null {
  const s = Math.ceil(segundosRestantes);
  if (s <= 0) return null;
  return s === 1 ? 'un segundo' : `unos ${s} segundos`;
}

/** Avance aproximado 0-95 %: lineal hasta el estimado (90 %) y luego se acerca a 95 % sin llegar. */
export function avanceAproximado(transcurrido: number, estimado: number): number {
  if (estimado <= 0) return 95;
  if (transcurrido <= estimado) return (transcurrido / estimado) * 90;
  const extra = (transcurrido - estimado) / estimado;
  return 95 - 5 / (1 + extra);
}

/** Mensaje de fase: tranquiliza si tarda más del doble de lo previsto (modelo en frío). */
export function textoFase(transcurrido: number, estimado: number): string | null {
  if (transcurrido < estimado) return null;
  if (transcurrido < estimado * 2 + 10) return 'Casi listo…';
  return 'Está tardando un poco más de lo normal. Puede seguir esperando o cancelar.';
}
