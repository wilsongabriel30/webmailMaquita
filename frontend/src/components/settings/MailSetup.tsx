import { useState, useEffect } from 'react';
import { api } from '../../api/client';

interface ServerCfg { host: string; port: number; security: string; }
interface Setup {
  email: string;
  username: string;
  host: string;
  imap: ServerCfg;
  smtp: ServerCfg;
  auth: string;
  note: string;
}

function Copy({ value }: { value: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      onClick={async () => { try { await navigator.clipboard.writeText(value); setOk(true); setTimeout(() => setOk(false), 1500); } catch { /* noop */ } }}
      className="ml-2 text-xs text-[#0078d4] hover:underline"
      title="Copiar"
    >{ok ? 'copiado ✓' : 'copiar'}</button>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
      <span className="text-sm text-[#605e5c]">{label}</span>
      <span className="text-sm font-mono text-[#323130] text-right">{value}<Copy value={value} /></span>
    </div>
  );
}

export function MailSetup() {
  const [s, setS] = useState<Setup | null>(null);
  const [err, setErr] = useState('');
  const [showAndroid, setShowAndroid] = useState(false);

  useEffect(() => {
    api.get<Setup>('/onboarding/settings').then(setS).catch((e: any) => setErr(e.message));
  }, []);

  if (err) return <div className="text-red-700 text-sm">{err}</div>;
  if (!s) return <div className="text-sm text-gray-500">Cargando…</div>;

  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h3 className="text-lg font-semibold">Configurar mi correo en el celular / Outlook</h3>
        <p className="text-sm text-[#605e5c] mt-1">
          Usá estos datos exactos. <strong>Tu usuario es siempre tu correo completo con @</strong>
          {' '}(no escribas <code>mail.</code> ni solo tu nombre).
        </p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
        Usuario: <strong>{s.username}</strong><Copy value={s.username} />
      </div>

      {/* iPhone */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="font-medium mb-2">📱 iPhone / iPad — automático</h4>
        <p className="text-sm text-[#605e5c] mb-3">
          Descargá el perfil y seguí: Ajustes → “Perfil descargado” → Instalar. Solo te pedirá tu contraseña.
        </p>
        <a
          href="/api/onboarding/apple-profile"
          className="inline-block bg-[#0078d4] text-white px-4 py-2 rounded hover:bg-[#106ebe] text-sm"
        >Descargar perfil para iPhone</a>
        <p className="text-xs text-gray-400 mt-2">Abrilo en Safari. iOS dirá “perfil sin firmar”: es normal, es de tu propia organización.</p>
      </div>

      {/* Manual */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="font-medium mb-2">⚙️ Manual (Outlook, Thunderbird, Android)</h4>
        <div className="mt-2">
          <div className="text-xs uppercase text-gray-400 mb-1">Entrante (IMAP)</div>
          <Row label="Servidor" value={s.imap.host} />
          <Row label="Puerto" value={String(s.imap.port)} />
          <Row label="Seguridad" value={s.imap.security} />
          <Row label="Usuario" value={s.username} />
        </div>
        <div className="mt-3">
          <div className="text-xs uppercase text-gray-400 mb-1">Saliente (SMTP)</div>
          <Row label="Servidor" value={s.smtp.host} />
          <Row label="Puerto" value={String(s.smtp.port)} />
          <Row label="Seguridad" value={s.smtp.security} />
          <Row label="Usuario" value={s.username} />
        </div>
        <p className="text-xs text-gray-400 mt-2">Autenticación: {s.auth}. La contraseña es la misma del webmail.</p>
      </div>

      {/* Android pasos */}
      <div className="bg-white border rounded-lg p-4">
        <button onClick={() => setShowAndroid(v => !v)} className="font-medium text-left w-full">
          🤖 Android — paso a paso {showAndroid ? '▲' : '▼'}
        </button>
        {showAndroid && (
          <ol className="list-decimal list-inside text-sm text-[#323130] mt-3 space-y-1">
            <li>Ajustes → Cuentas → Añadir cuenta → <strong>Personal (IMAP)</strong>.</li>
            <li>Escribí tu correo completo: <strong>{s.username}</strong>, y tu contraseña.</li>
            <li>Si pregunta el tipo, elegí <strong>IMAP</strong>.</li>
            <li>Entrante: servidor <strong>{s.imap.host}</strong>, puerto <strong>{s.imap.port}</strong>, <strong>SSL/TLS</strong>. Usuario = tu correo completo.</li>
            <li>Saliente: servidor <strong>{s.smtp.host}</strong>, puerto <strong>{s.smtp.port}</strong>, <strong>SSL/TLS</strong>, requiere inicio de sesión. Usuario = tu correo completo.</li>
          </ol>
        )}
      </div>
    </div>
  );
}
