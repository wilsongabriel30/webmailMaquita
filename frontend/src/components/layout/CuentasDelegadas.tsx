// Cuentas delegadas en la barra lateral: una sección por cuenta que la persona tiene a su
// cargo, con sus carpetas y no leídos. Al elegir una carpeta, la bandeja pasa a esa cuenta;
// al redactar desde ahí, el correo sale con esa dirección (ver ComposePanel).
import { useEffect, useState } from 'react';
import { useMailStore } from '../../store/mailStore';
import { api } from '../../api/client';
import type { Folder } from '../../types';
import { etiquetaCarpeta, type Cuenta } from '../../lib/cuentas';

interface CuentaConCarpetas extends Cuenta { carpetas: (Folder & { cuenta?: string })[] }

const iconos: Record<string, string> = {
  inbox: 'M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4',
  sent: 'M12 19l9 2-9-18-9 18 9-2zm0 0v-8',
  drafts: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
  trash: 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16',
  junk: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
  archive: 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4',
  folder: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
};

export function CuentasDelegadas() {
  const currentFolder = useMailStore(s => s.currentFolder);
  const setCurrentFolder = useMailStore(s => s.setCurrentFolder);
  const setCuentas = useMailStore(s => s.setCuentas);
  const [cuentas, setLista] = useState<CuentaConCarpetas[]>([]);
  const [plegadas, setPlegadas] = useState<Record<string, boolean>>({});

  const cargar = () => {
    api.get<{ cuentas: CuentaConCarpetas[] }>('/mail/cuentas')
      // Las cuentas con envío se abren completas desde el selector de cuentas; aquí solo las de lectura.
      .then(r => { setLista(r.cuentas.filter(c => !c.propia && !c.puede_enviar)); setCuentas(r.cuentas); })
      .catch(() => { /* sin cuentas delegadas o servidor caído: no se muestra nada */ });
  };
  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 120000);
    const h = () => cargar();
    window.addEventListener('refresh-messages', h);
    return () => { clearInterval(t); window.removeEventListener('refresh-messages', h); };
  }, []);

  if (cuentas.length === 0) return null;

  return (
    <>
      {cuentas.map(c => {
        const plegada = !!plegadas[c.email];
        const noLeidos = c.carpetas.filter(f => f.type === 'inbox').reduce((n, f) => n + (f.unseen || 0), 0);
        return (
          <div key={c.email} className="mt-2">
            <button onClick={() => setPlegadas(p => ({ ...p, [c.email]: !plegada }))}
              title={`Cuenta compartida contigo: ${c.email}${c.puede_enviar ? ' (puedes enviar desde ella)' : ' (solo lectura)'}`}
              className="w-full flex items-center gap-1.5 px-2 py-1 text-[11px] font-semibold text-[#605e5c] uppercase tracking-wide hover:text-[#323130]">
              <svg className={`w-3 h-3 transition-transform ${plegada ? '-rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
              <span className="truncate normal-case text-[12px]">{c.nombre || c.email}</span>
              {noLeidos > 0 && <span className="ml-auto text-[10px] font-semibold text-[#0078d4]">{noLeidos}</span>}
            </button>
            {!plegada && (
              <div className="pb-1">
                <div className="px-3 pb-1 text-[10px] text-[#a19f9d] truncate" title={c.email}>{c.email}</div>
                {c.carpetas.map(f => {
                  const activa = currentFolder === f.name;
                  return (
                    <button key={f.name} onClick={() => setCurrentFolder(f.name)}
                      className={`w-full flex items-center gap-2 px-2 py-[4px] rounded-sm text-left ${activa ? 'bg-[#e1dfdd] text-[#201f1e] font-semibold' : 'text-[#323130] hover:bg-[#f3f2f1]'}`}
                      style={{ paddingLeft: '20px' }}>
                      <svg className="w-[15px] h-[15px] shrink-0 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={iconos[f.type] || iconos.folder} />
                      </svg>
                      <span className="truncate flex-1">{etiquetaCarpeta(f.name)}</span>
                      {f.unseen > 0 && <span className="text-[11px] font-semibold text-[#0078d4]">{f.unseen}</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
