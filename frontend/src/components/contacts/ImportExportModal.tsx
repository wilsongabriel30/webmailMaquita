import { useState, useRef } from 'react';

interface Props {
  mode: 'import' | 'export';
  onClose: () => void;
  onImportDone: () => void;
}

export function ImportExportModal({ mode, onClose, onImportDone }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<{ imported: number; updated: number; skipped: number; errors: { row: number; error: string }[] } | null>(null);
  const [exportFormat, setExportFormat] = useState<'csv' | 'vcf'>('csv');
  const [exporting, setExporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      /* FIX: NO incluir Content-Type header manualmente para multipart/form-data.
         El api client de la app fuerza Content-Type: application/json en todas las requests,
         pero para multipart el browser DEBE auto-generar el boundary en el Content-Type.
         Si se fuerza application/json, el backend recibe un body malformado y falla con
         "No se encontró archivo" porque FastAPI no puede parsear el form data.
         Usamos fetch directo sin headers extra — el browser pone el Content-Type correcto. */
      const res = await fetch('/api/contacts/import', {
        method: 'POST',
        body: formData,
        credentials: 'include',
        // NO poner headers aquí — el browser genera el Content-Type con boundary
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Error del servidor' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
      onImportDone();
    } catch (e) {
      /* FIX: Mostrar el error real del servidor en vez de uno genérico.
         Antes siempre mostraba "Error al importar" sin importar qué falló. */
      const msg = e instanceof Error ? e.message : 'Error al importar';
      setResult({ imported: 0, updated: 0, skipped: 0, errors: [{ row: 0, error: msg }] });
    } finally {
      setImporting(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch(`/api/contacts/export?format=${exportFormat}`, {
        credentials: 'include',
        /* FIX: NO incluir Content-Type header para GET de descarga.
           Mismo problema que el import: el api client fuerza application/json
           pero el export retorna un archivo (text/csv o text/vcard).
           fetch sin headers custom respeta el Content-Type de la respuesta. */
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      /* FIX: Nombre de archivo dinámico con fecha actual, como lo genera el backend.
         Antes usaba un nombre fijo sin fecha. */
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      a.download = `contactos_maquita_${today}.${exportFormat === 'vcf' ? 'vcf' : 'csv'}`;
      a.click();
      URL.revokeObjectURL(url);
      onClose();
    } catch {
      // silently fail
    } finally {
      setExporting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9998,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 28, width: 480,
        maxHeight: '80vh', overflowY: 'auto',
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>
            {mode === 'import' ? 'Importar contactos' : 'Exportar contactos'}
          </h3>
          <button onClick={onClose} style={{
            border: 'none', background: 'none', fontSize: 20,
            cursor: 'pointer', color: '#605e5c', padding: 4,
          }}>&times;</button>
        </div>

        {mode === 'import' ? (
          <>
            {!result ? (
              <>
                <div
                  onClick={() => fileRef.current?.click()}
                  onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#0078d4'; }}
                  onDragLeave={e => { e.currentTarget.style.borderColor = '#8a8886'; }}
                  onDrop={e => {
                    e.preventDefault();
                    e.currentTarget.style.borderColor = '#8a8886';
                    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
                  }}
                  style={{
                    border: '2px dashed #8a8886', borderRadius: 8, padding: 40,
                    textAlign: 'center', cursor: 'pointer', marginBottom: 20,
                    background: '#faf9f8',
                  }}
                >
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#a19f9d" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                    <polyline points="17,8 12,3 7,8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  <p style={{ fontSize: 14, color: '#605e5c', margin: '12px 0 4px' }}>
                    {file ? file.name : 'Arrastra un archivo CSV aquí o haz clic para seleccionar'}
                  </p>
                  <p style={{ fontSize: 12, color: '#a19f9d' }}>
                    Compatible con Outlook, Gmail y archivos CSV estándar
                  </p>
                  <input ref={fileRef} type="file" accept=".csv" style={{ display: 'none' }}
                    onChange={e => { if (e.target.files?.[0]) setFile(e.target.files[0]); }} />
                </div>

                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button onClick={onClose} style={{
                    padding: '8px 20px', fontSize: 13, fontWeight: 600,
                    border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
                    color: '#323130', cursor: 'pointer',
                  }}>Cancelar</button>
                  <button
                    onClick={handleImport}
                    disabled={!file || importing}
                    style={{
                      padding: '8px 24px', fontSize: 13, fontWeight: 600,
                      border: 'none', borderRadius: 4,
                      background: !file ? '#c8c6c4' : '#0078d4',
                      color: '#fff', cursor: importing ? 'wait' : 'pointer',
                    }}
                  >{importing ? 'Importando...' : 'Importar'}</button>
                </div>
              </>
            ) : (
              <>
                <div style={{ marginBottom: 20 }}>
                  <div style={{ display: 'flex', gap: 20, marginBottom: 16 }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 28, fontWeight: 600, color: '#498205' }}>{result.imported}</div>
                      <div style={{ fontSize: 12, color: '#605e5c' }}>Importados</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 28, fontWeight: 600, color: '#0078d4' }}>{result.updated}</div>
                      <div style={{ fontSize: 12, color: '#605e5c' }}>Actualizados</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 28, fontWeight: 600, color: '#a19f9d' }}>{result.skipped}</div>
                      <div style={{ fontSize: 12, color: '#605e5c' }}>Omitidos</div>
                    </div>
                  </div>
                  {result.errors.length > 0 && (
                    <div style={{ background: '#fdf6f6', border: '1px solid #d13438', borderRadius: 4, padding: 12, maxHeight: 120, overflowY: 'auto' }}>
                      {result.errors.map((err, i) => (
                        <div key={i} style={{ fontSize: 12, color: '#d13438', marginBottom: 4 }}>
                          Fila {err.row}: {err.error}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button onClick={onClose} style={{
                    padding: '8px 24px', fontSize: 13, fontWeight: 600,
                    border: 'none', borderRadius: 4, background: '#0078d4',
                    color: '#fff', cursor: 'pointer',
                  }}>Cerrar</button>
                </div>
              </>
            )}
          </>
        ) : (
          <>
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: '#323130', display: 'block', marginBottom: 12 }}>
                Formato de exportación
              </label>
              <div style={{ display: 'flex', gap: 16 }}>
                {(['csv', 'vcf'] as const).map(fmt => (
                  <label key={fmt} style={{
                    display: 'flex', alignItems: 'center', gap: 8, fontSize: 14,
                    cursor: 'pointer', color: '#323130',
                  }}>
                    <input type="radio" checked={exportFormat === fmt}
                      onChange={() => setExportFormat(fmt)}
                      style={{ accentColor: '#0078d4' }} />
                    {fmt === 'csv' ? 'CSV (compatible con Excel)' : 'vCard (.vcf)'}
                  </label>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={onClose} style={{
                padding: '8px 20px', fontSize: 13, fontWeight: 600,
                border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
                color: '#323130', cursor: 'pointer',
              }}>Cancelar</button>
              <button
                onClick={handleExport}
                disabled={exporting}
                style={{
                  padding: '8px 24px', fontSize: 13, fontWeight: 600,
                  border: 'none', borderRadius: 4, background: '#0078d4',
                  color: '#fff', cursor: exporting ? 'wait' : 'pointer',
                }}
              >{exporting ? 'Exportando...' : 'Exportar'}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
