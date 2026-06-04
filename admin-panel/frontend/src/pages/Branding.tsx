import { useState, useEffect, useRef } from "react";
import { api } from "../api/client";

const FIELDS = [
  { key: "org_name", label: "Nombre de la organización", placeholder: "Ej: Maquita Cushunchic MCCH", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
  { key: "org_slogan", label: "Eslogan / Descripción corta", placeholder: "Ej: Comercializando como Hermanos", icon: "M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" },
  { key: "org_email", label: "Email de contacto", placeholder: "Ej: info@miorganizacion.org", type: "email", icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
  { key: "org_website", label: "Sitio web", placeholder: "Ej: https://www.miorganizacion.org", type: "url", icon: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" },
  { key: "org_phone", label: "Teléfono", placeholder: "Ej: +593 2 123 4567", icon: "M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" },
  { key: "footer_text", label: "Texto del pie de página", placeholder: "Ej: © 2026 Mi Organización. Todos los derechos reservados.", icon: "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2" },
];

function FileUpload({ label, type, currentUrl, onUpload, onDelete }: {
  label: string; type: "favicon" | "logo"; currentUrl: string | null;
  onUpload: (f: File) => void; onDelete: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const accept = type === "favicon" ? "image/png,image/jpeg,image/x-icon,image/svg+xml,.ico,.jpg,.jpeg" : "image/png,image/jpeg,image/svg+xml,image/webp";

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5">
      <h3 className="text-sm font-semibold text-ms-gray-130 mb-3 flex items-center gap-2">
        <svg className="w-4 h-4 text-ms-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={type === "favicon"
            ? "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"
            : "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
          } />
        </svg>
        {label}
      </h3>
      <div className="flex items-center gap-4">
        {/* Preview */}
        <div className="w-20 h-20 rounded border-2 border-dashed border-ms-gray-40 flex items-center justify-center bg-ms-gray-10 overflow-hidden shrink-0">
          {currentUrl ? (
            <img src={currentUrl} alt={label} className="max-w-full max-h-full object-contain" />
          ) : (
            <svg className="w-8 h-8 text-ms-gray-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          )}
        </div>
        <div className="flex-1">
          <p className="text-xs text-ms-gray-60 mb-2">
            {type === "favicon" ? "ICO, PNG o SVG — 32x32 o 64x64 px recomendado" : "PNG, JPG, SVG o WebP — max 2MB"}
          </p>
          <div className="flex gap-2">
            <input ref={ref} type="file" accept={accept} className="hidden"
              onChange={(e) => { if (e.target.files?.[0]) onUpload(e.target.files[0]); }} />
            <button onClick={() => ref.current?.click()}
              className="px-3 py-1.5 text-xs font-medium text-white rounded transition-colors"
              style={{ backgroundColor: '#0078d4' }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#106ebe')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#0078d4')}
            >
              {currentUrl ? "Cambiar" : "Subir archivo"}
            </button>
            {currentUrl && (
              <button onClick={onDelete}
                className="px-3 py-1.5 text-xs font-medium text-ms-red border border-ms-red/30 rounded hover:bg-red-50 transition-colors">
                Eliminar
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Branding() {
  const [data, setData] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [colorInput, setColorInput] = useState("#0078d4");

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const res = await api.get<Record<string, string>>("/branding");
      setData(res);
      setOriginal(res);
      setColorInput(res.primary_color || "#0078d4");
    } catch (err) {
      setError("Error al cargar configuración");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true); setSaved(false); setError("");
    try {
      const payload: Record<string, string> = {};
      for (const f of FIELDS) {
        if (data[f.key] !== undefined) payload[f.key] = data[f.key];
      }
      payload.primary_color = colorInput;
      await api.put("/branding", payload);
      setOriginal({ ...data, primary_color: colorInput });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError("Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (type: "favicon" | "logo", file: File) => {
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const token = localStorage.getItem("admin_token");
      const res = await fetch(`/api/branding/upload/${type}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Error al subir");
      }
      const json = await res.json();
      setData(prev => ({ ...prev, [`${type}_url`]: json.url + "?t=" + Date.now() }));
    } catch (err: any) {
      setError(err.message || "Error al subir archivo");
    }
  };

  const handleDelete = async (type: "favicon" | "logo") => {
    try {
      await api.del(`/branding/file/${type}`);
      setData(prev => { const n = { ...prev }; delete n[`${type}_url`]; return n; });
    } catch {
      setError("Error al eliminar");
    }
  };

  const hasChanges = JSON.stringify({ ...data, primary_color: colorInput }) !==
    JSON.stringify({ ...original, primary_color: original.primary_color });

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="text-ms-gray-60 text-sm">Cargando...</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-ms-gray-130 flex items-center gap-2">
          <svg className="w-6 h-6 text-ms-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
          </svg>
          Personalización
        </h1>
        <p className="text-sm text-ms-gray-60 mt-1">
          Configura la identidad visual de tu instalación de Maquita Mail. Estos datos se mostrarán en el login, el webmail y los correos del sistema.
        </p>
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-ms-red/30 rounded text-ms-red text-sm flex items-center gap-2">
          <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
          {error}
          <button onClick={() => setError("")} className="ml-auto text-ms-red/60 hover:text-ms-red">&times;</button>
        </div>
      )}
      {saved && (
        <div className="mb-4 p-3 bg-green-50 border border-green-300 rounded text-green-700 text-sm flex items-center gap-2">
          <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
          Configuración guardada correctamente
        </div>
      )}

      {/* File uploads */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <FileUpload label="Favicon" type="favicon"
          currentUrl={data.favicon_url || null}
          onUpload={(f) => handleUpload("favicon", f)}
          onDelete={() => handleDelete("favicon")} />
        <FileUpload label="Logo institucional" type="logo"
          currentUrl={data.logo_url || null}
          onUpload={(f) => handleUpload("logo", f)}
          onDelete={() => handleDelete("logo")} />
      </div>

      {/* Color */}
      <div className="bg-white rounded border border-ms-gray-30 p-5 mb-6">
        <h3 className="text-sm font-semibold text-ms-gray-130 mb-3 flex items-center gap-2">
          <svg className="w-4 h-4 text-ms-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
          </svg>
          Color primario
        </h3>
        <div className="flex items-center gap-4">
          <input type="color" value={colorInput} onChange={(e) => setColorInput(e.target.value)}
            className="w-12 h-10 rounded border border-ms-gray-40 cursor-pointer" />
          <input type="text" value={colorInput} onChange={(e) => setColorInput(e.target.value)}
            className="w-28 px-3 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-130 font-mono focus:outline-none focus:border-ms-blue"
            placeholder="#0078d4" maxLength={7} />
          <div className="flex gap-2">
            {["#0078d4", "#107c10", "#8661c5", "#d83b01", "#004e8c", "#c239b3"].map(c => (
              <button key={c} onClick={() => setColorInput(c)}
                className="w-7 h-7 rounded-full border-2 transition-all"
                style={{ backgroundColor: c, borderColor: colorInput === c ? '#323130' : 'transparent' }}
                title={c} />
            ))}
          </div>
        </div>
        {/* Preview */}
        <div className="mt-3 flex items-center gap-3">
          <span className="text-xs text-ms-gray-60">Vista previa:</span>
          <div className="h-8 px-4 rounded flex items-center" style={{ backgroundColor: colorInput }}>
            <span className="text-white text-xs font-medium">Maquita Mail</span>
          </div>
        </div>
      </div>

      {/* Text fields */}
      <div className="bg-white rounded border border-ms-gray-30 p-5 mb-6">
        <h3 className="text-sm font-semibold text-ms-gray-130 mb-4 flex items-center gap-2">
          <svg className="w-4 h-4 text-ms-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          Datos de la organización
        </h3>
        <div className="space-y-4">
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label className="block text-sm font-medium text-ms-gray-130 mb-1 flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5 text-ms-gray-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={f.icon} />
                </svg>
                {f.label}
              </label>
              <input
                type={f.type || "text"}
                value={data[f.key] || ""}
                onChange={(e) => setData(prev => ({ ...prev, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-130 focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving}
          className="px-5 py-2.5 text-white font-medium rounded text-sm transition-colors disabled:opacity-50"
          style={{ backgroundColor: '#0078d4' }}
          onMouseEnter={(e) => { if (!saving) e.currentTarget.style.backgroundColor = '#106ebe'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#0078d4'; }}
        >
          {saving ? "Guardando..." : "Guardar cambios"}
        </button>
        {hasChanges && (
          <span className="text-xs text-ms-gray-60 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            Hay cambios sin guardar
          </span>
        )}
      </div>

      {/* Info box */}
      <div className="mt-6 p-4 bg-ms-blue-lighter rounded border border-ms-blue-light">
        <p className="text-xs text-ms-gray-90">
          <strong>Nota:</strong> Estos datos permiten personalizar la instalación de Maquita Mail para tu organizacion.
          El favicon y logo se aplicarán en el login y la interfaz del webmail.
          Si publicas este proyecto en GitHub, cada organización podrá configurar su propia identidad desde aquí.
        </p>
      </div>
    </div>
  );
}
