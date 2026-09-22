import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';

// «Teléfono extraviado»: la persona ve la última ubicación conocida de su teléfono institucional,
// en lenguaje llano (cuándo, margen, ver en mapa), y puede pedir «Ubicar ahora» o «Hacer sonar».
// Nada técnico: sin IP, sin redes, sin fuentes.

interface Posicion { lat: number; lon: number; precision_m?: number | null; cuando: string; margen: string; minutos: number }
interface Tel { id: number; nombre: string; estado: string; ultimo_contacto?: string | null; ubicacion_permitida: boolean; posicion: Posicion | null; buscando: boolean }

const cuando = (iso: string) => {
  const d = new Date(iso); const hoy = new Date();
  const hora = d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === hoy.toDateString() ? `hoy a las ${hora}` : `${d.toLocaleDateString('es-EC')} a las ${hora}`;
};

export function MiTelefonoExtraviado() {
  const [lista, setLista] = useState<Tel[] | null>(null);
  const [aviso, setAviso] = useState('');
  const cargar = useCallback(async () => { try { setLista((await api.get<{ equipos: Tel[] }>('/settings/mi-equipo/ubicacion')).equipos); } catch { setLista([]); } }, []);
  useEffect(() => { cargar(); const t = setInterval(cargar, 30000); return () => clearInterval(t); }, [cargar]);

  const pedir = async (id: number, que: 'localizar' | 'sonar') => {
    setAviso('');
    try { await api.post(`/settings/mi-equipo/${id}/${que}`, {}); setAviso(que === 'sonar' ? 'Listo: el teléfono sonará 2 minutos aunque esté en silencio.' : 'Listo: le pedimos la ubicación. Suele tardar menos de un minuto si el teléfono tiene internet; esta pantalla se actualiza sola.'); cargar(); }
    catch (e: any) { setAviso(e.message); }
  };

  if (!lista || !lista.length) return null;
  return (
    <div className="mt-8">
      <h3 className="text-lg font-semibold">Teléfono extraviado</h3>
      <p className="text-sm text-[#605e5c] mt-1">Si no encuentras tu teléfono institucional, aquí está lo último que sabemos de él.</p>
      {aviso && <div className="mt-3 text-sm px-3 py-2 rounded bg-[#deecf9] text-[#004578]">{aviso}</div>}
      {lista.map((t) => (
        <div key={t.id} className="mt-3 border border-[#edebe9] rounded p-4">
          <div className="font-medium">{t.nombre}{t.estado === 'perdido' && <span className="ml-2 text-xs px-2 py-0.5 rounded bg-red-50 text-red-700">declarado perdido</span>}</div>
          {t.posicion ? (
            <div className="mt-2 text-sm">
              <div><strong>Última ubicación conocida:</strong> {cuando(t.posicion.cuando)} ({t.posicion.margen}).</div>
              <div className="text-xs text-[#605e5c] mt-1">La ubicación de un celular es aproximada: el teléfono puede estar en cualquier punto dentro de ese margen.</div>
              <div className="mt-2 flex flex-wrap gap-3 text-sm">
                <a className="text-[#0078d4] hover:underline" target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${t.posicion.lat},${t.posicion.lon}`}>Ver en Google Maps</a>
                <a className="text-[#0078d4] hover:underline" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${t.posicion.lat}&mlon=${t.posicion.lon}#map=18/${t.posicion.lat}/${t.posicion.lon}`}>Ver en OpenStreetMap</a>
              </div>
            </div>
          ) : (
            <div className="mt-2 text-sm text-[#605e5c]">
              {t.ubicacion_permitida ? 'Todavía no tenemos una ubicación de este teléfono. Pulsa «Ubicar ahora».' : 'Este teléfono no guarda su ubicación: para activarla hay que firmar la política de uso con Tecnología. Si lo perdiste, avisa a Tecnología para declararlo perdido y ubicarlo.'}
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={() => pedir(t.id, 'localizar')} disabled={t.buscando} className="px-3 py-1.5 rounded bg-[#0078d4] text-white text-sm hover:bg-[#106ebe] disabled:opacity-50">{t.buscando ? 'Buscando…' : 'Ubicar ahora'}</button>
            <button onClick={() => pedir(t.id, 'sonar')} className="px-3 py-1.5 rounded border border-[#c8c6c4] text-sm hover:bg-[#f3f2f1]">Hacer sonar</button>
          </div>
          {t.ultimo_contacto && <div className="mt-2 text-xs text-[#605e5c]">Último reporte del teléfono: {cuando(t.ultimo_contacto)}. Si hace mucho, puede estar apagado o sin internet.</div>}
        </div>
      ))}
      <p className="mt-2 text-xs text-[#605e5c]">Si no aparece o no responde, llama a Tecnología: pueden declararlo perdido y, con el resto de teléfonos de Maquita, ayudar a encontrarlo.</p>
    </div>
  );
}
