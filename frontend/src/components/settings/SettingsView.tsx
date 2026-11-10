import { useState, useEffect } from 'react';
import { IntegrationsSettings } from './IntegrationsSettings';
import { useLocation } from 'react-router-dom';
import { api } from '../../api/client';
import { PasswordChange } from './PasswordChange';
import { CerrarSesiones } from './CerrarSesiones';
import { IdentityManager } from './IdentityManager';
import { SignatureManager } from './SignatureManager';
import { TwoFactorSetup } from './TwoFactorSetup';
import { ContrasenasAplicacion } from './ContrasenasAplicacion';
import { MiEquipo } from './MiEquipo';
import { MailSetup } from './MailSetup';
import { useMailStore } from '../../store/mailStore';
import { abrirModalRegla } from '../../lib/reglas/abrirModalRegla';
import { resumenRegla } from '../../lib/reglas/resumenRegla';
import { BotonAplicarRegla } from '../reglas/BotonAplicarRegla';
import { ETIQUETA_ACCION, normalizarRegla, reglaVacia, type Regla } from '../../lib/reglas/tipos';
import { showToast } from '../common/Toast';
import EspacioLocal from './EspacioLocal';   // T-49: cuánto ocupa el caché cifrado en el equipo
import SmimeSettings from './SmimeSettings';   // Certificados S/MIME (por usuario)
import { RemitentesBloqueados } from './RemitentesBloqueados';   // 05/11/2026: lo que llena «Marcar como spam»
import MiFoto from './MiFoto';
import { olvidarPreferenciaAcuse } from '../../lib/acuseLectura';   // 09/11/2026

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
  /** Qué hacer cuando un correo recibido pide confirmación de lectura (09/11/2026). */
  acuse_lectura?: 'preguntar' | 'siempre' | 'nunca';
}

interface VacationSettings {
  enabled: boolean;
  subject: string;
  body: string;
  start_date: string;
  end_date: string;
}

type FilterRule = Regla;

type Tab = 'general' | 'foto' | 'signature' | 'identities' | 'autoreply' | 'filters' | 'bloqueados' | 'password' | 'security' | 'miequipo' | 'smime' | 'integrations' | 'mailsetup' | 'espacio';


