import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Dominio { dominio: string; linaje: string; emitido: boolean; nombres?: string[]; vence?: string; error?: string; espera?: number }
interface Estado {
  emitido: boolean; linaje: string; nombres?: string[]; vence?: string; en_uso?: boolean; incluidos?: string[]; omitidos?: string[];
  modo?: "compartido" | "por-dominio"; dominios?: Dominio[]; aviso?: string; error?: string; espera?: number;
}

const horas = (s?: number) => (s ? `${Math.max(1, Math.round(s / 3600))} h` : "");

/* Certificado del correo: webmail, IMAP, SMTP, autoconfiguración y FTP. En hospedaje («por-dominio»), uno por dominio de cliente. */
export function CertificadoCorreo() {
  const [est, setEst] = useState<Estado | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [omitidos, setOmitidos] = useState<string[]>([]);

  const cargar = () => api.get<Estado>("/dns/certificado/estado").then(setEst).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const emitir = async () => {
    setOcupado(true); setError("");
    try { const r = await api.post<Estado>("/dns/certificado"); setEst(r); setOmitidos(r.omitidos || []); }
    catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };

  const porDominio = est?.modo === "por-dominio";
  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold text-ms-gray-130">Certificado del correo</h2>
        <button onClick={emitir} disabled={ocupado} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">
          {ocupado ? "Emitiendo (hasta 2 min)…" : est?.emitido ? "Ampliar / renovar" : "Emitir"}</button>
      </div>
      <p className="text-xs text-ms-gray-90">
        {porDominio
          ? "Modo hospedaje: el certificado del servidor cubre el dominio principal y cada dominio de cliente tiene el suyo (no se comparten). "
          : "Un solo certificado gratuito (Let's Encrypt) para mail., autoconfig. y autodiscover. de cada dominio. "}
        Lo usan el webmail, los programas de correo (IMAP/SMTP) y el FTP. Solo incluye los nombres que ya apuntan a este servidor desde Internet. Se renueva solo.</p>
      {error && <p className="text-sm text-ms-red">{error}</p>}
      {est?.aviso && <p className="text-sm text-amber-700">Aviso de configuración: {est.aviso}</p>}
      {est?.error && <p className="text-sm text-amber-700">Último intento fallido: {est.error}{est.espera ? ` (se reintenta en ${horas(est.espera)})` : ""}</p>}
      {est && !est.emitido && <p className="text-sm text-amber-700">Todavía sin certificado: los programas de correo verán un aviso de seguridad. Emítalo cuando el semáforo del dominio esté en verde.</p>}
      {est?.emitido && (
        <div className="text-sm space-y-1">
          <div>Vence: <span className="font-mono text-xs">{est.vence}</span> {est.en_uso ? <span className="text-ms-green">· en uso por todos los servicios</span> : <span className="text-amber-700">· aún no en uso</span>}</div>
          <div className="flex flex-wrap gap-1">{est.nombres?.map((n) => <span key={n} className="px-2 py-0.5 bg-ms-gray-20 rounded text-xs font-mono">{n}</span>)}</div>
        </div>
      )}
      {omitidos.length > 0 && <p className="text-xs text-ms-gray-60">No incluidos (todavía no apuntan aquí): {omitidos.join(", ")}</p>}
      {porDominio && (est?.dominios?.length ?? 0) > 0 && (
        <table className="w-full text-xs mt-2">
          <thead><tr className="text-left text-ms-gray-90"><th className="py-1">Dominio</th><th>Certificado propio</th><th>Vence</th></tr></thead>
          <tbody>{est!.dominios!.map((d) => (
            <tr key={d.dominio} className="border-t border-ms-gray-20 align-top">
              <td className="py-1 font-mono">{d.dominio}</td>
              <td>{d.emitido ? <span className="text-ms-green">{d.nombres?.join(", ")}</span>
                : <span className="text-ms-gray-60">pendiente: usa el del servidor hasta que mail.{d.dominio} apunte aquí</span>}
                {d.error && <div className="text-amber-700">Falló: {d.error}{d.espera ? ` (se reintenta en ${horas(d.espera)})` : " (se reintenta en la próxima pasada)"}</div>}</td>
              <td className="font-mono">{d.vence || ""}</td>
            </tr>))}</tbody>
        </table>
      )}
    </div>
  );
}
