/**
 * MensajeEnPestana — página independiente que muestra UN solo correo.
 *
 * Se abre desde «Abrir en una nueva pestaña» del menú contextual de la lista
 * (/webmail/mensaje?folder=INBOX&uid=123). Reutiliza MessageView tal cual: aquí solo se
 * autentica, se cargan las carpetas (para fechas y acciones) y el mensaje, y se deja en el
 * estado como seleccionado. Como es otra pestaña, su estado no toca el de la bandeja original.
 *
 * 09/11/2026: Responder / Responder a todos / Reenviar abren el editor AQUÍ mismo (antes creaban la
 * redacción en el estado pero esta página no la dibujaba y parecía que los botones no hacían nada;
 * reporte de Graciela). Mientras se redacta, el editor ocupa la ventana; al enviar o descartar vuelve el correo.
 */
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { useAuthStore } from '../../store/authStore';
import { ToastContainer } from '../common/ToastContainer';
import { MessageView } from './MessageView';
import { ComposePanel } from '../compose/ComposePanel';
import { Toolbar } from './Toolbar';
import { BarraVolverAlCorreo } from './BarraVolverAlCorreo';
import type { Folder, MessageFull } from '../../types';

export function MensajeEnPestana() {
  const [searchParams] = useSearchParams();
  const { user, setUser } = useAuthStore();
  const setFolders = useMailStore(s => s.setFolders);
  const composeWindows = useMailStore(s => s.composeWindows);
  const restoreCompose = useMailStore(s => s.restoreCompose);
  const [error, setError] = useState('');

  const folder = searchParams.get('folder') || 'INBOX';
  const uid = Number(searchParams.get('uid') || 0);

  // Sesión: igual que la ventana de redacción (/compose), que también vive fuera del AppLayout.
  useEffect(() => {
    if (user) return;
    fetch('/api/auth/me', { credentials: 'include' })
      .then(r => r.json())
      .then(d => setUser(d.user || null))
      .catch(() => setUser(null));
  }, [user, setUser]);

  useEffect(() => {
    if (!user) return;
    let vigente = true;
    const cargar = async () => {
      if (!uid) { setError('Falta el identificador del correo.'); return; }
      const st = useMailStore.getState();
      if (folder !== st.currentFolder) st.setCurrentFolder(folder);
      st.setLoadingMessage(true);
      api.get<{ folders: Folder[] }>('/mail/folders')
        .then(r => { if (vigente) setFolders(r.folders); })
        .catch(() => { /* sin carpetas: el correo se ve igual */ });
      try {
        const msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(folder)}/${uid}`);
        if (!vigente) return;
        useMailStore.getState().setSelectedMessage(msg);
        if (msg?.subject) document.title = msg.subject;
      } catch {
        if (!vigente) return;
        useMailStore.getState().setLoadingMessage(false);
        setError('No se pudo abrir el correo. Puede que se haya movido o eliminado.');
      }
    };
    void cargar();
    return () => { vigente = false; };
  }, [user, folder, uid, setFolders]);

  // Sin barra de minimizados en esta ventana: una redacción minimizada se vuelve a mostrar.
  useEffect(() => {
    const minimizada = composeWindows.find(w => w.minimized);
    if (minimizada) restoreCompose(minimizada.id);
  }, [composeWindows, restoreCompose]);
  const redaccion = composeWindows.find(w => !w.minimized);

  if (!user) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#f3f2f1]">
        <div className="animate-spin w-8 h-8 border-2 border-[#0078d4] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-white overflow-hidden">
      {error ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
          <p className="text-[14px] text-[#323130]">{error}</p>
          <button type="button" onClick={() => window.close()} className="text-[12px] mt-3 text-[#0078d4] hover:underline">
            Cerrar esta pestaña
          </button>
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex overflow-hidden">
          {/* Ocupa todo el ancho de la ventana (07/11/2026): sin esto el correo se ajustaba a su
              contenido y quedaba un hueco blanco a la derecha. */}
          <div className="flex-1 min-w-0 flex flex-col">
            {redaccion ? (
              <>
                {/* Botón con palabras para cancelar la respuesta y volver a leer el correo (pedido 09/11/2026:
                    «por si le dan Responder por error o deciden no responder»). Cierra igual que la X del editor. */}
                <BarraVolverAlCorreo
                  asunto={redaccion.data?.subject || ''}
                  onVolver={() => window.dispatchEvent(new CustomEvent('compose-cerrar', { detail: { id: redaccion.id } }))}
                />
                {/* Misma cinta que la ventana de redacción (/compose): pestañas Mensaje, Insertar, Aplicar
                    formato y Opciones, para adjuntar correos, archivos, fotos… también desde aquí. */}
                <div className="shrink-0 relative z-[50]"><Toolbar /></div>
                <div className="flex-1 min-h-0 overflow-auto"><ComposePanel win={redaccion} /></div>
              </>
            ) : <MessageView />}
          </div>
        </div>
      )}
      <ToastContainer />
    </div>
  );
}
