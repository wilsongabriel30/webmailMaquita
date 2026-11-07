import { IndicadorGenerando } from './IndicadorGenerando';

interface Props {
  respondiendo: boolean;
  resumiendo: boolean;
  onCancelarRespuesta: () => void;
  onCancelarResumen: () => void;
}

/** Indicadores de espera de «Respuesta IA» y «Resumir» bajo el correo abierto (04/11/2026). */
export function EsperaIACorreo({ respondiendo, resumiendo, onCancelarRespuesta, onCancelarResumen }: Props) {
  return (
    <>
      {respondiendo && <IndicadorGenerando funcion="responder" onCancelar={onCancelarRespuesta} />}
      {resumiendo && <IndicadorGenerando funcion="resumir" onCancelar={onCancelarResumen} />}
    </>
  );
}
