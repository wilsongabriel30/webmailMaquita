import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Delegation {
  id: number;
  mailbox: string;
  delegate: string;
  access_level: string;
  folders: string[];
}

interface Mailbox {
  username: string;
  name: string;
  active: boolean;
}

const ACCESS_LEVELS = [
  { value: "read", label: "Lectura" },
  { value: "write", label: "Escritura" },
  { value: "full", label: "Completo" },
  { value: "send_as", label: "Enviar como" },
];

const FOLDERS = ["INBOX", "Sent", "Drafts", "Trash", "Junk"];

const ACCESS_LABELS: Record<string, string> = {
  read: "Lectura",
  write: "Escritura",
  full: "Completo",
  send_as: "Enviar como",
};

function _rightsToLevel(rights: string[]): string {
  if (rights.includes("expunge") || rights.includes("create")) return "full";
  if (rights.includes("write") || rights.includes("insert")) return "write";
  return "read";
}

export function SharedMailboxes() {
  const [delegations, setDelegations] = useState<Delegation[]>([]);
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    mailbox: "",
    delegate: "",
    access_level: "read",
    folders: ["INBOX"] as string[],
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [delsResp, mboxes] = await Promise.allSettled([
        api.get<{delegations: any[]}>("/shared/delegates"),
        api.get<Mailbox[]>("/mailboxes"),
      ]);
      // Delegaciones
      if (delsResp.status === "fulfilled") {
        const raw = delsResp.value;
        const rawDels = Array.isArray(raw) ? raw : ((raw as any)?.delegations || []);
        setDelegations(rawDels.map((d: any, i: number) => ({
          id: d.id ?? i, mailbox: d.mailbox, delegate: d.delegate,
          access_level: d.access_level || _rightsToLevel(d.rights || []),
          folders: d.folders || (d.folder ? [d.folder] : []),
        })));
      } else {
        setDelegations([]);
      }
      // Buzones
      if (mboxes.status === "fulfilled") {
        const m = mboxes.value;
        setMailboxes(Array.isArray(m) ? m.filter((mb) => mb.active) : []);
      }
    } catch (err: any) {
      console.warn("Error cargando delegaciones:", err?.message);
      setDelegations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggleFolder = (folder: string) => {
    setForm((prev) => ({
      ...prev,
      folders: prev.folders.includes(folder)
        ? prev.folders.filter((f) => f !== folder)
        : [...prev.folders, folder],
    }));
  };

  const grant = async () => {
    if (!form.mailbox || !form.delegate) {
      setError("Seleccione un buzón y escriba el email del delegado.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await api.post(`/shared/mailbox/${encodeURIComponent(form.mailbox)}/grant`, {
        delegate: form.delegate,
        access_level: form.access_level,
        folders: form.folders,
      });
      setForm({ mailbox: "", delegate: "", access_level: "read", folders: ["INBOX"] });
      setShowForm(false);
      load();
    } catch (e: any) {
      setError(e?.message || "Error al otorgar acceso.");
    } finally {
      setSubmitting(false);
    }
  };

  const revoke = async (delegation: Delegation) => {
    if (!confirm(`¿Revocar el acceso de ${delegation.delegate} al buzón ${delegation.mailbox}?`)) return;
    try {
      await api.post(`/shared/mailbox/${encodeURIComponent(delegation.mailbox)}/revoke`, {
        delegate: delegation.delegate,
      });
      load();
    } catch {
      alert("Error al revocar el acceso.");
    }
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Buzones compartidos y delegación</h1>
        <button
          onClick={() => { setShowForm(!showForm); setError(""); }}
          className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark"
          title="Abrir formulario para otorgar acceso a un buzón"
        >
          + Otorgar acceso
        </button>
      </div>

      {/* Formulario para otorgar acceso */}
      {showForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-ms-gray-130">Otorgar acceso a buzón</h2>

          {error && (
            <div className="px-3 py-2 bg-red-50 border border-red-200 rounded text-sm text-ms-red">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Buzón */}
            <div>
              <label className="block text-xs font-medium text-ms-gray-90 mb-1">Buzón (propietario)</label>
              <select
                value={form.mailbox}
                onChange={(e) => setForm({ ...form, mailbox: e.target.value })}
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue"
                title="Seleccione el buzón al que se otorgará acceso"
              >
                <option value="">— Seleccione un buzón —</option>
                {mailboxes.map((m) => (
                  <option key={m.username} value={m.username}>
                    {m.username}{m.name ? ` (${m.name})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Delegado */}
            <div>
              <label className="block text-xs font-medium text-ms-gray-90 mb-1">Delegado (quién recibe acceso)</label>
              <input
                type="email"
                placeholder="usuario@dominio.com"
                value={form.delegate}
                onChange={(e) => setForm({ ...form, delegate: e.target.value })}
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue"
                title="Email del usuario que recibirá acceso al buzón"
              />
            </div>
          </div>

          {/* Nivel de acceso */}
          <div>
            <label className="block text-xs font-medium text-ms-gray-90 mb-1">Nivel de acceso</label>
            <select
              value={form.access_level}
              onChange={(e) => setForm({ ...form, access_level: e.target.value })}
              className="w-full md:w-64 px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue"
              title="Define el nivel de permisos que tendrá el delegado"
            >
              {ACCESS_LEVELS.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>

          {/* Carpetas */}
          <div>
            <label className="block text-xs font-medium text-ms-gray-90 mb-2">Carpetas accesibles</label>
            <div className="flex flex-wrap gap-3">
              {FOLDERS.map((folder) => (
                <label
                  key={folder}
                  className="flex items-center gap-1.5 text-sm text-ms-gray-130 cursor-pointer"
                  title={`Incluir la carpeta ${folder} en el acceso delegado`}
                >
                  <input
                    type="checkbox"
                    checked={form.folders.includes(folder)}
                    onChange={() => toggleFolder(folder)}
                    className="accent-ms-blue"
                  />
                  {folder}
                </label>
              ))}
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={grant}
              disabled={submitting}
              className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50"
              title="Confirmar y otorgar el acceso al buzón seleccionado"
            >
              {submitting ? "Guardando..." : "Otorgar acceso"}
            </button>
            <button
              onClick={() => { setShowForm(false); setError(""); }}
              className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90 hover:bg-ms-gray-10"
              title="Cancelar y cerrar el formulario"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Tabla de delegaciones */}
      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <div className="px-4 py-3 bg-ms-gray-20 border-b border-ms-gray-30 flex items-center justify-between">
          <span className="text-sm font-semibold text-ms-gray-130">
            Delegaciones activas ({delegations.length})
          </span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-ms-gray-60 text-sm">Cargando...</div>
        ) : delegations.length === 0 ? (
          <div className="p-8 text-center text-ms-gray-60 text-sm">
            No hay delegaciones configuradas. Use el botón "Otorgar acceso" para crear una.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-10 border-b border-ms-gray-30">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Buzón</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Delegado</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Nivel de acceso</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Carpetas</th>
                <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ms-gray-30">
              {delegations.map((d) => (
                <tr key={d.id} className="hover:bg-ms-blue-lighter/50">
                  <td className="px-4 py-2.5 text-ms-gray-130 font-medium">{d.mailbox}</td>
                  <td className="px-4 py-2.5 text-ms-blue">{d.delegate}</td>
                  <td className="px-4 py-2.5">
                    <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-ms-blue-lighter text-ms-blue">
                      {ACCESS_LABELS[d.access_level] || d.access_level}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {(d.folders || []).map((f) => (
                        <span key={f} className="px-1.5 py-0.5 rounded text-[10px] bg-ms-gray-20 text-ms-gray-90">
                          {f}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => revoke(d)}
                      className="text-ms-red text-xs hover:underline"
                      title={`Revocar acceso de ${d.delegate} al buzón ${d.mailbox}`}
                    >
                      Revocar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
