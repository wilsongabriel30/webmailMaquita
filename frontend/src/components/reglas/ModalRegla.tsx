import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { EVENTO_MODAL_REGLA, type PeticionModalRegla } from '../../lib/reglas/abrirModalRegla';
import { cuerpoParaGuardar, faltaEnRegla, type Regla } from '../../lib/reglas/tipos';
import { EditorRegla } from './EditorRegla';

/* Ventana «Regla de correo»: crea o edita una regla y la guarda en el servidor.
   ModalReglaHost se monta una vez en la aplicación y abre la ventana cuando alguien llama a abrirModalRegla(). */

function motivoServidor(err: unknown): string {
  const m = err instanceof Error ? err.message : '';
  return m && !/^HTTP \d+$/.test(m) && m !== 'Session expired' ? m : '';
}

export function ModalRegla({ peticion, onCerrar }: { peticion: PeticionModalRegla; onCerrar: () => void }) {
  const [regla, setRegla] = useState<Regla>(peticion.regla);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const edita = peticion.indice !== undefined;
  const falta = faltaEnRegla(regla);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    document.addEventListener('keydown', esc);
    return () => document.removeEventListener('keydown', esc);
  }, [onCerrar]);

  const guardar = async () => {
    if (falta) { setError(falta); return; }
    setGuardando(true); setError('');
    try {
      const cuerpo = cuerpoParaGuardar(regla);
      const guardada = edita
        ? await api.put<Regla>(`/sieve/filters/${peticion.indice}`, cuerpo)
        : await api.post<Regla>('/sieve/filters', cuerpo);
      showToast(edita ? 'Regla guardada' : `Regla «${regla.name.trim()}» creada: se aplicará a los correos que lleguen desde ahora`);
      peticion.alGuardar?.(guardada);
      onCerrar();
    } catch (err) {
      setError(motivoServidor(err) || 'No se pudo guardar la regla. Inténtelo de nuevo.');
    } finally { setGuardando(false); }
  };

  return createPortal(
    <div className="fixed inset-0 z-[9000] flex items-center justify-center bg-black/40 p-4" onMouseDown={e => { if (e.target === e.currentTarget) onCerrar(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="titulo-modal-regla"
        className="bg-[#faf9f8] rounded-lg shadow-2xl w-full max-w-[760px] max-h-[92vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#edebe9] bg-white rounded-t-lg">
          <h2 id="titulo-modal-regla" className="text-[16px] font-semibold text-[#323130]">{edita ? 'Editar regla de correo' : 'Nueva regla de correo'}</h2>
          <button type="button" onClick={onCerrar} aria-label="Cerrar" className="w-8 h-8 flex items-center justify-center rounded hover:bg-[#edebe9] text-[#605e5c]">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="px-5 py-4 overflow-y-auto">
          <EditorRegla regla={regla} onCambio={r => { setRegla(r); setError(''); }} />
        </div>
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-t border-[#edebe9] bg-white rounded-b-lg">
          <span role="alert" className="text-sm text-[#a4262c] min-h-[1.25rem]">{error}</span>
          <div className="flex gap-2 shrink-0">
            <button type="button" onClick={onCerrar} className="px-4 py-2 text-sm border border-[#8a8886] rounded hover:bg-[#edebe9]">Cancelar</button>
            <button type="button" onClick={guardar} disabled={guardando} title={falta || undefined}
              className="px-4 py-2 text-sm bg-[#0078d4] text-white rounded hover:bg-[#106ebe] disabled:opacity-60">
              {guardando ? 'Guardando…' : edita ? 'Guardar cambios' : 'Crear regla'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function ModalReglaHost() {
  const [peticion, setPeticion] = useState<PeticionModalRegla | null>(null);
  useEffect(() => {
    const abrir = (e: Event) => setPeticion((e as CustomEvent<PeticionModalRegla>).detail);
    window.addEventListener(EVENTO_MODAL_REGLA, abrir);
    return () => window.removeEventListener(EVENTO_MODAL_REGLA, abrir);
  }, []);
  const cerrar = useCallback(() => setPeticion(null), []);
  if (!peticion) return null;
  return <ModalRegla key={`${peticion.indice ?? 'nueva'}-${peticion.regla.name}`} peticion={peticion} onCerrar={cerrar} />;
}
