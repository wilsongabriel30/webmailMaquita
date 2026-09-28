/**
 * Cuerpo HTML de un mensaje dentro de una conversación, con su propio aviso de imágenes
 * bloqueadas. Antes la conversación no tenía aviso: al abrirse el hilo, el botón
 * «Cargar imágenes» desaparecía y no había forma de verlas.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { MessageFull } from '../../types';
import AvisoImagenesBloqueadas from './AvisoImagenesBloqueadas';
import SafeEmailViewer from './SafeEmailViewer';

interface Props {
  msg: MessageFull;
  folder: string;
  style?: React.CSSProperties;
}

export default function CuerpoHtmlConImagenes({ msg, folder, style }: Props) {
  const [htmlConImagenes, setHtmlConImagenes] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => { setHtmlConImagenes(null); setError(false); }, [msg.uid, folder]);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(false);
    try {
      const completo = await api.get<MessageFull>(
        `/mail/message/${encodeURIComponent(folder)}/${msg.uid}?load_images=true`,
      );
      setHtmlConImagenes(completo.html_body || '');
    } catch {
      setError(true);
    } finally {
      setCargando(false);
    }
  }, [folder, msg.uid]);

  const hayBloqueadas = !!(msg.has_remote_images && msg.blocked_image_count > 0) && htmlConImagenes === null;

  return (
    <>
      {hayBloqueadas && (
        <div style={{ marginBottom: 12 }}>
          <AvisoImagenesBloqueadas cantidad={msg.blocked_image_count} cargando={cargando} error={error} onCargar={cargar} />
        </div>
      )}
      <SafeEmailViewer htmlBody={htmlConImagenes ?? msg.html_body} style={style} />
    </>
  );
}
