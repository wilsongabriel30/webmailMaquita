/**
 * Formulario «Firmar este PDF» (09/11/2026). Pensado para el celular: pocas opciones, botones
 * grandes. Carga los certificados que la persona tiene guardados en Raíces; si no tiene, deja
 * subir un .p12 del dispositivo o ir a Raíces a guardarlo.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  aceptarTerminos, cargarCertificados, ErrorFirmaPdf,
  type AreaFirma, type CertificadoFirma, type EstadoCertificados, type PosicionFirma,
} from '../../../lib/firmaPdf';
import { TerminosFirmaPdf } from './TerminosFirmaPdf';
import { SelectorAreaFirma } from './SelectorAreaFirma';

export interface OpcionesFirma {
  certificadoId?: string;
  archivoP12?: File | null;
  password: string;
  posicion: PosicionFirma;
  /** Página y rectángulo dibujado (puntos PDF); null con firma invisible. */
  area: AreaFirma | null;
  razon: string;
  guardar: boolean;
  guardarPassword: boolean;
  /** «responder»: firmar y abrir enseguida la respuesta; «otra»: firmar y quedarse para poner otra firma. */
  accion: 'responder' | 'resultado' | 'otra';
}

export interface ValoresFirmaIniciales {
  certificadoId?: string;
  archivoP12?: File | null;
  password?: string;
}

interface Props {
  nombreArchivo: string;
  folder: string;
  uid: number;
  partNumber: string;
  firmando: boolean;
  error: string;
  puedeResponder: boolean;
  /** Versión ya firmada sobre la que va la siguiente firma (null = el adjunto del correo). */
  documento?: Blob | null;
  /** Cuántas firmas lleva ya el documento (0 = ninguna). */
  firmasPuestas?: number;
  /** Página de la última firma, para arrancar allí. */
  paginaInicial?: number;
  inicial?: ValoresFirmaIniciales;
  onFirmar: (o: OpcionesFirma) => void;
  onCancelar: () => void;
}

const SUBIR = '__subir__';

