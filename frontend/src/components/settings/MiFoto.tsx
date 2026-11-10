/**
 * MiFoto.tsx — Configuración → Mi foto (05/11/2026; regla «la foto de Raíces manda», 09/11/2026).
 * Foto de perfil que ven los compañeros en la burbuja, la lista, el correo abierto, el Directorio y el
 * autocompletado. La base es la de Raíces (nómina); la persona puede poner otra para el correo, que se ve
 * para todos hasta que cambie su foto en Raíces (esa siempre tiene prioridad).
 */
import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { useAuthStore } from '../../store/authStore';
import { avisarMiFotoActualizada } from '../../hooks/useMiPerfil';
import { showToast } from '../common/Toast';

interface EstadoFoto {
  photo_url: string;
  foto_raices_url?: string;
  foto_propia_url?: string;
  origen_actual?: '' | 'nomina' | 'propio';
  la_gestiona_nomina: boolean;
  display_name?: string;
}

const VACIO: EstadoFoto = { photo_url: '', la_gestiona_nomina: false };

export default function MiFoto() {
  const [estado, setEstado] = useState<EstadoFoto | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const correo = useAuthStore((s) => s.user?.username || '');

  const cargar = () =>
    api.get<EstadoFoto>('/contacts/foto').then(setEstado).catch(() => setEstado(VACIO));
  useEffect(() => { cargar(); }, []);

  const subir = async (archivo: File) => {
    if (archivo.size > 5 * 1024 * 1024) { showToast('La imagen pesa más de 5 MB'); return; }
    setOcupado(true);
    try {
      const fd = new FormData();
      fd.append('archivo', archivo);
      const res = await fetch('/api/contacts/foto', { method: 'POST', body: fd, credentials: 'include' });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.detail || 'No se pudo subir la foto');
      setEstado(cuerpo);
      avisarMiFotoActualizada(correo);
      showToast(cuerpo.la_gestiona_nomina
        ? 'Foto actualizada. Se verá en el correo hasta que cambie tu foto en Raíces.'
        : 'Foto actualizada');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'No se pudo subir la foto');
    } finally {
      setOcupado(false);
      if (input.current) input.current.value = '';
    }
  };

  const quitar = async () => {
    setOcupado(true);
    try {
      const r = await api.del<EstadoFoto>('/contacts/foto');
      setEstado(r && 'photo_url' in r ? r : await api.get<EstadoFoto>('/contacts/foto'));
      avisarMiFotoActualizada(correo);
      showToast(r?.foto_raices_url ? 'Vuelves a usar tu foto de Raíces' : 'Foto quitada');
    } catch { showToast('No se pudo quitar la foto'); }
    finally { setOcupado(false); }
  };

  const url = estado?.photo_url || '';
  const deRaices = !!estado?.la_gestiona_nomina;
  const propiaActiva = estado?.origen_actual === 'propio' && !!estado?.foto_propia_url;
  return (
    <div className="max-w-[560px]">
      <h3 className="text-[16px] font-semibold text-[#323130] mb-1">Mi foto</h3>
      <p className="text-[13px] text-[#605e5c] mb-4">
        Es la foto que ven tus compañeros junto a tu nombre: en la lista de correos, el correo abierto, Contactos → Directorio
        y al escribir tu dirección. Las fotos subidas aquí se recortan al centro y se guardan en 256 × 256.
      </p>
      <div className="flex items-center gap-5">
        <div className="w-[96px] h-[96px] rounded-full bg-[#f3f2f1] overflow-hidden flex items-center justify-center shrink-0 border border-[#e1dfdd]">
          {url
            ? <img src={url} alt="Mi foto" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
            : <span className="text-[12px] text-[#a19f9d]">Sin foto</span>}
        </div>
        <div className="flex flex-col gap-2">
          <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) subir(f); }} />
          <button disabled={ocupado} onClick={() => input.current?.click()}
            className="px-3 py-1.5 text-[13px] rounded bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
            {url ? 'Cambiar foto' : 'Subir foto'}
          </button>
          {propiaActiva && deRaices && (
            <button disabled={ocupado} onClick={quitar}
              className="px-3 py-1.5 text-[13px] rounded border border-[#c8c6c4] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50">
              Volver a la foto de Raíces
            </button>
          )}
          {propiaActiva && !deRaices && (
            <button disabled={ocupado} onClick={quitar}
              className="px-3 py-1.5 text-[13px] rounded border border-[#c8c6c4] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50">
              Quitar foto
            </button>
          )}
        </div>
      </div>
      {deRaices && (
        <p className="mt-4 text-[12px] text-[#605e5c] bg-[#fff4ce] border border-[#f0e6b8] rounded px-3 py-2">
          {propiaActiva
            ? 'Ahora se muestra la foto que pusiste aquí. Tu foto de Raíces (nómina) sigue guardada: si la cambian en Raíces, esa nueva foto reemplazará a esta automáticamente.'
            : 'Tu foto viene de Raíces (nómina). Puedes poner otra para el correo; se verá para todos hasta que cambie tu foto en Raíces, que siempre tiene prioridad.'}
        </p>
      )}
    </div>
  );
}
