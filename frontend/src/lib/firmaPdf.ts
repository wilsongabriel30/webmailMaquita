/**
 * Firmar un PDF adjunto desde el correo (09/11/2026).
 *
 * Llamadas al backend (`/api/mail/firma-pdf/*`), que a su vez firma en Raíces con el
 * certificado .p12 que la persona tiene guardado allí (Herramientas → Editor PDF → Firma digital).
 * Aquí solo viven los tipos y las dos peticiones; la interfaz está en components/mail/firma/.
 */

export interface CertificadoFirma {
  id: string;
  name?: string;
  nombre?: string;
  org?: string;
  tiene_password: boolean;
}

export interface EstadoCertificados {
  exito: boolean;
  usuario: boolean;
  consentimiento: boolean;
  certificados: CertificadoFirma[];
  codigo?: string;
  mensaje?: string;
  url_raices?: string;
  version_terminos?: string;
}

/** «manual» = rectángulo dibujado por la persona sobre la página; «invisible» = firma sin sello. */
export type PosicionFirma = 'manual' | 'invisible';

/** Rectángulo del sello en puntos PDF, origen abajo-izquierda (como lo espera Raíces). */
export interface AreaFirma {
  pagina: number;
  x: number;
  y: number;
  ancho: number;
  alto: number;
}

export interface PaginaFirma {
  url: string;        // blob: de la imagen PNG (liberar con URL.revokeObjectURL)
  pagina: number;     // la dibujada (1..n)
  paginas: number;    // total
  anchoPt: number;
  altoPt: number;
}

/** De dónde sale el PDF a mostrar/firmar: el adjunto del correo o una versión ya firmada (en memoria). */
export type OrigenPdf =
  | { tipo: 'adjunto'; folder: string; uid: number; partNumber: string }
  | { tipo: 'blob'; blob: Blob };

/** Página del PDF dibujada por el servidor, para marcar encima dónde va la firma. */
export async function cargarPaginaFirma(origen: OrigenPdf, pagina: number, anchoPx: number): Promise<PaginaFirma> {
  let res: Response;
  if (origen.tipo === 'blob') {
    const fd = new FormData();
    fd.append('archivo', origen.blob, 'documento.pdf');
    fd.append('pagina', String(pagina));
    fd.append('ancho', String(Math.round(anchoPx)));
    res = await fetch('/api/mail/firma-pdf/pagina', { method: 'POST', credentials: 'include', body: fd });
  } else {
    const q = new URLSearchParams({ folder: origen.folder, uid: String(origen.uid), part_number: origen.partNumber, pagina: String(pagina), ancho: String(Math.round(anchoPx)) });
    res = await fetch(`/api/mail/firma-pdf/pagina?${q}`, { credentials: 'include' });
  }
  if (!res.ok) throw await errorDesde(res);
  const blob = await res.blob();
  return {
    url: URL.createObjectURL(blob),
    pagina: Number(res.headers.get('X-Pagina') || pagina),
    paginas: Number(res.headers.get('X-Paginas') || 1),
    anchoPt: Number(res.headers.get('X-Ancho-Pt') || 612),
    altoPt: Number(res.headers.get('X-Alto-Pt') || 792),
  };
}

export interface PeticionFirma {
  folder: string;
  uid: number;
  partNumber: string;
  filename: string;
  /** Versión ya firmada sobre la que se pone la siguiente firma (si no, se firma el adjunto del correo). */
  archivoPdf?: Blob | null;
  certificadoId?: string;
  archivoP12?: File | null;
  password?: string;
  posicion: PosicionFirma;
  /** Obligatorio con posicion «manual»: página y rectángulo dibujado. */
  area?: AreaFirma | null;
  razon?: string;
  /** Con .p12 subido: guardarlo en Raíces para la próxima vez; y, si se quiere, también su contraseña. */
  guardar?: boolean;
  guardarPassword?: boolean;
}

