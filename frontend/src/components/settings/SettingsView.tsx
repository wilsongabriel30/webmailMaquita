import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../../api/client';
import { PasswordChange } from './PasswordChange';
import { IdentityManager } from './IdentityManager';
import { SignatureManager } from './SignatureManager';
import { TwoFactorSetup } from './TwoFactorSetup';
import { useMailStore } from '../../store/mailStore';
import { getFolderDisplayName } from '../../folders';

interface Settings {
  display_name: string;
  signature_html: string;
  messages_per_page: number;
  reading_pane: string;
  block_remote_images: boolean;
  confirm_delete: boolean;
  auto_reply_enabled: boolean;
  auto_reply_subject: string;
  auto_reply_body: string;
}

interface VacationSettings {
  enabled: boolean;
  subject: string;
  body: string;
  start_date: string;
  end_date: string;
}

interface FilterRule {
  index?: number;
  name: string;
  condition: { field: string; operator: string; value: string };
  action: { type: string; value: string | null };
}

type Tab = 'general' | 'signature' | 'identities' | 'autoreply' | 'filters' | 'password' | 'security';

const FIELD_LABELS: Record<string, string> = { from: 'De', to: 'Para', subject: 'Asunto' };
const OP_LABELS: Record<string, string> = { contains: 'contiene', is: 'es exactamente', matches: 'coincide con' };
const ACTION_LABELS: Record<string, string> = { move: 'Mover a', flag: 'Marcar', delete: 'Eliminar', forward: 'Reenviar a' };

