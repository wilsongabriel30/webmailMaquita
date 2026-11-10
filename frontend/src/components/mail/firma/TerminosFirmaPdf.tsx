/**
 * Aviso de privacidad y términos de la firma electrónica (09/11/2026).
 *
 * Mismo texto que muestra Raíces (editor_firma_p12.js) la primera vez que alguien guarda un
 * certificado. Aquí se acepta sin salir del correo; la aceptación queda registrada en Raíces
 * (versión, fecha, IP) igual que si se hubiera hecho allí.
 */
import { useState } from 'react';

interface Props {
  version?: string;
  aceptando: boolean;
  error: string;
  onAceptar: () => void;
  onCancelar: () => void;
}

export function TerminosFirmaPdf({ version, aceptando, error, onAceptar, onCancelar }: Props) {
  const [marcado, setMarcado] = useState(false);
  return (
    <div className="p-4 text-[13px] text-[#323130] dark:text-[#e0e0e0] flex flex-col gap-3">
      <h3 className="text-[14px] font-semibold text-[#0b57c9]">Aviso de privacidad y términos de uso — Firma electrónica</h3>
      <p>
        Para poder firmar desde cualquier dispositivo sin volver a subir su certificado, Raíces puede
        <b> almacenar en el servidor</b> su archivo de firma (<b>.p12/.pfx</b>) y, <b>solo si usted lo elige</b>, su contraseña.
      </p>
      <ul className="list-disc pl-5 flex flex-col gap-1">
        <li>Su certificado y contraseña se guardan <b>cifrados</b> y son <b>de uso exclusivo suyo</b>: están aislados por su
          cuenta y <b>ningún otro usuario</b> puede verlos ni usar su firma.</li>
        <li>La contraseña (si decide guardarla) <b>nunca se muestra</b> ni sale del servidor; solo se usa para aplicar <b>sus</b> firmas.</li>
        <li>Usted es responsable del uso de su firma electrónica y de los documentos que firme con ella.</li>
        <li>Puede <b>eliminar</b> su certificado o <b>quitar</b> la contraseña guardada en cualquier momento (Raíces → Herramientas → Editor PDF → Firma digital).</li>
        <li>Guardar la contraseña es <b>opcional</b>: si no lo activa, se le pedirá cada vez que firme.</li>
      </ul>
      <label className="flex items-start gap-2 font-medium cursor-pointer">
        <input type="checkbox" className="mt-[3px] w-4 h-4 accent-[#0078d4]" checked={marcado} onChange={e => setMarcado(e.target.checked)} />
        <span>He leído y acepto el aviso de privacidad y los términos de uso{version ? ` (versión ${version})` : ''}.</span>
      </label>
      {error && <p role="alert" className="text-[#a4262c] bg-[#fde7e9] border border-[#f1707b] rounded px-3 py-2">{error}</p>}
      <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-1">
        <button type="button" onClick={onCancelar} disabled={aceptando}
          className="h-[40px] px-4 rounded border border-[#8a8886] bg-white dark:bg-[#1e1e1e]">Cancelar</button>
        <button type="button" onClick={onAceptar} disabled={!marcado || aceptando}
          className="h-[40px] px-5 rounded bg-[#0078d4] text-white font-medium disabled:opacity-50">
          {aceptando ? 'Guardando…' : 'Aceptar y continuar'}
        </button>
      </div>
    </div>
  );
}
