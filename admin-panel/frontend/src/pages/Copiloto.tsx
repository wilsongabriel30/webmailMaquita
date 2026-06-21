import { useState } from "react";
import { api } from "../api/client";

const SUGERENCIAS = [
  "¿Qué cuentas o riesgos debería revisar y por qué?",
  "¿Cómo está la cobertura de 2FA y qué recomiendas?",
  "¿Hubo actividad de phishing o enlaces peligrosos?",
  "Resume la postura de seguridad del correo este mes.",
];

export function Copiloto() {
  const [q, setQ] = useState("");
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");

  const ask = async (question?: string) => {
    const text = (question ?? q).trim();
    if (!text) return;
    setQ(text); setLoading(true); setAnswer("");
    try {
      const r = await api.post<{ answer: string }>("/copiloto/ask", { question: text, days });
      setAnswer(r?.answer || "(sin respuesta)");
    } catch { setAnswer("Error al consultar."); }
    setLoading(false);
  };

  return (
    <div className="p-6 max-w-3xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-160">Copiloto Maquita — seguridad</h1>
        <p className="text-sm text-ms-gray-110">Pregunta en lenguaje natural sobre la seguridad del correo. Responde la IA local (Qwen) con base en datos reales del sistema.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {SUGERENCIAS.map((sg, i) => (
          <button key={i} onClick={() => ask(sg)}
            className="text-xs px-3 py-1.5 rounded-full border border-ms-gray-30 text-ms-gray-130 hover:bg-ms-gray-10">{sg}</button>
        ))}
      </div>
      <div className="flex gap-2 items-end">
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={2} placeholder="Escribe tu pregunta de seguridad…"
          className="flex-1 px-3 py-2 border border-ms-gray-30 rounded text-sm resize-none" />
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="border border-ms-gray-30 rounded px-2 py-2 text-sm">
          <option value={7}>7 días</option><option value={30}>30 días</option><option value={90}>90 días</option>
        </select>
        <button onClick={() => ask()} disabled={loading || !q.trim()}
          className="text-white text-sm px-4 py-2 rounded disabled:opacity-50" style={{ backgroundColor: "#0078d4" }}>
          {loading ? "Pensando…" : "Preguntar"}
        </button>
      </div>
      {answer && (
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4">
          <pre className="text-sm whitespace-pre-wrap text-ms-gray-160" style={{ fontFamily: "inherit" }}>{answer}</pre>
        </div>
      )}
    </div>
  );
}
