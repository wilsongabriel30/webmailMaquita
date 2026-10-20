import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Estado { emitido: boolean; linaje: string; nombres?: string[]; vence?: string; en_uso?: boolean; incluidos?: string[]; omitidos?: string[] }

/* Un certificado para el correo de todos los dominios: webmail, IMAP, SMTP, autoconfiguración y FTP. */
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

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold text-ms-gray-130">Certificado del correo</h2>
        <button onClick={emitir} disabled={ocupado} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">
          {ocupado ? "Emitiendo (hasta 2 min)…" : est?.emitido ? "Ampliar / renovar" : "Emitir"}</button>
      </div>
      <p className="text-xs text-ms-gray-90">Un solo certificado gratuito (Let's Encrypt) para mail., autoconfig. y autodiscover. de cada dominio, usado por el webmail, los programas de correo (IMAP/SMTP) y el FTP. Solo incluye los nombres que ya apuntan a este servidor desde Internet. Se renueva solo.</p>
      {error && <p className="text-sm text-ms-red">{error}</p>}
      {est && !est.emitido && <p className="text-sm text-amber-700">Todavía sin certificado: los programas de correo verán un aviso de seguridad. Emítalo cuando el semáforo del dominio esté en verde.</p>}
      {est?.emitido && (
        <div className="text-sm space-y-1">
          <div>Vence: <span className="font-mono text-xs">{est.vence}</span> {est.en_uso ? <span className="text-ms-green">· en uso por todos los servicios</span> : <span className="text-amber-700">· aún no en uso</span>}</div>
          <div className="flex flex-wrap gap-1">{est.nombres?.map((n) => <span key={n} className="px-2 py-0.5 bg-ms-gray-20 rounded text-xs font-mono">{n}</span>)}</div>
        </div>
      )}
      {omitidos.length > 0 && <p className="text-xs text-ms-gray-60">No incluidos (todavía no apuntan aquí): {omitidos.join(", ")}</p>}
    </div>
  );
}