export function SettingsView() {
  const location = useLocation();
  useEffect(() => {
    if (useMailStore.getState().folders.length === 0) {
      api.get<{ folders: { name: string }[] }>('/mail/folders')
        .then(r => useMailStore.getState().setFolders(r.folders as never[]))
        .catch(() => {});
    }
  }, []);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [tab, setTab] = useState<Tab>('general');

  // Vacation (Sieve)
  const [vacation, setVacation] = useState<VacationSettings>({ enabled: false, subject: '', body: '', start_date: '', end_date: '' });
  const [vacationLoading, setVacationLoading] = useState(false);
  const [vacationLoaded, setVacationLoaded] = useState(false);

  // Filters (Sieve)
  const [filters, setFilters] = useState<FilterRule[]>([]);
  const [filtersLoading, setFiltersLoading] = useState(false);
  const [filtersLoaded, setFiltersLoaded] = useState(false);
  // Error al cargar las reglas: distinto de «no hay reglas», para no decir que hay cero cuando no se sabe.
  const [filtersError, setFiltersError] = useState(false);
  // Motivo que manda el servidor (p. ej. «No se pudo conectar con el servicio de reglas de correo…»).
  const [filtersErrorDetail, setFiltersErrorDetail] = useState('');

  useEffect(() => {
    api.get<Settings>('/settings').then(setSettings).catch(console.error);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const requestedTab = params.get('tab');
    const validTabs: Tab[] = ['general', 'foto', 'signature', 'identities', 'autoreply', 'filters', 'bloqueados', 'password', 'security', 'integrations', 'mailsetup'];
    if (requestedTab && validTabs.includes(requestedTab as Tab)) {
      setTab(requestedTab as Tab);
    }
  }, [location.search]);

  // El servidor explica los fallos en español (422, 424, 500); un «HTTP 500» pelado no se muestra.
  const motivoServidor = (err: unknown): string => {
    const m = err instanceof Error ? err.message : '';
    return m && !/^HTTP \d+$/.test(m) && m !== 'Session expired' ? m : '';
  };

  const fetchFilters = () => {
    setFiltersLoading(true);
    setFiltersError(false);
    setFiltersErrorDetail('');
    api.get<FilterRule[]>('/sieve/filters')
      .then(data => {
        // API returns array directly
        const arr = Array.isArray(data) ? data : (data as { filters?: FilterRule[] }).filters || [];
        setFilters(arr.map(normalizarRegla));
      })
      // Si falla (p. ej. 424 porque ManageSieve rechazó la sesión), se conservan las reglas ya
      // conocidas y se avisa del error con «Reintentar»; la sesión NO se cierra.
      .catch((err) => { setFiltersError(true); setFiltersErrorDetail(motivoServidor(err)); })
      .finally(() => { setFiltersLoading(false); setFiltersLoaded(true); });
  };

  useEffect(() => {
    if (tab === 'autoreply' && !vacationLoaded) {
      setVacationLoading(true);
      api.get<VacationSettings>('/sieve/vacation')
        .then(v => { setVacation(v); setVacationLoaded(true); })
        .catch(() => {})
        .finally(() => setVacationLoading(false));
    }
    if (tab === 'filters' && !filtersLoaded) {
      fetchFilters();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    try {
      await api.put('/settings', settings);
      olvidarPreferenciaAcuse();   // la vista del correo vuelve a leer la preferencia guardada
      if (settings.reading_pane) useMailStore.getState().setReadingPane(settings.reading_pane as 'right' | 'bottom' | 'off');
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      showToast('Cambios guardados');
    } catch (err) { console.error(err); showToast('No se pudo guardar. Revise la conexión e inténtelo de nuevo.', undefined, { fijo: true }); }
    finally { setSaving(false); }
  };

  const handleSaveVacation = async () => {
    setSaving(true);
    try {
      await api.put('/sieve/vacation', vacation);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      showToast(vacation.enabled ? 'Respuesta automática guardada y activada' : 'Respuesta automática guardada');
    } catch (err) { console.error(err); showToast('No se pudo guardar. Revise la conexión e inténtelo de nuevo.', undefined, { fijo: true }); }
    finally { setSaving(false); }
  };

  const handleDeleteFilter = async (index: number) => {
    try {
      await api.del(`/sieve/filters/${index}`);
      fetchFilters();
      showToast('Regla eliminada');
    } catch (err) { console.error(err); showToast(motivoServidor(err) || 'No se pudo eliminar la regla. Inténtelo de nuevo.', undefined, { fijo: true }); }
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
    { id: 'autoreply', label: 'Fuera de la oficina' },
    { id: 'filters', label: 'Reglas de correo' },
    { id: 'bloqueados', label: 'Remitentes bloqueados' },
    { id: 'foto', label: 'Mi foto' },
    { id: 'password', label: 'Contraseña' },
    { id: 'security', label: 'Seguridad' },
    { id: 'miequipo', label: 'Mi teléfono' },
    { id: 'smime', label: 'Certificados S/MIME' },
    { id: 'integrations', label: 'Integraciones' },
    { id: 'mailsetup', label: 'Configurar mi correo' },
    { id: 'espacio', label: 'Espacio en el equipo' },
  ];

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
      {/* flex-wrap: con letra grande o zoom 150 % las pestañas del final quedaban fuera de la
          pantalla, detrás de una barra de desplazamiento de 4 px. */}
      <div className="flex flex-wrap border-b border-[#edebe9]">
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
              <input value={settings.display_name} onChange={e => update('display_name', e.target.value)} aria-label="Nombre para mostrar"
                className="w-full px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none" />
            </Field>
            <Field label="Mensajes por página">
              <select value={settings.messages_per_page} onChange={e => update('messages_per_page', Number(e.target.value))} aria-label="Mensajes por página"
                className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none">
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </Field>
            <Field label="Cuando un correo me pide confirmación de lectura">
              <select value={settings.acuse_lectura || 'preguntar'} onChange={e => update('acuse_lectura', e.target.value as 'preguntar' | 'siempre' | 'nunca')}
                aria-label="Confirmaciones de lectura que me piden"
                className="px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none">
                <option value="preguntar">Preguntarme en cada correo</option>
                <option value="siempre">Enviarla siempre (sin preguntar)</option>
                <option value="nunca">No enviarla nunca</option>
              </select>
              <p className="mt-1 text-xs text-[#605e5c]">
                Para pedir usted la confirmación al enviar: en el correo nuevo, pestaña Opciones → Seguimiento.
              </p>
            </Field>
            <Field label="Panel de lectura">
              <select value={settings.reading_pane} onChange={e => update('reading_pane', e.target.value)} aria-label="Panel de lectura"
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
              <div className="text-sm text-[#a19f9d]">Cargando…</div>
            ) : (
              <>
                <Toggle label="Activar respuesta automática" checked={vacation.enabled}
                  onChange={v => {
                    const next = { ...vacation, enabled: v };
                    setVacation(next);
                    if (!v) {
                      // Apagar debe persistirse al instante (el botón Guardar solo existe encendido)
                      api.put('/sieve/vacation', next).then(() => {
                        setSaved(true); setTimeout(() => setSaved(false), 3000);
                        showToast('Respuesta automática desactivada');
                      }).catch(err => { console.error(err); showToast('No se pudo guardar. Revise la conexión e inténtelo de nuevo.', undefined, { fijo: true }); });
                    }
                  }} />
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
                    className="px-4 py-1.5 bg-[#605e5c] text-white text-sm rounded hover:bg-[#484644] disabled:opacity-50">
                    {saving ? 'Guardando...' : 'Respuesta automática desactivada'}
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
              <span className="text-sm text-[#605e5c]">{filtersError ? '' : <>{filters.length} regla{filters.length !== 1 ? 's' : ''} configurada{filters.length !== 1 ? 's' : ''}</>}</span>
              <button onClick={() => abrirModalRegla({ regla: reglaVacia(), alGuardar: fetchFilters })}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe]">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Nueva regla
              </button>
            </div>

            {filtersLoading ? (
              <div className="text-sm text-[#605e5c]" role="status">Cargando reglas...</div>
            ) : filtersError ? (
              <div role="alert" className="p-4 rounded border border-[#a4262c] bg-[#fde7e9] text-[#323130]">
                <p className="text-sm font-semibold text-[#a4262c]">No se pudieron cargar sus reglas de correo</p>
                <p className="text-sm mt-1">{filtersErrorDetail || 'Sus reglas no se han borrado: solo no pudimos leerlas en este momento. Revise su conexión e inténtelo de nuevo.'}</p>
                <button type="button" onClick={fetchFilters}
                  className="mt-3 px-4 py-2 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe]">
                  Reintentar
                </button>
              </div>
            ) : filters.length === 0 ? (
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
                    {(
                      <div className={`flex items-center justify-between p-3 bg-[#faf9f8] border border-[#edebe9] rounded hover:border-[#8a8886] transition-colors group ${f.enabled ? '' : 'opacity-60'}`}>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-[#323130]">{f.name}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                              f.actions[0].type === 'move' || f.actions[0].type === 'copy' ? 'bg-blue-100 text-blue-700' :
                              f.actions[0].type === 'flag' || f.actions[0].type === 'read' ? 'bg-yellow-100 text-yellow-700' :
                              f.actions[0].type === 'delete' ? 'bg-red-100 text-red-700' :
                              'bg-green-100 text-green-700'
                            }`}>
                              {ETIQUETA_ACCION[f.actions[0].type]}{f.actions.length > 1 ? ` +${f.actions.length - 1}` : ''}
                            </span>
                            {!f.enabled && <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#edebe9] text-[#605e5c]">desactivada</span>}
                          </div>
                          <p className="text-xs text-[#605e5c] mt-0.5">
                            {resumenRegla(f).condiciones} → <span className="text-[#323130]">{resumenRegla(f).acciones}</span>
                          </p>
                        </div>
                        <div className="flex items-center gap-1">
                          {f.enabled && <BotonAplicarRegla regla={f} />}
                          <button onClick={() => abrirModalRegla({ regla: f, indice: i, alGuardar: fetchFilters })}
                            className="text-[13px] text-[#0078d4] hover:bg-[#deecf9] px-2 py-1 rounded" title="Editar">
                            Editar
                          </button>
                          <button onClick={() => { if (window.confirm(`¿Eliminar la regla «${f.name}»?`)) handleDeleteFilter(i); }}
                            className="text-[13px] text-[#a4262c] hover:bg-[#fde7e9] px-2 py-1 rounded" title="Eliminar">
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

        {tab === 'bloqueados' && <RemitentesBloqueados />}
        {tab === 'foto' && <MiFoto />}

        {tab === 'espacio' && <EspacioLocal />}

        {tab === 'security' && (
          <>
            <TwoFactorSetup />
            <ContrasenasAplicacion />
          </>
        )}

        {tab === 'miequipo' && <MiEquipo />}
        {tab === 'integrations' && <IntegrationsSettings />}

        {tab === 'smime' && <SmimeSettings />}

        {tab === 'password' && (
          <>
            <PasswordChange />
            <CerrarSesiones />
          </>
        )}
        {tab === 'mailsetup' && (
          <MailSetup />
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