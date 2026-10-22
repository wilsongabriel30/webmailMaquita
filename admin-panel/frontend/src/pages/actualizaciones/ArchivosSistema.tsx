/* «Archivos del sistema cambiados» por la última actualización (fuera del código): bind, nginx, fail2ban,
   postfix, systemd, programas instalados, .env de las aplicaciones… agrupados, con la marca de los que
   tenían cambios locales (parches hechos a mano que la versión reemplazó) y dónde quedó la copia anterior. */

export interface ArchivoCambiado {
  ruta: string; grupo: string; cambios_locales?: boolean; copia?: string; antes?: string; solo_permisos?: boolean;
}
export interface ArchivosSistemaInforme {
  totales?: { creados: number; modificados: number; borrados: number };
  cambios_locales?: number; creados?: ArchivoCambiado[]; modificados?: ArchivoCambiado[]; borrados?: ArchivoCambiado[];
  recortado?: boolean; copias?: string; error?: string; error_locales?: string;
}

type Categoria = "creados" | "modificados" | "borrados";
const CATEGORIAS: [Categoria, string, string][] = [
  ["modificados", "modificado", "bg-amber-50 text-amber-700"],
  ["creados", "creado", "bg-green-50 text-ms-green"],
  ["borrados", "borrado", "bg-red-50 text-ms-red"],
];

/** Totales en una línea (para el historial). */
export function totalesArchivos(a?: ArchivosSistemaInforme): string {
  const t = a?.totales;
  if (!t) return "";
  const partes = [`${t.modificados} modificados`, `${t.creados} creados`, `${t.borrados} borrados`];
  return `archivos del sistema: ${partes.join(", ")}${a?.cambios_locales ? ` · ${a.cambios_locales} con cambios locales` : ""}`;
}

export function ArchivosSistema({ informe }: { informe: ArchivosSistemaInforme }) {
  const t = informe.totales;
  const filas = CATEGORIAS.flatMap(([cat, texto, color]) => (informe[cat] || []).map((a) => ({ ...a, texto, color })));
  const grupos = new Map<string, typeof filas>();
  filas.forEach((f) => grupos.set(f.grupo, [...(grupos.get(f.grupo) || []), f]));

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
      <h2 className="font-semibold text-ms-gray-130">Archivos del sistema cambiados</h2>
      {informe.error && <p className="text-sm text-ms-red">No se pudo completar la comparación: {informe.error}</p>}
      {t && (
        <p className="text-sm">
          {t.modificados} modificados, {t.creados} creados y {t.borrados} borrados fuera del código
          (configuración del servidor, programas instalados y archivos .env).
        </p>
      )}
      {!!informe.cambios_locales && (
        <p className="text-sm text-ms-red">
          {informe.cambios_locales === 1 ? "Un archivo tenía" : `${informe.cambios_locales} archivos tenían`} cambios
          locales (no coincidían con lo que instaló la versión anterior): la actualización los reemplazó. El contenido
          anterior está en la copia indicada; compárelo con <code>diff &lt;copia&gt; &lt;ruta&gt;</code> y lleve el cambio
          a la configuración que corresponda (ver «Si tiene parches locales» en la guía de actualizaciones).
        </p>
      )}
      {informe.error_locales && <p className="text-xs text-ms-gray-90">No se pudieron comprobar los cambios locales: {informe.error_locales}</p>}
      {filas.length === 0 && !informe.error && <p className="text-sm text-ms-gray-90">La actualización no cambió ningún archivo vigilado.</p>}
      {[...grupos.entries()].map(([grupo, lista]) => (
        <details key={grupo} open={lista.some((a) => a.cambios_locales) || lista.length <= 5} className="border-t border-ms-gray-30 pt-2">
          <summary className="text-sm font-medium cursor-pointer">
            {grupo} <span className="text-xs text-ms-gray-60">({lista.length})</span>
            {lista.some((a) => a.cambios_locales) && <span className="ml-2 px-2 py-0.5 rounded text-[11px] bg-red-50 text-ms-red">con cambios locales</span>}
          </summary>
          <ul className="mt-2 space-y-1">
            {lista.map((a) => (
              <li key={a.texto + a.ruta} className="text-xs flex flex-wrap items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded text-[11px] ${a.color}`}>{a.texto}</span>
                <code className="break-all">{a.ruta}</code>
                {a.solo_permisos && <span className="text-ms-gray-60">(solo permisos)</span>}
                {a.cambios_locales && <span className="px-1.5 py-0.5 rounded text-[11px] bg-red-50 text-ms-red font-medium">tenía cambios locales</span>}
                {a.antes && <span className="text-ms-gray-60">antes {a.antes}</span>}
                {a.copia && <span className="text-ms-gray-60">copia anterior: <code className="break-all">{a.copia}</code></span>}
              </li>
            ))}
          </ul>
        </details>
      ))}
      {informe.recortado && <p className="text-xs text-ms-gray-60">Lista recortada: la completa está en archivos-sistema.json, en el respaldo de la actualización.</p>}
      {informe.copias && <p className="text-xs text-ms-gray-60">Copias del contenido anterior (solo root): <code className="break-all">{informe.copias}</code></p>}
    </div>
  );
}
