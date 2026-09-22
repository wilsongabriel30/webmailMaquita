import { useEffect, useState } from "react";
import { api } from "../../api/client";

// QR de aprovisionamiento (control completo): se muestra en pantalla para que el teléfono restaurado
// de fábrica lo lea en la bienvenida (tocar 6 veces). El servidor lo genera con la huella del APK
// publicado y, si el código está en claro (recién creado o asignado), lo mete dentro para que la app se
// registre sola. Ventana a pantalla completa, con el QR grande a la izquierda y los pasos a la derecha.

const PASOS = [
  "Restablecer el teléfono de fábrica (o encender uno nuevo). No iniciar sesión en ninguna cuenta.",
  "En la primera pantalla de bienvenida (idioma), tocar 6 veces seguidas en un espacio vacío. Aparece «Configurar dispositivo de empresa» y se abre la cámara.",
  "Conectar al wifi si lo pide y leer este QR en la pantalla. El teléfono descarga Maquita Mail, verifica su huella y la instala como administradora.",
  "Terminar el asistente. Abrir Maquita Mail, iniciar sesión con el correo de la persona y entrar a «Mi equipo».",
  "Comprobar en este panel que el teléfono aparece como «Administrado», con serie e IMEI leídos por la app.",
];

export function QrAprovisionamiento({ codigo, codigoId, etiqueta, onCerrar }: { codigo?: string; codigoId?: number; etiqueta: string; onCerrar: () => void }) {
  const [d, setD] = useState<{ svg: string; con_codigo: boolean; version?: string } | null>(null);
  const [error, setError] = useState("");
  const [wifi, setWifi] = useState({ ssid: "", clave: "" });
  const [wifiUsado, setWifiUsado] = useState({ ssid: "", clave: "" });
  useEffect(() => { setD(null); api.post<{ svg: string; con_codigo: boolean; version?: string }>("/dispositivos/codigos/qr", { codigo, codigo_id: codigoId, wifi_ssid: wifiUsado.ssid, wifi_clave: wifiUsado.clave }).then(setD).catch((e) => setError(e.message)); }, [codigo, codigoId, wifiUsado]);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 overflow-y-auto" onClick={onCerrar}>
      <style>{`.qr-aprov{width:100%;height:auto;display:block} @media print{body *{visibility:hidden} #qr-imprimir,#qr-imprimir *{visibility:visible} #qr-imprimir{position:fixed;inset:0;background:#fff;box-shadow:none;max-width:none}}`}</style>
      <div id="qr-imprimir" className="bg-white rounded-lg shadow-xl w-[min(96vw,1000px)] mx-auto my-6 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-xl font-semibold text-ms-gray-130">Enrolar un teléfono con control completo</h2>
            <p className="text-sm text-ms-gray-60 mt-1">{etiqueta ? `${etiqueta} · ` : ""}App {d?.version || "publicada"}{d ? (d.con_codigo ? " · el código va dentro del QR: la app se registra sola" : " · sin código: al terminar, escribirlo en «Mi equipo»") : ""}</p>
          </div>
          <button onClick={onCerrar} className="text-2xl leading-none text-ms-gray-60 hover:text-ms-gray-130 print:hidden" aria-label="Cerrar">×</button>
        </div>
        <div className="grid md:grid-cols-[minmax(280px,420px)_1fr] gap-8 items-start">
          <div className="bg-white border border-ms-gray-30 rounded-lg p-4">
            {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
            {d ? <div dangerouslySetInnerHTML={{ __html: d.svg }} /> : !error && <div className="text-sm text-ms-gray-60 p-16 text-center">Generando el QR…</div>}
            <p className="text-xs text-ms-gray-60 mt-3 text-center">Mostrar este QR en la pantalla o impreso, a unos 20 cm de la cámara del teléfono.</p>
            <div className="mt-3 border-t border-ms-gray-20 pt-3 print:hidden">
              <div className="text-xs font-medium text-ms-gray-90 mb-1">Wifi de la sede (opcional): el teléfono se conecta solo durante el alta</div>
              <div className="flex flex-wrap gap-2">
                <input value={wifi.ssid} onChange={(e) => setWifi({ ...wifi, ssid: e.target.value })} placeholder="Nombre de la red" className="flex-1 min-w-[120px] px-2 py-1 text-xs border border-ms-gray-40 rounded" />
                <input value={wifi.clave} onChange={(e) => setWifi({ ...wifi, clave: e.target.value })} placeholder="Clave" type="password" className="flex-1 min-w-[100px] px-2 py-1 text-xs border border-ms-gray-40 rounded" />
                <button onClick={() => setWifiUsado(wifi)} className="px-2.5 py-1 text-xs border border-ms-gray-40 rounded hover:bg-ms-gray-10">Incluir en el QR</button>
              </div>
              {wifiUsado.ssid && <div className="text-xs text-ms-gray-60 mt-1">El QR incluye la red «{wifiUsado.ssid}» (la clave va dentro del QR: no lo deje impreso a la vista).</div>}
            </div>
          </div>
          <div>
            <h3 className="text-base font-semibold mb-3">Pasos</h3>
            <ol className="space-y-3">
              {PASOS.map((t, i) => <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-ms-gray-130">
                <span className="shrink-0 w-7 h-7 rounded-full bg-ms-blue text-white flex items-center justify-center text-sm font-semibold">{i + 1}</span>
                <span>{i === 3 && d ? (d.con_codigo ? "Terminar el asistente. Abrir Maquita Mail, iniciar sesión con el correo de la persona y entrar a «Mi equipo»: se registra solo (si pide el código, escribirlo)." : t + " Escribir el código de este enrolamiento y tocar «Registrar este teléfono».") : t}</span>
              </li>)}
            </ol>
            <div className="mt-5 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 leading-relaxed">
              <strong>Si al tocar 6 veces no sale nada:</strong> ese teléfono no tiene el asistente de Google (Huawei y Honor sin servicios Google). En ese modelo no hay control completo por QR; queda el modo limitado.<br />
              <strong>El QR vale para la versión publicada ahora.</strong> Cuando se publique otra versión de la app, vuelva a abrir esta ventana.
            </div>
            <div className="flex gap-2 pt-5 print:hidden">
              <button onClick={() => window.print()} className="px-4 py-2 text-sm border border-ms-gray-40 rounded hover:bg-ms-gray-10">Imprimir</button>
              <button onClick={onCerrar} className="px-4 py-2 text-sm bg-ms-blue text-white rounded hover:bg-ms-blue-dark">Cerrar</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
