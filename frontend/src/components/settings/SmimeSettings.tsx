import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Cert {
  id: number;
  user_email: string;
  issuer?: string | null;
  subject?: string | null;
  serial_number?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  fingerprint?: string | null;
  is_private: boolean;
  created_at?: string | null;
}

/**
 * Gestión de certificados S/MIME del usuario: subir el propio certificado (.p12/.pfx
 * con clave privada, o .pem/.crt público de otros para cifrarles), listarlos y
 * eliminarlos. El backend ya firma/cifra/verifica con ellos (/api/smime/*).
 */
export default function SmimeSettings() {
  const [certs, setCerts] = useState<Cert[]>([]);
  const [cargando, setCargando] = useState(true);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [passphrase, setPassphrase] = useState('');
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState('');

  const cargar = () => {
    setCargando(true);
    api
      .get<Cert[]>('/smime/keys')
      .then((r) => setCerts(r || []))
      .catch(() => setCerts([]))
      .finally(() => setCargando(false));
  };
  useEffect(cargar, []);

  const subir = async () => {
    if (!archivo) return;
    setSubiendo(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', archivo);
      if (passphrase) fd.append('passphrase', passphrase);
      const res = await fetch('/api/smime/keys/upload', {
        method: 'POST',
        body: fd,
        credentials: 'include',
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: 'No se pudo subir el certificado' }));
        throw new Error(j.detail || 'No se pudo subir el certificado');
      }
      setArchivo(null);
      setPassphrase('');
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo subir el certificado');
    } finally {
      setSubiendo(false);
    }
  };

  const eliminar = async (id: number) => {
    if (!confirm('¿Eliminar este certificado S/MIME?')) return;
    await api.del(`/smime/keys/${id}`).catch(() => {});
    cargar();
  };

  const fecha = (s?: string | null) => (s ? new Date(s).toLocaleDateString() : '—');
  const vencido = (s?: string | null) => (s ? new Date(s) < new Date() : false);

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h3 className="text-base font-semibold text-[#323130]">Certificados S/MIME</h3>
        <p className="text-sm text-[#605e5c] mt-1">
          Sube tu certificado <b>.p12/.pfx</b> (con clave privada) para <b>firmar</b> y{' '}
          <b>descifrar</b> tus correos. También puedes subir el certificado público
          (<b>.pem/.crt</b>) de un contacto para <b>cifrarle</b> mensajes.
        </p>
      </div>

      {/* Subir */}
      <div className="border border-[#edebe9] rounded p-4 space-y-3 bg-[#faf9f8]">
        <input
          type="file"
          accept=".p12,.pfx,.pem,.crt,.cer"
          onChange={(e) => setArchivo(e.target.files?.[0] || null)}
          className="block text-sm"
        />
        <input
          type="password"
          placeholder="Contraseña del .p12/.pfx (si tiene)"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          className="border border-[#8a8886] rounded px-3 py-1.5 text-sm w-full max-w-xs"
        />
        {error && <div className="text-sm text-[#a4262c]">{error}</div>}
        <button
          onClick={subir}
          disabled={!archivo || subiendo}
          className="bg-[#0078d4] text-white text-sm font-medium rounded px-4 py-1.5 disabled:opacity-50"
        >
          {subiendo ? 'Subiendo...' : 'Subir certificado'}
        </button>
      </div>

      {/* Lista */}
      {cargando ? (
        <div className="text-sm text-[#605e5c]">Cargando...</div>
      ) : certs.length === 0 ? (
        <div className="text-sm text-[#605e5c]">Todavía no tienes certificados S/MIME.</div>
      ) : (
        <div className="space-y-2">
          {certs.map((c) => (
            <div
              key={c.id}
              className="border border-[#edebe9] rounded p-3 flex items-start justify-between gap-3"
            >
              <div className="text-sm">
                <div className="font-medium text-[#323130]">
                  {c.user_email}{' '}
                  {c.is_private ? (
                    <span className="ml-2 text-xs bg-[#dff6dd] text-[#107c10] rounded px-2 py-0.5">
                      con clave privada (firmar/descifrar)
                    </span>
                  ) : (
                    <span className="ml-2 text-xs bg-[#eff6fc] text-[#0078d4] rounded px-2 py-0.5">
                      público (cifrar)
                    </span>
                  )}
                </div>
                <div className="text-[#605e5c] mt-1">Emisor: {c.issuer || '—'}</div>
                <div className={vencido(c.valid_to) ? 'text-[#a4262c]' : 'text-[#605e5c]'}>
                  Válido hasta: {fecha(c.valid_to)} {vencido(c.valid_to) && '(VENCIDO)'}
                </div>
                {c.fingerprint && (
                  <div className="text-[#a19f9d] text-xs mt-1 break-all">
                    Huella: {c.fingerprint}
                  </div>
                )}
              </div>
              <button
                onClick={() => eliminar(c.id)}
                className="text-[#a4262c] text-sm hover:underline whitespace-nowrap"
              >
                Eliminar
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
