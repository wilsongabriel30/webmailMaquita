// Compartir una lista (como en To Do): la propietaria busca personas de la organización en el directorio y las suma,
// quita miembros o deja de compartir; un miembro puede salirse. Pestaña «Actividad» con el registro de la lista y,
// al pie, la preferencia personal de recibir también por correo los avisos de las listas compartidas.
import { useEffect, useState } from 'react';
import { api } from '../../../api/client';
import { SelectorPersonas } from '../../tareas/SelectorPersonas';
import type { TaskList } from '../types';
import { COLORS } from '../types';
import { useMiembros } from '../hooks/useMiembros';
import { ActividadLista } from './ActividadLista';
import { CirculoPersona } from './CirculoPersona';
import { separarEmoji } from './nombreLista';

interface Props {
  lista: TaskList;
  yo: string;
  onCerrar: () => void;
  /** Cambió quién está en la lista: se recarga la barra. */
  onCambio: () => void;
  /** La persona se salió de la lista: hay que mostrar otra. */
  onSalir: () => void;
}

const boton = (color: string, fondo = 'white') => ({
  fontSize: 13, padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
  border: `1px solid ${color}`, color: fondo === 'white' ? color : 'white', background: fondo,
});

export function DialogoCompartir({ lista, yo, onCerrar, onCambio, onSalir }: Props) {
  const { miembros, recargar } = useMiembros(lista.id);
  const [pestana, setPestana] = useState<'personas' | 'actividad'>('personas');
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [porCorreo, setPorCorreo] = useState<boolean | null>(null);
  const soyDuena = lista.role !== 'member';
  const { texto } = separarEmoji(lista.name);

  useEffect(() => {
    let vigente = true;
    api.get<{ avisos_correo: boolean }>('/tasks/preferencias')
      .then(p => { if (vigente) setPorCorreo(p.avisos_correo); })
      .catch(() => {});
    return () => { vigente = false; };
  }, []);
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onCerrar]);

  const hacer = async (accion: () => Promise<unknown>, despues?: () => void) => {
    setOcupado(true);
    setError('');
    try {
      await accion();
      recargar();
      onCambio();
      despues?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar la acción');
    }
    setOcupado(false);
  };

  const agregar = (emails: string[]) => {
    const email = emails[emails.length - 1];
    if (email) void hacer(() => api.post(`/tasks/lists/${lista.id}/miembros`, { email }));
  };
  const quitar = (email: string, nombre: string) => {
    const propio = email === yo;
    const pregunta = propio ? `¿Salir de la lista «${texto}»? Dejarás de verla.` : `¿Quitar a ${nombre} de la lista?`;
    if (!confirm(pregunta)) return;
    void hacer(() => api.del(`/tasks/lists/${lista.id}/miembros/${encodeURIComponent(email)}`), propio ? onSalir : undefined);
  };
  const dejarDeCompartir = () => {
    if (!confirm(`¿Dejar de compartir «${texto}»? Las demás personas dejarán de verla.`)) return;
    void hacer(() => api.del(`/tasks/lists/${lista.id}/miembros`));
  };
  const cambiarCorreo = (valor: boolean) => {
    setPorCorreo(valor);
    api.put('/tasks/preferencias', { avisos_correo: valor }).catch(() => setPorCorreo(!valor));
  };

  return (
    <div role="presentation" onClick={onCerrar}
      style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div role="dialog" aria-modal="true" aria-label={`Compartir la lista ${texto}`} onClick={e => e.stopPropagation()}
        style={{
          width: 440, maxWidth: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column', background: 'white',
          borderRadius: 8, boxShadow: '0 8px 32px rgba(0,0,0,0.2)', fontFamily: "'Segoe UI', system-ui, sans-serif",
        }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '16px 20px 8px' }}>
          <h2 style={{ flex: 1, margin: 0, fontSize: 16, fontWeight: 600, color: COLORS.text }}>Compartir «{texto}»</h2>
          <button type="button" aria-label="Cerrar" onClick={onCerrar}
            style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: COLORS.secondary }}>&times;</button>
        </div>
        <div role="tablist" style={{ display: 'flex', gap: 16, padding: '0 20px', borderBottom: `1px solid ${COLORS.border}` }}>
          {(['personas', 'actividad'] as const).map(p => (
            <button key={p} type="button" role="tab" aria-selected={pestana === p} onClick={() => setPestana(p)}
              style={{
                background: 'none', border: 'none', padding: '8px 0', cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
                color: pestana === p ? COLORS.primary : COLORS.secondary, fontWeight: pestana === p ? 600 : 400,
                borderBottom: pestana === p ? `2px solid ${COLORS.primary}` : '2px solid transparent',
              }}>
              {p === 'personas' ? `Personas (${miembros.length})` : 'Actividad'}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
          {pestana === 'actividad' ? (
            <ActividadLista ruta={`/tasks/lists/${lista.id}/actividad`} />
          ) : (
            <>
              {soyDuena && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12, color: COLORS.secondary, marginBottom: 4 }}>
                    Busca a una persona de la organización por nombre, correo o departamento:
                  </div>
                  <SelectorPersonas valor={[]} onChange={agregar} multiple={false} placeholder="Agregar persona…" />
                </div>
              )}
              {miembros.map(m => (
                <div key={m.email} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0' }}>
                  <CirculoPersona email={m.email} nombre={m.nombre} tamano={30} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, color: COLORS.text }}>{m.nombre}{m.email === yo ? ' (tú)' : ''}</div>
                    <div style={{ fontSize: 12, color: COLORS.secondary, overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.email}</div>
                  </div>
                  {m.role === 'owner' ? (
                    <span style={{ fontSize: 11, color: COLORS.secondary }}>Propietaria</span>
                  ) : (soyDuena || m.email === yo) && (
                    <button type="button" disabled={ocupado} onClick={() => quitar(m.email, m.nombre)}
                      style={boton(m.email === yo ? '#d13438' : COLORS.secondary)}>
                      {m.email === yo ? 'Salir' : 'Quitar'}
                    </button>
                  )}
                </div>
              ))}
              {miembros.length <= 1 && soyDuena && (
                <p style={{ fontSize: 12, color: COLORS.secondary }}>
                  Esta lista todavía no está compartida. Las personas que agregues la verán en su barra y podrán agregar,
                  completar y asignar tareas.
                </p>
              )}
              {error && <div role="alert" style={{ fontSize: 12, color: '#d13438', marginTop: 8 }}>{error}</div>}
            </>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 20px', borderTop: `1px solid ${COLORS.border}` }}>
          <label style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: COLORS.text }}>
            <input type="checkbox" checked={!!porCorreo} disabled={porCorreo === null}
              onChange={e => cambiarCorreo(e.target.checked)} />
            Recibir también por correo los avisos de mis listas compartidas
          </label>
          {soyDuena && miembros.length > 1 && (
            <button type="button" disabled={ocupado} onClick={dejarDeCompartir} style={boton('#d13438')}>Dejar de compartir</button>
          )}
        </div>
      </div>
    </div>
  );
}
