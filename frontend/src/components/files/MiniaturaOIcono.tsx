import { useState } from 'react';
import type { Item } from './tipos';
import { iconoDe } from './utilidadesArchivos';

const _EXT_PREVIEW = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'pdf',
  'docx', 'doc', 'odt', 'xlsx', 'xls', 'ods', 'csv', 'pptx', 'ppt', 'odp']);

export function MiniaturaOIcono({ item }: { item: Item }) {
  const [fallo, setFallo] = useState(false);
  const puede = !item.es_carpeta && _EXT_PREVIEW.has((item.extension || '').toLowerCase());
  if (!puede || fallo) {
    return <div className="text-4xl text-center mb-2 h-20 flex items-center justify-center">{iconoDe(item)}</div>;
  }
  return (
    <img src={`/api/almacen/preview?file=${encodeURIComponent(item.ruta)}&x=256&y=256`}
      loading="lazy" decoding="async" alt=""
      onError={() => setFallo(true)}
      className="w-full h-20 object-contain mb-2 rounded bg-[#faf9f8] dark:bg-[#1b1a19]" />
  );
}
