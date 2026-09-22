import { useEffect, useState } from "react";
import { api } from "../../api/client";

// QR de aprovisionamiento (control completo): se muestra en pantalla para que el teléfono restaurado
// de fábrica lo lea en la bienvenida (tocar 6 veces). El servidor lo genera con la huella del APK
// publicado y, si el código está en claro (recién creado o asignado), lo mete dentro para que la app se
// registre sola.

export function QrAprovisionamiento({ codigo, codigoId, etiqueta, onCerrar }: { codigo?: string; codigoId?: number; etiqueta: string; onCerrar: () => void }) {
  const [d, setD] = useState<{ svg: string; con_codigo: boolean; version?: string } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.post<{ svg: string; con_codigo: boolean; version?: string }>("/dispositivos/codigos/qr", { codigo, codigo_id: codigoId }).then(setD).catch((e) => setError(e.message)); }, [codigo, codigoId]);

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onCerrar}>
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full p-5 grid md:grid-cols-2 gap-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex flex-col items-center">
          {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
          {d ? <div className="w-full max-w-[360px]" dangerouslySetInnerHTML={{ __html: d.svg }} /> : !error && <div className="text-sm text-ms-gray-60 p-10">Generando…</div>}
          {d && <p className="text-xs text-ms-gray-60 mt-2 text-center">App {d.version || "publicada"} · {d.con_codigo ? "con el código dentro: la app se registra sola" : "sin código: escribirlo en la app al terminar"}{etiqueta ? ` · ${etiqueta}` : ""}</p>}
        </div>
        <div className="text-sm space-y-2">
          <h3 className="text-base font-semibold">Enrolar un teléfono con control completo</h3>
          <ol className="list-decimal pl-5 space-y-1.5">
            <li>Restablecer el teléfono de fábrica (o encender uno nuevo). No iniciar sesión en ninguna cuenta.</li>
            <li>En la primera pantalla de bienvenida (idioma), <strong>tocar 6 veces seguidas en un espacio vacío</strong>. Sale «Configurar dispositivo de empresa» y abre la cámara.</li>
            <li>Conectar al wifi si lo pide y <strong>leer este QR</strong> en la pantalla. El teléfono descarga Maquita Mail, verifica su huella y la instala como administradora.</li>
            <li>Terminar el asistente. Abrir Maquita Mail, iniciar sesión con el correo de la persona y entrar a «Mi equipo»: {d?.con_codigo ? "se registra solo (si no, escribir el código)." : "escribir el código de este enrolamiento y «Registrar este teléfono»."}</li>
            <li>Comprobar aquí que aparece como <strong>Administrado</strong>, con serie e IMEI leídos por la app.</li>
          </ol>
          <p className="text-xs text-ms-gray-60">Si al tocar 6 veces no sale nada, ese teléfono no tiene el asistente de Google (Huawei/Honor sin servicios Google): solo queda el modo limitado. El QR vale para la versión publicada ahora; al publicar otra, vuelva a abrirlo.</p>
          <div className="flex gap-2 pt-2">
            <button onClick={() => window.print()} className="px-3 py-1.5 text-sm border border-ms-gray-40 rounded hover:bg-ms-gray-10">Imprimir</button>
            <button onClick={onCerrar} className="px-3 py-1.5 text-sm bg-ms-blue text-white rounded hover:bg-ms-blue-dark">Cerrar</button>
          </div>
        </div>
      </div>
    </div>
  );
}