export interface ResultadoFirma {
  blob: Blob;
  nombre: string;
  certificadoGuardado: boolean;
  passwordGuardada: boolean;
}

export class ErrorFirmaPdf extends Error {
  codigo?: string;
  urlRaices?: string;
  versionTerminos?: string;
  status: number;
  constructor(mensaje: string, status: number, codigo?: string, urlRaices?: string, versionTerminos?: string) {
    super(mensaje);
    this.status = status;
    this.codigo = codigo;
    this.urlRaices = urlRaices;
    this.versionTerminos = versionTerminos;
  }
}

async function errorDesde(res: Response): Promise<ErrorFirmaPdf> {
  let cuerpo: { detail?: unknown; mensaje?: string; codigo?: string; url_raices?: string; version_terminos?: string } = {};
  try { cuerpo = await res.json(); } catch { /* sin cuerpo JSON */ }
  const detalle = typeof cuerpo.detail === 'string' ? cuerpo.detail : undefined;
  // 404 sin mensaje propio = el servidor aún no tiene la ruta (backend sin reiniciar tras publicar).
  const sinRuta = res.status === 404 && !cuerpo.mensaje && (!detalle || detalle === 'Not Found');
  const mensaje = sinRuta
    ? 'La firma desde el correo aún no está habilitada en este servidor. Intente más tarde.'
    : cuerpo.mensaje || detalle || `No se pudo completar (HTTP ${res.status})`;
  return new ErrorFirmaPdf(mensaje, res.status, cuerpo.codigo, cuerpo.url_raices, cuerpo.version_terminos);
}

export async function cargarCertificados(): Promise<EstadoCertificados> {
  const res = await fetch('/api/mail/firma-pdf/certificados', { credentials: 'include' });
  if (!res.ok) throw await errorDesde(res);
  return res.json();
}

export async function aceptarTerminos(version?: string): Promise<void> {
  const fd = new FormData();
  fd.append('version', version || '');
  fd.append('acepta', '1');
  const res = await fetch('/api/mail/firma-pdf/consentimiento', { method: 'POST', credentials: 'include', body: fd });
  if (!res.ok) throw await errorDesde(res);
}

export async function firmarAdjunto(p: PeticionFirma): Promise<ResultadoFirma> {
  const fd = new FormData();
  fd.append('folder', p.folder);
  fd.append('uid', String(p.uid));
  fd.append('part_number', p.partNumber);
  fd.append('filename', p.filename);
  if (p.archivoPdf) fd.append('archivo', p.archivoPdf, p.filename);
  if (p.certificadoId) fd.append('certificado_id', p.certificadoId);
  if (p.archivoP12) fd.append('certificado', p.archivoP12, p.archivoP12.name);
  fd.append('password', p.password || '');
  fd.append('posicion', p.posicion);
  if (p.posicion === 'manual' && p.area) {
    fd.append('pagina', String(p.area.pagina));
    fd.append('x', p.area.x.toFixed(2));
    fd.append('y', p.area.y.toFixed(2));
    fd.append('ancho', p.area.ancho.toFixed(2));
    fd.append('alto', p.area.alto.toFixed(2));
  } else {
    fd.append('pagina', '-1');
  }
  if (p.razon) fd.append('razon', p.razon);
  if (p.archivoP12 && p.guardar) {
    fd.append('guardar', '1');
    if (p.guardarPassword) fd.append('guardar_password', '1');
  }
  const res = await fetch('/api/mail/firma-pdf/firmar', { method: 'POST', credentials: 'include', body: fd });
  if (!res.ok) throw await errorDesde(res);
  const blob = await res.blob();
  const base = p.filename.replace(/\.pdf$/i, '') || 'documento';
  return {
    blob,
    nombre: `${base}_firmado.pdf`,
    certificadoGuardado: !!res.headers.get('X-Certificado-Guardado'),
    passwordGuardada: res.headers.get('X-Certificado-Password-Guardada') === '1',
  };
}

export function descargarBlob(blob: Blob, nombre: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = nombre;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
