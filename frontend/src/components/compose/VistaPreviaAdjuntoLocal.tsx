// Vista previa de un adjunto ANTES de enviarlo (06/11/2026).
//
// Pedido de Finanzas: «mandamos una carta equivocada y a la persona le llegaron errores».
// Al redactar, cada adjunto se puede abrir para comprobar que es el correcto:
//   - imágenes, PDF, texto y código: se ven aquí mismo (el archivo no sale del equipo);
//   - Word, Excel y PowerPoint: OnlyOffice en modo lectura (backend/app/mail/routers/vista_previa_local.py);
//   - lo demás: se avisa que no tiene vista previa.
// El código (html, js, py, sql…) se muestra como texto, nunca se ejecuta.
import { useEffect, useRef, useState } from 'react';

type Tipo = 'imagen' | 'pdf' | 'texto' | 'office' | 'nada';

const TEXTO = new Set([
  'txt', 'md', 'markdown', 'log', 'csv', 'tsv', 'json', 'xml', 'yml', 'yaml', 'ini', 'conf', 'cfg', 'env',
  'sql', 'html', 'htm', 'css', 'js', 'jsx', 'ts', 'tsx', 'py', 'php', 'java', 'c', 'h', 'cpp', 'cs', 'go',
  'rb', 'sh', 'bat', 'ps1', 'vb', 'vbs', 'r', 'kt', 'swift', 'rs', 'pl', 'lua', 'dart', 'scss', 'svg',
]);
const OFFICE = new Set(['docx', 'doc', 'odt', 'rtf', 'xlsx', 'xls', 'ods', 'pptx', 'ppt', 'odp']);
const MAX_TEXTO = 2 * 1024 * 1024;

function tipoVistaPrevia(nombre: string, mime: string): Tipo {
  const ext = (nombre.split('.').pop() || '').toLowerCase();
  if (OFFICE.has(ext)) return 'office';
  if (ext === 'pdf' || mime === 'application/pdf') return 'pdf';
  if (TEXTO.has(ext)) return 'texto';
  if (mime.startsWith('image/')) return 'imagen';
  if (mime.startsWith('text/')) return 'texto';
  return 'nada';
}

interface Props {
  archivo: File;
  onClose: () => void;
}

