import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface AgentInfo { name: string; descripcion: string; }

export function Agents() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, any>>({});
  const [userInput, setUserInput] = useState("");

  useEffect(() => {
    api.get<{ agents: AgentInfo[] }>("/agents/list").then((r) => setAgents(r?.agents || [])).catch(() => {});
  }, []);

  const run = async (name: string, apply: boolean, user?: string) => {
    if (apply && !confirm(`El agente "${name}" APLICARÁ acciones (puede contener cuentas). ¿Continuar?`)) return;
    setRunning(name);
    try {
      const r = await api.post<any>("/agents/run", { name, apply, user: user || "" });
      setResults((p) => ({ ...p, [name]: r }));
    } catch {
      setResults((p) => ({ ...p, [name]: { error: "Error al ejecutar." } }));
    }
    setRunning(null);
  };

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Agentes autónomos (IA local)"
          items={[
            { titulo: "Qué hace esta sección", desc: "Lista agentes de IA que investigan y auditan el servidor de correo (seguridad, bandejas, etc.) usando el modelo local; cada tarjeta es un agente distinto con su descripción." },
            { titulo: "Ejecutar (simulación)", desc: "Modo seguro por defecto: el agente analiza y muestra hallazgos, resumen y acciones propuestas, pero NO cambia nada en el sistema." },
            { titulo: "Aplicar", desc: "Solo el agente de seguridad lo ofrece. Ejecuta de verdad las acciones propuestas (puede contener/deshabilitar cuentas comprometidas). Pide confirmación antes y marca cada acción como aplicada." },
            { titulo: "Agente de bandeja", desc: "Requiere escribir el buzón a analizar en el campo junto al botón; clasifica los correos en acción requerida, posible spam, newsletter e informativos." },
            { titulo: "Resultados", desc: "Bajo cada agente verás el resumen, datos verificados (facts), el análisis de la IA y la lista de elementos o acciones. Los resultados no se guardan: se pierden al salir de la página." },
          ]}
        />
      </div>
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
              <div className="flex gap-2 items-center">
                {ag.name === "bandeja" && (
                  <input value={userInput} onChange={(e) => setUserInput(e.target.value)} placeholder="buzon@maquita.org"
                    title="Correo del buzón que analizará el agente de bandeja. Obligatorio para este agente; el análisis es de solo lectura."
                    className="text-sm px-2 py-1.5 border border-ms-gray-30 rounded w-56" />
                )}
                <button onClick={() => run(ag.name, false, ag.name === "bandeja" ? userInput : undefined)} disabled={running === ag.name}
                  title="Ejecuta el agente en modo simulación: investiga con la IA local y muestra hallazgos y acciones propuestas SIN aplicar ningún cambio en el sistema."
                  className="text-sm px-3 py-1.5 rounded border border-ms-gray-30 disabled:opacity-50">
                  {running === ag.name ? "Ejecutando…" : "Ejecutar (simulación)"}
                </button>
                {ag.name === "seguridad" && (
                  <button onClick={() => run(ag.name, true)} disabled={running === ag.name}
                    title="PELIGRO: ejecuta el agente de seguridad en modo real. Aplica de verdad las acciones que decida (puede contener o bloquear cuentas comprometidas). Pide confirmación antes de ejecutar."
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
                {(res.items || []).length > 0 && (
                  <ul className="text-xs space-y-1">
                    {res.items.map((it: any, i: number) => {
                      const c = it.categoria === "accion_requerida" ? { bg: "#fde7e9", t: "#a4262c", l: "acción" } :
                        it.categoria === "probable_spam" ? { bg: "#fff4ce", t: "#7a6400", l: "spam?" } :
                        it.categoria === "newsletter" ? { bg: "#eef2f8", t: "#605e5c", l: "newsletter" } :
                        { bg: "#f3f2f1", t: "#605e5c", l: "info" };
                      return (
                        <li key={i} className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded" style={{ background: c.bg, color: c.t }}>{c.l}</span>
                          <span className="text-ms-gray-110">{it.prioridad}</span>
                          <span className="text-ms-gray-160 truncate">{it.subject}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
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
