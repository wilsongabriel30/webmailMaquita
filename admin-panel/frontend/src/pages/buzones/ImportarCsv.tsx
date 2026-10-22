import { useState } from "react";
import { api } from "../../api/client";
import { descargarCsv, leerTextoCsv, PLANTILLA_CSV } from "../../lib/archivosCsv";

// Importar buzones desde un CSV: vista previa fila a fila (no cambia nada) y después crear las
// filas válidas. Las contraseñas generadas llegan una sola vez, en un CSV para descargar.
interface Fila { fila: number; correo: string; nombre: string; alias: string[]; cuota_mb: number | null; clave: string; errores: string[]; valida: boolean; resultado?: string }
interface Vista { filas: Fila[]; validas: number; con_errores: number }
interface Resultado { creadas: number; omitidas: number; resultados: Fila[]; informe_csv: string; claves_csv: string | null }

const MAX_BYTES = 1024 * 1024;
const boton = "px-3 py-1.5 rounded text-sm";

export function ImportarCsv({ onCerrar, onCreadas }: { onCerrar: () => void; onCreadas: () => void }) {
  const [csv, setCsv] = useState("");
  const [nombreArchivo, setNombreArchivo] = useState("");
  const [vista, setVista] = useState<Vista | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [soloErrores, setSoloErrores] = useState(false);

  const elegir = async (archivo: File | undefined) => {
    setVista(null); setResultado(null); setError("");
    if (!archivo) return;
    if (archivo.size > MAX_BYTES) { setError("El archivo pesa más de 1 MB: divídalo en varios."); return; }
    setNombreArchivo(archivo.name);
    setCsv(await leerTextoCsv(archivo));
  };

  const revisar = async () => {
    setOcupado(true); setError("");
    try { setVista(await api.post<Vista>("/importar-cuentas/vista-previa", { csv })); }
    catch (e) { setError((e as Error).message); }
    finally { setOcupado(false); }
  };

  const aplicar = async () => {
    if (!vista || !confirm(`Se crearán ${vista.validas} buzón(es); las filas con errores se omiten. Se registra en auditoría. ¿Continuar?`)) return;
    setOcupado(true); setError("");
    try {
      const r = await api.post<Resultado>("/importar-cuentas/aplicar", { csv });
      setResultado(r); setVista(null); onCreadas();
    } catch (e) { setError((e as Error).message); }
    finally { setOcupado(false); }
  };

  const filas = resultado ? resultado.resultados : vista ? vista.filas : [];
  const visibles = soloErrores ? filas.filter((f) => f.errores.length) : filas;

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ms-gray-130">Importar buzones desde un archivo CSV</h2>
        <button onClick={onCerrar} className="text-xs text-ms-gray-60 hover:underline">Cerrar</button>
      </div>
      <p className="text-xs text-ms-gray-60">
        Columnas: <strong>correo</strong>, <strong>nombre</strong>, clave (si falta, se genera), cuota_mb (si falta, la del dominio) y alias (separados por punto y coma).
        Hasta 2000 filas y 1 MB. Primero se revisa todo sin crear nada.{" "}
        <button onClick={() => descargarCsv("plantilla-cuentas.csv", PLANTILLA_CSV)} className="text-ms-blue hover:underline">Descargar plantilla</button>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input type="file" accept=".csv,text/csv" onChange={(e) => elegir(e.target.files?.[0])} className="text-sm" aria-label="Archivo CSV" />
        <button disabled={!csv || ocupado} onClick={revisar} className={`${boton} border border-ms-blue text-ms-blue disabled:opacity-50`}>{ocupado && !vista ? "Revisando…" : "Revisar archivo"}</button>
        {vista && <button disabled={!vista.validas || ocupado} onClick={aplicar} className={`${boton} bg-ms-blue text-white disabled:opacity-50`}>{ocupado ? "Creando…" : `Crear ${vista.validas} buzón(es)`}</button>}
      </div>
      {error && <p role="alert" className="text-sm text-ms-red">{error}</p>}

      {vista && <p className="text-sm">{nombreArchivo}: <strong>{vista.validas}</strong> fila(s) listas y <strong className={vista.con_errores ? "text-ms-red" : ""}>{vista.con_errores}</strong> con errores (se omitirán).</p>}
      {resultado && (
        <div className="rounded border border-ms-gray-30 bg-ms-gray-20 p-3 text-sm space-y-2">
          <p>Se crearon <strong>{resultado.creadas}</strong> buzón(es); se omitieron <strong>{resultado.omitidas}</strong>.</p>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => descargarCsv("informe-importacion.csv", resultado.informe_csv)} className={`${boton} border border-ms-gray-40`}>Descargar informe</button>
            {resultado.claves_csv && <button onClick={() => descargarCsv("contrasenas-generadas.csv", resultado.claves_csv!)} className={`${boton} bg-ms-blue text-white`}>Descargar contraseñas generadas</button>}
          </div>
          {resultado.claves_csv && <p className="text-xs text-ms-red">Las contraseñas generadas solo se muestran ahora: descárguelas antes de cerrar y entréguelas por un medio seguro.</p>}
        </div>
      )}

      {filas.length > 0 && (
        <>
          <label className="text-xs text-ms-gray-90 flex items-center gap-1"><input type="checkbox" checked={soloErrores} onChange={(e) => setSoloErrores(e.target.checked)} /> Ver solo las filas con errores</label>
          <div className="max-h-96 overflow-auto border border-ms-gray-30 rounded">
            <table className="w-full text-xs">
              <thead className="bg-ms-gray-20 sticky top-0">
                <tr>{["Fila", "Correo", "Nombre", "Cuota", "Alias", "Contraseña", "Estado"].map((t) => <th key={t} className="text-left px-2 py-1.5 font-medium text-ms-gray-90">{t}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-ms-gray-30">
                {visibles.map((f) => (
                  <tr key={f.fila} className={f.errores.length ? "bg-red-50" : ""}>
                    <td className="px-2 py-1">{f.fila}</td>
                    <td className="px-2 py-1 font-medium">{f.correo || "—"}</td>
                    <td className="px-2 py-1">{f.nombre}</td>
                    <td className="px-2 py-1">{f.cuota_mb === null ? "—" : f.cuota_mb ? `${f.cuota_mb} MB` : "Sin límite"}</td>
                    <td className="px-2 py-1">{f.alias.join(", ")}</td>
                    <td className="px-2 py-1">{f.clave}</td>
                    <td className="px-2 py-1">{f.errores.length ? <span className="text-ms-red">{f.errores.join(". ")}</span>
                      : <span className="text-ms-green">{f.resultado === "creada" ? "Creada" : "Lista"}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
