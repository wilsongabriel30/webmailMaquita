import { useEffect, useState } from "react";
import { api } from "../api/client";

interface AgentInfo { name: string; descripcion: string; }

export function Agents() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, any>>({});

  useEffect(() => {
    api.get<{ agents: AgentInfo[] }>("/agents/list").then((r) => setAgents(r?.agents || [])).catch(() => {});
  }, []);

  const run = async (name: string, apply: boolean) => {
    if (apply && !confirm(`El agente "${name}" APLICARÁ acciones (puede contener cuentas). ¿Continuar?`)) return;
    setRunning(name);
    try {
      const r = await api.post<any>("/agents/run", { name, apply });
      setResults((p) => ({ ...p, [name]: r }));
    } catch {
      setResults((p) => ({ ...p, [name]: { error: "Error al ejecutar." } }));
    }
    setRunning(null);
  };

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-160">Agentes autónomos (IA local)</h1>
        <p className="text-sm text-ms-gray-110">Investigan, auditan y actúan con la IA local (Qwen). Seguro por defecto: ejecutan en simulación; "Aplicar" pide confirmación.</p>
      </div>
      {!agents.length && <div className="text-sm text-ms-gray-110">Cargando agentes…</div>}
      {agents.map((ag) => {
        const res = results[ag.name];
        return (
          <div key={ag.name} className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <h2 className="text-sm font-semibold text-ms-gray-160 capitalize">{ag.name}</h2>
                <p className="text-xs text-ms-gray-110">{ag.descripcion}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => run(ag.name, false)} disabled={running === ag.name}
                  className="text-sm px-3 py-1.5 rounded border border-ms-gray-30 disabled:opacity-50">
                  {running === ag.name ? "Ejecutando…" : "Ejecutar (simulación)"}
                </button>
                {ag.name === "seguridad" && (
                  <button onClick={() => run(ag.name, true)} disabled={running === ag.name}
                    className="text-white text-sm px-3 py-1.5 rounded disabled:opacity-50" style={{ backgroundColor: "#a4262c" }}>
                    Aplicar
                  </button>
                )}
              </div>
            </div>
            {res && (res.error ? (
              <div className="text-sm text-red-600">{res.error}</div>
            ) : (
              <div className="border-t border-ms-gray-30 pt-3 space-y-2 text-sm">
                <div className="text-ms-gray-160 font-medium">{res.summary}</div>
                {res.facts && (
                  <div className="text-xs text-ms-gray-110 flex flex-wrap gap-x-4 gap-y-1">
                    {Object.entries(res.facts).map(([k, v]) => (
                      <span key={k}><span className="font-mono">{k}</span>: {String(v)}</span>
                    ))}
                  </div>
                )}
                {res.ai && <pre className="text-xs whitespace-pre-wrap p-3 rounded text-ms-gray-160" style={{ backgroundColor: "#faf9f8" }}>{res.ai}</pre>}
                {(res.actions || []).length > 0 && (
                  <ul className="text-xs space-y-1">
                    {res.actions.map((act: any, i: number) => (
                      <li key={i}>
                        <span className="px-1.5 py-0.5 rounded" style={{ background: act.applied ? "#fde7e9" : "#fff4ce", color: act.applied ? "#a4262c" : "#7a6400" }}>{act.type}</span>{" "}
                        <span className="font-medium">{act.target}</span> — {act.detail}{act.applied && <span style={{ color: "#a4262c" }}> (aplicado)</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
