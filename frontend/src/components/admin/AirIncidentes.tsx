import { useState } from 'react';
import { api } from '../../api/client';

interface Incident {
  username: string;
  severity?: string;
  reasons?: string[];
  rationale?: string;
  responded?: boolean;
  signals?: { score?: number; [k: string]: unknown };
  ai?: { resumen?: string; summary?: string; recommendation?: string; [k: string]: unknown };
  [k: string]: unknown;
}

const SEV_COLOR: Record<string, string> = {
  high: 'bg-[#fde7e9] text-[#a4262c]',
  medium: 'bg-[#fff4ce] text-[#797775]',
  low: 'bg-[#eff6fc] text-[#0078d4]',
};

/**
 * AIR — Respuesta automática a incidentes. Investiga señales de riesgo (logins,
 * envíos, reglas) y muestra incidentes; permite CONTENER (bloquear) una cuenta
 * comprometida. El motor y la IA ya viven en el backend (/api/air/*).
 */
export function AirIncidentes() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [cargado, setCargado] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [hours, setHours] = useState(24);

  const investigar = async () => {
    setCargando(true);
    try {
      const r = await api.get<{ count: number; incidents: Incident[] }>(
        `/air/incidents?hours=${hours}&ai=true`
      );
      setIncidents(r?.incidents || []);
      setCargado(true);
    } catch {
      setIncidents([]);
      setCargado(true);
    } finally {
      setCargando(false);
    }
  };

  const contener = async (username: string) => {
    if (!confirm(`¿Contener la cuenta ${username}? Se bloqueará y se cerrará su sesión.`)) return;
    await api.post('/air/act', { username, action: 'lock' }).catch(() => {});
    investigar();
  };

  const resumenIA = (inc: Incident) =>
    inc.ai?.resumen || inc.ai?.summary || inc.ai?.recommendation || '';

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#323130]">AIR — Respuesta a incidentes</h2>
          <p className="text-sm text-[#605e5c]">
            Investiga señales de riesgo y contén cuentas comprometidas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-[#605e5c]">Últimas</label>
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="border border-[#8a8886] rounded px-2 py-1 text-sm"
          >
            <option value={6}>6 h</option>
            <option value={24}>24 h</option>
            <option value={72}>72 h</option>
            <option value={168}>7 días</option>
          </select>
          <button
            onClick={investigar}
            disabled={cargando}
            className="bg-[#0078d4] text-white text-sm font-medium rounded px-4 py-1.5 disabled:opacity-50"
          >
            {cargando ? 'Investigando...' : 'Investigar'}
          </button>
        </div>
      </div>

      {!cargado ? (
        <div className="text-sm text-[#605e5c]">
          Pulsa <b>Investigar</b> para analizar la actividad reciente.
        </div>
      ) : incidents.length === 0 ? (
        <div className="text-sm text-[#107c10] bg-[#dff6dd] rounded p-3">
          Sin incidentes en la ventana seleccionada.
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((inc, i) => (
            <div key={inc.username + i} className="border border-[#edebe9] rounded p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-[#323130]">{inc.username}</span>
                  <span
                    className={`text-xs rounded px-2 py-0.5 ${
                      SEV_COLOR[inc.severity || 'low'] || SEV_COLOR.low
                    }`}
                  >
                    {inc.severity || 'low'}
                  </span>
                  {typeof inc.signals?.score === 'number' && (
                    <span className="text-xs text-[#605e5c]">score {inc.signals.score}</span>
                  )}
                  {inc.responded && (
                    <span className="text-xs bg-[#dff6dd] text-[#107c10] rounded px-2 py-0.5">
                      ya contenido
                    </span>
                  )}
                </div>
                {!inc.responded && (
                  <button
                    onClick={() => contener(inc.username)}
                    className="bg-[#a4262c] text-white text-xs font-semibold rounded px-3 py-1.5 whitespace-nowrap"
                  >
                    Contener
                  </button>
                )}
              </div>
              {(inc.reasons?.length || inc.rationale) && (
                <ul className="mt-2 text-sm text-[#605e5c] list-disc list-inside">
                  {(inc.reasons || []).map((r, j) => (
                    <li key={j}>{r}</li>
                  ))}
                  {!inc.reasons?.length && inc.rationale && <li>{inc.rationale}</li>}
                </ul>
              )}
              {resumenIA(inc) && (
                <div className="mt-2 text-sm text-[#323130] bg-[#eff6fc] rounded p-2">
                  <b>IA:</b> {resumenIA(inc)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
