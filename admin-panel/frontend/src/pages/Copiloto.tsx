import { useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

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
      <div className="flex justify-end">
        <SectionHelp
          titulo="Copiloto Maquita — seguridad"
          items={[
            { titulo: "Qué hace esta sección", desc: "Es un asistente de IA para el administrador: le preguntas en lenguaje natural sobre la seguridad del correo y responde analizando datos reales del sistema (cuentas, 2FA, phishing, etc.)." },
            { titulo: "Preguntas sugeridas", desc: "Los botones redondos son ejemplos listos: un clic envía esa pregunta directamente y muestra la respuesta abajo." },
            { titulo: "Pregunta libre", desc: "En el cuadro de texto puedes escribir cualquier consulta de seguridad con tus propias palabras." },
            { titulo: "Periodo analizado", desc: "El selector de días (7, 30 o 90) define cuánto historial de eventos usa la IA para responder." },
            { titulo: "Privacidad y alcance", desc: "Responde la IA local del servidor (no salen datos a terceros). Es solo consulta: no ejecuta cambios ni acciones en el sistema." },
          ]}
        />
      </div>
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-160">Copiloto Maquita — seguridad</h1>
        <p className="text-sm text-ms-gray-110">Pregunta en lenguaje natural sobre la seguridad del correo. Responde la IA local (Qwen) con base en datos reales del sistema.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {SUGERENCIAS.map((sg, i) => (
          <button key={i} onClick={() => ask(sg)}
            title="Envía esta pregunta sugerida al copiloto de inmediato y muestra la respuesta de la IA abajo. Solo consulta, no cambia nada."
            className="text-xs px-3 py-1.5 rounded-full border border-ms-gray-30 text-ms-gray-130 hover:bg-ms-gray-10">{sg}</button>
        ))}
      </div>
      <div className="flex gap-2 items-end">
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={2} placeholder="Escribe tu pregunta de seguridad…"
          title="Escribe aquí tu pregunta de seguridad en lenguaje natural (ej. ¿qué cuentas debería revisar?). Luego pulsa Preguntar."
          className="flex-1 px-3 py-2 border border-ms-gray-30 rounded text-sm resize-none" />
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} title="Periodo de historial que analizará la IA para responder: últimos 7, 30 o 90 días de eventos del sistema." className="border border-ms-gray-30 rounded px-2 py-2 text-sm">
          <option value={7}>7 días</option><option value={30}>30 días</option><option value={90}>90 días</option>
        </select>
        <button onClick={() => ask()} disabled={loading || !q.trim()}
          title="Envía la pregunta escrita a la IA local, que responde con base en los datos reales del periodo elegido. Solo consulta, no modifica el sistema."
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
