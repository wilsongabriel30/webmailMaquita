/**
 * IdentityManager.tsx
 *
 * Settings section for managing mail identities (sender profiles).
 * Each identity has a display name, email address, and optional HTML signature.
 *
 * API contract:
 *   GET    /api/identities              -> Identity[]
 *   POST   /api/identities              -> Identity   (create)
 *   PUT    /api/identities/:id          -> Identity   (update)
 *   DELETE /api/identities/:id          -> void       (delete)
 */

import { sanitizeSignatureHtml } from '../../lib/sanitize';
import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';

//  Types

export interface Identity {
  id: string;
  name: string;
  email: string;
  signature: string;   // HTML string
  isDefault: boolean;
}

type IdentityDraft = Omit<Identity, 'id' | 'isDefault'>;

interface Feedback {
  type: 'success' | 'error';
  message: string;
}

//  Component

export function IdentityManager() {
  const [identities, setIdentidades] = useState<Identity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  // Editing / creating state
  const [editingId, setEditingId] = useState<string | null>(null);       // id of identity being edited
  const [isCreating, setIsCreating] = useState(false);
  const [draft, setDraft] = useState<IdentityDraft>({ name: '', email: '', signature: '' });

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<string | null>(null);

  //  Fetch identities

  const fetchIdentidades = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<Identity[]>('/identities');
      setIdentidades(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar las identidades.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIdentidades();
  }, [fetchIdentidades]);

  //  Helpers

  const clearEdit = useCallback(() => {
    setEditingId(null);
    setIsCreating(false);
    setDraft({ name: '', email: '', signature: '' });
  }, []);

  const flash = useCallback((fb: Feedback) => {
    setFeedback(fb);
    setTimeout(() => setFeedback(null), 4000);
  }, []);

  const updateDraft = useCallback(
    (field: keyof IdentityDraft, value: string) => {
      setDraft((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const draftValid = (draft.name?.trim()?.length ?? 0) > 0 && (draft.email?.trim()?.length ?? 0) > 0;

  //  CRUD operations

  const startCreate = useCallback(() => {
    clearEdit();
    setIsCreating(true);
    setDraft({ name: '', email: '', signature: '' });
  }, [clearEdit]);

  const startEdit = useCallback(
    (identity: Identity) => {
      clearEdit();
      setEditingId(identity.id);
      setDraft({
        name: identity.name || '',
        email: identity.email || '',
        signature: identity.signature || '',
      });
    },
    [clearEdit],
  );

  const handleSave = useCallback(async () => {
    if (!draftValid) return;

    try {
      if (isCreating) {
        await api.post('/identities', draft);
        flash({ type: 'success', message: 'Identidad creada.' });
      } else if (editingId) {
        await api.put(`/api/identities/${editingId}`, draft);
        flash({ type: 'success', message: 'Identidad actualizada.' });
      }
      clearEdit();
      await fetchIdentidades();
    } catch (err: unknown) {
      flash({
        type: 'error',
        message: err instanceof Error ? err.message : 'No se pudo guardar la identidad.',
      });
    }
  }, [draftValid, isCreating, editingId, draft, clearEdit, fetchIdentidades, flash]);

  const handleDelete = useCallback(
    async (id: string) => {
      if (identities.length <= 1) {
        flash({ type: 'error', message: 'No se puede eliminar la última identidad.' });
        setDeletingId(null);
        return;
      }

      try {
        await api.del(`/api/identities/${id}`);
        flash({ type: 'success', message: 'Identidad eliminada.' });
        setDeletingId(null);
        clearEdit();
        await fetchIdentidades();
      } catch (err: unknown) {
        flash({
          type: 'error',
          message: err instanceof Error ? err.message : 'No se pudo eliminar la identidad.',
        });
      }
    },
    [identities.length, clearEdit, fetchIdentidades, flash],
  );

  const handleSetDefault = useCallback(
    async (id: string) => {
      try {
        await api.put(`/api/identities/${id}`, { isDefault: true });
        flash({ type: 'success', message: 'Identidad predeterminada actualizada.' });
        await fetchIdentidades();
      } catch (err: unknown) {
        flash({
          type: 'error',
          message: err instanceof Error ? err.message : 'Failed to set default.',
        });
      }
    },
    [fetchIdentidades, flash],
  );

  //  Render

  return (
    <section
      className="rounded border border-[#edebe9] bg-white"
      style={{ fontFamily: "'Calibri', 'Segoe UI', sans-serif" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#edebe9] px-5 py-3">
        <div>
          <h2 className="text-[15px] font-semibold text-[#323130]">
            Identidades
          </h2>
          <p className="mt-0.5 text-[12px] text-[#605e5c]">
            Administra tus perfiles de envío y firmas.
          </p>
        </div>
        <button
          type="button"
          onClick={startCreate}
          disabled={isCreating}
          className={[
            'rounded px-3 py-[5px] text-[13px] font-semibold text-white transition-colors',
            isCreating
              ? 'cursor-not-allowed bg-[#c8c6c4]'
              : 'bg-[#0078d4] hover:bg-[#106ebe]',
          ].join(' ')}
        >
          + Nueva identidad
        </button>
      </div>

      {/* Feedback */}
      {feedback && (
        <div
          className={[
            'mx-5 mt-3 rounded px-3 py-2 text-[13px]',
            feedback.type === 'success'
              ? 'bg-[#dff6dd] text-[#0b6a0b]'
              : 'bg-[#fde7e9] text-[#d13438]',
          ].join(' ')}
        >
          {feedback.message}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="px-5 py-6 text-center text-[13px] text-[#605e5c]">
          Cargando identidades...
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="px-5 py-6 text-center text-[13px] text-[#d13438]">
          {error}
          <button
            onClick={fetchIdentidades}
            className="ml-2 underline hover:no-underline"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Inline create form */}
      {isCreating && (
        <div className="border-b border-[#edebe9] bg-[#faf9f8] px-5 py-4">
          <h3 className="mb-3 text-[13px] font-semibold text-[#323130]">
            Nueva identidad
          </h3>
          <IdentityForm
            draft={draft}
            onUpdate={updateDraft}
            onSave={handleSave}
            onCancelar={clearEdit}
            saveLabel="Crear"
            valid={draftValid}
          />
        </div>
      )}

      {/* Identity list */}
      {!loading && !error && (
        <ul className="divide-y divide-[#edebe9]">
          {identities.map((identity) => {
            const isEditing = editingId === identity.id;
            const isDeleting = deletingId === identity.id;

            return (
              <li key={identity.id} className="px-5 py-3">
                {isEditing ? (
                  /*  Edit form  */
                  <div>
                    <h3 className="mb-3 text-[13px] font-semibold text-[#323130]">
                      Editar identidad
                    </h3>
                    <IdentityForm
                      draft={draft}
                      onUpdate={updateDraft}
                      onSave={handleSave}
                      onCancelar={clearEdit}
                      saveLabel="Guardar"
                      valid={draftValid}
                    />
                  </div>
                ) : (
                  /*  Display row  */
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-semibold text-[#323130]">
                          {identity.name}
                        </span>
                        {identity.isDefault && (
                          <span className="rounded bg-[#deecf9] px-1.5 py-0.5 text-[10px] font-semibold text-[#0078d4]">
                            PREDETERMINADA
                          </span>
                        )}
                      </div>
                      <p className="text-[12px] text-[#605e5c]">
                        {identity.email}
                      </p>
                      {identity.signature && (
                        <div
                          className="mt-1 max-h-[60px] overflow-hidden text-[11px] text-[#a19f9d]"
                        >{stripToPreview(identity.signature)}</div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex shrink-0 items-center gap-1">
                      {!identity.isDefault && (
                        <ActionBtn
                          label="Marcar como predeterminada"
                          onClick={() => handleSetDefault(identity.id)}
                        />
                      )}
                      <ActionBtn
                        label="Editar"
                        onClick={() => startEdit(identity)}
                      />
                      {isDeleting ? (
                        <span className="flex items-center gap-1 text-[12px]">
                          <span className="text-[#d13438]">¿Eliminar?</span>
                          <ActionBtn
                            label="Sí"
                            danger
                            onClick={() => handleDelete(identity.id)}
                          />
                          <ActionBtn
                            label="No"
                            onClick={() => setDeletingId(null)}
                          />
                        </span>
                      ) : (
                        <ActionBtn
                          label="Eliminar"
                          danger
                          onClick={() => setDeletingId(identity.id)}
                        />
                      )}
                    </div>
                  </div>
                )}
              </li>
            );
          })}

          {identities.length === 0 && !isCreating && (
            <li className="px-5 py-6 text-center text-[13px] text-[#a19f9d]">
              No hay identidades configuradas.
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

//  Subcomponents

function IdentityForm({
  draft,
  onUpdate,
  onSave,
  onCancelar,
  saveLabel,
  valid,
}: {
  draft: IdentityDraft;
  onUpdate: (field: keyof IdentityDraft, value: string) => void;
  onSave: () => void;
  onCancelar: () => void;
  saveLabel: string;
  valid: boolean;
}) {
  return (
    <div className="max-w-lg space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] font-semibold text-[#605e5c]">
            Nombre para mostrar *
          </label>
          <input
            type="text"
            value={draft.name}
            onChange={(e) => onUpdate('name', e.target.value)}
            placeholder="Juan Pérez"
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-[12px] font-semibold text-[#605e5c]">
            Dirección de correo *
          </label>
          <input
            type="email"
            value={draft.email}
            onChange={(e) => onUpdate('email', e.target.value)}
            placeholder="correo@ejemplo.com"
            className={inputClass}
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-[12px] font-semibold text-[#605e5c]">
          Firma (HTML)
        </label>
        <textarea
          value={draft.signature}
          onChange={(e) => onUpdate('signature', e.target.value)}
          rows={5}
          placeholder="<p>Saludos cordiales,<br/>Su nombre</p>"
          className={[
            'block w-full rounded border border-[#edebe9] bg-white px-2 py-[5px]',
            'text-[13px] text-[#323130] placeholder-[#a19f9d]',
            'outline-none focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4]',
            'resize-y',
          ].join(' ')}
        />
        {/* Preview */}
        {(draft.signature || "").trim().length > 0 && (
          <div className="mt-2 rounded border border-[#edebe9] bg-[#faf9f8] p-2">
            <p className="mb-1 text-[10px] font-semibold uppercase text-[#a19f9d]">
              Preview
            </p>
            <div
              className="text-[12px] text-[#323130]"
              dangerouslySetInnerHTML={{ __html: sanitizeSignatureHtml(draft.signature || '') }}
            />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={onSave}
          disabled={!valid}
          className={[
            'rounded px-4 py-[5px] text-[13px] font-semibold text-white transition-colors',
            valid
              ? 'bg-[#0078d4] hover:bg-[#106ebe]'
              : 'cursor-not-allowed bg-[#c8c6c4]',
          ].join(' ')}
        >
          {saveLabel}
        </button>
        <button
          type="button"
          onClick={onCancelar}
          className="rounded px-3 py-[5px] text-[13px] text-[#323130] hover:bg-[#f3f2f1]"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

function ActionBtn({
  label,
  onClick,
  danger = false,
}: {
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded px-2 py-[3px] text-[12px] transition-colors',
        danger
          ? 'text-[#d13438] hover:bg-[#fde7e9]'
          : 'text-[#0078d4] hover:bg-[#f3f2f1]',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

//  Utilities

/** Strip HTML to a short plain-text preview. */
function stripToPreview(html: string): string {
  const text = html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
  return text.length > 120 ? text.slice(0, 117) + '...' : text;
}

const inputClass = [
  'block w-full rounded border border-[#edebe9] bg-white px-2 py-[5px]',
  'text-[13px] text-[#323130] placeholder-[#a19f9d]',
  'outline-none focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4]',
].join(' ');
