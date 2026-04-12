import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';

interface Suggestion {
  id: number;
  field_name: string;
  field_value: string;
  confidence: number;
  status: string;
  created_at: string;
}

interface Props {
  contactId: number;
}

const FIELD_LABELS: Record<string, string> = {
  phone: 'Telefono',
  phone_mobile: 'Celular',
  website: 'Sitio web',
  job_title: 'Cargo',
  company: 'Empresa',
  address: 'Direccion',
};

export function SignatureEnrichment({ contactId }: Props) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    loadSuggestions();
  }, [contactId]);

  const loadSuggestions = async () => {
    try {
      const data = await api.get<Suggestion[]>(`/contacts/${contactId}/signature-suggestions`);
      setSuggestions(data);
    } catch { /* ignore */ }
  };

  const handleApply = async (sugId: number) => {
    try {
      await api.post(`/contacts/${contactId}/signature-suggestions/${sugId}/apply`);
      setSuggestions(prev => prev.filter(s => s.id !== sugId));
    } catch { /* ignore */ }
  };

  const handleDismiss = async (sugId: number) => {
    try {
      await api.post(`/contacts/${contactId}/signature-suggestions/${sugId}/dismiss`);
      setSuggestions(prev => prev.filter(s => s.id !== sugId));
    } catch { /* ignore */ }
  };

  if (suggestions.length === 0) return null;

  return (
    <div style={styles.container}>
      <div style={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <span style={styles.headerTitle}>
          Datos detectados en firma ({suggestions.length})
        </span>
        <span style={{ ...styles.chevron, transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
          {'\u25BC'}
        </span>
      </div>

      {!collapsed && (
        <div style={styles.body}>
          <div style={styles.hint}>
            Estos datos fueron detectados en las firmas de correos recibidos. Confirma los que deseas agregar.
          </div>
          {suggestions.map(s => (
            <div key={s.id} style={styles.item}>
              <div style={{ flex: 1 }}>
                <div style={styles.fieldLabel}>
                  {FIELD_LABELS[s.field_name] || s.field_name}
                </div>
                <div style={styles.fieldValue}>{s.field_value}</div>
                <div style={styles.confidence}>
                  Confianza: {Math.round(s.confidence * 100)}%
                </div>
              </div>
              <div style={styles.actions}>
                <button
                  onClick={() => handleApply(s.id)}
                  style={styles.applyBtn}
                  title="Aplicar"
                >
                  {'\u2713'}
                </button>
                <button
                  onClick={() => handleDismiss(s.id)}
                  style={styles.dismissBtn}
                  title="Descartar"
                >
                  {'\u00D7'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  container: {
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    color: '#323130', border: '1px solid #edebe9', borderRadius: 4, marginTop: 12,
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 14px', cursor: 'pointer', backgroundColor: '#fff3cd',
    borderBottom: '1px solid #edebe9', userSelect: 'none',
  },
  headerTitle: { fontWeight: 600, fontSize: 14, color: '#856404' },
  chevron: { fontSize: 12, color: '#856404', transition: 'transform 0.2s' },
  body: { padding: 14 },
  hint: {
    fontSize: 12, color: '#605e5c', marginBottom: 12, lineHeight: 1.4,
    padding: '8px 10px', backgroundColor: '#faf9f8', borderRadius: 4,
  },
  item: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
    borderRadius: 4, marginBottom: 6, border: '1px solid #edebe9',
    backgroundColor: '#fff',
  },
  fieldLabel: {
    fontSize: 11, color: '#0078d4', fontWeight: 600, textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  fieldValue: { fontSize: 14, color: '#323130', fontWeight: 500, marginTop: 2 },
  confidence: { fontSize: 11, color: '#a19f9d', marginTop: 2 },
  actions: { display: 'flex', gap: 4 },
  applyBtn: {
    border: '1px solid #498205', background: '#fff', color: '#498205',
    fontSize: 14, cursor: 'pointer', padding: '4px 10px', borderRadius: 4,
    fontWeight: 700,
  },
  dismissBtn: {
    border: '1px solid #c8c6c4', background: '#fff', color: '#a19f9d',
    fontSize: 16, cursor: 'pointer', padding: '4px 10px', borderRadius: 4,
  },
};
