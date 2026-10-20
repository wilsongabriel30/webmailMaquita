const REDES: { clave: string; nombre: string }[] = [
  { clave: "facebook", nombre: "Facebook" },
  { clave: "instagram", nombre: "Instagram" },
  { clave: "x", nombre: "X (Twitter)" },
  { clave: "youtube", nombre: "YouTube" },
  { clave: "linkedin", nombre: "LinkedIn" },
  { clave: "tiktok", nombre: "TikTok" },
];

/* Redes sociales de la institución: van a la página del sitio y a los datos para buscadores e IA. */
export function RedesSociales({ valor, onCambio }: { valor: string; onCambio: (json: string) => void }) {
  let redes: Record<string, string> = {};
  try { redes = JSON.parse(valor || "{}"); } catch { redes = {}; }
  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
      <h3 className="text-sm font-semibold text-ms-gray-130">Redes sociales</h3>
      <p className="text-xs text-ms-gray-60">Enlaces completos (https://…). Se muestran en la página del sitio y ayudan a que buscadores e IA reconozcan a la institución.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        {REDES.map((r) => (
          <label key={r.clave} className="text-xs text-ms-gray-90">{r.nombre}
            <input type="url" value={redes[r.clave] || ""} placeholder="https://"
              onChange={(e) => onCambio(JSON.stringify({ ...redes, [r.clave]: e.target.value.trim() }))}
              className="mt-1 w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          </label>
        ))}
      </div>
    </div>
  );
}
