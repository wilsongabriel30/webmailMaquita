/**
 * ContrasenasAplicacion.tsx — Contraseñas de aplicación (D-5).
 *
 * Una por cliente externo (Outlook, Thunderbird, el celular): se genera aquí, se muestra UNA vez
 * y se revoca cuando se quiera. Con la política activa, la contraseña principal deja de valer en
 * IMAP/SMTP/ActiveSync: solo sirve para entrar al webmail y a la app.
 * API: GET/POST /api/settings/contrasenas-aplicacion, DELETE /{id}.
 */

import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Clave {
  id: number;
  nombre: string;
  prefijo: string;
  creada: string;
  ultimo_uso: string | null;
  ultimo_ip: string | null;
}

interface Listado {
  contrasenas: Clave[];
  obligatorias: boolean;
  maximo: number;
}

function fecha(iso: string | null): string {
  if (!iso) return 'nunca';
  try { return new Date(iso).toLocaleString('es-EC', { dateStyle: 'short', timeStyle: 'short' }); } catch { return iso; }
}

export function ContrasenasAplicacion() {
  const [datos, setDatos] = useState<Listado>({ contrasenas: [], obligatorias: false, maximo: 10 });
  const [nombre, setNombre] = useState('');
  const [contrasenaActual, setContrasenaActual] = useState('');
  const [nueva, setNueva] = useState<{ nombre: string; contrasena: string } | null>(null);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [copiada, setCopiada] = useState(false);

  const cargar = useCallback(async () => {
    try { setDatos(await api.get<Listado>('/settings/contrasenas-aplicacion')); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'No se pudo cargar'); }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const crear = async () => {
    setError(''); setNueva(null); setCopiada(false);
    if (!nombre.trim()) { setError('Ponle un nombre: el cliente donde la vas a usar'); return; }
    if (!contrasenaActual) { setError('Escribe tu contraseña actual para confirmar'); return; }
    setOcupado(true);
    try {
      const r = await api.post<{ contrasena: string; nombre: string }>('/settings/contrasenas-aplicacion', {
        nombre: nombre.trim(), contrasena_actual: contrasenaActual,
      });
      setNueva({ nombre: r.nombre, contrasena: r.contrasena });
      setNombre(''); setContrasenaActual('');
      await cargar();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'No se pudo crear');
    } finally { setOcupado(false); }
  };

  const revocar = async (c: Clave) => {
    if (!window.confirm(`¿Revocar la contraseña de «${c.nombre}»? Ese cliente dejará de conectarse.`)) return;
    try { await api.del(`/settings/contrasenas-aplicacion/${c.id}`); await cargar(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'No se pudo revocar'); }
  };

  const copiar = async () => {
    if (!nueva) return;
    try { await navigator.clipboard.writeText(nueva.contrasena); setCopiada(true); } catch { /* sin portapapeles: la persona la copia a mano */ }
  };

  return (
    <div className="mt-8 border-t border-[#edebe9] pt-6">
      <h3 className="text-base font-semibold text-[#323130] mb-1">Contraseñas de aplicación</h3>
      <p className="text-sm text-[#605e5c] mb-3">
        Para Outlook, Thunderbird, el celular o cualquier programa que no sea este webmail. Una por cliente:
        si pierdes el dispositivo, revocas solo esa.
        {datos.obligatorias
          ? ' Tu contraseña principal solo sirve para entrar aquí y a la app; en los demás programas usa una de estas.'
          : ' Hoy tu contraseña principal todavía sirve en esos programas; pronto dejará de hacerlo.'}
      </p>

      {nueva && (
        <div className="mb-4 p-3 rounded border border-[#107c10] bg-[#dff6dd] text-sm">
          <div className="font-medium text-[#323130]">Contraseña para «{nueva.nombre}». Cópiala ahora: no se vuelve a mostrar.</div>
          <div className="flex items-center gap-2 mt-2">
            <code className="text-lg tracking-wider bg-white px-2 py-1 rounded border border-[#c8c6c4] select-all">{nueva.contrasena}</code>
            <button onClick={copiar} className="px-3 py-1 text-sm rounded bg-[#0078d4] text-white hover:bg-[#106ebe]">
              {copiada ? 'Copiada' : 'Copiar'}
            </button>
          </div>
          <div className="text-[#605e5c] mt-2">Se puede escribir con o sin guiones. Usuario: tu correo completo; servidor: el de siempre.</div>
        </div>
      )}

      {datos.contrasenas.length > 0 && (
        <table className="w-full text-sm mb-4">
          <thead>
            <tr className="text-left text-[#605e5c] border-b border-[#edebe9]">
              <th className="py-1 font-normal">Cliente</th>
              <th className="py-1 font-normal">Empieza por</th>
              <th className="py-1 font-normal">Creada</th>
              <th className="py-1 font-normal">Último uso</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {datos.contrasenas.map(c => (
              <tr key={c.id} className="border-b border-[#f3f2f1]">
                <td className="py-2 text-[#323130]">{c.nombre}</td>
                <td className="py-2 font-mono">{c.prefijo}…</td>
                <td className="py-2">{fecha(c.creada)}</td>
                <td className="py-2">{fecha(c.ultimo_uso)}{c.ultimo_ip ? ` (${c.ultimo_ip})` : ''}</td>
                <td className="py-2 text-right">
                  <button onClick={() => revocar(c)} className="text-[#a4262c] hover:underline">Revocar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {datos.contrasenas.length < datos.maximo && (
        <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
          <label className="flex-1 text-sm text-[#605e5c]">
            Nombre del cliente
            <input value={nombre} onChange={e => setNombre(e.target.value)} placeholder="Outlook del trabajo, iPhone…" maxLength={80}
              className="mt-1 w-full px-3 py-2 border border-[#c8c6c4] rounded text-[#323130] focus:outline-none focus:border-[#0078d4]" />
          </label>
          <label className="flex-1 text-sm text-[#605e5c]">
            Tu contraseña actual
            <input type="password" value={contrasenaActual} onChange={e => setContrasenaActual(e.target.value)} autoComplete="current-password"
              className="mt-1 w-full px-3 py-2 border border-[#c8c6c4] rounded text-[#323130] focus:outline-none focus:border-[#0078d4]" />
          </label>
          <button onClick={crear} disabled={ocupado}
            className="px-4 py-2 rounded bg-[#0078d4] text-white text-sm hover:bg-[#106ebe] disabled:opacity-50">
            {ocupado ? 'Creando…' : 'Crear contraseña'}
          </button>
        </div>
      )}
      {error && <div className="mt-2 text-sm text-[#a4262c]">{error}</div>}
    </div>
  );
}
