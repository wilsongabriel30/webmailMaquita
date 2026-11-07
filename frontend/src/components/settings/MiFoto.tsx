/**
 * MiFoto.tsx — Configuración → Mi foto (05/11/2026).
 * Foto de perfil que ven los compañeros en el Directorio de Contactos y en las listas.
 * Donde la nómina (Raíces) tiene la foto institucional, esa manda y aquí solo se informa.
 */
import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

interface EstadoFoto { photo_url: string; la_gestiona_nomina: boolean; display_name?: string }

export default function MiFoto() {
  const [estado, setEstado] = useState<EstadoFoto | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const cargar = () =>
    api.get<EstadoFoto>('/contacts/foto').then(setEstado)
      .catch(() => setEstado({ photo_url: '', la_gestiona_nomina: false }));
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
      showToast(cuerpo.la_gestiona_nomina
        ? 'Foto guardada. La foto institucional la gestiona Talento Humano y es la que se muestra.'
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
    try { await api.del('/contacts/foto'); await cargar(); showToast('Foto quitada'); }
    catch { showToast('No se pudo quitar la foto'); }
    finally { setOcupado(false); }
  };

  const url = estado?.photo_url || '';
  return (
    <div className="max-w-[560px]">
      <h3 className="text-[16px] font-semibold text-[#323130] mb-1">Mi foto</h3>
      <p className="text-[13px] text-[#605e5c] mb-4">
        Es la foto que ven tus compañeros en Contactos → Directorio y junto a tu nombre. Se recorta al centro y se guarda en 256 × 256.
      </p>
      <div className="flex items-center gap-5">
        <div className="w-[96px] h-[96px] rounded-full bg-[#f3f2f1] overflow-hidden flex items-center justify-center shrink-0 border border-[#e1dfdd]">
          {url
            ? <img src={url} alt="Mi foto" className="w-full h-full object-cover" />
            : <span className="text-[12px] text-[#a19f9d]">Sin foto</span>}
        </div>
        <div className="flex flex-col gap-2">
          <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) subir(f); }} />
          <button disabled={ocupado} onClick={() => input.current?.click()}
            className="px-3 py-1.5 text-[13px] rounded bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
            {url ? 'Cambiar foto' : 'Subir foto'}
          </button>
          {url && !estado?.la_gestiona_nomina && (
            <button disabled={ocupado} onClick={quitar}
              className="px-3 py-1.5 text-[13px] rounded border border-[#c8c6c4] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50">
              Quitar foto
            </button>
          )}
        </div>
      </div>
      {estado?.la_gestiona_nomina && (
        <p className="mt-4 text-[12px] text-[#605e5c] bg-[#fff4ce] border border-[#f0e6b8] rounded px-3 py-2">
          Tu foto institucional viene de la nómina y la gestiona Talento Humano. Si quieres cambiarla, pídeselo a ellos.
        </p>
      )}
    </div>
  );
}
