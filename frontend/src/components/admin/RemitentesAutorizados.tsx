// Quién puede ENVIAR a una lista (06/11/2026).
// Con al menos una persona aquí, el servidor solo acepta correos a la lista de esas cuentas
// (servicio maquita-politica-listas en Postfix); el resto recibe un rechazo explicado.
// Sin nadie, la lista queda abierta. Se guarda en mail_groups.allowed_senders (PUT /admin/groups/{id}).
import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Props {
  grupoId: number;
  direccion: string;
  autorizados: string;               // texto guardado: direcciones separadas por coma
  onGuardado: (nuevo: string) => void;
}

const EMAIL_RE = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;

function separar(texto: string): string[] {
  return (texto || '').split(/[\s,;]+/).map((x) => x.trim().toLowerCase()).filter(Boolean);
}

export function RemitentesAutorizados({ grupoId, direccion, autorizados, onGuardado }: Props) {
  const [lista, setLista] = useState<string[]>(separar(autorizados));
  const [nuevo, setNuevo] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { setLista(separar(autorizados)); setError(''); }, [autorizados, grupoId]);

  const guardar = async (siguiente: string[]) => {
    setGuardando(true);
    setError('');
    try {
      const texto = siguiente.join(', ');
      await api.put(`/admin/groups/${grupoId}`, { allowed_senders: texto });
      setLista(siguiente);
      onGuardado(texto);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar');
    } finally {
      setGuardando(false);
    }
  };

  const agregar = () => {
    const correo = nuevo.trim().toLowerCase();
    if (!EMAIL_RE.test(correo)) { setError('Escriba una dirección de correo válida.'); return; }
    if (lista.includes(correo)) { setError('Esa persona ya está autorizada.'); return; }
    setNuevo('');
    guardar([...lista, correo]);
  };

  const quitar = (correo: string) => {
    const aviso = lista.length === 1
      ? `Si quita a ${correo}, la lista ${direccion} quedará ABIERTA: cualquiera podrá escribirle. ¿Continuar?`
      : `¿Quitar a ${correo}? Ya no podrá enviar correos a ${direccion}.`;
    if (!confirm(aviso)) return;
    guardar(lista.filter((x) => x !== correo));
  };

  return (
    <div className="mb-5 p-3 rounded-lg border border-amber-200 bg-amber-50">
      <h4 className="text-sm font-semibold text-slate-800">Pueden enviar a esta lista</h4>
      <p className="text-xs text-slate-600 mt-0.5 mb-2">
        {lista.length > 0
          ? 'Solo estas personas pueden escribir a la lista; a cualquier otra el servidor le rechaza el envío.'
          : 'Nadie restringido: cualquiera puede escribir a la lista. Agregue personas para limitarla.'}
      </p>
      <div className="flex gap-2 mb-2">
        <input value={nuevo} onChange={(e) => setNuevo(e.target.value)} disabled={guardando}
          placeholder="correo@example.org"
          onKeyDown={(e) => e.key === 'Enter' && agregar()}
          className="flex-1 px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white" />
        <button onClick={agregar} disabled={guardando || !nuevo.trim()}
          className="px-3 py-1.5 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm disabled:opacity-50">
          Autorizar
        </button>
      </div>
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
      {lista.length > 0 && (
        <div className="space-y-1">
          {lista.map((c) => (
            <div key={c} className="flex items-center justify-between py-1 px-2 rounded bg-white border border-amber-100">
              <span className="text-sm text-slate-800">{c}</span>
              <button onClick={() => quitar(c)} disabled={guardando} title={`Quitar a ${c}`}
                className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50">Quitar</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
