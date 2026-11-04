import { useEffect, useState } from 'react';
import { ESPERA_IA, avanceAproximado, textoFase, textoRestante, type FuncionIA } from './esperaIA';

interface Props {
  funcion: FuncionIA;
  /** Si se pasa, se muestra el botón «Cancelar». */
  onCancelar?: () => void;
}

/**
 * Indicador amable mientras la IA trabaja, pensado para personas mayores: letra grande,
 * texto claro, cuenta regresiva aproximada que al llegar a 0 dice «Casi listo…» (nunca
 * negativa), barra suave y botón Cancelar. El lector de pantalla oye el texto y los cambios
 * de fase (aria-live="polite"), no cada segundo de la cuenta.
 */
export function IndicadorGenerando({ funcion, onCancelar }: Props) {
  const { texto, segundos } = ESPERA_IA[funcion];
  const [transcurrido, setTranscurrido] = useState(0);

  useEffect(() => {
    const inicio = Date.now();
    const id = window.setInterval(() => setTranscurrido((Date.now() - inicio) / 1000), 250);
    return () => window.clearInterval(id);
  }, []);

  const restante = textoRestante(segundos - transcurrido);
  const fase = textoFase(transcurrido, segundos);
  const avance = avanceAproximado(transcurrido, segundos);

  return (
    <div className="indicador-ia" style={{ padding: '12px 24px', borderTop: '1px solid #edebe9', background: '#f5f9fd', flexShrink: 0 }}>
      <style>{'@media (prefers-reduced-motion: reduce){.indicador-ia-barra{transition:none!important}}'}</style>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 220px', minWidth: 0 }}>
          <p role="status" aria-live="polite" style={{ margin: 0, fontSize: 17, fontWeight: 600, color: '#201f1e', lineHeight: 1.4 }}>
            {texto}
            <span style={{ display: 'block', fontSize: 16, fontWeight: 400, color: '#3b3a39' }}>
              {fase ?? `Tardará ${textoRestante(segundos)}.`}
            </span>
          </p>
          {restante && (
            <p aria-hidden="true" style={{ margin: '2px 0 0', fontSize: 15, color: '#484644' }}>
              Faltan {restante}
            </p>
          )}
        </div>
        {onCancelar && (
          <button type="button" onClick={onCancelar}
            style={{ minHeight: 44, minWidth: 110, padding: '8px 18px', fontSize: 16, fontWeight: 600, background: '#fff', color: '#201f1e', border: '2px solid #605e5c', borderRadius: 8, cursor: 'pointer' }}>
            Cancelar
          </button>
        )}
      </div>
      <div aria-hidden="true" style={{ marginTop: 10, height: 8, borderRadius: 4, background: '#dfe6ee', overflow: 'hidden' }}>
        <div className="indicador-ia-barra" style={{ height: '100%', width: `${avance}%`, background: '#0078d4', borderRadius: 4, transition: 'width 0.25s linear' }} />
      </div>
    </div>
  );
}
