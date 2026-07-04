import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Factor { label: string; points: number; }
interface User { user: string; score: number; level: string; factors: Factor[]; }
interface Data { users: User[]; counts: Record<string, number>; window: string; }

const LEVEL: Record<string, { label: string; cls: string; bar: string }> = {
  critico: { label: "Crítico", cls: "bg-red-100 text-red-700", bar: "#d13438" },
  alto: { label: "Alto", cls: "bg-orange-100 text-orange-700", bar: "#ca5010" },
  medio: { label: "Medio", cls: "bg-amber-100 text-amber-700", bar: "#ffb900" },
  bajo: { label: "Bajo", cls: "bg-ms-gray-20 text-ms-gray-130", bar: "#8a8886" },
};

export function InsiderRisk() {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [openUser, setOpenUser] = useState<string | null>(null);

  useEffect(() => {
    api.get<Data>("/insider-risk/users").then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  const users = data?.users || [];
  const counts = data?.counts || {};
  const maxScore = Math.max(1, ...users.map((u) => u.score));

  return (
    <div className="max-w-3xl">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Riesgo interno (Insider Risk)"
          items={[
            { titulo: "Para qué sirve", desc: "Calcula un puntaje de riesgo por usuario combinando señales reales del sistema: alertas de fuga de datos (DLP), cuentas comprometidas, accesos fallidos, marcas de cumplimiento y resultados de la simulación de phishing." },
            { titulo: "Tarjetas superiores", desc: "Cuentan cuántos usuarios hay en cada nivel de riesgo: crítico, alto, medio y bajo, en la ventana de tiempo indicada (por defecto 30 días)." },
            { titulo: "Lista de usuarios", desc: "Ordenada por riesgo. Cada fila muestra el nivel, una barra proporcional al puntaje y el total de puntos. Haz clic en una fila para ver el detalle." },
            { titulo: "Factores", desc: "Al desplegar un usuario se listan los eventos que suman puntos (incidentes, fallos) o los restan (buena conducta, como reportar phishing)." },
            { titulo: "Cómo actuar", desc: "El puntaje es orientativo y de solo lectura: no ejecuta acciones. Un valor alto sugiere capacitar al usuario, revisar su equipo o verificar si su cuenta fue comprometida." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Riesgo interno (Insider Risk)</h1>
      <p className="text-sm text-ms-gray-110 mb-4">
        Puntaje de riesgo por usuario, combinando señales reales: alertas de fuga de datos (DLP), cuentas
        comprometidas, accesos fallidos, marcas de cumplimiento y resultados de la simulación de phishing.
        Sirve para saber <b>a quién acompañar o capacitar</b>. (Últimos {data?.window || "30 días"}.)
      </p>

      <div className="grid grid-cols-4 gap-3 mb-6">
        {(["critico", "alto", "medio", "bajo"] as const).map((lv) => (
          <div key={lv} className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold" style={{ color: LEVEL[lv].bar }}>{counts[lv] || 0}</div>
            <div className="text-xs text-ms-gray-110 mt-1">{LEVEL[lv].label}</div>
          </div>
        ))}
      </div>

      <h2 className="text-base font-semibold text-ms-gray-160 mb-2">Usuarios por riesgo</h2>
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        {users.length === 0 ? (
          <div className="p-4 text-sm text-ms-gray-110">Sin riesgo detectado en nadie. 🎉</div>
        ) : users.map((u) => {
          const lv = LEVEL[u.level] || LEVEL.bajo;
          const open = openUser === u.user;
          return (
            <div key={u.user} className="border-t border-ms-gray-10 first:border-0">
              <div className="flex items-center gap-3 p-3 cursor-pointer hover:bg-ms-gray-10" onClick={() => setOpenUser(open ? null : u.user)} title="Despliega o contrae el detalle: los factores que suman o restan puntos al riesgo de este usuario. Solo consulta; no modifica nada.">
                <span className={`text-xs rounded px-2 py-0.5 shrink-0 ${lv.cls}`}>{lv.label}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ms-gray-160 truncate">{u.user}</div>
                  <div className="h-1.5 bg-ms-gray-20 rounded mt-1 overflow-hidden">
                    <div className="h-full rounded" style={{ width: `${Math.min(100, (u.score / maxScore) * 100)}%`, background: lv.bar }} />
                  </div>
                </div>
                <div className="text-lg font-bold shrink-0" style={{ color: lv.bar }}>{u.score}</div>
                <span className="text-ms-gray-110 text-xs shrink-0">{open ? "▲" : "▼"}</span>
              </div>
              {open && (
                <div className="px-4 pb-3 pt-0">
                  <div className="text-xs text-ms-gray-110 mb-1">Factores que suman al puntaje:</div>
                  <ul className="space-y-1">
                    {u.factors.map((f, i) => (
                      <li key={i} className="flex items-center justify-between text-sm bg-ms-gray-10 rounded px-3 py-1.5">
                        <span className="text-ms-gray-160">{f.label}</span>
                        <span className={`font-medium ${f.points < 0 ? "text-green-700" : "text-ms-gray-130"}`}>{f.points > 0 ? "+" : ""}{f.points}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-ms-gray-110 mt-3">
        El puntaje es orientativo. Un valor alto sugiere acompañar al usuario (capacitación, revisar su equipo,
        verificar si su cuenta fue comprometida). Reportar phishing <b>resta</b> puntos (buena conducta).
      </p>
    </div>
  );
}
