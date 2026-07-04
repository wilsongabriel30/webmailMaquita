import { useEffect, useState, useRef } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface AR { id: number; username: string; active: boolean; subject: string; body: string; start_date: string; end_date: string; reply_once_per_day: boolean; user_fullname: string }
interface Suggestion { username: string; name: string }

export function AutoResponder() {
  const [list, setList] = useState<AR[]>([]);
  const [form, setForm] = useState({ username: "", active: false, subject: "Fuera de oficina", body: "", start_date: "", end_date: "", reply_once_per_day: false });
  const [editing, setEditing] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSugg, setShowSugg] = useState(false);
  const timerRef = useRef<any>(null);

  const load = () => api.get<AR[]>("/autoresponder").then(setList).catch(() => {});
  useEffect(() => { load(); }, []);

  const searchUsers = (q: string) => {
    setForm({ ...form, username: q });
    if (timerRef.current) clearTimeout(timerRef.current);
    if (q.length < 2) { setSuggestions([]); setShowSugg(false); return; }
    timerRef.current = setTimeout(() => {
      api.get<Suggestion[]>(`/mailboxes/search/autocomplete?q=${encodeURIComponent(q)}&limit=8`)
        .then((d) => { setSuggestions(d); setShowSugg(d.length > 0); })
        .catch(() => {});
    }, 300);
  };

  const save = async () => {
    const data = { ...form, start_date: form.start_date || null, end_date: form.end_date || null };
    await api.post("/autoresponder", data);
    setForm({ username: "", active: false, subject: "Fuera de oficina", body: "", start_date: "", end_date: "", reply_once_per_day: false });
    setEditing(false);
    load();
  };

  const edit = (ar: AR) => {
    setForm({
      username: ar.username, active: ar.active, subject: ar.subject, body: ar.body,
      start_date: ar.start_date?.slice(0, 10) || "", end_date: ar.end_date?.slice(0, 10) || "",
      reply_once_per_day: ar.reply_once_per_day,
    });
    setEditing(true);
  };

  const del = async (username: string) => {
    if (!confirm(`Eliminar auto-respuesta de ${username}?`)) return;
    await api.del(`/autoresponder/${username}`);
    load();
  };

  const deactivate = async (ar: AR) => {
    await api.post("/autoresponder", { ...ar, active: false });
    load();
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Respuestas automáticas (Fuera de oficina)</h1>
        <SectionHelp titulo="Respuestas automáticas" items={[
          { titulo: "Para qué sirve", desc: "Configura mensajes de fuera de oficina: cuando alguien escribe al usuario, el servidor le responde automáticamente con el asunto y mensaje definidos aquí." },
          { titulo: "Formulario", desc: "Escriba el email del usuario (con autocompletado), el asunto y el cuerpo del mensaje. Las fechas de inicio y fin delimitan el periodo; si se dejan vacías la respuesta es permanente." },
          { titulo: "Responder una vez por día", desc: "Evita spam: cada remitente recibe la respuesta automática como máximo una vez al día, aunque envíe varios correos." },
          { titulo: "Tabla inferior", desc: "Lista todas las respuestas configuradas con su estado (Activo/Inactivo) y su periodo de vigencia." },
          { titulo: "Acciones", desc: "Editar modifica el mensaje, Desactivar lo pausa sin borrarlo (se puede reactivar) y Eliminar lo borra permanentemente. Todo se registra en auditoría." },
        ]} />
      </div>

      <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ms-gray-130">{editing ? "Editar respuesta" : "Configurar respuesta automatica"}</h2>
        <div className="grid grid-cols-2 gap-3">
          <div className="relative">
            <input value={form.username} onChange={(e) => searchUsers(e.target.value)}
              onFocus={() => suggestions.length > 0 && setShowSugg(true)}
              placeholder="usuario@dominio"
              disabled={editing}
              title="Escribe el email del usuario para configurar su respuesta automatica. Autocompletado disponible."
              className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue disabled:bg-ms-gray-20" />
            {showSugg && suggestions.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-ms-gray-30 rounded shadow-lg max-h-40 overflow-auto">
                {suggestions.map((s) => (
                  <button key={s.username} onClick={() => { setForm({ ...form, username: s.username }); setShowSugg(false); }}
                    title={`Seleccionar ${s.username} para configurar su respuesta automatica.`}
                    className="w-full text-left px-3 py-2 hover:bg-ms-blue-lighter text-sm flex justify-between">
                    <span className="font-medium">{s.username}</span>
                    {s.name && <span className="text-ms-gray-60 text-xs">{s.name}</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
          <input placeholder="Asunto del mensaje" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
            title="Asunto que veran los remitentes en la respuesta automatica."
            className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            title="Define el inicio del periodo de la respuesta automatica. Dejar vacio para que sea permanente."
            className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            title="Define el fin del periodo de la respuesta automatica. Dejar vacio para que sea permanente."
            className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
        </div>
        <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} rows={4}
          placeholder="Mensaje de respuesta automatica..."
          title="Cuerpo del mensaje que recibiran los remitentes automaticamente. Escribe un mensaje claro indicando ausencia y fecha de retorno."
          className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-ms-gray-130"
            title="Controla si la respuesta automatica esta activa. Desmarcar para pausar sin eliminar.">
            <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })}
              title="Controla si la respuesta automatica esta activa. Desmarcar para pausar sin eliminar."
              className="accent-ms-blue" />
            Activar
          </label>
          <label className="flex items-center gap-2 text-sm text-ms-gray-130"
            title="Si esta activo, cada remitente recibira la respuesta automatica solo una vez por dia, evitando spam.">
            <input type="checkbox" checked={form.reply_once_per_day} onChange={(e) => setForm({ ...form, reply_once_per_day: e.target.checked })}
              title="Si esta activo, cada remitente recibira la respuesta automatica solo una vez por dia, evitando spam."
              className="accent-ms-blue" />
            Responder una vez por dia por remitente
          </label>
        </div>
        <div className="flex gap-2">
          <button onClick={save}
            title={editing ? "Modifica la respuesta automatica existente. Los cambios se aplican inmediatamente. Se registra en auditoria." : "Activa la respuesta automatica para este usuario. Los remitentes recibiran este mensaje automaticamente. Se registra en auditoria."}
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm">{editing ? "Guardar" : "Crear"}</button>
          {editing && <button onClick={() => { setEditing(false); setForm({ username: "", active: true, subject: "Fuera de oficina", body: "", start_date: "", end_date: "", reply_once_per_day: true }); }}
            title="Cancela la edicion y limpia el formulario. No se guardan cambios."
            className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>}
        </div>
      </div>

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Usuario</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Nombre</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Asunto</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Estado</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Periodo</th>
            <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
          </tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {list.map((ar) => (
              <tr key={ar.id} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5 font-medium text-ms-gray-130">{ar.username}</td>
                <td className="px-4 py-2.5 text-ms-gray-60 text-xs">{ar.user_fullname || "-"}</td>
                <td className="px-4 py-2.5 text-ms-gray-130 text-xs">{ar.subject}</td>
                <td className="px-4 py-2.5 text-center">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${ar.active ? "bg-green-50 text-ms-green" : "bg-ms-gray-20 text-ms-gray-60"}`}
                    title={ar.active ? "La respuesta automatica esta activa y respondiendo a los remitentes." : "La respuesta automatica esta pausada. No se envian respuestas."}>
                    {ar.active ? "Activo" : "Inactivo"}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-60">
                  {ar.start_date && ar.end_date ? `${ar.start_date.slice(0, 10)} a ${ar.end_date.slice(0, 10)}` : "Permanente"}
                </td>
                <td className="px-4 py-2.5 text-right space-x-2">
                  <button onClick={() => edit(ar)}
                    title="Modifica la respuesta automatica existente. Los cambios se aplican inmediatamente. Se registra en auditoria."
                    className="text-ms-blue text-xs hover:underline">Editar</button>
                  {ar.active && <button onClick={() => deactivate(ar)}
                    title="Desactiva temporalmente sin eliminar. Se puede reactivar despues."
                    className="text-ms-orange text-xs hover:underline">Desactivar</button>}
                  <button onClick={() => del(ar.username)}
                    title="PRECAUCION: Elimina la respuesta automatica permanentemente. El usuario dejara de responder automaticamente. Se registra en auditoria."
                    className="text-ms-red text-xs hover:underline">Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {list.length === 0 && <div className="p-6 text-center text-ms-gray-60 text-sm">Sin respuestas automáticas configuradas</div>}
      </div>
    </div>
  );
}
