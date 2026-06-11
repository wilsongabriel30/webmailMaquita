/**
 * SignatureManager.tsx — Visual WYSIWYG editor for email signatures
 *
 * Features:
 *   - Rich text editor (like Word) — no HTML knowledge needed
 *   - Live preview showing how signature looks in email
 *   - "Load default template" for domain-based corporate templates
 *   - Signature position options (bottom / before quotes)
 *   - Include in replies/forwards toggles
 *   - Optional HTML source view for advanced users
 */

import { sanitizeSignatureHtml } from '../../lib/sanitize';
import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../../api/client';

interface Signature {
  id: number;
  owner: string;
  name: string;
  html_content: string;
  is_default: boolean;
  created_at: string;
}

interface SignatureSettings {
  position: 'bottom' | 'before_quote';
  include_in_reply: boolean;
  include_in_forward: boolean;
}

interface Feedback { type: 'success' | 'error'; message: string; }

const DEFAULT_SIG_SETTINGS: SignatureSettings = {
  position: 'bottom',
  include_in_reply: true,
  include_in_forward: true,
};

export function SignatureManager() {
  const [signatures, setSignatures] = useState<Signature[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [draftName, setDraftName] = useState('');
  const [draftDefault, setDraftDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [sigSettings, setSigSettings] = useState<SignatureSettings>(DEFAULT_SIG_SETTINGS);

  const flash = useCallback((fb: Feedback) => {
    setFeedback(fb);
    setTimeout(() => setFeedback(null), 4000);
  }, []);

  const fetchSignatures = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<Signature[]>('/settings/signatures');
      setSignatures(res);
    } catch (err: unknown) {
      flash({ type: 'error', message: err instanceof Error ? err.message : 'Error al cargar firmas' });
    } finally {
      setLoading(false);
    }
  }, [flash]);

  useEffect(() => {
    const saved = localStorage.getItem('maquita_sig_settings');
    if (saved) try { setSigSettings({ ...DEFAULT_SIG_SETTINGS, ...JSON.parse(saved) }); } catch {}
  }, []);

  useEffect(() => { fetchSignatures(); }, [fetchSignatures]);

  const saveSigSettings = useCallback((s: SignatureSettings) => {
    setSigSettings(s);
    localStorage.setItem('maquita_sig_settings', JSON.stringify(s));
    flash({ type: 'success', message: 'Configuración de firma guardada' });
  }, [flash]);

  const clearEdit = useCallback(() => {
    setEditingId(null);
    setIsCreating(false);
    setDraftName('');
    setDraftDefault(false);
  }, []);

  const startCreate = useCallback(() => {
    clearEdit();
    setIsCreating(true);
  }, [clearEdit]);

  const startEdit = useCallback((sig: Signature) => {
    clearEdit();
    setEditingId(sig.id);
    setDraftName(sig.name);
    setDraftDefault(sig.is_default);
  }, [clearEdit]);

  const handleSave = useCallback(async (html: string) => {
    if (!draftName.trim()) { flash({ type: 'error', message: 'El nombre es obligatorio' }); return; }
    setSaving(true);
    try {
      if (isCreating) {
        await api.post('/settings/signatures', { name: draftName.trim(), html_content: html, is_default: draftDefault });
        flash({ type: 'success', message: 'Firma creada' });
      } else if (editingId) {
        await api.put(`/settings/signatures/${editingId}`, { name: draftName.trim(), html_content: html, is_default: draftDefault || undefined });
        flash({ type: 'success', message: 'Firma actualizada' });
      }
      clearEdit();
      await fetchSignatures();
    } catch (err: unknown) {
      flash({ type: 'error', message: err instanceof Error ? err.message : 'Error al guardar' });
    } finally { setSaving(false); }
  }, [draftName, draftDefault, isCreating, editingId, clearEdit, fetchSignatures, flash]);

  const handleDelete = useCallback(async (id: number) => {
    try {
      await api.del(`/settings/signatures/${id}`);
      flash({ type: 'success', message: 'Firma eliminada' });
      setDeletingId(null);
      clearEdit();
      await fetchSignatures();
    } catch (err: unknown) {
      flash({ type: 'error', message: err instanceof Error ? err.message : 'Error al eliminar' });
    }
  }, [clearEdit, fetchSignatures, flash]);

  const handleSetDefault = useCallback(async (id: number) => {
    try {
      await api.put(`/settings/signatures/${id}`, { is_default: true });
      flash({ type: 'success', message: 'Firma predeterminada actualizada' });
      await fetchSignatures();
    } catch (err: unknown) {
      flash({ type: 'error', message: err instanceof Error ? err.message : 'Error' });
    }
  }, [fetchSignatures, flash]);

  const isEditing = editingId !== null || isCreating;
  const editingSig = editingId ? signatures.find(s => s.id === editingId) : null;

  return (
    <section className="space-y-5" style={{ fontFamily: "'Calibri', 'Segoe UI', sans-serif" }}>
      {feedback && (
        <div className={`rounded px-3 py-2 text-[13px] ${feedback.type === 'success' ? 'bg-[#dff6dd] text-[#0b6a0b]' : 'bg-[#fde7e9] text-[#d13438]'}`}>
          {feedback.message}
        </div>
      )}

      {/* Signature Position Settings */}
      <div className="rounded border border-[#edebe9] bg-white">
        <div className="border-b border-[#edebe9] px-5 py-3">
          <h2 className="text-[15px] font-semibold text-[#323130]">Configuración de firma</h2>
          <p className="mt-0.5 text-[12px] text-[#605e5c]">Elige donde aparece tu firma en los correos</p>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div>
            <label className="block text-[12px] font-semibold text-[#605e5c] mb-2">Posición de la firma</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="sig_pos" checked={sigSettings.position === 'bottom'}
                  onChange={() => saveSigSettings({ ...sigSettings, position: 'bottom' })}
                  className="w-4 h-4 text-[#0078d4]" />
                <span className="text-[13px] text-[#323130]">Al pie del correo (después del mensaje)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="sig_pos" checked={sigSettings.position === 'before_quote'}
                  onChange={() => saveSigSettings({ ...sigSettings, position: 'before_quote' })}
                  className="w-4 h-4 text-[#0078d4]" />
                <span className="text-[13px] text-[#323130]">Antes del texto citado (en respuestas y reenvios)</span>
              </label>
            </div>
          </div>
          <div className="border-t border-[#edebe9] pt-3 space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={sigSettings.include_in_reply}
                onChange={e => saveSigSettings({ ...sigSettings, include_in_reply: e.target.checked })}
                className="w-4 h-4 rounded border-[#8a8886] text-[#0078d4]" />
              <span className="text-[13px] text-[#323130]">Incluir firma en respuestas</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={sigSettings.include_in_forward}
                onChange={e => saveSigSettings({ ...sigSettings, include_in_forward: e.target.checked })}
                className="w-4 h-4 rounded border-[#8a8886] text-[#0078d4]" />
              <span className="text-[13px] text-[#323130]">Incluir firma en reenvios</span>
            </label>
          </div>
        </div>
      </div>

      {/* Signatures List */}
      <div className="rounded border border-[#edebe9] bg-white">
        <div className="flex items-center justify-between border-b border-[#edebe9] px-5 py-3">
          <div>
            <h2 className="text-[15px] font-semibold text-[#323130]">Firmas de correo</h2>
            <p className="mt-0.5 text-[12px] text-[#605e5c]">La firma predeterminada se inserta automáticamente al redactar.</p>
          </div>
          {!isEditing && (
            <button type="button" onClick={startCreate}
              className="rounded px-3 py-[5px] text-[13px] font-semibold text-white bg-[#0078d4] hover:bg-[#106ebe] transition-colors">
              + Nueva firma
            </button>
          )}
        </div>

        {loading && <div className="px-5 py-6 text-center text-[13px] text-[#605e5c]">Cargando firmas...</div>}

        {isEditing && (
          <div className="border-b border-[#edebe9] bg-[#faf9f8] px-5 py-4">
            <h3 className="mb-3 text-[14px] font-semibold text-[#323130]">
              {isCreating ? 'Nueva firma' : 'Editar firma'}
            </h3>
            <VisualSignatureEditor
              initialHtml={editingSig?.html_content || ''}
              name={draftName}
              isDefault={draftDefault}
              onNameChange={setDraftName}
              onDefaultChange={setDraftDefault}
              onSave={handleSave}
              onCancel={clearEdit}
              saveLabel={isCreating ? 'Crear firma' : 'Guardar cambios'}
              saving={saving}
            />
          </div>
        )}

        {!loading && (
          <ul className="divide-y divide-[#edebe9]">
            {signatures.map(sig => {
              if (editingId === sig.id) return null;
              const isDeleting = deletingId === sig.id;
              return (
                <li key={sig.id} className="px-5 py-3 hover:bg-[#faf9f8] transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[14px] font-semibold text-[#323130]">{sig.name}</span>
                        {sig.is_default && (
                          <span className="rounded bg-[#deecf9] px-2 py-0.5 text-[10px] font-bold text-[#0078d4]">PREDETERMINADA</span>
                        )}
                      </div>
                      {sig.html_content ? (
                        <div className="rounded border border-[#edebe9] bg-white p-3 max-h-[200px] overflow-auto">
                          <div className="text-[13px] sig-preview" dangerouslySetInnerHTML={{ __html: sanitizeSignatureHtml(sig.html_content) }} />
                        </div>
                      ) : (
                        <p className="text-[12px] text-[#a19f9d] italic py-2">Sin contenido - haz clic en Editar para agregar tu firma</p>
                      )}
                    </div>
                    <div className="flex flex-col gap-1 shrink-0 pt-1">
                      {!sig.is_default && (
                        <ActionBtn label="Predeterminada" onClick={() => handleSetDefault(sig.id)} />
                      )}
                      <ActionBtn label="Editar" onClick={() => startEdit(sig)} />
                      {isDeleting ? (
                        <div className="flex items-center gap-1">
                          <ActionBtn label="Si" danger onClick={() => handleDelete(sig.id)} />
                          <ActionBtn label="No" onClick={() => setDeletingId(null)} />
                        </div>
                      ) : (
                        <ActionBtn label="Eliminar" danger onClick={() => setDeletingId(sig.id)} />
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
            {signatures.length === 0 && !isCreating && (
              <li className="px-5 py-8 text-center">
                <p className="text-[13px] text-[#a19f9d] mb-2">No hay firmas configuradas</p>
                <button onClick={startCreate} className="text-[13px] text-[#0078d4] hover:underline">Crear tu primera firma</button>
              </li>
            )}
          </ul>
        )}
      </div>
    </section>
  );
}

/* ── Signature Editor — field-based + HTML source ── */

interface SigFields {
  nombre: string;
  cargo: string;
  telefono1: string;
  telefono2: string;
  email: string;
  ciudad: string;
}

const EMPTY_FIELDS: SigFields = { nombre: '', cargo: '', telefono1: '', telefono2: '', email: '', ciudad: 'Quito - Ecuador' };

function extractFields(html: string): SigFields {
  const f = { ...EMPTY_FIELDS };
  // Name: blue bold span
  const nm = html.match(/color:#0061a1">([^<]+)<\/span><\/strong>/);
  if (nm) f.nombre = nm[1].trim();
  // Cargo: div with color:#555
  const cg = html.match(/color:#555">([^<]*)<\/div>/);
  if (cg) f.cargo = cg[1].trim();
  // Phones
  const phones: string[] = [];
  const pr = /font-family:Verdana[^>]*>\(([^<]+)<\/span><\/td>/g;
  let pm;
  while ((pm = pr.exec(html)) !== null) phones.push('(' + pm[1]);
  if (phones[0]) f.telefono1 = phones[0];
  if (phones[1]) f.telefono2 = phones[1];
  // Email
  const em = html.match(/mailto:([^"]+)"/);
  if (em) f.email = em[1];
  // Ciudad
  const ci = html.match(/font-family:Verdana[^>]*>([^<]*(?:Ecuador|Guayaquil|Cuenca|Ambato)[^<]*)<\/span><\/td>/i);
  if (ci) f.ciudad = ci[1].trim();
  return f;
}

function applyFields(tpl: string, f: SigFields): string {
  return tpl
    .replace('{{NOMBRE}}', f.nombre)
    .replace('{{CARGO}}', f.cargo)
    .replace('{{TELEFONO1}}', f.telefono1)
    .replace('{{TELEFONO2}}', f.telefono2)
    .replace(/\{\{EMAIL\}\}/g, f.email)
    .replace('{{CIUDAD}}', f.ciudad);
}

function VisualSignatureEditor({
  initialHtml, name, isDefault,
  onNameChange, onDefaultChange,
  onSave, onCancel, saveLabel, saving,
}: {
  initialHtml: string; name: string; isDefault: boolean;
  onNameChange: (v: string) => void; onDefaultChange: (v: boolean) => void;
  onSave: (html: string) => void; onCancel: () => void;
  saveLabel: string; saving: boolean;
}) {
  const [mode, setMode] = useState<'fields' | 'visual' | 'html'>('fields');
  const visualRef = useRef<HTMLDivElement>(null);
  const userEdited = useRef(false);
  const [htmlSrc, setHtmlSrc] = useState(initialHtml);
  const [rawTemplate, setRawTemplate] = useState('');
  const [fields, setFields] = useState<SigFields>(EMPTY_FIELDS);
  const [loadingTpl, setLoadingTpl] = useState(true);
  const [previewHtml, setPreviewHtml] = useState(initialHtml);

  // On mount: load raw template (for field-based editing) + extract fields
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ template: string; raw_template: string; name: string; email: string }>('/settings/signatures/load-default');
        if (cancelled) return;
        if (res.raw_template) {
          setRawTemplate(res.raw_template);
          if (initialHtml) {
            // Editing existing signature — extract fields but keep original HTML for preview/visual
            const ef = extractFields(initialHtml);
            if (!ef.email && res.email) ef.email = res.email;
            setFields(ef);
            // DON'T overwrite previewHtml — keep the existing signature as-is
          } else {
            // New signature — build from template
            const df = { ...EMPTY_FIELDS, email: res.email || '' };
            setFields(df);
            setPreviewHtml(applyFields(res.raw_template, df));
            setHtmlSrc(applyFields(res.raw_template, df));
          }
        }
      } catch {}
      if (!cancelled) setLoadingTpl(false);
    })();
    return () => { cancelled = true; };
  }, [initialHtml]);

  const hasTemplate = rawTemplate.includes('{{NOMBRE}}');

  // Update preview when user edits fields (not on initial extraction)
  const fieldsActive = mode === 'fields';
  useEffect(() => {
    if (hasTemplate && fieldsActive && userEdited.current) {
      const rendered = applyFields(rawTemplate, fields);
      setPreviewHtml(rendered);
      setHtmlSrc(rendered);
    }
  }, [fields, rawTemplate, hasTemplate, fieldsActive]);

  const updateField = useCallback((key: keyof SigFields, value: string) => {
    userEdited.current = true;
    setFields(prev => ({ ...prev, [key]: value }));
  }, []);

  const loadDefaultTemplate = useCallback(async () => {
    userEdited.current = true;
    setLoadingTpl(true);
    try {
      const res = await api.get<{ template: string; raw_template: string; name: string; email: string }>('/settings/signatures/load-default');
      if (res.raw_template) {
        setRawTemplate(res.raw_template);
        if (!name.trim() && res.name) onNameChange(res.name);
        const df = { ...fields, email: fields.email || res.email || '' };
        setFields(df);
        setPreviewHtml(applyFields(res.raw_template, df));
      } else {
        alert('No hay plantilla predeterminada para tu dominio');
      }
    } catch { alert('Error al cargar plantilla'); }
    finally { setLoadingTpl(false); }
  }, [fields, name, onNameChange]);

  const applyHtmlAndPreview = useCallback(() => {
    setPreviewHtml(htmlSrc);
    setMode('fields');
  }, [htmlSrc]);

  const handleSaveClick = useCallback(() => {
    if (mode === 'visual' && visualRef.current) {
      const html = visualRef.current.innerHTML;
      onSave(html);
    } else if (mode === 'html') {
      onSave(htmlSrc);
    } else if (hasTemplate) {
      onSave(applyFields(rawTemplate, fields));
    } else {
      onSave(htmlSrc);
    }
  }, [mode, htmlSrc, hasTemplate, rawTemplate, fields, onSave]);

  // Toolbar exec command helper
  const execCmd = useCallback((cmd: string, value?: string) => {
    document.execCommand(cmd, false, value);
    visualRef.current?.focus();
    // Update preview from visual editor
    if (visualRef.current) setPreviewHtml(visualRef.current.innerHTML);
  }, []);

  // Sync preview when visual editor content changes
  const handleVisualInput = useCallback(() => {
    if (visualRef.current) setPreviewHtml(visualRef.current.innerHTML);
  }, []);

  // When switching to visual mode, load current preview HTML into the contentEditable
  const switchToVisual = useCallback(() => {
    setMode('visual');
    // Need to set content after render
    setTimeout(() => {
      if (visualRef.current) {
        visualRef.current.innerHTML = previewHtml;
      }
    }, 0);
  }, [previewHtml]);

  if (loadingTpl) return <div className="py-4 text-center text-[13px] text-[#605e5c]">Cargando editor...</div>;

  return (
    <div className="space-y-4">
      {/* Name row */}
      <div className="flex gap-3 items-end flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <label className="mb-1 block text-[12px] font-semibold text-[#605e5c]">Nombre de la firma *</label>
          <input type="text" value={name} onChange={e => onNameChange(e.target.value)}
            placeholder="Ej: Firma corporativa"
            className="block w-full rounded border border-[#edebe9] bg-white px-3 py-[6px] text-[13px] text-[#323130] placeholder-[#a19f9d] outline-none focus:border-[#0078d4]" />
        </div>
        <button type="button" onClick={loadDefaultTemplate} disabled={loadingTpl}
          className="rounded border border-[#0078d4] px-3 py-[6px] text-[12px] font-semibold text-[#0078d4] hover:bg-[#deecf9] transition-colors whitespace-nowrap disabled:opacity-50">
          Cargar plantilla predeterminada
        </button>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 border-b border-[#edebe9] pb-1">
        <button type="button" onClick={() => setMode('fields')}
          className={`rounded-t px-3 py-1.5 text-[12px] font-semibold transition-colors ${mode === 'fields' ? 'bg-white text-[#0078d4] border border-b-0 border-[#edebe9]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'}`}>
          Editar campos
        </button>
        <button type="button" onClick={switchToVisual}
          className={`rounded-t px-3 py-1.5 text-[12px] font-semibold transition-colors ${mode === 'visual' ? 'bg-white text-[#0078d4] border border-b-0 border-[#edebe9]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'}`}>
          Editor visual
        </button>
        <button type="button" onClick={() => { setHtmlSrc(previewHtml); setMode('html'); }}
          className={`rounded-t px-3 py-1.5 text-[12px] font-semibold transition-colors ${mode === 'html' ? 'bg-white text-[#0078d4] border border-b-0 border-[#edebe9]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'}`}>
          HTML (avanzado)
        </button>
      </div>

      {mode === 'visual' ? (
        <div>
          {/* Toolbar */}
          <div className="rounded-t border border-[#edebe9] bg-[#f3f2f1] px-2 py-1 flex flex-wrap items-center gap-0.5">
            <VBtn onClick={() => execCmd('bold')} title="Negrita"><strong>N</strong></VBtn>
            <VBtn onClick={() => execCmd('italic')} title="Cursiva"><em className="font-serif">K</em></VBtn>
            <VBtn onClick={() => execCmd('underline')} title="Subrayado"><span className="underline">S</span></VBtn>
            <span className="w-px h-5 bg-[#d2d0ce] mx-1" />
            <select className="h-7 text-[11px] border border-[#d2d0ce] rounded bg-white px-1"
              onChange={e => execCmd('fontSize', e.target.value)} defaultValue="3">
              <option value="1">Muy pequeno</option>
              <option value="2">Pequeno</option>
              <option value="3">Normal</option>
              <option value="4">Mediano</option>
              <option value="5">Grande</option>
            </select>
            <span className="w-px h-5 bg-[#d2d0ce] mx-1" />
            <div className="relative w-7 h-7 flex items-center justify-center">
              <input type="color" defaultValue="#0061a1" className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={e => execCmd('foreColor', e.target.value)} />
              <span className="text-[12px] font-bold pointer-events-none" style={{ color: '#0061a1' }}>A</span>
              <div className="absolute bottom-0.5 left-1 right-1 h-[3px] rounded pointer-events-none" style={{ background: '#0061a1' }} />
            </div>
            <span className="w-px h-5 bg-[#d2d0ce] mx-1" />
            <VBtn onClick={() => execCmd('justifyLeft')} title="Izquierda">
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M1 2h14v1H1zm0 4h10v1H1zm0 4h14v1H1zm0 4h10v1H1z"/></svg>
            </VBtn>
            <VBtn onClick={() => execCmd('justifyCenter')} title="Centro">
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M1 2h14v1H1zm2 4h10v1H3zm-2 4h14v1H1zm2 4h10v1H3z"/></svg>
            </VBtn>
            <VBtn onClick={() => execCmd('justifyRight')} title="Derecha">
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M1 2h14v1H1zm4 4h10v1H5zm-4 4h14v1H1zm4 4h10v1H5z"/></svg>
            </VBtn>
            <span className="w-px h-5 bg-[#d2d0ce] mx-1" />
            <VBtn onClick={() => { const url = prompt('URL del enlace:', 'https://'); if (url) execCmd('createLink', url); }} title="Enlace">
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor"><path d="M7.8 4.8L9.2 3.4a2.5 2.5 0 013.5 3.5L11.3 8.3l-.7-.7 1.4-1.4a1.5 1.5 0 00-2.1-2.1L8.5 5.5l-.7-.7zm.4 6.4L6.8 12.6a2.5 2.5 0 01-3.5-3.5L4.7 7.7l.7.7-1.4 1.4a1.5 1.5 0 002.1 2.1l1.4-1.4.7.7zM5.6 10.3l4.7-4.7.7.7-4.7 4.7-.7-.7z"/></svg>
            </VBtn>
          </div>
          {/* Editable area */}
          <div ref={visualRef} contentEditable suppressContentEditableWarning
            onInput={handleVisualInput}
            className="rounded-b border border-t-0 border-[#edebe9] bg-white px-4 py-3 min-h-[200px] max-h-[400px] overflow-y-auto outline-none sig-preview"
            style={{ fontFamily: 'Verdana, Geneva, sans-serif', fontSize: 13, color: '#323130', lineHeight: 1.5 }} />
        </div>
      ) : mode === 'html' ? (
        <div>
          <textarea value={htmlSrc} onChange={e => setHtmlSrc(e.target.value)} rows={12}
            className="block w-full rounded border border-[#edebe9] bg-white px-3 py-2 text-[12px] text-[#323130] font-mono outline-none focus:border-[#0078d4] resize-y" />
          <button type="button" onClick={applyHtmlAndPreview}
            className="mt-2 rounded px-3 py-1 text-[12px] bg-[#0078d4] text-white hover:bg-[#106ebe]">
            Aplicar y ver vista previa
          </button>
        </div>
      ) : hasTemplate ? (
        <div className="rounded border border-[#edebe9] bg-[#faf9f8] p-4">
          <p className="text-[11px] text-[#605e5c] mb-3">Modifica tus datos y la vista previa se actualiza al instante:</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            <FieldInput label="Nombre completo" value={fields.nombre} onChange={v => updateField('nombre', v)} placeholder="Ej: Wilson Arguello" />
            <FieldInput label="Cargo / Area" value={fields.cargo} onChange={v => updateField('cargo', v)} placeholder="Ej: Soporte Informatico" />
            <FieldInput label="Telefono fijo" value={fields.telefono1} onChange={v => updateField('telefono1', v)} placeholder="Ej: (593 2) 3061624" />
            <FieldInput label="Celular" value={fields.telefono2} onChange={v => updateField('telefono2', v)} placeholder="Ej: (593 9) 95797062" />
            <FieldInput label="Correo electrónico" value={fields.email} onChange={v => updateField('email', v)} placeholder="usuario@ejemplo.com" />
            <FieldInput label="Ciudad" value={fields.ciudad} onChange={v => updateField('ciudad', v)} placeholder="Quito - Ecuador" />
          </div>
        </div>
      ) : (
        <div>
          <p className="text-[11px] text-[#605e5c] mb-2">No hay plantilla cargada. Usa "Cargar plantilla predeterminada" o edita el HTML directamente.</p>
          <textarea value={htmlSrc} onChange={e => { setHtmlSrc(e.target.value); setPreviewHtml(e.target.value); }} rows={8}
            className="block w-full rounded border border-[#edebe9] bg-white px-3 py-2 text-[12px] text-[#323130] font-mono outline-none focus:border-[#0078d4] resize-y" />
        </div>
      )}

      {/* Live Preview — ALWAYS visible */}
      <div>
        <p className="text-[11px] font-semibold text-[#605e5c] mb-1 flex items-center gap-1">
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor"><path d="M8 3C4.5 3 1.7 5.6 1 8c.7 2.4 3.5 5 7 5s6.3-2.6 7-5c-.7-2.4-3.5-5-7-5zm0 8.5A3.5 3.5 0 114.5 8 3.5 3.5 0 018 11.5z"/><circle cx="8" cy="8" r="1.5"/></svg>
          Asi se vera tu firma en el correo
        </p>
        <div className="rounded border border-[#edebe9] bg-white p-4 shadow-sm">
          <div className="text-[13px] text-[#605e5c] italic mb-3">...contenido del correo...</div>
          <div className="border-t border-[#edebe9] pt-3 mt-3">
            <div className="text-[13px] sig-preview" dangerouslySetInnerHTML={{ __html: sanitizeSignatureHtml(previewHtml) }} />
          </div>
        </div>
      </div>

      {/* Default + Save */}
      <div className="flex items-center justify-between pt-1">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={isDefault} onChange={e => onDefaultChange(e.target.checked)}
            className="w-4 h-4 rounded border-[#8a8886] text-[#0078d4]" />
          <span className="text-[12px] text-[#323130]">Usar como firma predeterminada</span>
        </label>
        <div className="flex items-center gap-2">
          <button type="button" onClick={handleSaveClick} disabled={saving || !name.trim()}
            className={`rounded px-4 py-[6px] text-[13px] font-semibold text-white transition-colors ${
              !saving && name.trim() ? 'bg-[#0078d4] hover:bg-[#106ebe]' : 'cursor-not-allowed bg-[#c8c6c4]'}`}>
            {saving ? 'Guardando...' : saveLabel}
          </button>
          <button type="button" onClick={onCancel} className="rounded px-3 py-[6px] text-[13px] text-[#323130] hover:bg-[#e1dfdd]">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

function VBtn({ children, onClick, title }: { children: React.ReactNode; onClick: () => void; title?: string }) {
  return (
    <button type="button" onClick={onClick} title={title}
      className="w-7 h-7 flex items-center justify-center rounded text-[12px] text-[#605e5c] hover:bg-[#e1dfdd] transition-colors">
      {children}
    </button>
  );
}

function FieldInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="mb-0.5 block text-[11px] font-semibold text-[#605e5c]">{label}</label>
      <input type="text" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="block w-full rounded border border-[#edebe9] bg-white px-3 py-[5px] text-[13px] text-[#323130] placeholder-[#a19f9d] outline-none focus:border-[#0078d4]" />
    </div>
  );
}

function ActionBtn({ label, onClick, danger = false }: { label: string; onClick: () => void; danger?: boolean; }) {
  return (
    <button type="button" onClick={onClick}
      className={`rounded px-2 py-[3px] text-[12px] transition-colors ${
        danger ? 'text-[#d13438] hover:bg-[#fde7e9]' : 'text-[#0078d4] hover:bg-[#deecf9]'}`}>
      {label}
    </button>
  );
}
