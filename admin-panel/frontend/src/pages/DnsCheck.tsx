import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

export function DnsCheck() {
  const [domain, setDomain] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [managedDomains, setManagedDomains] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<{ domains: string[] }>("/dnscheck").then((r) => {
      setManagedDomains(r.domains || []);
    }).catch(() => {});
  }, []);

  const check = async (d?: string) => {
    const target = (d || domain).trim().toLowerCase();
    if (!target) return;
    setDomain(target);
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.get(`/dnscheck/${encodeURIComponent(target)}`);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Error al verificar DNS");
    }
    setLoading(false);
  };

  const gradeColor = (g: string) => {
    if (g === "A") return "text-green-700 bg-green-50 border-green-300";
    if (g === "B") return "text-blue-700 bg-blue-50 border-blue-300";
    if (g === "C") return "text-yellow-700 bg-yellow-50 border-yellow-300";
    return "text-red-700 bg-red-50 border-red-300";
  };

  const scoreBarColor = (s: number) =>
    s >= 75 ? "bg-green-500" : s >= 50 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Verificación DNS de dominios</h1>
        <SectionHelp titulo="Verificación DNS" items={[
          { titulo: "Para qué sirve", desc: "Audita la configuración DNS de correo de cualquier dominio (propio o externo) para diagnosticar por qué un correo no llega o cae en spam. Es solo lectura: no modifica nada." },
          { titulo: "Dominios del servidor", desc: "Los chips azules son los dominios ya administrados por este servidor; haga clic en uno para analizarlo sin escribirlo." },
          { titulo: "Calificación y puntuación", desc: "Resume la salud del dominio con una letra (A a F) y un puntaje sobre 100, más indicadores de si puede recibir correo, entregar correo y autenticarse por completo." },
          { titulo: "Tarjetas de detalle", desc: "MX (a dónde llega el correo), SPF (quién puede enviar), DKIM (firma digital), DMARC (política de autenticación), PTR (DNS inverso, clave para no caer en spam) y Autoconfig (configuración automática de clientes)." },
          { titulo: "Recomendaciones", desc: "Al final se listan los registros DNS faltantes o mal configurados que debe corregir en el proveedor DNS del dominio." },
        ]} />
      </div>
      <p className="text-xs text-ms-gray-60">
        Analiza MX, SPF, DKIM, DMARC, PTR y autoconfig de cualquier dominio. Usa resolvers públicos (Google DNS).
      </p>

      {/* Dominios administrados — acceso rapido */}
      {managedDomains.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-ms-gray-90 font-medium">Dominios del servidor:</span>
          {managedDomains.map((d) => (
            <button key={d} onClick={() => check(d)}
              className="px-2.5 py-1 text-xs bg-ms-blue-lighter text-ms-blue rounded hover:bg-ms-blue hover:text-white transition-colors"
              title={`Verificar configuración DNS de ${d}`}>
              {d}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input value={domain} onChange={(e) => setDomain(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && check()}
          placeholder="ejemplo.com, ejemplo.com, gmail.com..."
          title="Dominio a verificar (sin prefijo mail. ni http://)"
          className="flex-1 px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
        <button onClick={() => check()} disabled={loading}
          title="Verificar configuración DNS (solo lectura)"
          className="px-5 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">
          {loading ? "Verificando..." : "Verificar"}
        </button>
      </div>

      {error && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">{error}</div>
      )}

      {/* Sugerencia si ingresaron hostname en vez de dominio */}
      {result?.hint && result?.base_domain && (
        <div className="px-4 py-3 bg-blue-50 border border-blue-200 rounded flex items-center gap-3">
          <svg className="w-5 h-5 text-blue-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-blue-800 flex-1">{result.hint}</p>
          <button onClick={() => check(result.base_domain)}
            title={`Ejecuta la verificación DNS sobre el dominio base ${result.base_domain} en lugar del hostname ingresado. Solo lectura, no modifica nada.`}
            className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 whitespace-nowrap">
            Verificar {result.base_domain}
          </button>
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Score card */}
          <div className="bg-white rounded border border-ms-gray-30 p-5 flex items-center gap-6">
            <div className={`w-20 h-20 rounded-full flex items-center justify-center border-4 ${gradeColor(result.results.grade)}`}>
              <span className="text-3xl font-bold">{result.results.grade}</span>
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-ms-gray-130">{result.domain}</h2>
              <p className="text-sm text-ms-gray-60">Puntuación: {result.results.score}/100</p>
              <div className="w-48 bg-ms-gray-30 rounded-full h-2 mt-2">
                <div className={`h-2 rounded-full transition-all ${scoreBarColor(result.results.score)}`}
                  style={{ width: `${result.results.score}%` }} />
              </div>
            </div>
            {/* Indicador de estado de migracion */}
            {result.results.summary && (
              <div className="text-right text-xs space-y-1">
                <div className={`flex items-center gap-1.5 justify-end ${result.results.summary.ready_for_mail ? "text-green-600" : "text-red-500"}`}>
                  <span className={`w-2 h-2 rounded-full ${result.results.summary.ready_for_mail ? "bg-green-500" : "bg-red-500"}`} />
                  {result.results.summary.ready_for_mail ? "Puede recibir correo" : "No puede recibir correo"}
                </div>
                <div className={`flex items-center gap-1.5 justify-end ${result.results.summary.ready_for_delivery ? "text-green-600" : "text-yellow-600"}`}>
                  <span className={`w-2 h-2 rounded-full ${result.results.summary.ready_for_delivery ? "bg-green-500" : "bg-yellow-500"}`} />
                  {result.results.summary.ready_for_delivery ? "Listo para entrega" : "Entrega puede fallar"}
                </div>
                <div className={`flex items-center gap-1.5 justify-end ${result.results.summary.fully_authenticated ? "text-green-600" : "text-yellow-600"}`}>
                  <span className={`w-2 h-2 rounded-full ${result.results.summary.fully_authenticated ? "bg-green-500" : "bg-yellow-500"}`} />
                  {result.results.summary.fully_authenticated ? "Autenticación completa" : "Autenticación incompleta"}
                </div>
              </div>
            )}
          </div>

          {/* Detail cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { key: "mx", title: "MX (Servidor de correo)", icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
              { key: "spf", title: "SPF (Remitentes autorizados)", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" },
              { key: "dkim", title: "DKIM (Firma digital)", icon: "M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" },
              { key: "dmarc", title: "DMARC (Política autenticación)", icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" },
              { key: "ptr", title: "PTR (DNS inverso)", icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" },
              { key: "autoconfig", title: "Autoconfig / Autodiscover", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" },
            ].map(({ key, title, icon }) => {
              const chk = result.results[key];
              if (!chk) return null;
              return (
                <div key={key} className="bg-white rounded border border-ms-gray-30 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <svg className={`w-5 h-5 ${chk.ok ? "text-green-500" : "text-red-500"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
                    </svg>
                    <span className="text-sm font-semibold text-ms-gray-130">{title}</span>
                    <span className={`ml-auto text-[10px] px-2 py-0.5 rounded font-medium ${chk.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                      {chk.ok ? "OK" : "Falta"}
                    </span>
                  </div>
                  <p className="text-xs text-ms-gray-90 mb-2">{chk.message}</p>
                  {chk.records?.length > 0 && (
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {chk.records.map((r: any, i: number) => (
                        <div key={i} className="text-[10px] font-mono bg-ms-gray-10 p-1.5 rounded text-ms-gray-130 break-all">
                          {typeof r === "string" ? r : typeof r === "object" && r.selector
                            ? `${r.selector}: ${r.record}`
                            : typeof r === "object" && r.ip
                            ? `${r.ip} → ${r.ptr || "(sin PTR)"}${r.match ? " ✓" : ""}`
                            : JSON.stringify(r)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Recomendaciones */}
          {result.results.summary?.recommendations?.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
              <h3 className="text-sm font-semibold text-yellow-800 mb-2">Recomendaciones</h3>
              <ul className="space-y-1.5">
                {result.results.summary.recommendations.map((r: string, i: number) => (
                  <li key={i} className="text-xs text-yellow-900 flex items-start gap-2">
                    <span className="text-yellow-600 mt-0.5">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
