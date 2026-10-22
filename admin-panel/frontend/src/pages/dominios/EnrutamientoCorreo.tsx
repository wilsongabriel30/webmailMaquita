import { useEffect, useState } from "react";
import { api } from "../../api/client";

// Tarjeta «Enrutamiento de correo» de la ficha del dominio: MX de respaldo o reenvío a otro servidor.
// Postfix lo lee de la base (ajuste 68): guardar surte efecto sin recargar nada.
type Modo = "" | "respaldo" | "reenvio";
interface Config {
  dominio: string; modo: Modo | null; destino_host?: string | null; destino_puerto?: number | null;
  tls_obligatorio?: boolean; verificar_destinatarios?: boolean; activo?: boolean; destinatarios: string[];
  cuentas_locales: number; siguiente_salto?: string | null; actualizado_por?: string; actualizado_en?: string;
}

const campo = "px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

export function EnrutamientoCorreo({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [config, setConfig] = useState<Config | null>(null);
  const [postfixListo, setPostfixListo] = useState<boolean | null>(null);
  const [modo, setModo] = useState<Modo>("");
  const [host, setHost] = useState("");
  const [puerto, setPuerto] = useState("25");
  const [tls, setTls] = useState(false);
  const [verificar, setVerificar] = useState(false);
  const [lista, setLista] = useState("");
  const [activo, setActivo] = useState(true);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  const pintar = (c: Config) => {
    setConfig(c); setModo(c.modo || ""); setHost(c.destino_host || ""); setPuerto(String(c.destino_puerto || 25));
    setTls(!!c.tls_obligatorio); setVerificar(!!c.verificar_destinatarios); setLista(c.destinatarios.join("\n"));
    setActivo(c.activo !== false);
  };
  useEffect(() => {
    setMensaje(""); setError("");
    api.get<Config>(`/enrutamiento/${encodeURIComponent(dominio)}`).then(pintar).catch((e) => setError(e.message));
    api.get<{ postfix: boolean | null }>("/enrutamiento/estado").then((r) => setPostfixListo(r.postfix)).catch(() => {});
  }, [dominio]);

  const guardar = async () => {
    setMensaje(""); setError("");
    if (!modo) {
      if (!config?.modo) return;
      if (!confirm(`Quitar el enrutamiento de ${dominio}? Su correo volverá a entregarse en los buzones de este servidor. Se registra en auditoría.`)) return;
      try { await api.del(`/enrutamiento/${encodeURIComponent(dominio)}`); setMensaje("Enrutamiento quitado."); pintar({ ...config, modo: null, destinatarios: [] }); }
      catch (e) { setError((e as Error).message); }
      return;
    }
    const cuentas = config?.cuentas_locales || 0;
    if (activo && cuentas > 0 && !confirm(`${dominio} tiene ${cuentas} buzón(es) en este servidor. Con el enrutamiento activo dejarán de recibir correo: irá al otro servidor. ¿Continuar?`)) return;
    try {
      const c = await api.put<Config>(`/enrutamiento/${encodeURIComponent(dominio)}`, {
        modo, destino_host: modo === "reenvio" ? host : null, destino_puerto: modo === "reenvio" ? puerto : null,
        tls_obligatorio: modo === "reenvio" && tls, verificar_destinatarios: verificar, activo,
        destinatarios: lista.split(/[\s,;]+/).filter(Boolean), confirmar_cuentas: cuentas > 0,
      });
      pintar(c); setMensaje("Guardado. Postfix lo aplica en la siguiente conexión.");
    } catch (e) { setError((e as Error).message); }
  };

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ms-gray-130">Enrutamiento de correo · {dominio}</h2>
        <button onClick={onCerrar} className="text-xs text-ms-gray-60 hover:underline">Cerrar</button>
      </div>
      {postfixListo === false && <p className="text-xs text-ms-red">Postfix todavía no lee el enrutamiento: aplique en el servidor el ajuste 68-enrutamiento-de-correo (sudo bash deploy/ajustes/aplicar-ajustes.sh --aplicar).</p>}
      <fieldset className="space-y-1 text-sm">
        <legend className="text-xs font-medium text-ms-gray-90 mb-1">¿Dónde se entrega el correo de {dominio}?</legend>
        <label className="flex gap-2"><input type="radio" name="modo" checked={modo === ""} onChange={() => setModo("")} /> En los buzones de este servidor (sin enrutamiento)</label>
        <label className="flex gap-2"><input type="radio" name="modo" checked={modo === "respaldo"} onChange={() => setModo("respaldo")} /> MX de respaldo: aceptar y guardar en cola mientras el servidor principal no responde</label>
        <label className="flex gap-2"><input type="radio" name="modo" checked={modo === "reenvio"} onChange={() => setModo("reenvio")} /> Reenviar siempre a otro servidor</label>
      </fieldset>
      {modo === "reenvio" && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <input placeholder="mx.example.com o 203.0.113.25" value={host} onChange={(e) => setHost(e.target.value)} aria-label="Servidor de destino" className={`${campo} sm:col-span-2`} />
          <input type="number" min={1} max={65535} value={puerto} onChange={(e) => setPuerto(e.target.value)} aria-label="Puerto" className={campo} />
          <label className="text-sm flex gap-2 sm:col-span-3"><input type="checkbox" checked={tls} onChange={(e) => setTls(e.target.checked)} /> Exigir TLS hacia ese servidor (sin cifrado, el correo espera en la cola)</label>
        </div>
      )}
      {modo === "respaldo" && <p className="text-xs text-ms-gray-60">El registro MX de este servidor debe tener una preferencia MAYOR (número más alto) que el del servidor principal; si no, el correo daría vueltas.</p>}
      {modo && (
        <div className="space-y-2">
          <label className="text-sm flex gap-2"><input type="checkbox" checked={verificar} onChange={(e) => setVerificar(e.target.checked)} /> Aceptar solo estas direcciones (recomendado: evita guardar correo para destinatarios que no existen)</label>
          {verificar && <textarea rows={5} value={lista} onChange={(e) => setLista(e.target.value)} placeholder={`ana@${dominio}\nventas@${dominio}`} aria-label="Destinatarios válidos" className={`${campo} w-full font-mono text-xs`} />}
          <label className="text-sm flex gap-2"><input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} /> Activo</label>
        </div>
      )}
      {config?.siguiente_salto && <p className="text-xs text-ms-gray-60">Transporte en Postfix: <code>{config.siguiente_salto}</code></p>}
      {config?.actualizado_por && <p className="text-xs text-ms-gray-60">Último cambio: {config.actualizado_por}{config.actualizado_en ? `, ${new Date(config.actualizado_en).toLocaleString("es")}` : ""}</p>}
      {error && <p role="alert" className="text-sm text-ms-red">{error}</p>}
      {mensaje && <p role="status" className="text-sm text-ms-green">{mensaje}</p>}
      <button onClick={guardar} disabled={!config || (!modo && !config.modo)} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Guardar</button>
    </div>
  );
}
