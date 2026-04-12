import { useState } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';

interface SyncItem {
  contact_id: number;
  etag: string;
  vcard_uid: string | null;
  needs_sync: boolean;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function CardDAVSync({ isOpen, onClose }: Props) {
  const [syncState, setSyncState] = useState<SyncItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported: number; updated: number; errors: string[] } | null>(null);

  const checkSync = async () => {
    setLoading(true);
    try {
      const data = await api.get<SyncItem[]>('/contacts/carddav/sync');
      setSyncState(data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch('/api/contacts/carddav/addressbook.vcf', { credentials: 'include' });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'contacts.vcf';
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
    setExporting(false);
  };

  const handleImportVCard = async (file: File) => {
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const res = await fetch('/api/contacts/carddav/import-vcard', {
        method: 'POST',
        headers: { 'Content-Type': 'text/vcard' },
        body: text,
        credentials: 'include',
      });
      const data = await res.json();
      setImportResult(data);
    } catch (e: any) {
      setImportResult({ imported: 0, updated: 0, errors: [e?.message || 'Error'] });
    }
    setImporting(false);
  };

  if (!isOpen) return null;

  const needsSync = syncState.filter(s => s.needs_sync).length;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>Sincronizacion CardDAV</h2>
          <button onClick={onClose} style={styles.closeBtn}>{'\u00D7'}</button>
        </div>

        <div style={styles.body}>
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Exportar contactos (vCard)</h3>
            <p style={styles.desc}>
              Descarga todos tus contactos en formato vCard 3.0 para importar en otros clientes
              (iOS, Android, Thunderbird, macOS Contacts).
            </p>
            <button onClick={handleExport} disabled={exporting} style={styles.primaryBtn}>
              {exporting ? 'Exportando...' : 'Descargar addressbook.vcf'}
            </button>
          </div>

          <div style={styles.divider} />

          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Importar vCard</h3>
            <p style={styles.desc}>
              Importa contactos desde un archivo .vcf exportado de otro servicio.
            </p>
            <label style={styles.fileLabel}>
              <input
                type="file"
                accept=".vcf"
                style={{ display: 'none' }}
                onChange={e => {
                  const file = e.target.files?.[0];
                  if (file) handleImportVCard(file);
                }}
              />
              {importing ? 'Importando...' : 'Seleccionar archivo .vcf'}
            </label>

            {importResult && (
              <div style={styles.resultBox}>
                <div>{importResult.imported} importados, {importResult.updated} actualizados</div>
                {importResult.errors.length > 0 && (
                  <div style={{ color: '#d13438', marginTop: 4 }}>
                    {importResult.errors.length} errores
                  </div>
                )}
              </div>
            )}
          </div>

          <div style={styles.divider} />

          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Estado de sincronizacion</h3>
            <p style={styles.desc}>
              Verifica que contactos necesitan sincronizarse.
            </p>
            <button onClick={checkSync} disabled={loading} style={styles.secondaryBtn}>
              {loading ? 'Verificando...' : 'Verificar estado'}
            </button>

            {syncState.length > 0 && (
              <div style={styles.syncInfo}>
                <div style={styles.syncStat}>
                  <span style={styles.syncNumber}>{syncState.length}</span>
                  <span style={styles.syncLabel}>Total contactos</span>
                </div>
                <div style={styles.syncStat}>
                  <span style={{ ...styles.syncNumber, color: needsSync > 0 ? '#ca5010' : '#498205' }}>
                    {needsSync}
                  </span>
                  <span style={styles.syncLabel}>Pendientes de sync</span>
                </div>
              </div>
            )}
          </div>

          <div style={styles.divider} />

          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Configuracion CardDAV</h3>
            <p style={styles.desc}>
              Para sincronizar con clientes CardDAV externos, usa estos datos:
            </p>
            <div style={styles.configBox}>
              <div style={styles.configRow}>
                <span style={styles.configLabel}>Servidor:</span>
                <code style={styles.configValue}>{window.location.origin}/api/contacts/carddav/</code>
              </div>
              <div style={styles.configRow}>
                <span style={styles.configLabel}>Tipo:</span>
                <code style={styles.configValue}>CardDAV</code>
              </div>
              <div style={styles.configRow}>
                <span style={styles.configLabel}>Libro:</span>
                <code style={styles.configValue}>addressbook.vcf</code>
              </div>
            </div>
          </div>
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
    background: '#fff', borderRadius: 8, width: 560, maxWidth: '95vw', maxHeight: '85vh',
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
  section: { marginBottom: 8 },
  sectionTitle: { margin: '0 0 8px', fontSize: 15, fontWeight: 600, color: '#323130' },
  desc: { fontSize: 13, color: '#605e5c', marginBottom: 12 },
  divider: { height: 1, backgroundColor: '#edebe9', margin: '16px 0' },
  primaryBtn: {
    padding: '8px 20px', background: '#0078d4', color: '#fff', border: 'none',
    borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
  secondaryBtn: {
    padding: '8px 20px', background: 'transparent', color: '#0078d4',
    border: '1px solid #0078d4', borderRadius: 4, fontSize: 13, cursor: 'pointer',
  },
  fileLabel: {
    display: 'inline-block', padding: '8px 20px', background: 'transparent',
    color: '#0078d4', border: '1px solid #0078d4', borderRadius: 4,
    fontSize: 13, cursor: 'pointer',
  },
  resultBox: {
    marginTop: 12, padding: '10px 14px', backgroundColor: '#f3f2f1',
    borderRadius: 4, fontSize: 13,
  },
  syncInfo: {
    display: 'flex', gap: 24, marginTop: 12,
  },
  syncStat: { display: 'flex', flexDirection: 'column', alignItems: 'center' },
  syncNumber: { fontSize: 24, fontWeight: 700, color: '#0078d4' },
  syncLabel: { fontSize: 12, color: '#605e5c' },
  configBox: {
    padding: 14, backgroundColor: '#faf9f8', borderRadius: 4, border: '1px solid #edebe9',
  },
  configRow: {
    display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center',
    fontSize: 13,
  },
  configLabel: { color: '#605e5c', fontWeight: 600, minWidth: 70 },
  configValue: {
    color: '#323130', backgroundColor: '#e1dfdd', padding: '2px 8px',
    borderRadius: 3, fontSize: 12, fontFamily: 'monospace',
  },
};
