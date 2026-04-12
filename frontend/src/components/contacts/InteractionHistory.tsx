import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Props {
  contactId: number;
  contactEmail: string;
}

interface Stats {
  total_sent: number;
  total_received: number;
  last_sent: string | null;
  last_received: string | null;
}

interface Interaction {
  id: number;
  direction: 'sent' | 'received';
  subject: string;
  date: string;
  folder: string;
}

const styles = {
  container: {
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    color: '#323130',
    border: '1px solid #edebe9',
    borderRadius: 4,
    marginTop: 12,
  } as React.CSSProperties,
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 14px',
    cursor: 'pointer',
    backgroundColor: '#faf9f8',
    borderBottom: '1px solid #edebe9',
    userSelect: 'none' as const,
  } as React.CSSProperties,
  headerTitle: {
    fontWeight: 600,
    fontSize: 14,
    color: '#0078d4',
  } as React.CSSProperties,
  chevron: {
    fontSize: 12,
    color: '#605e5c',
    transition: 'transform 0.2s',
  } as React.CSSProperties,
  body: {
    padding: 14,
  } as React.CSSProperties,
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 10,
    marginBottom: 18,
  } as React.CSSProperties,
  statCard: {
    textAlign: 'center' as const,
    padding: '12px 8px',
    backgroundColor: '#f3f2f1',
    borderRadius: 4,
  } as React.CSSProperties,
  statNumber: {
    fontSize: 22,
    fontWeight: 700,
    color: '#0078d4',
    lineHeight: 1.2,
  } as React.CSSProperties,
  statLabel: {
    fontSize: 11,
    color: '#605e5c',
    marginTop: 4,
  } as React.CSSProperties,
  timelineList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
  } as React.CSSProperties,
  timelineItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '8px 4px',
    borderBottom: '1px solid #edebe9',
    cursor: 'pointer',
  } as React.CSSProperties,
  dot: (sent: boolean): React.CSSProperties => ({
    width: 10,
    height: 10,
    borderRadius: '50%',
    backgroundColor: sent ? '#0078d4' : '#107c10',
    marginTop: 4,
    flexShrink: 0,
  }),
  directionIcon: {
    fontSize: 14,
    flexShrink: 0,
    width: 18,
    textAlign: 'center' as const,
    marginTop: 2,
  } as React.CSSProperties,
  itemContent: {
    flex: 1,
    minWidth: 0,
  } as React.CSSProperties,
  itemSubject: {
    fontSize: 13,
    fontWeight: 600,
    color: '#323130',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  } as React.CSSProperties,
  itemMeta: {
    fontSize: 11,
    color: '#605e5c',
    marginTop: 2,
  } as React.CSSProperties,
  verMas: {
    display: 'block',
    margin: '12px auto 0',
    padding: '6px 20px',
    border: '1px solid #0078d4',
    borderRadius: 4,
    backgroundColor: 'transparent',
    color: '#0078d4',
    fontSize: 13,
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    cursor: 'pointer',
  } as React.CSSProperties,
  loading: {
    textAlign: 'center' as const,
    padding: 20,
    color: '#605e5c',
    fontSize: 13,
  } as React.CSSProperties,
  error: {
    textAlign: 'center' as const,
    padding: 14,
    color: '#a4262c',
    fontSize: 13,
  } as React.CSSProperties,
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function InteractionHistory({ contactId, contactEmail }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [visibleCount, setVisibleCount] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      api.get<Stats>(`/contacts/${contactId}/stats`),
      api.get<{ interactions: Interaction[]; total: number }>(`/contacts/${contactId}/interactions`),
    ])
      .then(([statsData, interactionsData]) => {
        if (cancelled) return;
        setStats(statsData);
        setInteractions(interactionsData.interactions);
      })
      .catch((err) => {
        if (cancelled) return;
        setError('Error al cargar el historial de interacciones.');
        console.error(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [contactId]);

  const visibleItems = interactions.slice(0, visibleCount);
  const hasMore = interactions.length > visibleCount;

  return (
    <div style={styles.container}>
      <div style={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <span style={styles.headerTitle}>
          Historial de interacciones — {contactEmail}
        </span>
        <span
          style={{
            ...styles.chevron,
            transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
          }}
        >
          ▼
        </span>
      </div>

      {!collapsed && (
        <div style={styles.body}>
          {loading && <div style={styles.loading}>Cargando...</div>}
          {error && <div style={styles.error}>{error}</div>}

          {!loading && !error && stats && (
            <>
              <div style={styles.statsGrid}>
                <div style={styles.statCard}>
                  <div style={styles.statNumber}>{stats.total_sent}</div>
                  <div style={styles.statLabel}>Enviados</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statNumber}>{stats.total_received}</div>
                  <div style={styles.statLabel}>Recibidos</div>
                </div>
                <div style={styles.statCard}>
                  <div style={{ ...styles.statNumber, fontSize: 13, fontWeight: 600 }}>
                    {formatDate(stats.last_sent)}
                  </div>
                  <div style={styles.statLabel}>Ultimo enviado</div>
                </div>
                <div style={styles.statCard}>
                  <div style={{ ...styles.statNumber, fontSize: 13, fontWeight: 600 }}>
                    {formatDate(stats.last_received)}
                  </div>
                  <div style={styles.statLabel}>Ultimo recibido</div>
                </div>
              </div>

              {interactions.length === 0 && (
                <div style={styles.loading}>Sin interacciones registradas.</div>
              )}

              {interactions.length > 0 && (
                <>
                  <ul style={styles.timelineList}>
                    {visibleItems.map((item) => {
                      const isSent = item.direction === 'sent';
                      return (
                        <li
                          key={item.id}
                          style={styles.timelineItem}
                          onClick={() => alert(item.subject)}
                        >
                          <span style={styles.dot(isSent)} />
                          <span style={styles.directionIcon}>
                            {isSent ? '↑' : '↓'}
                          </span>
                          <div style={styles.itemContent}>
                            <div style={styles.itemSubject}>{item.subject}</div>
                            <div style={styles.itemMeta}>
                              {formatDate(item.date)} · {item.folder}
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>

                  {hasMore && (
                    <button
                      style={styles.verMas}
                      onClick={() => setVisibleCount((prev) => prev + 20)}
                    >
                      Ver mas ({interactions.length - visibleCount} restantes)
                    </button>
                  )}
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

/* fin InteractionHistory */
