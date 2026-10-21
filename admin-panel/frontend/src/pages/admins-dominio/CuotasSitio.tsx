import { api } from "../../api/client";

// Cuotas de «Mi sitio web» (portal de dominio) por dominio asignado. Las aplica el intermediario
// maquita-sitios-portal; aquí solo se fijan y se ve el uso (sitios y disco; el de las bases lo ve el portal).
export interface Cuota { max_sitios: number; disco_mb: number; bases_mb: number }
export interface UsoSitio { sitios: number; disco_mb: number }
export interface CuotasSitio {
  disponible: boolean;
  por_defecto: Cuota;
  dominios: Record<string, { cuota: Cuota; uso: UsoSitio | null }>;
}

export const cargarCuotas = () => api.get<CuotasSitio>("/admins-dominio/cuotas-sitio");

export async function guardarCuotas(cambios: Record<string, Cuota>, dominios: string[]) {
  for (const [dominio, cuota] of Object.entries(cambios)) {
    if (!dominios.includes(dominio)) continue;
    await api.put(`/admins-dominio/cuotas-sitio/${encodeURIComponent(dominio)}`, cuota);
  }
}

interface Props {
  datos: CuotasSitio | null;
  dominios: string[];
  valores: Record<string, Cuota>;
  onCambio: (dominio: string, cuota: Cuota) => void;
}

const numero = "w-20 px-2 py-1 border border-ms-gray-40 rounded text-xs focus:outline-none focus:border-ms-blue";
const CAMPOS: { clave: keyof Cuota; texto: string }[] = [
  { clave: "max_sitios", texto: "Sitios" },
  { clave: "disco_mb", texto: "Disco (MB)" },
  { clave: "bases_mb", texto: "Bases (MB)" },
];

export function CuotasSitioEditor({ datos, dominios, valores, onCambio }: Props) {
  if (!datos || !dominios.length) return null;
  if (!datos.disponible) {
    return <p className="text-xs text-ms-gray-60">Cuotas de sitios web: falta aplicar el ajuste 58-sitios-en-el-portal en el servidor.</p>;
  }
  return (
    <div>
      <div className="text-xs font-medium text-ms-gray-90 mb-1">Sitios web desde el portal (cuota por dominio)</div>
      <div className="border border-ms-gray-30 rounded p-2 space-y-2">
        {dominios.map((d) => {
          const cuota = valores[d] || datos.dominios[d]?.cuota || datos.por_defecto;
          const uso = datos.dominios[d]?.uso;
          return (
            <div key={d} className="text-xs">
              <div className="text-ms-gray-130 font-medium">{d}</div>
              <div className="flex flex-wrap gap-2 mt-1">
                {CAMPOS.map(({ clave, texto }) => (
                  <label key={clave} className="flex flex-col text-ms-gray-60">{texto}
                    <input type="number" min={0} className={numero} value={cuota[clave]}
                      onChange={(e) => onCambio(d, { ...cuota, [clave]: Math.max(0, parseInt(e.target.value || "0", 10)) })} />
                  </label>
                ))}
              </div>
              {uso && <div className="text-ms-gray-60 mt-0.5">En uso: {uso.sitios} sitio{uso.sitios === 1 ? "" : "s"}, {uso.disco_mb} MB de disco</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
