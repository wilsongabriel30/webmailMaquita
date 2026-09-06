import { useEffect, useRef, useState } from "react";

/* Chat institucional flotante — disponible en TODAS las vistas del correo.
   - Se activa/desactiva y parametriza desde: Administracion -> Chat
     (endpoint publico /api/chat-config: { enabled, embed_url }).
   - Si esta desactivado por el admin, el boton NO aparece.
   - Autodetecta ademas si la instalacion tiene chat (/api/chat): si no responde,
     el boton tampoco aparece.
   - El icono BRILLA cuando hay mensajes nuevos sin leer (NO usa la campanita).
   - Brillo INSTANTANEO: el iframe del chat avisa por postMessage al llegar un
     mensaje (reutiliza el socket del chat). El iframe se monta oculto desde el
     inicio para estar conectado aunque el panel este cerrado. Un sondeo cada 15s
     corrige el conteo (respaldo). */

const POLL_MS = 15000;

export function ChatFlotante() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [embedUrl, setEmbedUrl] = useState("/chat/?embed=1");
  const [disponible, setDisponible] = useState(false);
  const [abierto, setAbierto] = useState(false);
  const [noLeidos, setNoLeidos] = useState(0);
  // Origen del chat cuando vive aparte; vacio = mismo origen que el correo.
  const [origenChat, setOrigenChat] = useState("");
  const abiertoRef = useRef(false);

  // 1) Config del panel de control (activado + URL).
  useEffect(() => {
    fetch("/api/chat-config", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && typeof d.enabled === "boolean") {
          setEnabled(d.enabled);
          if (d.embed_url) setEmbedUrl(d.embed_url);
        } else setEnabled(false);
      })
      // Ante error, el chat NO se da por habilitado. Antes se asumia que si, y
      // justo en las instalaciones sin chat eso arrancaba un sondeo infinito
      // con 404 (reportado por una replica externa).
      .catch(() => setEnabled(false));
  }, []);

  // 1b) Entrada al chat. Desde que el chat vive en su propio origen, su cookie ya
  //     no viaja con la del correo: hay que pedir un vale de un solo uso y cargar
  //     el iframe con el. Si el chat sigue en el origen del correo, esto devuelve
  //     la misma URL relativa y no cambia nada.
  useEffect(() => {
    if (enabled === false) return;
    let vivo = true;
    fetch("/api/chat-sso", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!vivo || !d || !d.url) return;
        setEmbedUrl(d.url);
        if (d.origen) setOrigenChat(d.origen);
      })
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [enabled]);

  // 2) Autodeteccion de disponibilidad del backend de chat.
  //    Se re-chequea cada 60 s y al volver el foco. Si el token de sesion expiro
  //    (cookie de 1 h), se intenta refrescar y se reintenta, para que la burbuja
  //    NO desaparezca "sin explicacion" tras una hora de uso.
  useEffect(() => {
    if (enabled === false) return;
    let vivo = true;
    // Un 404 en esta ruta significa que el chat no esta instalado: no se arregla
    // solo, a diferencia de un 503 temporal. Tras tres seguidos se deja de
    // sondear hasta recargar la pagina. Sin esto, una instalacion sin chat
    // generaba una peticion fallida por minuto y por persona, mas una en cada
    // cambio de foco, y una consola llena de errores.
    let noInstalado = 0;
    const detener = () => {
      clearInterval(t);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
    };
    const comprobar = async () => {
      try {
        let r = await fetch("/api/chat/conversations?limit=1", { credentials: "include" });
        if (r.status === 401) {
          await fetch("/api/auth/refresh", { method: "POST", credentials: "include" }).catch(() => {});
          r = await fetch("/api/chat/conversations?limit=1", { credentials: "include" });
        }
        if (!vivo) return;
        if (r.status === 404) {
          noInstalado += 1;
          setDisponible(false);
          if (noInstalado >= 3) detener();
          return;
        }
        noInstalado = 0;
        setDisponible(r.ok);
      } catch {
        if (vivo) setDisponible(false);
      }
    };
    const onFocus = () => comprobar();
    const t = setInterval(comprobar, 60000);
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    comprobar();
    return () => {
      vivo = false;
      detener();
    };
  }, [enabled]);

  // Helper: recalcular no leidos desde el servidor.
  const refrescarNoLeidos = () => {
    fetch("/api/chat/conversations", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const lista = d.conversaciones || d.conversations || [];
        const total = lista.reduce(
          (acc: number, c: { mensajes_no_leidos?: number; unread_count?: number }) =>
            acc + (c.mensajes_no_leidos || c.unread_count || 0),
          0
        );
        setNoLeidos(abiertoRef.current ? 0 : total);
      })
      .catch(() => {});
  };

  // 3) Sondeo de respaldo (corrige el conteo y limpia al leer en otro lado).
  useEffect(() => {
    if (enabled === false || !disponible) return;
    refrescarNoLeidos();
    const t = setInterval(refrescarNoLeidos, POLL_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, disponible]);

  // 4) Aviso INSTANTANEO desde el iframe del chat (postMessage) al llegar mensaje.
  useEffect(() => {
    function onMsg(e: MessageEvent) {
      // El iframe del chat puede estar en OTRO origen. Se acepta solo el suyo
      // (o el propio, mientras siga sirviendose bajo el correo). Nunca cualquiera.
      const permitido = origenChat || window.location.origin;
      if (e.origin !== permitido) return;
      const d = e.data as { source?: string; type?: string } | null;
      if (d && d.source === "maquita-chat" && d.type === "nuevo-mensaje") {
        if (!abiertoRef.current) {
          setNoLeidos((n) => (n > 0 ? n : 1)); // brillo inmediato
          refrescarNoLeidos(); // luego corrige el numero real
        }
      }
    }
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origenChat]);

  const toggle = () => {
    setAbierto((v) => {
      const nv = !v;
      abiertoRef.current = nv;
      if (nv) setNoLeidos(0);
      return nv;
    });
  };

  if (enabled === false || !disponible) return null;

  const brilla = !abierto && noLeidos > 0;

  return (
    <>
      <style>{`
        @keyframes chatGlow {
          0%,100% { box-shadow: 0 4px 16px rgba(0,120,212,.45); }
          50%     { box-shadow: 0 0 0 6px rgba(0,120,212,.25), 0 4px 22px rgba(0,120,212,.85); }
        }
        .chat-fab-glow { animation: chatGlow 1.1s ease-in-out infinite; }
      `}</style>

      {/* Panel (el iframe se monta SIEMPRE y oculto, para estar conectado). */}
      <div style={{
        position: "fixed", bottom: 84, right: 20, width: 440, height: 640,
        maxWidth: "calc(100vw - 40px)", maxHeight: "calc(100vh - 120px)",
        borderRadius: 12, boxShadow: "0 8px 32px rgba(0,0,0,.28)",
        overflow: "hidden", zIndex: 9998, background: "#fff",
        display: abierto ? "block" : "none",
      }}>
        <iframe src={embedUrl} title="Chat institucional"
          style={{ width: "100%", height: "100%", border: 0 }} />
      </div>

      {/* Boton flotante */}
      <button onClick={toggle}
        className={brilla ? "chat-fab-glow" : undefined}
        title={abierto ? "Cerrar el chat" : (noLeidos > 0 ? `Tienes ${noLeidos} mensaje(s) nuevo(s)` : "Chat institucional")}
        style={{
          position: "fixed", bottom: 20, right: 20, width: 52, height: 52,
          borderRadius: "50%", border: 0, cursor: "pointer", zIndex: 9999,
          background: brilla ? "#0091ff" : "#0078d4", color: "#fff", fontSize: 22,
          boxShadow: "0 4px 16px rgba(0,120,212,.45)",
        }}>
        {abierto ? "✕" : "💬"}
        {brilla && (
          <span style={{
            position: "absolute", top: -3, right: -3, minWidth: 20, height: 20,
            padding: "0 5px", borderRadius: 10, background: "#e11", color: "#fff",
            fontSize: 12, lineHeight: "20px", fontWeight: 700,
            boxShadow: "0 0 0 2px #fff",
          }}>{noLeidos > 99 ? "99+" : noLeidos}</span>
        )}
      </button>
    </>
  );
}
