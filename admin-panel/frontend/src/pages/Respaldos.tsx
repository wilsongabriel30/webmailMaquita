import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { DestinoCaja } from "./respaldos/DestinoCaja";
import { RestaurarCaja } from "./respaldos/RestaurarCaja";
import { caja, type Estado } from "./respaldos/tipos";

/* Respaldos del servidor: estado, respaldar y comprobar, restaurar un sitio o un buzón, destino y claves. */
export function Respaldos() {
  const [est, setEst] = useState<Estado | null>(null);
  const [mensaje, setMensaje] = useState("");

  const cargar = () => api.get<Estado>("/respaldos").then(setEst).catch((e) => setMensaje(e.message));
  useEffect(() => { cargar(); }, []);
  const trabajando = !!est && (est.en_curso || est.restauracion?.estado === "en curso");
  useEffect(() => {
    if (!trabajando) return;
    const t = setInterval(cargar, 5000);
    return () => clearInterval(t);
  }, [trabajando]);

  const lanzar = async (ruta: string) => {
    setMensaje("");
    try { await api.post(ruta); setTimeout(cargar, 1500); } catch (e) { setMensaje((e as Error).message); }
  };

  if (!est) return <div className="p-6 text-sm text-ms-gray-60">{mensaje || "Cargando…"}</div>;
  const u = est.ultimo;
  const ok = est.ultimo_correcto;
  const comp = est.comprobacion;

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <h1 className="text-xl font-semibold text-ms-gray-130">Respaldos</h1>
      <SectionHelp titulo="Respaldos" items={[
        { titulo: "Qué se respalda", desc: "Correo y calendarios, todas las bases de datos (una por archivo), el Drive, los sitios web, la configuración, certificados, claves DKIM y secretos. Cada noche solo se guarda lo que cambió (restic), cifrado con la clave de recuperación." },
        { titulo: "Dónde", desc: "En este servidor y, si se configura, en un destino externo (otro servidor, S3 o un disco). Sin copia externa, una avería del disco se lleva también los respaldos." },
        { titulo: "La máquina completa", desc: "Para volver a tener el servidor entero tras un desastre, programe además en Proxmox el respaldo semanal de la VM (deploy/plantilla/respaldo-vm.sh)." },
      ]} />

      <div className={caja}>
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-sm space-y-1">
            {ok ? <p>Último respaldo correcto: <b>{ok.inicio}</b> ({ok.total_mb} MB respaldados, {ok.nuevo_mb} MB nuevos, {ok.bases} bases, {ok.duracion_s} s){ok.externo && <> · copia externa: {ok.externo}</>}</p>
              : <p className="text-ms-red">Todavía no hay ningún respaldo correcto.</p>}
            {u && u !== ok && u.estado !== "correcto" && <p className="text-ms-red">El último intento ({u.inicio}) {u.estado}: {u.error || u.externo}</p>}
            <p className="text-xs text-ms-gray-60">{est.instantaneas.length} instantáneas · {est.config.destino.tipo === "ninguno" ? "sin copia externa" : `copia externa: ${est.config.destino.url}`} · {est.disco_libre_gb} GB libres</p>
            {comp && <p className="text-xs">Comprobación ({comp.fecha_comprobacion}): <b className={comp.estado === "correcta" ? "text-ms-green" : "text-ms-red"}>{comp.estado}</b>{comp.prueba_base_correo && <> — base del correo {comp.prueba_base_correo}</>}{comp.error && <> — {comp.error}</>}</p>}
          </div>
          <div className="ml-auto flex gap-2">
            <button onClick={() => lanzar("/respaldos/respaldar")} disabled={trabajando} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Respaldar ahora</button>
            <button onClick={() => lanzar("/respaldos/comprobar")} disabled={trabajando || !est.instantaneas.length} title="Lee una muestra de los datos y prueba a restaurar la base del correo en una base desechable." className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Comprobar</button>
          </div>
        </div>
        {trabajando && <p className="text-sm text-amber-700">Trabajando… (se actualiza solo)</p>}
      </div>

      {est.instantaneas.length > 0 && <RestaurarCaja est={est} alTerminar={() => setTimeout(cargar, 1500)} />}
      <DestinoCaja conf={est.config} alGuardar={cargar} />
      {mensaje && <p className="text-sm text-ms-red">{mensaje}</p>}
    </div>
  );
}
