import { useState, useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';

interface ImportService {
  id: string;
  name: string;
  description: string;
  icon: string;
  available: boolean;
  setup_required?: boolean;
  note?: string;
}

interface ImportResult {
  imported: number;
  updated: number;
  skipped: number;
  errors: string[];
  total_parsed?: number;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete?: () => void;
}

const SERVICE_ICONS: Record<string, string> = {
  csv: '\uD83D\uDCC4',
  vcard: '\uD83D\uDCCB',
  google: 'G',
  microsoft: 'M',
  linkedin: 'in',
};

export function MultiImportModal({ isOpen, onClose, onImportComplete }: Props) {
  const [services, setServices] = useState<ImportService[]>([]);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      loadServices();
      setSelectedService(null);
      setResult(null);
    }
  }, [isOpen]);

  const loadServices = async () => {
    try {
      const data = await api.get<ImportService[]>('/contacts/import/services');
      setServices(data);
    } catch { /* ignore */ }
  };

  const handleFileUpload = async (file: File) => {
    if (!selectedService) return;
    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      let endpoint = '';
      if (selectedService === 'vcard') {
        endpoint = '/contacts/import/vcard';
      } else if (selectedService === 'linkedin') {
        endpoint = '/contacts/import/linkedin';
      } else if (selectedService === 'csv') {
        endpoint = '/contacts/import';
      }

      const res = await fetch(`/api${endpoint}`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });
      const data = await res.json();
      setResult(data as ImportResult);
      onImportComplete?.();
    } catch (e: any) {
      setResult({
        imported: 0, updated: 0, skipped: 0,
        errors: [e?.message || 'Error al importar'],
      });
    }
    setLoading(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
  };

  if (!isOpen) return null;

  const acceptMap: Record<string, string> = {
    csv: '.csv',
    vcard: '.vcf',
    linkedin: '.csv',
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>Importar contactos</h2>
          <button onClick={onClose} style={styles.closeBtn}>{'\u00D7'}</button>
        </div>

        <div style={styles.body}>
          {!selectedService && !result && (
            <>
              <p style={styles.subtitle}>Selecciona el origen de los contactos:</p>
              <div style={styles.serviceGrid}>
                {services.map(svc => (
                  <div
                    key={svc.id}
                    style={{
                      ...styles.serviceCard,
                      opacity: svc.available ? 1 : 0.5,
                      cursor: svc.available ? 'pointer' : 'default',
                    }}
                    onClick={() => svc.available && setSelectedService(svc.id)}
                  >
                    <div style={styles.serviceIcon}>
                      {SERVICE_ICONS[svc.icon] || svc.icon}
                    </div>
                    <div style={styles.serviceName}>{svc.name}</div>
                    <div style={styles.serviceDesc}>{svc.description}</div>
                    {!svc.available && svc.setup_required && (
                      <div style={styles.serviceNote}>Requiere configuracion</div>
                    )}
                    {svc.note && (
                      <div style={styles.serviceNote}>{svc.note}</div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {selectedService && !result && !loading && (
            <>
              <button
                onClick={() => setSelectedService(null)}
                style={styles.backBtn}
              >
                {'\u2190'} Volver
              </button>
              <div style={styles.serviceTitle}>
                {services.find(s => s.id === selectedService)?.name}
              </div>

              <div
                style={{
                  ...styles.dropZone,
                  borderColor: dragOver ? '#0078d4' : '#c8c6c4',
                  backgroundColor: dragOver ? '#f0f6ff' : '#faf9f8',
                }}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div style={styles.dropIcon}>{'\uD83D\uDCC1'}</div>
                <div style={styles.dropText}>
                  Arrastra un archivo aqui o haz clic para seleccionar
                </div>
                <div style={styles.dropHint}>
                  Formato aceptado: {acceptMap[selectedService] || '*'}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={acceptMap[selectedService]}
                  onChange={handleFileInput}
                  style={{ display: 'none' }}
                />
              </div>
            </>
          )}

          {loading && (
            <div style={styles.center}>
              <div style={styles.spinner}>Importando contactos...</div>
            </div>
          )}

          {result && (
            <div style={styles.resultPanel}>
              <div style={styles.resultTitle}>
                {result.errors.length === 0 && result.imported + result.updated > 0
                  ? 'Importacion completada'
                  : result.errors.length > 0
                  ? 'Importacion con errores'
                  : 'Sin cambios'}
              </div>

              <div style={styles.resultGrid}>
                <div style={styles.resultCard}>
                  <div style={styles.resultNumber}>{result.imported}</div>
                  <div style={styles.resultLabel}>Nuevos</div>
                </div>
                <div style={styles.resultCard}>
                  <div style={styles.resultNumber}>{result.updated}</div>
                  <div style={styles.resultLabel}>Actualizados</div>
                </div>
                <div style={styles.resultCard}>
                  <div style={styles.resultNumber}>{result.skipped}</div>
                  <div style={styles.resultLabel}>Sin cambios</div>
                </div>
              </div>

              {result.errors.length > 0 && (
                <div style={styles.errorList}>
                  <div style={styles.errorTitle}>Errores ({result.errors.length}):</div>
                  {result.errors.slice(0, 10).map((err, i) => (
                    <div key={i} style={styles.errorItem}>{err}</div>
                  ))}
                  {result.errors.length > 10 && (
                    <div style={styles.errorItem}>...y {result.errors.length - 10} mas</div>
                  )}
                </div>
              )}

              <div style={styles.resultActions}>
                <button
                  onClick={() => { setResult(null); setSelectedService(null); }}
                  style={styles.importMoreBtn}
                >
                  Importar mas
                </button>
                <button onClick={onClose} style={styles.doneBtn}>
                  Listo
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modal: {
    background: '#fff', borderRadius: 8, width: 640, maxWidth: '95vw', maxHeight: '85vh',
    display: 'flex', flexDirection: 'column',
    boxShadow: '0 25px 65px rgba(0,0,0,0.3)',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 20px', borderBottom: '1px solid #edebe9',
  },
  title: { margin: 0, fontSize: 18, fontWeight: 600, color: '#323130' },
  closeBtn: {
    border: 'none', background: 'none', fontSize: 22, cursor: 'pointer',
    color: '#605e5c', padding: '4px 8px',
  },
  body: { padding: 20, overflowY: 'auto', flex: 1 },
  subtitle: { fontSize: 14, color: '#605e5c', marginBottom: 16 },
  serviceGrid: {
    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12,
  },
  serviceCard: {
    padding: 16, border: '1px solid #edebe9', borderRadius: 8,
    textAlign: 'center', transition: 'border-color 0.2s',
  },
  serviceIcon: {
    fontSize: 28, marginBottom: 8, width: 48, height: 48, margin: '0 auto 8',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: '#f3f2f1', borderRadius: '50%', fontWeight: 700, color: '#0078d4',
  },
  serviceName: { fontSize: 14, fontWeight: 600, color: '#323130', marginBottom: 4 },
  serviceDesc: { fontSize: 12, color: '#605e5c' },
  serviceNote: {
    fontSize: 11, color: '#a19f9d', marginTop: 8, fontStyle: 'italic',
  },
  backBtn: {
    border: 'none', background: 'none', color: '#0078d4', fontSize: 13,
    cursor: 'pointer', padding: 0, marginBottom: 12,
  },
  serviceTitle: {
    fontSize: 16, fontWeight: 600, color: '#323130', marginBottom: 16,
  },
  dropZone: {
    padding: 40, border: '2px dashed #c8c6c4', borderRadius: 8,
    textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s',
  },
  dropIcon: { fontSize: 36, marginBottom: 12 },
  dropText: { fontSize: 14, color: '#323130', fontWeight: 500 },
  dropHint: { fontSize: 12, color: '#a19f9d', marginTop: 8 },
  center: { textAlign: 'center', padding: 40 },
  spinner: { fontSize: 14, color: '#0078d4', fontWeight: 500 },
  resultPanel: { textAlign: 'center' },
  resultTitle: { fontSize: 18, fontWeight: 600, color: '#323130', marginBottom: 20 },
  resultGrid: {
    display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20,
  },
  resultCard: {
    padding: 16, backgroundColor: '#f3f2f1', borderRadius: 8,
  },
  resultNumber: { fontSize: 28, fontWeight: 700, color: '#0078d4' },
  resultLabel: { fontSize: 12, color: '#605e5c', marginTop: 4 },
  errorList: {
    textAlign: 'left', padding: 12, backgroundColor: '#fef0f0', borderRadius: 4,
    marginBottom: 16,
  },
  errorTitle: { fontSize: 13, fontWeight: 600, color: '#d13438', marginBottom: 8 },
  errorItem: { fontSize: 12, color: '#d13438', marginBottom: 4 },
  resultActions: { display: 'flex', gap: 12, justifyContent: 'center' },
  importMoreBtn: {
    padding: '8px 20px', background: 'transparent', color: '#0078d4',
    border: '1px solid #0078d4', borderRadius: 4, fontSize: 13, cursor: 'pointer',
  },
  doneBtn: {
    padding: '8px 20px', background: '#0078d4', color: '#fff',
    border: 'none', borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
};
