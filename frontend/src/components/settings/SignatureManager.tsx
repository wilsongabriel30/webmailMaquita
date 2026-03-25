/**
 * SignatureManager.tsx
 *
 * Settings section for managing multiple email signatures.
 * Each signature has a name, HTML content, and default flag.
 *
 * API:
 *   GET    /api/settings/signatures        -> Signature[]
 *   POST   /api/settings/signatures        -> Signature
 *   PUT    /api/settings/signatures/:id    -> Signature
 *   DELETE /api/settings/signatures/:id    -> { status }
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';

interface Signature {
  id: number;
  owner: string;
  name: string;
  html_content: string;
  is_default: boolean;
  created_at: string;
}

interface Feedback {
  type: 'success' | 'error';
  message: string;
}

export function SignatureManager() {
  const [signatures, setSignatures] = useState<Signature[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  // Editing state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [draftName, setDraftName] = useState('');
  const [draftHtml, setDraftHtml] = useState('');
  const [draftDefault, setDraftDefault] = useState(false);
  const [saving, setSaving] = useState(false);

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<number | null>(null);

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

  useEffect(() => { fetchSignatures(); }, [fetchSignatures]);

  const clearEdit = useCallback(() => {
    setEditingId(null);
    setIsCreating(false);
    setDraftName('');
    setDraftHtml('');
    setDraftDefault(false);
  }, []);

  const startCreate = useCallback(() => {
    clearEdit();
    setIsCreating(true);
    setDraftName('');
    setDraftHtml('');
    setDraftDefault(false);
  }, [clearEdit]);

  const startEdit = useCallback((sig: Signature) => {
    clearEdit();
    setEditingId(sig.id);
    setDraftName(sig.name);
    setDraftHtml(sig.html_content);
    setDraftDefault(sig.is_default);
  }, [clearEdit]);

  const handleSave = useCallback(async () => {
    if (!draftName.trim()) { flash({ type: 'error', message: 'El nombre es obligatorio' }); return; }
    setSaving(true);
    try {
      if (isCreating) {
        await api.post('/settings/signatures', {
          name: draftName.trim(),
          html_content: draftHtml,
          is_default: draftDefault,
        });
        flash({ type: 'success', message: 'Firma creada' });
      } else if (editingId) {
        await api.put(`/settings/signatures/${editingId}`, {
          name: draftName.trim(),
          html_content: draftHtml,
          is_default: draftDefault || undefined,
        });
        flash({ type: 'success', message: 'Firma actualizada' });
      }
      clearEdit();
      await fetchSignatures();
    } catch (err: unknown) {
      flash({ type: 'error', message: err instanceof Error ? err.message : 'Error al guardar' });
    } finally {
      setSaving(false);
    }
  }, [draftName, draftHtml, draftDefault, isCreating, editingId, clearEdit, fetchSignatures, flash]);

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

  return (
    <section className="rounded border border-[#edebe9] bg-white" style={{ fontFamily: "'Calibri', 'Segoe UI', sans-serif" }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#edebe9] px-5 py-3">
        <div>
          <h2 className="text-[15px] font-semibold text-[#323130]">Firmas de correo</h2>
          <p className="mt-0.5 text-[12px] text-[#605e5c]">
            Administra multiples firmas. La firma predeterminada se usa automaticamente al redactar.
          </p>
        </div>
        <button type="button" onClick={startCreate} disabled={isCreating}
          className={`rounded px-3 py-[5px] text-[13px] font-semibold text-white transition-colors ${
            isCreating ? 'cursor-not-allowed bg-[#c8c6c4]' : 'bg-[#0078d4] hover:bg-[#106ebe]'
          }`}>
          + Agregar firma
        </button>
      </div>

      {/* Feedback */}
      {feedback && (
        <div className={`mx-5 mt-3 rounded px-3 py-2 text-[13px] ${
          feedback.type === 'success' ? 'bg-[#dff6dd] text-[#0b6a0b]' : 'bg-[#fde7e9] text-[#d13438]'
        }`}>
          {feedback.message}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="px-5 py-6 text-center text-[13px] text-[#605e5c]">Cargando firmas...</div>
      )}

      {/* Create form */}
      {isCreating && (
        <div className="border-b border-[#edebe9] bg-[#faf9f8] px-5 py-4">
          <h3 className="mb-3 text-[13px] font-semibold text-[#323130]">Nueva firma</h3>
          <SignatureForm
            name={draftName} html={draftHtml} isDefault={draftDefault}
            onNameChange={setDraftName} onHtmlChange={setDraftHtml} onDefaultChange={setDraftDefault}
            onSave={handleSave} onCancel={clearEdit} saveLabel="Crear" saving={saving}
          />
        </div>
      )}

      {/* Signature list */}
      {!loading && (
        <ul className="divide-y divide-[#edebe9]">
          {signatures.map(sig => {
            const isEditing = editingId === sig.id;
            const isDeleting = deletingId === sig.id;

            return (
              <li key={sig.id} className="px-5 py-3">
                {isEditing ? (
                  <div>
                    <h3 className="mb-3 text-[13px] font-semibold text-[#323130]">Editar firma</h3>
                    <SignatureForm
                      name={draftName} html={draftHtml} isDefault={draftDefault}
                      onNameChange={setDraftName} onHtmlChange={setDraftHtml} onDefaultChange={setDraftDefault}
                      onSave={handleSave} onCancel={clearEdit} saveLabel="Guardar" saving={saving}
                    />
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-semibold text-[#323130]">{sig.name}</span>
                        {sig.is_default && (
                          <span className="rounded bg-[#deecf9] px-1.5 py-0.5 text-[10px] font-semibold text-[#0078d4]">
                            PREDETERMINADA
                          </span>
                        )}
                      </div>
                      {sig.html_content ? (
                        <div className="mt-1 max-h-[60px] overflow-hidden text-[11px] text-[#a19f9d]"
                          dangerouslySetInnerHTML={{ __html: stripToPreview(sig.html_content) }} />
                      ) : (
                        <p className="mt-1 text-[11px] text-[#a19f9d] italic">Sin contenido</p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      {!sig.is_default && (
                        <ActionBtn label="Predeterminada" onClick={() => handleSetDefault(sig.id)} />
                      )}
                      <ActionBtn label="Editar" onClick={() => startEdit(sig)} />
                      {isDeleting ? (
                        <span className="flex items-center gap-1 text-[12px]">
                          <span className="text-[#d13438]">Eliminar?</span>
                          <ActionBtn label="Si" danger onClick={() => handleDelete(sig.id)} />
                          <ActionBtn label="No" onClick={() => setDeletingId(null)} />
                        </span>
                      ) : (
                        <ActionBtn label="Eliminar" danger onClick={() => setDeletingId(sig.id)} />
                      )}
                    </div>
                  </div>
                )}
              </li>
            );
          })}

          {signatures.length === 0 && !isCreating && (
            <li className="px-5 py-6 text-center text-[13px] text-[#a19f9d]">
              No hay firmas configuradas.
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

// ── Subcomponents ───────────────────────────────────────────────────────────

function SignatureForm({
  name, html, isDefault,
  onNameChange, onHtmlChange, onDefaultChange,
  onSave, onCancel, saveLabel, saving,
}: {
  name: string; html: string; isDefault: boolean;
  onNameChange: (v: string) => void; onHtmlChange: (v: string) => void; onDefaultChange: (v: boolean) => void;
  onSave: () => void; onCancel: () => void; saveLabel: string; saving: boolean;
}) {
  return (
    <div className="max-w-lg space-y-3">
      <div>
        <label className="mb-1 block text-[12px] font-semibold text-[#605e5c]">Nombre *</label>
        <input type="text" value={name} onChange={e => onNameChange(e.target.value)}
          placeholder="Ej: Firma corporativa"
          className="block w-full rounded border border-[#edebe9] bg-white px-2 py-[5px] text-[13px] text-[#323130] placeholder-[#a19f9d] outline-none focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4]" />
      </div>

      <div>
        <label className="mb-1 block text-[12px] font-semibold text-[#605e5c]">Contenido HTML</label>
        <textarea value={html} onChange={e => onHtmlChange(e.target.value)}
          rows={8} placeholder="<p>Saludos cordiales,<br/>Tu nombre</p>"
          className="block w-full rounded border border-[#edebe9] bg-white px-2 py-[5px] text-[13px] text-[#323130] placeholder-[#a19f9d] outline-none focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4] resize-y font-mono" />
        {/* Preview */}
        {html.trim().length > 0 && (
          <div className="mt-2 rounded border border-[#edebe9] bg-[#faf9f8] p-2">
            <p className="mb-1 text-[10px] font-semibold uppercase text-[#a19f9d]">Vista previa</p>
            <div className="text-[12px] text-[#323130]" dangerouslySetInnerHTML={{ __html: html }} />
          </div>
        )}
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={isDefault} onChange={e => onDefaultChange(e.target.checked)}
          className="w-4 h-4 rounded border-[#8a8886] text-[#0078d4] focus:ring-[#0078d4]" />
        <span className="text-[12px] text-[#323130]">Usar como firma predeterminada</span>
      </label>

      <div className="flex items-center gap-2 pt-1">
        <button type="button" onClick={onSave} disabled={saving || !name.trim()}
          className={`rounded px-4 py-[5px] text-[13px] font-semibold text-white transition-colors ${
            !saving && name.trim() ? 'bg-[#0078d4] hover:bg-[#106ebe]' : 'cursor-not-allowed bg-[#c8c6c4]'
          }`}>
          {saving ? 'Guardando...' : saveLabel}
        </button>
        <button type="button" onClick={onCancel}
          className="rounded px-3 py-[5px] text-[13px] text-[#323130] hover:bg-[#f3f2f1]">
          Cancelar
        </button>
      </div>
    </div>
  );
}

function ActionBtn({ label, onClick, danger = false }: { label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button type="button" onClick={onClick}
      className={`rounded px-2 py-[3px] text-[12px] transition-colors ${
        danger ? 'text-[#d13438] hover:bg-[#fde7e9]' : 'text-[#0078d4] hover:bg-[#f3f2f1]'
      }`}>
      {label}
    </button>
  );
}

function stripToPreview(html: string): string {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  const text = tmp.textContent ?? tmp.innerText ?? '';
  return text.length > 120 ? text.slice(0, 117) + '...' : text;
}
