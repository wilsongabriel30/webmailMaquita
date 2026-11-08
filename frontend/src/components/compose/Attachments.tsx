// 07/11/2026: van arriba, debajo del asunto (como Outlook).
// 06/11/2026: cada adjunto se puede abrir ANTES de enviar (VistaPreviaAdjuntoLocal) para comprobar
// que es el archivo correcto (pedido de Finanzas: se mandó una carta equivocada).
import { useState } from 'react';
import { VistaPreviaAdjuntoLocal } from './VistaPreviaAdjuntoLocal';

interface AttachmentFile {
  name: string;
  size: number;
  type: string;
  file?: File;
}

interface Props {
  files: AttachmentFile[];
  onRemove: (idx: number) => void;
}

export function Attachments({ files, onRemove }: Props) {
  const [verIdx, setVerIdx] = useState<number | null>(null);
  if (files.length === 0) return null;
  const enVista = verIdx !== null ? files[verIdx]?.file : undefined;

  return (
    <div className="px-4 pt-2.5 pb-2 border-b border-[#edebe9] bg-white shrink-0 max-h-[30%] overflow-y-auto">
      <p className="text-[12px] text-[#605e5c] mb-1.5">{files.length} archivo{files.length > 1 ? 's' : ''} adjunto{files.length > 1 ? 's' : ''} · pulse uno para verlo antes de enviar</p>
      <div className="flex flex-wrap gap-1.5">
        {files.map((f, i) => (
          <div key={i} className="flex items-center gap-2 px-2.5 py-2 bg-white border border-[#e1dfdd] rounded-md shadow-sm group hover:border-[#c8c6c4] transition-colors w-[240px] max-w-full">
            <div className="w-7 h-7 bg-[#e1dfdd] rounded flex items-center justify-center shrink-0">
              <FileIcon type={f.type} />
            </div>
            <button type="button" onClick={() => f.file && setVerIdx(i)} disabled={!f.file}
              title={f.file ? `Ver «${f.name}» antes de enviar` : f.name}
              className="min-w-0 flex-1 text-left enabled:cursor-pointer disabled:cursor-default group/ver">
              <p className="text-[12px] text-[#323130] truncate font-medium group-enabled/ver:group-hover/ver:underline">{f.name}</p>
              <p className="text-[12px] text-[#605e5c]">{formatSize(f.size)}{f.file && <span className="text-[#0078d4]"> · Ver</span>}</p>
            </button>
            <button onClick={() => onRemove(i)} aria-label={`Quitar el adjunto ${f.name}`} title={`Quitar el adjunto ${f.name}`}
              className="w-6 h-6 rounded-full flex items-center justify-center text-[#605e5c] hover:text-[#a4262c] hover:bg-[#fde7e9] transition-all shrink-0">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>
      {enVista && <VistaPreviaAdjuntoLocal archivo={enVista} onClose={() => setVerIdx(null)} />}
    </div>
  );
}

function FileIcon({ type }: { type: string }) {
  const color = type.startsWith('image/') ? '#0078d4' :
    type.includes('pdf') ? '#d13438' :
    type.includes('word') || type.includes('document') ? '#2b579a' :
    type.includes('excel') || type.includes('sheet') ? '#217346' :
    type.includes('powerpoint') || type.includes('presentation') ? '#b7472a' : '#605e5c';

  return (
    <svg className="w-4 h-4" fill="none" stroke={color} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}