export function VistaPreviaAdjuntoLocal({ archivo, onClose }: Props) {
  const tipo = tipoVistaPrevia(archivo.name, archivo.type || '');
  const [url, setUrl] = useState('');
  const [texto, setTexto] = useState('');
  const [estado, setEstado] = useState<'cargando' | 'listo' | 'error'>(tipo === 'nada' ? 'listo' : 'cargando');
  const marcoOffice = useRef<HTMLDivElement>(null);
  const caja = useRef<HTMLDivElement>(null);

  // Imagen y PDF: dirección blob: local, se libera al cerrar.
  useEffect(() => {
    if (tipo !== 'imagen' && tipo !== 'pdf') return;
    const u = URL.createObjectURL(archivo);
    let vivo = true;
    // La dirección blob: es un recurso externo: se crea aquí y se publica al estado en la siguiente microtarea.
    queueMicrotask(() => { if (vivo) { setUrl(u); setEstado('listo'); } });
    return () => { vivo = false; URL.revokeObjectURL(u); };
  }, [archivo, tipo]);

  // Texto y código: se leen los primeros 2 MB.
  useEffect(() => {
    if (tipo !== 'texto') return;
    let vivo = true;
    archivo.slice(0, MAX_TEXTO).text()
      .then((t) => {
        if (!vivo) return;
        setTexto(archivo.size > MAX_TEXTO ? t + '\n\n[… archivo recortado: se muestran los primeros 2 MB]' : t);
        setEstado('listo');
      })
      .catch(() => vivo && setEstado('error'));
    return () => { vivo = false; };
  }, [archivo, tipo]);

  // Office: se sube a una vista previa temporal (15 min) y se abre OnlyOffice en modo lectura.
  useEffect(() => {
    if (tipo !== 'office') return;
    let vivo = true;
    const datos = new FormData();
    datos.append('archivo', archivo, archivo.name);
    fetch('/api/mail/vista-previa-local', { method: 'POST', credentials: 'include', body: datos })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((config) => {
        if (!vivo) return;
        const abrir = () => {
          setEstado('listo');
          setTimeout(() => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any -- DocsAPI lo inyecta el script de OnlyOffice
            const api = (window as any).DocsAPI;
            if (!vivo || !marcoOffice.current || !api) { if (vivo) setEstado('error'); return; }
            marcoOffice.current.innerHTML = '<div id="vpl-oo"></div>';
            config.type = 'embedded';
            config.width = '100%';
            config.height = '100%';
            new api.DocEditor('vpl-oo', config);
          }, 50);
        };
        const id = 'onlyoffice-api-script';
        let s = document.getElementById(id) as HTMLScriptElement | null;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any -- DocsAPI lo inyecta el script de OnlyOffice
        if (s && (window as any).DocsAPI) { abrir(); return; }
        if (!s) {
          s = document.createElement('script');
          s.id = id;
          s.src = '/onlyoffice/web-apps/apps/api/documents/api.js';
          document.head.appendChild(s);
        }
        s.addEventListener('load', abrir, { once: true });
        s.addEventListener('error', () => vivo && setEstado('error'), { once: true });
      })
      .catch(() => vivo && setEstado('error'));
    return () => { vivo = false; };
  }, [archivo, tipo]);

  // Escape cierra solo la vista previa, no la redacción.
  useEffect(() => {
    caja.current?.focus();
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose(); }
    };
    window.addEventListener('keydown', tecla, true);
    return () => window.removeEventListener('keydown', tecla, true);
  }, [onClose]);

  const tamano = archivo.size < 1048576 ? `${Math.max(1, Math.round(archivo.size / 1024))} KB` : `${(archivo.size / 1048576).toFixed(1)} MB`;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        ref={caja}
        tabIndex={-1}
        role="dialog"
        aria-label={`Vista previa de ${archivo.name}`}
        className={`bg-white dark:bg-[#2d2d2d] rounded-lg shadow-2xl flex flex-col overflow-hidden outline-none ${tipo === 'office' ? 'w-[96vw] max-w-[1400px] h-[92vh]' : 'w-[92vw] max-w-[900px] max-h-[90vh]'}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#edebe9] dark:border-[#444] gap-3">
          <div className="min-w-0">
            <p className="text-[14px] font-medium text-[#323130] dark:text-[#e0e0e0] truncate">{archivo.name}</p>
            <p className="text-[12px] text-[#605e5c] dark:text-[#999]">Vista previa antes de enviar · {tamano}</p>
          </div>
          <button onClick={onClose} aria-label="Cerrar la vista previa" title="Cerrar (Esc)"
            className="p-1.5 hover:bg-[#f3f2f1] dark:hover:bg-[#383838] rounded text-[#605e5c] dark:text-[#aaa] shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-auto flex items-center justify-center p-3 bg-[#faf9f8] dark:bg-[#1e1e1e] min-h-[300px]">
          {estado === 'cargando' && (
            <div className="flex flex-col items-center gap-3">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0078d4] border-t-transparent" />
              <p className="text-[13px] text-[#605e5c]">Abriendo el documento…</p>
            </div>
          )}
          {estado === 'error' && (
            <p className="text-[14px] text-[#a4262c] text-center px-6">No se pudo abrir la vista previa de este archivo. Puede enviarlo igual o quitarlo y adjuntarlo de nuevo.</p>
          )}
          {estado === 'listo' && tipo === 'imagen' && url && (
            <img src={url} alt={archivo.name} className="max-w-full max-h-[75vh] object-contain" />
          )}
          {estado === 'listo' && tipo === 'pdf' && url && (
            <iframe src={url} title={archivo.name} className="w-full h-[75vh] border-0 bg-white" />
          )}
          {estado === 'listo' && tipo === 'texto' && (
            <pre className="w-full h-[75vh] overflow-auto p-4 text-[13px] font-mono text-[#323130] dark:text-[#e0e0e0] whitespace-pre-wrap break-words">{texto}</pre>
          )}
          {tipo === 'office' && estado !== 'error' && (
            <div ref={marcoOffice} className={estado === 'listo' ? 'w-full h-full self-stretch' : 'hidden'} style={{ minHeight: 520 }} />
          )}
          {tipo === 'nada' && (
            <div className="flex flex-col items-center gap-2 text-center px-6">
              <p className="text-[14px] text-[#605e5c]">Este tipo de archivo no tiene vista previa.</p>
              <p className="text-[12px] text-[#a19f9d]">{archivo.type || 'tipo desconocido'} · {tamano}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
