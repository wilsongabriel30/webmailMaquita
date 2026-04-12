import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import { CATEGORY_COLORS } from './types';

interface Category {
  id: number;
  name: string;
  color: string;
  contact_count: number;
}

interface Props {
  mode: 'manage' | 'assign';
  contactId?: number;
  currentCategoryIds?: number[];
  onClose: () => void;
  onSaved: () => void;
}

type EditingState = { id: number; name: string; color: string } | null;

export function CategoryManager({ mode, contactId, currentCategoryIds = [], onClose, onSaved }: Props) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Manage mode state
  const [editing, setEditing] = useState<EditingState>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(CATEGORY_COLORS[0].value);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  // Assign mode state
  const [selectedIds, setSelectedIds] = useState<number[]>(currentCategoryIds);

  const fetchCategories = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get<Category[]>('/contacts/categories');
      setCategories(res);
    } catch {
      setError('Error al cargar categorías');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  useEffect(() => {
    setSelectedIds(currentCategoryIds);
  }, [currentCategoryIds]);

  // ── Manage handlers ──

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      await api.post('/contacts/categories', { name: newName.trim(), color: newColor });
      setCreating(false);
      setNewName('');
      setNewColor(CATEGORY_COLORS[0].value);
      await fetchCategories();
      onSaved();
    } catch {
      setError('Error al crear categoría');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!editing || !editing.name.trim()) return;
    setSaving(true);
    try {
      await api.put(`/contacts/categories/${editing.id}`, { name: editing.name.trim(), color: editing.color });
      setEditing(null);
      await fetchCategories();
      onSaved();
    } catch {
      setError('Error al actualizar categoría');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await api.del(`/contacts/categories/${id}`);
      setDeleteConfirmId(null);
      await fetchCategories();
      onSaved();
    } catch {
      setError('Error al eliminar categoría');
    } finally {
      setSaving(false);
    }
  };

  // ── Assign handlers ──

  const toggleCategory = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleAssignSave = async () => {
    if (contactId == null) return;
    setSaving(true);
    try {
      await api.put(`/contacts/${contactId}/categories`, { category_ids: selectedIds });
      onSaved();
      onClose();
    } catch {
      setError('Error al asignar categorías');
    } finally {
      setSaving(false);
    }
  };

  // ── Styles ──

  const s = {
    overlay: {
      position: 'fixed' as const,
      inset: 0,
      backgroundColor: 'rgba(0,0,0,0.4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    },
    modal: {
      backgroundColor: '#fff',
      borderRadius: 8,
      padding: 28,
      width: 440,
      maxHeight: '80vh',
      display: 'flex',
      flexDirection: 'column' as const,
      boxShadow: '0 8px 30px rgba(0,0,0,0.25)',
    },
    title: {
      fontSize: 20,
      fontWeight: 600,
      margin: 0,
      marginBottom: 20,
      color: '#323130',
    },
    list: {
      flex: 1,
      overflowY: 'auto' as const,
      marginBottom: 16,
    },
    item: {
      display: 'flex',
      alignItems: 'center',
      padding: '8px 0',
      borderBottom: '1px solid #edebe9',
      fontSize: 13,
      color: '#323130',
    },
    dot: (color: string) => ({
      width: 12,
      height: 12,
      borderRadius: '50%',
      backgroundColor: color,
      flexShrink: 0,
      marginRight: 10,
    }),
    itemName: {
      flex: 1,
      overflow: 'hidden' as const,
      textOverflow: 'ellipsis' as const,
      whiteSpace: 'nowrap' as const,
    },
    count: {
      fontSize: 12,
      color: '#8a8886',
      marginRight: 10,
    },
    btnPrimary: {
      backgroundColor: '#0078d4',
      color: '#fff',
      border: 'none',
      borderRadius: 4,
      padding: '6px 16px',
      fontSize: 13,
      fontWeight: 600,
      cursor: 'pointer',
      fontFamily: 'inherit',
    },
    btnDanger: {
      backgroundColor: '#d13438',
      color: '#fff',
      border: 'none',
      borderRadius: 4,
      padding: '6px 12px',
      fontSize: 13,
      fontWeight: 600,
      cursor: 'pointer',
      fontFamily: 'inherit',
    },
    btnSecondary: {
      backgroundColor: '#fff',
      color: '#323130',
      border: '1px solid #8a8886',
      borderRadius: 4,
      padding: '6px 16px',
      fontSize: 13,
      fontWeight: 600,
      cursor: 'pointer',
      fontFamily: 'inherit',
    },
    btnIcon: {
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      padding: '4px 6px',
      fontSize: 14,
      color: '#605e5c',
      borderRadius: 4,
    },
    input: {
      border: '1px solid #8a8886',
      borderRadius: 4,
      padding: '6px 10px',
      fontSize: 13,
      fontFamily: 'inherit',
      outline: 'none',
      width: '100%',
      boxSizing: 'border-box' as const,
    },
    label: {
      fontSize: 13,
      fontWeight: 600,
      color: '#323130',
      marginBottom: 4,
      display: 'block',
    },
    colorPicker: {
      display: 'flex',
      gap: 6,
      flexWrap: 'wrap' as const,
      marginTop: 6,
    },
    colorDot: (color: string, selected: boolean) => ({
      width: 24,
      height: 24,
      borderRadius: '50%',
      backgroundColor: color,
      cursor: 'pointer',
      border: selected ? '3px solid #323130' : '2px solid transparent',
      boxSizing: 'border-box' as const,
    }),
    footer: {
      display: 'flex',
      justifyContent: 'flex-end',
      gap: 8,
      paddingTop: 8,
      borderTop: '1px solid #edebe9',
    },
    error: {
      backgroundColor: '#fde7e9',
      color: '#a4262c',
      padding: '8px 12px',
      borderRadius: 4,
      fontSize: 13,
      marginBottom: 12,
    },
    checkbox: {
      marginRight: 10,
      accentColor: '#0078d4',
      width: 16,
      height: 16,
      cursor: 'pointer',
    },
    formRow: {
      marginBottom: 12,
    },
  };

  // ── Color picker sub-component ──

  const ColorPicker = ({ value, onChange }: { value: string; onChange: (c: string) => void }) => (
    <div style={s.colorPicker}>
      {CATEGORY_COLORS.map((c) => (
        <div
          key={c.value}
          role="button"
          tabIndex={0}
          title={c.name}
          style={s.colorDot(c.value, value === c.value) as React.CSSProperties}
          onClick={() => onChange(c.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onChange(c.value); }}
        />
      ))}
    </div>
  );

  // ── Inline form (create / edit) ──

  const renderForm = (
    nameVal: string,
    colorVal: string,
    onNameChange: (v: string) => void,
    onColorChange: (v: string) => void,
    onSave: () => void,
    onCancel: () => void,
  ) => (
    <div style={{ backgroundColor: '#faf9f8', borderRadius: 6, padding: 16, marginBottom: 12 }}>
      <div style={s.formRow}>
        <label style={s.label}>Nombre</label>
        <input
          style={s.input}
          value={nameVal}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Nombre de categoría"
          maxLength={50}
          autoFocus
          onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = '#0078d4'; }}
          onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = '#8a8886'; }}
          onKeyDown={(e) => { if (e.key === 'Enter') onSave(); }}
        />
      </div>
      <div style={s.formRow}>
        <label style={s.label}>Color</label>
        <ColorPicker value={colorVal} onChange={onColorChange} />
      </div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button style={s.btnSecondary} onClick={onCancel} disabled={saving}>Cancelar</button>
        <button style={{ ...s.btnPrimary, opacity: saving ? 0.6 : 1 }} onClick={onSave} disabled={saving || !nameVal.trim()}>
          {saving ? 'Guardando...' : 'Guardar'}
        </button>
      </div>
    </div>
  );

  // ── Delete confirmation ──

  const renderDeleteConfirm = (cat: Category) => (
    <div style={{ backgroundColor: '#fde7e9', borderRadius: 6, padding: 14, marginBottom: 8 }}>
      <p style={{ fontSize: 13, color: '#323130', margin: '0 0 10px' }}>
        ¿Eliminar <strong>{cat.name}</strong>? Se removerá de {cat.contact_count} contacto(s).
      </p>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button style={s.btnSecondary} onClick={() => setDeleteConfirmId(null)} disabled={saving}>Cancelar</button>
        <button style={{ ...s.btnDanger, opacity: saving ? 0.6 : 1 }} onClick={() => handleDelete(cat.id)} disabled={saving}>
          {saving ? 'Eliminando...' : 'Eliminar'}
        </button>
      </div>
    </div>
  );

  // ── Manage mode ──

  const renderManage = () => (
    <>
      <h2 style={s.title}>Administrar categorías</h2>

      {error && <div style={s.error}>{error}</div>}

      {creating
        ? renderForm(newName, newColor, setNewName, setNewColor, handleCreate, () => { setCreating(false); setNewName(''); setNewColor(CATEGORY_COLORS[0].value); })
        : (
          <button
            style={{ ...s.btnPrimary, marginBottom: 16, alignSelf: 'flex-start' }}
            onClick={() => { setCreating(true); setEditing(null); setDeleteConfirmId(null); }}
          >
            + Nueva categoría
          </button>
        )
      }

      <div style={s.list}>
        {loading && <p style={{ fontSize: 13, color: '#8a8886' }}>Cargando...</p>}
        {!loading && categories.length === 0 && (
          <p style={{ fontSize: 13, color: '#8a8886' }}>No hay categorías creadas.</p>
        )}
        {categories.map((cat) => (
          <React.Fragment key={cat.id}>
            {deleteConfirmId === cat.id && renderDeleteConfirm(cat)}

            {editing?.id === cat.id ? (
              renderForm(
                editing.name,
                editing.color,
                (v) => setEditing({ ...editing, name: v }),
                (v) => setEditing({ ...editing, color: v }),
                handleUpdate,
                () => setEditing(null),
              )
            ) : (
              <div style={s.item}>
                <div style={s.dot(cat.color)} />
                <span style={s.itemName}>{cat.name}</span>
                <span style={s.count}>{cat.contact_count}</span>
                <button
                  style={s.btnIcon}
                  title="Editar"
                  onClick={() => { setEditing({ id: cat.id, name: cat.name, color: cat.color }); setCreating(false); setDeleteConfirmId(null); }}
                >
                  &#9998;
                </button>
                <button
                  style={{ ...s.btnIcon, color: '#d13438' }}
                  title="Eliminar"
                  onClick={() => { setDeleteConfirmId(cat.id); setEditing(null); setCreating(false); }}
                >
                  &#128465;
                </button>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      <div style={s.footer}>
        <button style={s.btnSecondary} onClick={onClose}>Cerrar</button>
      </div>
    </>
  );

  // ── Assign mode ──

  const renderAssign = () => (
    <>
      <h2 style={s.title}>Asignar categorías</h2>

      {error && <div style={s.error}>{error}</div>}

      <div style={s.list}>
        {loading && <p style={{ fontSize: 13, color: '#8a8886' }}>Cargando...</p>}
        {!loading && categories.length === 0 && (
          <p style={{ fontSize: 13, color: '#8a8886' }}>No hay categorías disponibles.</p>
        )}
        {categories.map((cat) => (
          <label
            key={cat.id}
            style={{ ...s.item, cursor: 'pointer' }}
          >
            <input
              type="checkbox"
              checked={selectedIds.includes(cat.id)}
              onChange={() => toggleCategory(cat.id)}
              style={s.checkbox as React.CSSProperties}
            />
            <div style={s.dot(cat.color)} />
            <span style={s.itemName}>{cat.name}</span>
          </label>
        ))}
      </div>

      <div style={s.footer}>
        <button style={s.btnSecondary} onClick={onClose}>Cancelar</button>
        <button
          style={{ ...s.btnPrimary, opacity: saving ? 0.6 : 1 }}
          onClick={handleAssignSave}
          disabled={saving}
        >
          {saving ? 'Guardando...' : 'Guardar'}
        </button>
      </div>
    </>
  );

  // ── Render ──

  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.modal as React.CSSProperties} onClick={(e) => e.stopPropagation()}>
        {mode === 'manage' ? renderManage() : renderAssign()}
      </div>
    </div>
  );
}