export function SettingsView() {
  const location = useLocation();
  const folders = useMailStore(s => s.folders);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [tab, setTab] = useState<Tab>('general');

  // Vacation (Sieve)
  const [vacation, setVacation] = useState<VacationSettings>({ enabled: false, subject: '', body: '', start_date: '', end_date: '' });
  const [vacationLoading, setVacationLoading] = useState(false);

  // Filters (Sieve)
  const [filters, setFilters] = useState<FilterRule[]>([]);
  const [filtersLoading, setFiltersLoading] = useState(false);
  const [newFilter, setNewFilter] = useState<FilterRule>({ name: '', condition: { field: 'from', operator: 'contains', value: '' }, action: { type: 'move', value: '' } });
  const [showAddFilter, setShowAddFilter] = useState(false);
  const [editingFilter, setEditingFilter] = useState<number | null>(null);
  const [editFilter, setEditFilter] = useState<FilterRule | null>(null);
  const [previewResult, setPreviewResult] = useState<{ matching_count: number; sample_subjects: string[] } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    api.get<Settings>('/settings').then(setSettings).catch(console.error);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const requestedTab = params.get('tab');
    const validTabs: Tab[] = ['general', 'signature', 'identities', 'autoreply', 'filters', 'password', 'security'];
    if (requestedTab && validTabs.includes(requestedTab as Tab)) {
      setTab(requestedTab as Tab);
    }
  }, [location.search]);

  const fetchFilters = () => {
    setFiltersLoading(true);
    api.get<FilterRule[]>('/sieve/filters')
      .then(data => {
        // API returns array directly
        const arr = Array.isArray(data) ? data : (data as any).filters || [];
        setFilters(arr);
      })
      .catch(() => setFilters([]))
      .finally(() => setFiltersLoading(false));
  };

  useEffect(() => {
    if (tab === 'autoreply') {
      setVacationLoading(true);
      api.get<VacationSettings>('/sieve/vacation')
        .then(setVacation)
        .catch(() => {})
        .finally(() => setVacationLoading(false));
    }
    if (tab === 'filters') {
      fetchFilters();
    }
  }, [tab]);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    try {
      await api.put('/settings', settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) { console.error(err); }
    finally { setSaving(false); }
  };

  const handleSaveVacation = async () => {
    setSaving(true);
    try {
      await api.put('/sieve/vacation', vacation);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) { console.error(err); }
    finally { setSaving(false); }
  };

  const handleAddFilter = async () => {
    if (!newFilter.name || !newFilter.condition.value) return;
    try {
      await api.post('/sieve/filters', newFilter);
      setNewFilter({ name: '', condition: { field: 'from', operator: 'contains', value: '' }, action: { type: 'move', value: '' } });
      setShowAddFilter(false);
      setPreviewResult(null);
      fetchFilters();
    } catch (err) { console.error(err); }
  };

  const handleUpdateFilter = async (index: number) => {
    if (!editFilter || !editFilter.name || !editFilter.condition.value) return;
    try {
      await api.put(`/sieve/filters/${index}`, {
        name: editFilter.name,
        condition: editFilter.condition,
        action: editFilter.action,
      });
      setEditingFilter(null);
      setEditFilter(null);
      fetchFilters();
    } catch (err) { console.error(err); }
  };

  const handleDeleteFilter = async (index: number) => {
    try {
      await api.del(`/sieve/filters/${index}`);
      fetchFilters();
    } catch (err) { console.error(err); }
  };

  const handlePreview = async (condition: { field: string; operator: string; value: string }) => {
    if (!condition.value) return;
    setPreviewLoading(true);
    try {
      const res = await api.get<{ matching_count: number; sample_subjects: string[] }>(
        `/sieve/filters/preview?field=${condition.field}&operator=${condition.operator}&value=${encodeURIComponent(condition.value)}`
      );
      setPreviewResult(res);
    } catch { setPreviewResult(null); }
    finally { setPreviewLoading(false); }
  };

  if (!settings) return (
    <div className="flex-1 flex items-center justify-center bg-white">
      <div className="animate-spin w-8 h-8 border-2 border-[#0078d4] border-t-transparent rounded-full" />
    </div>
  );

  const update = (key: keyof Settings, value: unknown) =>
    setSettings({ ...settings, [key]: value });

  const tabs: { id: Tab; label: string }[] = [
    { id: 'general', label: 'General' },
    { id: 'signature', label: 'Firmas' },
    { id: 'identities', label: 'Identidades' },
    { id: 'autoreply', label: 'Respuesta automática' },
    { id: 'filters', label: 'Reglas de correo' },
    { id: 'password', label: 'Contraseña' },
    { id: 'security', label: 'Seguridad' },
  ];

  const folderOptions = folders.map(f => f.name);

  const renderFilterForm = (
    filter: FilterRule,
    setFilter: (f: FilterRule) => void,
    onSave: () => void,
    onCancel: () => void,
    saveLabel: string,
  ) => (
    <div className="p-4 bg-[#faf9f8] border border-[#edebe9] rounded space-y-3">
      <Field label="Nombre de la regla">
        <input value={filter.name} onChange={e => setFilter({ ...filter, name: e.target.value })}
          className="w-full px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none"
          placeholder="Ej: Correos de proveedores" />
      </Field>

      <div className="bg-white p-3 rounded border border-[#edebe9]">
        <div className="text-xs font-semibold text-[#605e5c] uppercase tracking-wider mb-2">Condición</div>
        <div className="flex gap-2 items-end flex-wrap">
          <Field label="Si el campo">
            <select value={filter.condition.field}
              onChange={e => setFilter({ ...filter, condition: { ...filter.condition, field: e.target.value } })}
              className="px-2 py-2 border border-[#8a8886] rounded text-sm">
              <option value="from">De (remitente)</option>
              <option value="to">Para (destinatario)</option>
              <option value="subject">Asunto</option>
            </select>
          </Field>
          <Field label="">
            <select value={filter.condition.operator}
              onChange={e => setFilter({ ...filter, condition: { ...filter.condition, operator: e.target.value } })}
              className="px-2 py-2 border border-[#8a8886] rounded text-sm">
              <option value="contains">contiene</option>
              <option value="is">es exactamente</option>
              <option value="matches">coincide con patrón</option>
            </select>
          </Field>
          <Field label="">
            <input value={filter.condition.value}
              onChange={e => setFilter({ ...filter, condition: { ...filter.condition, value: e.target.value } })}
              className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none min-w-[200px]"
              placeholder="valor..." />
          </Field>
          <button onClick={() => handlePreview(filter.condition)}
            disabled={!filter.condition.value || previewLoading}
            className="px-3 py-2 text-xs text-[#0078d4] border border-[#0078d4] rounded hover:bg-[#deecf9] disabled:opacity-50">
            {previewLoading ? '...' : 'Vista previa'}
          </button>
        </div>
        {previewResult && (
          <div className="mt-2 p-2 bg-[#deecf9] rounded text-xs text-[#323130]">
            <b>{previewResult.matching_count}</b> mensaje{previewResult.matching_count !== 1 ? 's' : ''} coinciden en Bandeja de entrada
            {previewResult.sample_subjects.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-[#605e5c]">
                {previewResult.sample_subjects.map((s, i) => <li key={i} className="truncate">- {s}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="bg-white p-3 rounded border border-[#edebe9]">
        <div className="text-xs font-semibold text-[#605e5c] uppercase tracking-wider mb-2">Acción</div>
        <div className="flex gap-2 items-end flex-wrap">
          <Field label="Entonces">
            <select value={filter.action.type}
              onChange={e => setFilter({ ...filter, action: { ...filter.action, type: e.target.value } })}
              className="px-2 py-2 border border-[#8a8886] rounded text-sm">
              <option value="move">Mover a carpeta</option>
              <option value="flag">Marcar con bandera</option>
              <option value="delete">Eliminar</option>
              <option value="forward">Reenviar a</option>
            </select>
          </Field>
          {filter.action.type === 'move' && (
            <Field label="Carpeta destino">
              <select value={filter.action.value || ''}
                onChange={e => setFilter({ ...filter, action: { ...filter.action, value: e.target.value } })}
                className="px-2 py-2 border border-[#8a8886] rounded text-sm min-w-[180px]">
                <option value="">-- Seleccionar --</option>
                {folderOptions.map(f => (
                  <option key={f} value={f}>{getFolderDisplayName(f)}</option>
                ))}
              </select>
            </Field>
          )}
          {filter.action.type === 'forward' && (
            <Field label="Reenviar a">
              <input value={filter.action.value || ''}
                onChange={e => setFilter({ ...filter, action: { ...filter.action, value: e.target.value } })}
                className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none"
                placeholder="email@ejemplo.com" />
            </Field>
          )}
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <button onClick={onSave}
          disabled={!filter.name || !filter.condition.value}
          className="px-4 py-1.5 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe] disabled:opacity-50">
          {saveLabel}
        </button>
        <button onClick={onCancel}
          className="px-4 py-1.5 text-sm text-[#605e5c] hover:bg-[#e1dfdd] rounded">
          Cancelar
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#edebe9] flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[#323130]">Configuración</h1>
        <div className="flex items-center gap-3">
          {saved && <span className="text-xs text-green-600">Guardado</span>}
          {tab === 'general' && (
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-1.5 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe] disabled:opacity-50">
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#edebe9] overflow-x-auto">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-5 py-2.5 text-sm transition-colors whitespace-nowrap ${
              tab === t.id ? 'text-[#0078d4] border-b-2 border-[#0078d4] font-medium' : 'text-[#605e5c] hover:text-[#323130]'
            }`}>{t.label}</button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
        {tab === 'general' && (
          <div className="space-y-5">
            <Field label="Nombre para mostrar">
              <input value={settings.display_name} onChange={e => update('display_name', e.target.value)}
                className="w-full px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none" />
            </Field>
            <Field label="Mensajes por página">
              <select value={settings.messages_per_page} onChange={e => update('messages_per_page', Number(e.target.value))}
                className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none">
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </Field>
            <Field label="Panel de lectura">
              <select value={settings.reading_pane} onChange={e => update('reading_pane', e.target.value)}
                className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none">
                <option value="right">A la derecha</option>
                <option value="bottom">Abajo</option>
                <option value="off">Desactivado</option>
              </select>
            </Field>
            <Toggle label="Bloquear imágenes remotas" checked={settings.block_remote_images}
              onChange={v => update('block_remote_images', v)} />
            <Toggle label="Confirmar al eliminar" checked={settings.confirm_delete}
              onChange={v => update('confirm_delete', v)} />
          </div>
        )}

        {tab === 'signature' && (
          <SignatureManager />
        )}

        {tab === 'identities' && (
          <IdentityManager />
        )}

        {tab === 'autoreply' && (
          <div className="space-y-5">
            {vacationLoading ? (
              <div className="text-sm text-[#a19f9d]">Cargando configuración de Sieve...</div>
            ) : (
              <>
                <Toggle label="Activar respuesta automática" checked={vacation.enabled}
                  onChange={v => setVacation({ ...vacation, enabled: v })} />
                {vacation.enabled && (
                  <>
                    <Field label="Asunto">
                      <input value={vacation.subject} onChange={e => setVacation({ ...vacation, subject: e.target.value })}
                        className="w-full px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none"
                        placeholder="Estoy fuera de la oficina" />
                    </Field>
                    <Field label="Mensaje">
                      <textarea value={vacation.body} onChange={e => setVacation({ ...vacation, body: e.target.value })}
                        rows={5} className="w-full px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none resize-none"
                        placeholder="Gracias por su correo. Estaré de vuelta el..." />
                    </Field>
                    <div className="flex gap-4">
                      <Field label="Desde (opcional)">
                        <input type="date" value={vacation.start_date} onChange={e => setVacation({ ...vacation, start_date: e.target.value })}
                          className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none" />
                      </Field>
                      <Field label="Hasta (opcional)">
                        <input type="date" value={vacation.end_date} onChange={e => setVacation({ ...vacation, end_date: e.target.value })}
                          className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none" />
                      </Field>
                    </div>
                    <button onClick={handleSaveVacation} disabled={saving}
                      className="px-4 py-1.5 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe] disabled:opacity-50">
                      {saving ? 'Guardando...' : 'Guardar respuesta automática'}
                    </button>
                  </>
                )}
                {!vacation.enabled && (
                  <button onClick={handleSaveVacation} disabled={saving}
                    className="px-4 py-1.5 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe] disabled:opacity-50">
                    Desactivar respuesta automática
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {tab === 'filters' && (
          <div className="space-y-4">
            {/* Header con descripción clara */}
            <div className="bg-[#deecf9] p-3 rounded text-sm text-[#323130]">
              <p className="font-medium mb-1">Reglas de correo</p>
              <p className="text-xs text-[#605e5c]">
                Organiza tu correo automáticamente. Las reglas se aplican a los mensajes nuevos que llegan a tu buzón.
                Puedes mover correos a carpetas, marcarlos, eliminarlos o reenviarlos según el remitente, destinatario o asunto.
              </p>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-[#605e5c]">{filters.length} regla{filters.length !== 1 ? 's' : ''} configurada{filters.length !== 1 ? 's' : ''}</span>
              <button onClick={() => { setShowAddFilter(!showAddFilter); setPreviewResult(null); }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe]">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Nueva regla
              </button>
            </div>

            {showAddFilter && renderFilterForm(
              newFilter,
              setNewFilter,
              handleAddFilter,
              () => { setShowAddFilter(false); setPreviewResult(null); },
              'Crear regla',
            )}

            {filtersLoading ? (
              <div className="text-sm text-[#a19f9d]">Cargando reglas...</div>
            ) : filters.length === 0 && !showAddFilter ? (
              <div className="text-center py-12 text-[#a19f9d]">
                <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
                <p className="text-sm font-medium">No hay reglas configuradas</p>
                <p className="text-xs mt-1">Crea una regla para organizar tu correo automáticamente</p>
              </div>
            ) : (
              <div className="space-y-2">
                {filters.map((f, i) => (
                  <div key={i}>
                    {editingFilter === i && editFilter ? (
                      renderFilterForm(
                        editFilter,
                        setEditFilter,
                        () => handleUpdateFilter(i),
                        () => { setEditingFilter(null); setEditFilter(null); setPreviewResult(null); },
                        'Guardar cambios',
                      )
                    ) : (
                      <div className="flex items-center justify-between p-3 bg-[#faf9f8] border border-[#edebe9] rounded hover:border-[#8a8886] transition-colors group">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-[#323130]">{f.name}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                              f.action.type === 'move' ? 'bg-blue-100 text-blue-700' :
                              f.action.type === 'flag' ? 'bg-yellow-100 text-yellow-700' :
                              f.action.type === 'delete' ? 'bg-red-100 text-red-700' :
                              'bg-green-100 text-green-700'
                            }`}>
                              {ACTION_LABELS[f.action.type] || f.action.type}
                            </span>
                          </div>
                          <p className="text-xs text-[#605e5c] mt-0.5">
                            Si <b>{FIELD_LABELS[f.condition.field] || f.condition.field}</b>{' '}
                            {OP_LABELS[f.condition.operator] || f.condition.operator}{' '}
                            &quot;<span className="text-[#323130]">{f.condition.value}</span>&quot;
                            {f.action.value && (
                              <> → <span className="text-[#323130]">{f.action.type === 'move' ? getFolderDisplayName(f.action.value) : f.action.value}</span></>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => { setEditingFilter(i); setEditFilter({ ...f }); setPreviewResult(null); }}
                            className="text-xs text-[#0078d4] hover:bg-[#deecf9] px-2 py-1 rounded" title="Editar">
                            Editar
                          </button>
                          <button onClick={() => handleDeleteFilter(i)}
                            className="text-xs text-[#a4262c] hover:bg-[#fde7e9] px-2 py-1 rounded" title="Eliminar">
                            Eliminar
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'security' && (
          <TwoFactorSetup />
        )}

        {tab === 'password' && (
          <PasswordChange />
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      {label && <label className="block text-sm font-medium text-[#323130] mb-1.5">{label}</label>}
      {children}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <div className={`w-10 h-5 rounded-full transition-colors relative ${checked ? 'bg-[#0078d4]' : 'bg-[#8a8886]'}`}
        onClick={() => onChange(!checked)}>
        <div className={`w-4 h-4 bg-white rounded-full absolute top-0.5 transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </div>
      <span className="text-sm text-[#323130]">{label}</span>
    </label>
  );
}
