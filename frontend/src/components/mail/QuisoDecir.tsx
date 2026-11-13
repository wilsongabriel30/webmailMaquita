/**
 * «¿Quiso decir…?»: si la búsqueda no encontró nada y parece un nombre mal escrito, propone la
 * forma correcta (el servidor la saca de los nombres del directorio y de la agenda de la persona).
 */
import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { aplicarBusqueda } from '../../lib/busquedaGlobal';

export function QuisoDecir({ consulta }: { consulta: string }) {
  const texto = consulta.trim();
  const [dato, setDato] = useState<{ texto: string; opciones: string[] } | null>(null);

  useEffect(() => {
    if (texto.length < 3) return;
    let vigente = true;
    api.get<{ sugerencias: string[] }>(`/mail/search/sugerencias?q=${encodeURIComponent(texto)}`)
      .then(r => { if (vigente) setDato({ texto, opciones: r.sugerencias || [] }); })
      .catch(() => { /* sin sugerencias */ });
    return () => { vigente = false; };
  }, [texto]);

  const opciones = dato && dato.texto === texto ? dato.opciones : [];
  if (opciones.length === 0) return null;
  return (
    <p className="text-[13px] text-[#323130] dark:text-[#e0e0e0] mt-2" role="status">
      ¿Quiso decir{' '}
      {opciones.map((o, i) => (
        <span key={o}>
          {i > 0 && ' o '}
          <button type="button" className="font-semibold text-[#0078d4] hover:underline" onClick={() => aplicarBusqueda(o)}>
            {o}
          </button>
        </span>
      ))}
      ?
    </p>
  );
}
