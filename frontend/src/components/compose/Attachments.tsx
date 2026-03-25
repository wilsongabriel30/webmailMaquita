interface AttachmentFile {
  name: string;
  size: number;
  type: string;
}

interface Props {
  files: AttachmentFile[];
  onRemove: (idx: number) => void;
}

export function Attachments({ files, onRemove }: Props) {
  if (files.length === 0) return null;

  return (
    <div className="px-4 py-2 border-t border-[#edebe9] bg-[#faf9f8] shrink-0">
      <p className="text-[11px] text-[#605e5c] mb-1.5">{files.length} archivo{files.length > 1 ? 's' : ''} adjunto{files.length > 1 ? 's' : ''}</p>
      <div className="flex flex-wrap gap-1.5">
        {files.map((f, i) => (
          <div key={i} className="flex items-center gap-2 px-2.5 py-1.5 bg-white border border-[#edebe9] rounded group hover:border-[#c8c6c4] transition-colors max-w-[220px]">
            <div className="w-7 h-7 bg-[#e1dfdd] rounded flex items-center justify-center shrink-0">
              <FileIcon type={f.type} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[12px] text-[#323130] truncate font-medium">{f.name}</p>
              <p className="text-[10px] text-[#a19f9d]">{formatSize(f.size)}</p>
            </div>
            <button onClick={() => onRemove(i)}
              className="w-4 h-4 rounded-full flex items-center justify-center text-[#a19f9d] hover:text-[#a4262c] hover:bg-[#fde7e9] opacity-0 group-hover:opacity-100 transition-all shrink-0">
              <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>
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