export function FormularioFirmaPdf({ nombreArchivo, folder, uid, partNumber, firmando, error, puedeResponder, documento = null, firmasPuestas = 0, paginaInicial, inicial, onFirmar, onCancelar }: Props) {
  const [estado, setEstado] = useState<EstadoCertificados | null>(null);
  const [errorCarga, setErrorCarga] = useState<ErrorFirmaPdf | null>(null);
  const [certificadoId, setCertificadoId] = useState(inicial?.certificadoId || '');
  const [archivoP12, setArchivoP12] = useState<File | null>(inicial?.archivoP12 || null);
  const [password, setPassword] = useState(inicial?.password || '');
  const [verPassword, setVerPassword] = useState(false);
  // Dónde va la firma: la persona la dibuja sobre la página (o elige firma sin sello visible).
  const [area, setArea] = useState<AreaFirma | null>(null);
  const [invisible, setInvisible] = useState(false);
  // El PDF que se muestra y se firma: el adjunto del correo o la versión ya firmada (firmas sucesivas).
  const origen = useMemo(() => documento
    ? ({ tipo: 'blob', blob: documento } as const)
    : ({ tipo: 'adjunto', folder, uid, partNumber } as const), [documento, folder, uid, partNumber]);
  // Tras cada firma el documento cambia: se borra el área para dibujar la siguiente.
  useEffect(() => { setArea(null); }, [firmasPuestas]);
  const [razon, setRazon] = useState('');
  // Con .p12 subido: guardarlo en Raíces para la próxima vez y, si se quiere, también la contraseña.
  const [guardar, setGuardar] = useState(true);
  const [guardarPassword, setGuardarPassword] = useState(false);
  const [aceptando, setAceptando] = useState(false);
  const [errorTerminos, setErrorTerminos] = useState('');
  const [intento, setIntento] = useState(0);
  const inputP12 = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let vigente = true;
    setErrorCarga(null);
    cargarCertificados()
      .then(e => {
        if (!vigente) return;
        setEstado(e);
        if (inicial?.certificadoId) setCertificadoId(inicial.certificadoId);
        else if (e.certificados?.length) setCertificadoId(e.certificados[0].id);
        else setCertificadoId(SUBIR);
      })
      .catch((e: ErrorFirmaPdf) => { if (vigente) setErrorCarga(e); });
    return () => { vigente = false; };
  }, [intento]);

  const aceptar = async () => {
    setAceptando(true); setErrorTerminos('');
    try {
      await aceptarTerminos(errorCarga?.versionTerminos);
      setIntento(n => n + 1);   // vuelve a cargar: ya con consentimiento
    } catch (e) {
      setErrorTerminos(e instanceof ErrorFirmaPdf ? e.message : 'No se pudo registrar la aceptación.');
    } finally {
      setAceptando(false);
    }
  };

  const certificado: CertificadoFirma | undefined = estado?.certificados.find(c => c.id === certificadoId);
  const subiendo = certificadoId === SUBIR;
  const pidePassword = subiendo || (certificado ? !certificado.tiene_password : false);
  const faltaArea = !invisible && !area;
  const listo = !firmando && !faltaArea && (subiendo ? !!archivoP12 : !!certificado) && (!pidePassword || password.length > 0);

  const enviar = (accion: 'responder' | 'resultado' | 'otra' = puedeResponder ? 'responder' : 'resultado') => {
    if (!listo) return;
    onFirmar({
      accion,
      certificadoId: subiendo ? undefined : certificadoId,
      archivoP12: subiendo ? archivoP12 : null,
      password,
      posicion: invisible ? 'invisible' : 'manual',
      area: invisible ? null : area,
      razon: razon.trim(),
      guardar: subiendo && guardar,
      guardarPassword: subiendo && guardar && guardarPassword,
    });
  };

  // ---- estados de carga / bloqueo ----
  if (errorCarga?.codigo === 'SIN_CONSENTIMIENTO') {
    // Primera vez: se aceptan los términos aquí mismo, sin ir a Raíces.
    return (
      <TerminosFirmaPdf version={errorCarga.versionTerminos} aceptando={aceptando} error={errorTerminos}
        onAceptar={aceptar} onCancelar={onCancelar} />
    );
  }
  if (errorCarga) {
    const sinUsuario = errorCarga.codigo === 'SIN_USUARIO';
    const sinConsentimiento = false;
    return (
      <div className="p-4 text-[13px] text-[#323130] dark:text-[#e0e0e0]">
        <p className="mb-3">{errorCarga.message}</p>
        {(sinConsentimiento || (!sinUsuario && errorCarga.urlRaices)) && errorCarga.urlRaices && (
          <a href={errorCarga.urlRaices} target="_blank" rel="noopener noreferrer"
            className="inline-block mb-3 text-[#0078d4] hover:underline">
            Abrir la firma digital en Raíces
          </a>
        )}
        <div className="flex justify-end">
          <button type="button" onClick={onCancelar} className="h-[36px] px-4 rounded border border-[#8a8886] text-[13px]">Cerrar</button>
        </div>
      </div>
    );
  }
  if (!estado) {
    return (
      <div className="p-6 flex items-center justify-center gap-2 text-[13px] text-[#605e5c]">
        <div className="animate-spin w-5 h-5 border-2 border-[#0078d4] border-t-transparent rounded-full" />
        Consultando sus certificados en Raíces…
      </div>
    );
  }

  const campo = 'w-full h-[40px] px-3 rounded border border-[#8a8886] bg-white dark:bg-[#1e1e1e] dark:border-[#555] text-[14px] text-[#323130] dark:text-[#e0e0e0]';
  const etiqueta = 'block text-[12px] font-medium text-[#605e5c] dark:text-[#aaa] mb-1';

  return (
    <form className="p-4 flex flex-col gap-4 text-[13px]" onSubmit={e => { e.preventDefault(); enviar(); }}>
      {firmasPuestas > 0 ? (
        <p className="text-[#107c10] font-medium">
          El documento ya lleva {firmasPuestas} {firmasPuestas === 1 ? 'firma' : 'firmas'}. Dibuje dónde va la
          siguiente (puede ser la misma firma en otra hoja o la de otra persona).
        </p>
      ) : (
        <p className="text-[#605e5c] dark:text-[#aaa] truncate" title={nombreArchivo}>
          Se firmará <span className="text-[#323130] dark:text-[#e0e0e0] font-medium">{nombreArchivo}</span> con su
          certificado. El original del correo no cambia: obtendrá una copia firmada.
        </p>
      )}

      {/* Certificado */}
      <div>
        <label className={etiqueta} htmlFor="firma-cert">Certificado</label>
        <select id="firma-cert" className={campo} value={certificadoId}
          onChange={e => { setCertificadoId(e.target.value); setPassword(''); }}>
          {estado.certificados.map(c => (
            <option key={c.id} value={c.id}>
              {(c.nombre || c.name || c.id) + (c.org ? ` · ${c.org}` : '') + (c.tiene_password ? ' · contraseña guardada' : '')}
            </option>
          ))}
          <option value={SUBIR}>Usar un archivo .p12 de este dispositivo…</option>
        </select>
        {!estado.certificados.length && (
          <p className="mt-1 text-[12px] text-[#605e5c]">
            No tiene certificados guardados en Raíces.{' '}
            {estado.url_raices && (
              <a href={estado.url_raices} target="_blank" rel="noopener noreferrer" className="text-[#0078d4] hover:underline">
                Guardar uno en Raíces
              </a>
            )}{' '}
            o suba el .p12 aquí (solo se usa para esta firma; no se guarda).
          </p>
        )}
        {subiendo && (
          <div className="mt-2 flex items-center gap-2">
            <input ref={inputP12} type="file" accept=".p12,.pfx,application/x-pkcs12" className="hidden"
              onChange={e => setArchivoP12(e.target.files?.[0] || null)} />
            <button type="button" onClick={() => inputP12.current?.click()}
              className="h-[36px] px-3 rounded border border-[#8a8886] text-[13px] bg-white dark:bg-[#1e1e1e] dark:text-[#e0e0e0]">
              Elegir archivo .p12
            </button>
            <span className="truncate text-[12px] text-[#605e5c]">{archivoP12?.name || 'Ninguno elegido'}</span>
          </div>
        )}
        {subiendo && (
          <div className="mt-2 flex flex-col gap-1.5 text-[12px] text-[#323130] dark:text-[#e0e0e0]">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="w-4 h-4 accent-[#0078d4]" checked={guardar}
                onChange={e => { setGuardar(e.target.checked); if (!e.target.checked) setGuardarPassword(false); }} />
              Guardar este certificado en Raíces para la próxima vez (solo si la firma sale bien)
            </label>
            <label className={'flex items-center gap-2 cursor-pointer ' + (guardar ? '' : 'opacity-50')}>
              <input type="checkbox" className="w-4 h-4 accent-[#0078d4]" checked={guardarPassword} disabled={!guardar}
                onChange={e => setGuardarPassword(e.target.checked)} />
              Guardar también la contraseña (cifrada; no se la volverá a pedir)
            </label>
          </div>
        )}
      </div>

      {/* Contraseña */}
      {pidePassword && (
        <div>
          <label className={etiqueta} htmlFor="firma-pw">Contraseña del certificado</label>
          <div className="relative">
            <input id="firma-pw" type={verPassword ? 'text' : 'password'} className={campo + ' pr-16'} value={password}
              autoComplete="off" onChange={e => setPassword(e.target.value)} />
            <button type="button" onClick={() => setVerPassword(v => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[12px] text-[#0078d4]">
              {verPassword ? 'Ocultar' : 'Ver'}
            </button>
          </div>
          <p className="mt-1 text-[11px] text-[#605e5c]">Solo se usa para firmar ahora; no se guarda en el correo.</p>
        </div>
      )}

      {/* Dónde va la firma: se dibuja sobre la página (como en el editor PDF de Raíces) */}
      {!invisible && (
        <SelectorAreaFirma key={firmasPuestas} origen={origen} paginaInicial={paginaInicial} area={area} onChange={setArea} disabled={firmando} />
      )}
      <label className="flex items-center gap-2 cursor-pointer text-[12px] text-[#323130] dark:text-[#e0e0e0]">
        <input type="checkbox" className="w-4 h-4 accent-[#0078d4]" checked={invisible}
          onChange={e => { setInvisible(e.target.checked); if (e.target.checked) setArea(null); }} />
        Firmar sin sello visible (la firma queda en el PDF, pero no se dibuja nada)
      </label>

      <div>
        <label className={etiqueta} htmlFor="firma-razon">Motivo (opcional)</label>
        <input id="firma-razon" className={campo} value={razon} maxLength={120} placeholder="Documento firmado digitalmente"
          onChange={e => setRazon(e.target.value)} />
      </div>

      {error && (
        <p role="alert" className="text-[13px] text-[#a4262c] bg-[#fde7e9] border border-[#f1707b] rounded px-3 py-2">{error}</p>
      )}

      <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-1">
        <button type="button" onClick={onCancelar} disabled={firmando}
          className="h-[40px] px-4 rounded border border-[#8a8886] text-[13px] text-[#323130] dark:text-[#e0e0e0] bg-white dark:bg-[#1e1e1e]">
          Cancelar
        </button>
        <button type="button" disabled={!listo} onClick={() => enviar('otra')}
          title="Firma aquí y deja el documento listo para dibujar la siguiente firma (otra hoja u otra persona)"
          className="h-[40px] px-4 rounded border border-[#0078d4] text-[#0078d4] text-[13px] font-medium disabled:opacity-50">
          Firmar y añadir otra
        </button>
        {puedeResponder && (
          <button type="button" disabled={!listo} onClick={() => enviar('resultado')}
            title="Firma y muestra el PDF para descargarlo o reenviarlo"
            className="h-[40px] px-4 rounded border border-[#0078d4] text-[#0078d4] text-[13px] font-medium disabled:opacity-50">
            Solo firmar
          </button>
        )}
        <button type="submit" disabled={!listo}
          title={faltaArea && !firmando ? 'Dibuje en la hoja dónde irá la firma' : (puedeResponder ? 'Firma y abre la respuesta a este correo con el PDF firmado adjunto' : undefined)}
          className="h-[40px] px-5 rounded bg-[#0078d4] text-white text-[13px] font-medium disabled:opacity-50 flex items-center justify-center gap-2">
          {firmando && <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />}
          {firmando ? 'Firmando…' : (puedeResponder ? 'Firmar y responder' : 'Firmar')}
        </button>
      </div>
    </form>
  );
}
