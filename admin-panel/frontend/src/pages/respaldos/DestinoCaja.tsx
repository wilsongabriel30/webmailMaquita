import { useState } from "react";
import { api } from "../../api/client";
import { caja, campo, type Config } from "./tipos";

const TIPOS: Record<string, { nombre: string; ejemplo: string }> = {
  ninguno: { nombre: "Ninguno (solo en este servidor)", ejemplo: "" },
  sftp: { nombre: "Otro servidor por SFTP", ejemplo: "sftp:respaldos@servidor.example.org:/respaldos/institucion" },
  rest: { nombre: "Servidor REST de restic", ejemplo: "rest:https://respaldos.example.org:8000/institucion" },
  s3: { nombre: "Almacenamiento S3 compatible", ejemplo: "s3:https://s3.example.org/cubo/institucion" },
  carpeta: { nombre: "Disco montado (USB, NAS)", ejemplo: "/mnt/usb/respaldos" },
};

/* Copia automática, retención y destino externo; clave de recuperación y clave SSH para guardarlas fuera. */
export function DestinoCaja({ conf, alGuardar }: { conf: Config; alGuardar: () => void }) {
  const [c, setC] = useState<Config>(conf);
  const [cred, setCred] = useState<Record<string, string>>({});
  const [claves, setClaves] = useState<{ clave_recuperacion: string; ssh_publica: string } | null>(null);
  const [mensaje, setMensaje] = useState("");

  const guardar = async () => {
    setMensaje("");
    try {
      const credenciales = Object.keys(cred).length ? cred : undefined;
      await api.put("/respaldos/config", { ...c, credenciales }); setCred({}); setMensaje("Guardado. El destino se usa desde el próximo respaldo."); alGuardar();
    } catch (e) { setMensaje((e as Error).message); }
  };
  const verClaves = async () => {
    if (!confirm("Se mostrará la clave de recuperación de los respaldos. Cópiela a un lugar seguro FUERA de este servidor (gestor de contraseñas, sobre cerrado). Sin ella los respaldos no se pueden abrir.")) return;
    try { setClaves(await api.post("/respaldos/clave")); } catch (e) { setMensaje((e as Error).message); }
  };
  const credencial = (k: string, etiqueta: string, secreto = false) => (
    <input key={k} type={secreto ? "password" : "text"} autoComplete="off" placeholder={`${etiqueta} (no se vuelve a mostrar)`}
      value={cred[k] || ""} onChange={(e) => setCred({ ...cred, [k]: e.target.value })} className={`${campo} w-64`} />
  );

  return (
    <div className={caja}>
      <h2 className="font-semibold text-ms-gray-130">Configuración</h2>
      <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={c.automatico} onChange={(e) => setC({ ...c, automatico: e.target.checked })} />Respaldar cada noche (02:30)</label>
      <div className="flex flex-wrap gap-3 text-sm items-center">
        <span>Conservar:</span>
        {(["diarios", "semanales", "mensuales"] as const).map((k) => (
          <label key={k} className="flex items-center gap-1"><input type="number" min={k === "diarios" ? 1 : 0} max={60} value={c.conservar[k]}
            onChange={(e) => setC({ ...c, conservar: { ...c.conservar, [k]: Number(e.target.value) } })} className={`${campo} w-16`} />{k}</label>
        ))}
      </div>
      <div className="space-y-2">
        <p className="text-sm">Copia fuera del servidor <span className="text-xs text-ms-gray-60">(protege si se pierde el disco o el servidor)</span>:</p>
        <div className="flex flex-wrap gap-2">
          <select value={c.destino.tipo} onChange={(e) => setC({ ...c, destino: { tipo: e.target.value, url: "" } })} className={campo}>
            {Object.entries(TIPOS).map(([k, t]) => <option key={k} value={k}>{t.nombre}</option>)}
          </select>
          {c.destino.tipo !== "ninguno" && <input value={c.destino.url} onChange={(e) => setC({ ...c, destino: { ...c.destino, url: e.target.value.trim() } })}
            placeholder={TIPOS[c.destino.tipo].ejemplo} className={`${campo} flex-1 min-w-[18rem] font-mono`} />}
        </div>
        {c.destino.tipo === "s3" && <div className="flex flex-wrap gap-2">{credencial("AWS_ACCESS_KEY_ID", "Clave de acceso")}{credencial("AWS_SECRET_ACCESS_KEY", "Clave secreta", true)}</div>}
        {c.destino.tipo === "rest" && <div className="flex flex-wrap gap-2">{credencial("RESTIC_REST_USERNAME", "Usuario")}{credencial("RESTIC_REST_PASSWORD", "Contraseña", true)}</div>}
        {c.destino.tipo === "sftp" && <p className="text-xs text-ms-gray-90">Autorice en el servidor de destino la clave SSH pública de este servidor («Ver claves» abajo) para ese usuario.</p>}
      </div>
      <div className="flex gap-2">
        <button onClick={guardar} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Guardar</button>
        <button onClick={verClaves} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm">Ver claves</button>
      </div>
      {claves && (
        <div className="border border-amber-300 bg-amber-50 rounded p-3 text-sm space-y-1">
          <p><b>Clave de recuperación</b> (guárdela fuera del servidor): <code className="select-all break-all">{claves.clave_recuperacion}</code></p>
          <p><b>Clave SSH pública</b> (para el destino SFTP): <code className="select-all break-all text-xs">{claves.ssh_publica}</code></p>
        </div>
      )}
      {mensaje && <p className="text-sm text-ms-gray-90">{mensaje}</p>}
    </div>
  );
}
