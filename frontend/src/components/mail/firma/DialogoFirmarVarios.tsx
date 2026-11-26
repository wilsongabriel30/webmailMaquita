/**
 * Diálogo «Firmar varios PDF» (26/11/2026).
 *
 * Pedido de Gerencia: cuando llegan varios PDF al correo (2, 4, 6, 12…), firmarlos todos sin abrir,
 * bajar y firmar uno por uno. Reutiliza la firma de un documento (lib/firmaPdf + FormularioFirmaPdf):
 *   - Si todos los PDF tienen el MISMO tamaño de página, se dibuja la firma UNA vez y se REPLICA a
 *     todos (con opción de firmar cada uno por separado).
 *   - Si son distintos, asistente «documento N de M»: se dibuja y firma cada uno.
 * El certificado y la contraseña se piden una sola vez. Al terminar, los firmados se adjuntan solos
 * a una respuesta. La firma la hace Raíces, igual que en el diálogo de un documento.
 */
import { useEffect, useState } from 'react';
import {
  firmarAdjunto, cargarPaginaFirma, ErrorFirmaPdf, type AreaFirma,
} from '../../../lib/firmaPdf';
import { FormularioFirmaPdf, type OpcionesFirma, type ValoresFirmaIniciales } from './FormularioFirmaPdf';

interface Documento { partNumber: string; filename: string; }
interface Firmado { partNumber: string; nombre: string; blob: Blob; }
interface Fallo { filename: string; motivo: string; }

interface Props {
  open: boolean;
  onClose: () => void;
  folder: string;
  uid: number;
  documentos: Documento[];
  /** Responder el correo con todos los PDF firmados adjuntos. */
  onResponderCon: (archivos: File[]) => void;
}

type Fase = 'cargando' | 'intro' | 'doc' | 'replicando' | 'listo';

