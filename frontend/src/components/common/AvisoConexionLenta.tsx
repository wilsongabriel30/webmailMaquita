// Franja «tu conexión está lenta» (08/10/2026). Distinta de OfflineBanner: aquí SÍ hay conexión y el servidor
// responde bien, pero la red de la persona tarda. Se le explica para que no refresque a mitad de una acción.
import { useEffect, useState } from "react";
import { estadoRed, type EstadoRed } from "../../lib/conexionLenta";
import { estadoConexion } from "../../lib/conexion";

const OCULTAR_MS = 10 * 60 * 1000;   // «Entendido» la oculta 10 minutos
const OFRECER_RECARGA_S = 45;        // tras tanto rato esperando, se ofrece recargar

export function AvisoConexionLenta() {
  const [estado, setEstado] = useState<EstadoRed>(estadoRed().estado);
  const [oculta, setOculta] = useState(false);
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    const h = () => { const e = estadoRed().estado; setEstado(e); if (e !== "esperando") setSegundos(0); };
    window.addEventListener("red-lenta-cambio", h);
    return () => window.removeEventListener("red-lenta-cambio", h);
  }, []);
  useEffect(() => {
    if (estado !== "esperando") return;
    const iv = setInterval(() => setSegundos(Math.round((Date.now() - estadoRed().esperandoDesde) / 1000) + 10), 1000);
    return () => clearInterval(iv);
  }, [estado]);

  // Sin conexión ya lo explica OfflineBanner; no se ponen dos franjas
  if (estado === "normal" || !estadoConexion().hayConexion) return null;
  if (estado === "lenta" && oculta) return null;

  const boton = { background: "rgba(255,255,255,.25)", border: "1px solid rgba(255,255,255,.6)", color: "#fff", borderRadius: 4, padding: "1px 8px", cursor: "pointer", fontSize: 12, marginLeft: 8 } as const;

  return (
    <div data-conexion-lenta role="status" aria-live="polite" className="text-white text-center py-2 px-4 text-sm font-medium shrink-0 flex items-center justify-center gap-2 flex-wrap" style={{ background: "#1f5f99" }}>
      {estado === "esperando" ? (
        <>
          <span>Tu conexión a internet está tardando en responder ({segundos} s). Seguimos esperando: no cierres ni recargues todavía.</span>
          {segundos >= OFRECER_RECARGA_S && <button style={boton} onClick={() => window.location.reload()}>Recargar la página</button>}
        </>
      ) : (
        <>
          <span>Tu conexión a internet está lenta. El servidor de correo funciona con normalidad: las acciones tardarán un poco más. Espera a que terminen antes de volver a hacer clic.</span>
          <button style={boton} onClick={() => { setOculta(true); setTimeout(() => setOculta(false), OCULTAR_MS); }}>Entendido</button>
        </>
      )}
    </div>
  );
}
