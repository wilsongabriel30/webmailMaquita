import { useState } from "react";
import { api } from "../../api/client";
import { caja, campo, type Estado } from "./tipos";

/* Restaurar un sitio web o un buzón desde una instantánea (sin riesgo: ver la ayuda de cada opción). */
export function RestaurarCaja({ est, alTerminar }: { est: Estado; alTerminar: () => void }) {
  const [tipo, setTipo] = useState<"buzon" | "sitio">("buzon");
  const [objeto, setObjeto] = useState("");
  const [inst, setInst] = useState(est.instantaneas[0]?.id || "");
  const [mensaje, setMensaje] = useState("");
  const r = est.restauracion;

  const restaurar = async () => {
    const fecha = est.instantaneas.find((i) => i.id === inst)?.fecha;
    const aviso = tipo === "sitio"
      ? `El sitio ${objeto} volverá a como estaba el ${fecha} (archivos y bases de datos). Antes se guarda su estado actual por si hay que deshacerlo. ¿Continuar?`
      : `Los correos de ${objeto} del ${fecha} se copiarán a una carpeta nueva «Restaurado-…» dentro del mismo buzón. No se borra ni se cambia nada de lo actual. ¿Continuar?`;
    if (!confirm(aviso)) return;
    setMensaje("");
    try { await api.post("/respaldos/restaurar", { tipo, objeto: objeto.trim().toLowerCase(), instantanea: inst }); alTerminar(); }
    catch (e) { setMensaje((e as Error).message); }
  };

  return (
    <div className={caja}>
      <h2 className="font-semibold text-ms-gray-130">Restaurar</h2>
      <div className="flex flex-wrap gap-4 text-sm">
        <label><input type="radio" checked={tipo === "buzon"} onChange={() => { setTipo("buzon"); setObjeto(""); }} className="mr-1" />Correos de un buzón</label>
        <label><input type="radio" checked={tipo === "sitio"} onChange={() => { setTipo("sitio"); setObjeto(est.sitios[0] || ""); }} className="mr-1" />Un sitio web</label>
      </div>
      <p className="text-xs text-ms-gray-90">{tipo === "buzon"
        ? "Los correos del respaldo aparecen en una carpeta nueva «Restaurado-fecha» del buzón (con sus subcarpetas): la persona recupera lo que necesite. No se toca nada de lo actual."
        : "Archivos y bases de datos del sitio vuelven a como estaban. Antes se respalda el estado actual (etiqueta «antes-de-restaurar»), así que se puede deshacer."}</p>
      <div className="flex flex-wrap gap-2 items-center">
        {tipo === "buzon"
          ? <input value={objeto} onChange={(e) => setObjeto(e.target.value)} placeholder="persona@dominio" className={`${campo} w-64`} />
          : <select value={objeto} onChange={(e) => setObjeto(e.target.value)} className={campo}>{est.sitios.map((s) => <option key={s}>{s}</option>)}</select>}
        <select value={inst} onChange={(e) => setInst(e.target.value)} className={campo}>
          {est.instantaneas.map((i) => <option key={i.id} value={i.id}>{i.fecha} {i.etiquetas.includes("antes-de-restaurar") ? "(antes de restaurar)" : i.etiquetas.includes("manual") ? "(manual)" : ""}</option>)}
        </select>
        <button onClick={restaurar} disabled={!objeto.trim() || !inst || est.en_curso} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Restaurar</button>
      </div>
      {r && (
        <p className={`text-sm ${r.estado === "falló" ? "text-ms-red" : "text-ms-gray-90"}`}>
          Última restauración ({r.tipo === "restaurar-sitio" ? "sitio" : "buzón"} {r.objeto}, {r.inicio}): <b>{r.estado}</b>
          {r.carpeta && <> — {r.mensajes} correos en la carpeta «{r.carpeta}»</>}{r.error && <> — {r.error}</>}
        </p>
      )}
      {mensaje && <p className="text-sm text-ms-red">{mensaje}</p>}
    </div>
  );
}