export function DialogoFirmarVarios({ open, onClose, folder, uid, documentos, onResponderCon }: Props) {
  const [fase, setFase] = useState<Fase>('cargando');
  const [mismasDim, setMismasDim] = useState(false);
  const [forzarUno, setForzarUno] = useState(false);
  const [idx, setIdx] = useState(0);
  const [docBlob, setDocBlob] = useState<Blob | null>(null);   // versión firmada en curso del documento actual
  const [firmasDoc, setFirmasDoc] = useState(0);
  const [firmados, setFirmados] = useState<Firmado[]>([]);
  const [fallos, setFallos] = useState<Fallo[]>([]);
  const [cert, setCert] = useState<ValoresFirmaIniciales | undefined>(undefined);
  const [firmando, setFirmando] = useState(false);
  const [error, setError] = useState('');
  const [progreso, setProgreso] = useState(0);

  // `documentos` es un arreglo nuevo en cada render; se depende de una clave estable para no repetir.
  const docsKey = documentos.map(d => d.partNumber).join('|');

  // Al abrir: medir el tamaño de página de cada PDF para decidir si se puede replicar la firma.
  useEffect(() => {
    if (!open) return;
    let vigente = true;
    (async () => {
      setFase('cargando'); setError('');
      try {
        const dims: Array<{ a: number; h: number }> = [];
        for (const d of documentos) {
          const p = await cargarPaginaFirma({ tipo: 'adjunto', folder, uid, partNumber: d.partNumber }, 1, 200);
          try { URL.revokeObjectURL(p.url); } catch { /* nada */ }
          dims.push({ a: Math.round(p.anchoPt), h: Math.round(p.altoPt) });
        }
        if (!vigente) return;
        const iguales = dims.length > 1 && dims.every(x => x.a === dims[0].a && x.h === dims[0].h);
        setMismasDim(iguales);
        setFase('intro');
      } catch {
        if (vigente) { setMismasDim(false); setFase('intro'); }  // si no se pudo medir, se firma uno por uno
      }
    })();
    return () => { vigente = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, folder, uid, docsKey]);

  if (!open) return null;

  const total = documentos.length;
  const replicar = mismasDim && !forzarUno;

  const cerrar = () => {
    setFase('cargando'); setIdx(0); setDocBlob(null); setFirmasDoc(0);
    setFirmados([]); setFallos([]); setCert(undefined); setError(''); setProgreso(0); setForzarUno(false);
    onClose();
  };

  const avanzarODone = () => {
    const sig = idx + 1;
    if (sig >= total) { setFase('listo'); return; }
    setIdx(sig); setDocBlob(null); setFirmasDoc(0); setError('');
  };

  // Replica la MISMA posición de firma en el resto de documentos (mismo tamaño de página).
  const replicarResto = async (o: OpcionesFirma, area: AreaFirma, yaFirmado: Firmado) => {
    setFase('replicando'); setProgreso(1);
    const acumulado: Firmado[] = [yaFirmado];
    const fallidos: Fallo[] = [];
    for (let i = 1; i < total; i++) {
      try {
        const r = await firmarAdjunto({
          folder, uid, partNumber: documentos[i].partNumber, filename: documentos[i].filename,
          archivoPdf: null, certificadoId: o.certificadoId, archivoP12: o.archivoP12, password: o.password,
          posicion: 'manual', area, razon: o.razon, guardar: false, guardarPassword: false,
        });
        acumulado.push({ partNumber: documentos[i].partNumber, nombre: r.nombre, blob: r.blob });
      } catch (e) {
        fallidos.push({ filename: documentos[i].filename, motivo: e instanceof ErrorFirmaPdf ? e.message : 'No se pudo firmar' });
      }
      setProgreso(i + 1);
    }
    setFirmados(acumulado); setFallos(fallidos); setFase('listo');
  };

  const firmar = async (o: OpcionesFirma) => {
    setFirmando(true); setError('');
    try {
      const d = documentos[idx];
      const r = await firmarAdjunto({
        folder, uid, partNumber: d.partNumber, filename: d.filename, archivoPdf: docBlob,
        certificadoId: o.certificadoId, archivoP12: o.archivoP12, password: o.password,
        posicion: o.posicion, area: o.area, razon: o.razon,
        guardar: o.guardar, guardarPassword: o.guardarPassword,
      });
      setCert({ certificadoId: o.certificadoId, archivoP12: o.archivoP12, password: o.password });
      // «Firmar y añadir otra»: otra firma sobre el MISMO documento (otra hoja u otra persona).
      if (o.accion === 'otra') {
        setDocBlob(r.blob); setFirmasDoc(n => n + 1); setFirmando(false); return;
      }
      const firmadoActual: Firmado = { partNumber: d.partNumber, nombre: r.nombre, blob: r.blob };
      // Primer documento con todos del mismo tamaño y firma con sello: se replica al resto.
      if (idx === 0 && replicar && total > 1 && o.posicion === 'manual' && o.area) {
        setFirmando(false);
        await replicarResto(o, o.area, firmadoActual);
        return;
      }
      setFirmados(f => [...f, firmadoActual]);
      setFirmando(false);
      avanzarODone();
    } catch (e) {
      setError(e instanceof ErrorFirmaPdf ? e.message : 'No se pudo firmar el PDF. Intente de nuevo.');
      setFirmando(false);
    }
  };

  const responder = () => {
    const archivos = firmados.map(f => new File([f.blob], f.nombre, { type: 'application/pdf' }));
    cerrar();
    onResponderCon(archivos);
  };

  const titulo = fase === 'listo' ? 'Documentos firmados'
    : fase === 'replicando' ? 'Firmando todos…'
    : fase === 'doc' ? `Documento ${idx + 1} de ${total}${firmasDoc ? ` · firma N.º ${firmasDoc + 1}` : ''}`
    : `Firmar ${total} documentos`;

  return (
    <div className="fixed inset-0 z-[1200] flex items-end sm:items-center justify-center bg-black/50 p-0 sm:p-4"
      onClick={e => { e.stopPropagation(); if (e.target === e.currentTarget && !firmando && fase !== 'replicando') cerrar(); }}
      onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); if (!firmando && fase !== 'replicando') cerrar(); } }}>
      <div role="dialog" aria-modal="true" aria-labelledby="firma-varios-titulo"
        className="w-full sm:max-w-[640px] max-h-[95vh] overflow-auto bg-white dark:bg-[#2d2d2d] rounded-t-lg sm:rounded-lg shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#edebe9] dark:border-[#444] shrink-0">
          <h2 id="firma-varios-titulo" className="text-[15px] font-semibold text-[#323130] dark:text-[#e0e0e0] flex items-center gap-2">
            <svg className="w-5 h-5 text-[#0078d4]" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M4 21h16" />
            </svg>
            {titulo}
          </h2>
          <button type="button" onClick={cerrar} disabled={firmando || fase === 'replicando'} aria-label="Cerrar"
            className="p-1.5 rounded hover:bg-[#f3f2f1] dark:hover:bg-[#383838] text-[#605e5c] dark:text-[#aaa] disabled:opacity-40">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {fase === 'cargando' && (
          <div className="p-8 flex items-center justify-center gap-2 text-[13px] text-[#605e5c]">
            <div className="animate-spin w-5 h-5 border-2 border-[#0078d4] border-t-transparent rounded-full" />
            Preparando los documentos…
          </div>
        )}

        {fase === 'intro' && (
          <div className="p-4 flex flex-col gap-3 text-[13px] text-[#323130] dark:text-[#e0e0e0]">
            <p>Se van a firmar <b>{total}</b> documentos:</p>
            <ul className="max-h-[180px] overflow-auto border border-[#edebe9] dark:border-[#444] rounded divide-y divide-[#edebe9] dark:divide-[#444]">
              {documentos.map((d, i) => (
                <li key={d.partNumber} className="px-3 py-2 flex items-center gap-2">
                  <span className="text-[#a19f9d]">{i + 1}.</span>
                  <span className="truncate">{d.filename}</span>
                </li>
              ))}
            </ul>
            {mismasDim ? (
              <>
                <p className="text-[12px] text-[#107c10]">Todos tienen el mismo tamaño de página: dibuje la firma una vez y se pondrá en el mismo lugar en todos.</p>
                <label className="flex items-center gap-2 cursor-pointer text-[12px]">
                  <input type="checkbox" checked={forzarUno} onChange={e => setForzarUno(e.target.checked)} />
                  Prefiero firmar cada documento por separado
                </label>
              </>
            ) : (
              <p className="text-[12px] text-[#605e5c]">Los documentos tienen tamaños distintos: se firmará uno por uno.</p>
            )}
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-1">
              <button type="button" onClick={cerrar} className="h-[40px] px-4 rounded border border-[#8a8886] text-[13px]">Cancelar</button>
              <button type="button" onClick={() => { setIdx(0); setFase('doc'); }}
                className="h-[40px] px-5 rounded bg-[#0078d4] text-white text-[13px] font-medium">Empezar</button>
            </div>
          </div>
        )}

        {fase === 'doc' && (
          <FormularioFirmaPdf
            nombreArchivo={documentos[idx].filename} folder={folder} uid={uid} partNumber={documentos[idx].partNumber}
            firmando={firmando} error={error} puedeResponder={false}
            documento={docBlob} firmasPuestas={firmasDoc} inicial={cert}
            onFirmar={firmar} onCancelar={cerrar} />
        )}

        {fase === 'replicando' && (
          <div className="p-8 flex flex-col items-center justify-center gap-3 text-[13px] text-[#605e5c]">
            <div className="animate-spin w-6 h-6 border-2 border-[#0078d4] border-t-transparent rounded-full" />
            <p>Firmando documento {progreso} de {total}…</p>
          </div>
        )}

        {fase === 'listo' && (
          <div className="p-4 flex flex-col gap-3 text-[13px] text-[#323130] dark:text-[#e0e0e0]">
            <p className="text-[#107c10] font-medium">Se firmaron {firmados.length} de {total} documentos.</p>
            {fallos.length > 0 && (
              <div className="text-[12px] text-[#a4262c] bg-[#fde7e9] border border-[#f1707b] rounded px-3 py-2">
                <p className="font-medium mb-1">No se pudieron firmar {fallos.length}:</p>
                <ul className="list-disc pl-5">
                  {fallos.map((f, i) => <li key={i}>{f.filename} — {f.motivo}</li>)}
                </ul>
              </div>
            )}
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-1">
              <button type="button" onClick={cerrar} className="h-[40px] px-4 rounded border border-[#8a8886] text-[13px]">Cerrar</button>
              <button type="button" onClick={responder} disabled={!firmados.length}
                className="h-[40px] px-5 rounded bg-[#0078d4] text-white text-[13px] font-medium disabled:opacity-50">
                Responder con {firmados.length === 1 ? 'el documento firmado' : `los ${firmados.length} firmados`}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
