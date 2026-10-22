import { useEffect, useState } from "react";

// Botón «Entrar con Identidad» (OpenID Connect) de la pantalla de entrada. Solo aparece si el
// superadministrador lo activó (SSO / Identidad → Entrada al panel con OpenID Connect).
// Si la vuelta del proveedor falló, /login?entrada=<código> explica por qué.
const MOTIVOS: Record<string, string> = {
  desactivada: "La entrada con el proveedor de identidad está desactivada.",
  proveedor: "No se pudo hablar con el proveedor de identidad. Inténtelo más tarde.",
  configuracion: "La entrada con el proveedor de identidad está mal configurada. Avise al superadministrador.",
  estado: "La entrada caducó o empezó en otro navegador. Vuelva a intentarlo.",
  rechazada: "El proveedor de identidad no autorizó la entrada.",
  token: "La respuesta del proveedor de identidad no es válida.",
  sin_cuenta: "Su identidad no corresponde a ninguna cuenta del panel.",
  grupo: "Su cuenta del proveedor no está en el grupo autorizado para este panel.",
  desactivada_cuenta: "Su cuenta del panel está desactivada.",
  bloqueada: "Su cuenta del panel está bloqueada unos minutos por intentos fallidos.",
};

export function EntradaIdentidad() {
  const [texto, setTexto] = useState("");
  const [motivo] = useState(() => {
    const codigo = new URLSearchParams(window.location.search).get("entrada");
    if (codigo) window.history.replaceState(null, "", "/login");
    return codigo ? MOTIVOS[codigo] || "No se pudo entrar con el proveedor de identidad." : "";
  });

  useEffect(() => {
    fetch("/api/auth/oidc/estado")
      .then((r) => (r.ok ? r.json() : { activado: false }))
      .then((e: { activado?: boolean; texto_boton?: string }) => setTexto(e.activado ? e.texto_boton || "Entrar con Identidad" : ""))
      .catch(() => {});
  }, []);

  if (!texto && !motivo) return null;
  return (
    <div className="mt-4 space-y-3">
      {motivo && <div className="p-3 bg-red-50 border border-ms-red/30 rounded text-ms-red text-sm" role="alert">{motivo}</div>}
      {texto && (
        <>
          <div className="flex items-center gap-2 text-xs text-ms-gray-60"><span className="flex-1 border-t border-ms-gray-30" />o<span className="flex-1 border-t border-ms-gray-30" /></div>
          <a href="/api/auth/oidc/inicio"
            title="Entra con la cuenta del proveedor de identidad de la organización (OpenID Connect). Si su cuenta del panel tiene segundo factor, se le pedirá al volver."
            className="block w-full py-2.5 text-center border border-ms-blue text-ms-blue hover:bg-ms-blue-lighter font-medium rounded text-sm">
            {texto}
          </a>
        </>
      )}
    </div>
  );
}
