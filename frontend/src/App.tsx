import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate , useLocation } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { LoginPage } from './components/auth/LoginPage';
import { AppLayout } from './components/layout/AppLayout';
import { TwoFactorGate } from './components/auth/TwoFactorGate';
import { MailView } from './components/mail/MailView';
const SettingsView = React.lazy(() => import('./components/settings/SettingsView').then(m => ({ default: m.SettingsView })));
const AdminLayout = React.lazy(() => import('./components/admin/AdminLayout').then(m => ({ default: m.AdminLayout })));
const Dashboard = React.lazy(() => import('./components/admin/Dashboard').then(m => ({ default: m.Dashboard })));
const DomainsManager = React.lazy(() => import('./components/admin/DomainsManager').then(m => ({ default: m.DomainsManager })));
const MailboxManager = React.lazy(() => import('./components/admin/MailboxManager').then(m => ({ default: m.MailboxManager })));
const AliasManager = React.lazy(() => import('./components/admin/AliasManager').then(m => ({ default: m.AliasManager })));
const GroupManager = React.lazy(() => import('./components/admin/GroupManager').then(m => ({ default: m.GroupManager })));
const QueueViewer = React.lazy(() => import('./components/admin/QueueViewer').then(m => ({ default: m.QueueViewer })));
const AuditLog = React.lazy(() => import('./components/admin/AuditLog').then(m => ({ default: m.AuditLog })));
const DisclaimerManager = React.lazy(() => import('./components/admin/DisclaimerManager').then(m => ({ default: m.DisclaimerManager })));
const MessageTracking = React.lazy(() => import('./components/admin/MessageTracking').then(m => ({ default: m.MessageTracking })));
const SpamQuarantine = React.lazy(() => import("./components/admin/SpamQuarantine").then(m => ({ default: m.SpamQuarantine })));
const CompliancePanel = React.lazy(() => import("./components/admin/CompliancePanel").then(m => ({ default: m.CompliancePanel })));
const FirewallPanel = React.lazy(() => import("./components/admin/FirewallPanel").then(m => ({ default: m.FirewallPanel })));
const MailGuardPanel = React.lazy(() => import("./components/admin/MailGuardPanel").then(m => ({ default: m.MailGuardPanel })));
const ChatSettingsPanel = React.lazy(() => import("./components/admin/ChatSettingsPanel").then(m => ({ default: m.ChatSettingsPanel })));
const DriveExternos = React.lazy(() => import("./components/admin/DriveExternos").then(m => ({ default: m.DriveExternos })));
const ContactsView = React.lazy(() => import('./components/contacts/ContactsView').then(m => ({ default: m.ContactsView })));
const RagAssistant = React.lazy(() => import('./components/rag/RagAssistant').then(m => ({ default: m.RagAssistant })));
const TasksView = React.lazy(() => import('./components/tasks/TasksView').then(m => ({ default: m.TasksView })));
const CalendarView = React.lazy(() => import('./components/calendar/CalendarView'));
const FilesView = React.lazy(() => import('./components/files/FilesView').then(m => ({ default: m.FilesView })));
import { ComposePopup } from "./components/mail/ComposePopup";
import { useMailStore } from "./store/mailStore";

function RedirigirAlmacen() {
  // El producto de archivos es el explorador clasico (template del equipo),
  // servido fuera de la SPA en /archivos-almacen.
  React.useEffect(() => { window.location.replace('/archivos-almacen'); }, []);
  return <Spinner />;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthStore();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthStore();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function Spinner() {
  return (
    <div className="h-screen flex items-center justify-center bg-[#f3f2f1]">
      <div className="animate-spin w-8 h-8 border-2 border-[#0078d4] border-t-transparent rounded-full" />
    </div>
  );
}


class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen flex items-center justify-center bg-[#f3f2f1]">
          <div className="text-center max-w-md p-8 bg-white rounded-lg shadow-lg">
            <svg className="w-12 h-12 mx-auto mb-4 text-[#d13438]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <h2 className="text-lg font-semibold text-[#323130] mb-2">Algo salió mal</h2>
            <p className="text-[13px] text-[#605e5c] mb-4">{this.state.error?.message || "Error inesperado"}</p>
            <button onClick={() => window.location.reload()}
              className="px-4 py-2 bg-[#0078d4] text-white rounded text-[13px] font-medium hover:bg-[#106ebe]">
              Recargar página
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const { setUser, user } = useAuthStore();
  const prevUserRef = React.useRef<string | null>(null);

  // BUG 6: Reset mail state when user account changes
  useEffect(() => {
    const currentEmail = user?.username || null;
    if (prevUserRef.current !== null && prevUserRef.current !== currentEmail) {
      // User changed — reset all mail state
      useMailStore.getState().reset();
      document.title = 'Maquita Mail';
    }
    prevUserRef.current = currentEmail;
  }, [user?.username]);

  // BUG 2: Re-validate session when tab becomes visible (prevents blank screen)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetch('/api/auth/me', { credentials: 'include' })
          .then((res) => {
            if (res.status === 401 || res.status === 403) { setUser(null); return; }
            if (!res.ok) return;   // T-35 (d): sin red o servidor caído no se cierra la sesión local
            return res.json();
          })
          .then((data) => {
            if (data) setUser(data.user || null);
          })
          .catch(() => { /* T-35 (d): sin red, se conserva la sesión conocida */ });
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    // Check for impersonate token from admin panel
    const params = new URLSearchParams(window.location.search);
    const impToken = params.get('impersonate');
    const impUser = params.get('user');
    if (impToken && impUser) {
      // Remove params from URL immediately
      window.history.replaceState({}, '', window.location.pathname);
      fetch('/api/auth/impersonate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: impUser, admin_token: impToken }),
        credentials: 'include',
      })
        .then((r) => {
          if (r.ok) return r.json();
          throw new Error('Impersonate failed');
        })
        .then(() => {
          // Re-fetch user session after impersonate sets cookies
          return fetch('/api/auth/me', { credentials: 'include' });
        })
        .then((r) => r.json())
        .then((data) => setUser(data.user || null))
        .catch(() => setUser(null));
      return;
    }

    // T-35 (d): sin red, o si el servidor no responde, se abre con la última sesión conocida (guardada al validar).
    const ultimaSesionConocida = () => { try { return JSON.parse(localStorage.getItem('ultima_sesion') || 'null'); } catch { return null; } };
    fetch('/api/auth/me', { credentials: 'include' })
      .then((res) => {
        if (res.status === 401 || res.status === 403) return { user: null };
        if (!res.ok) throw new Error('servidor ' + res.status);   // 5xx / 503 del service worker: no expulsar
        return res.json();
      })
      .then((data) => {
        const u = data.user || null;
        if (u) { try { localStorage.setItem('ultima_sesion', JSON.stringify(u)); } catch { /* sin almacenamiento */ } }
        setUser(u);
      })
      .catch(() => setUser(ultimaSesionConocida()));

    // Global error handler for unhandled promise rejections
    const handler = (e: PromiseRejectionEvent) => {
      console.error('[Maquita] Unhandled:', e.reason);
    };
    window.addEventListener('unhandledrejection', handler);
    return () => window.removeEventListener('unhandledrejection', handler);
  }, []);


  // Load branding (favicon, title) from admin config
  useEffect(() => {
    fetch("/api/branding")
      .then(r => r.ok ? r.json() : ({} as any))
      .then((b: any) => {
        if (b.favicon_url) {
          const link = document.querySelector("link[rel=\"icon\"]") as HTMLLinkElement;
          if (link) {
            link.href = b.favicon_url;
            link.type = "";
          }
        }
        if (b.org_name) {
          document.title = b.org_name + " Mail";
        }
      })
      .catch(() => {});
  }, []);

  return (
    <ErrorBoundary>
    <BrowserRouter basename="/webmail">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/compose" element={<ProtectedRoute><ComposePopup /></ProtectedRoute>} />
        <Route path="/drive" element={<RedirigirAlmacen />} />
        <Route path="/" element={<ProtectedRoute><TwoFactorGate /><AppLayout /></ProtectedRoute>}>
          <Route index element={<MailView />} />
          <Route path="contacts" element={<React.Suspense fallback={<Spinner />}><ContactsView /></React.Suspense>} />
          <Route path="calendar" element={<React.Suspense fallback={<Spinner />}><CalendarView /></React.Suspense>} />
          <Route path="tasks" element={<React.Suspense fallback={<Spinner />}><TasksView /></React.Suspense>} />
          <Route path="files" element={<React.Suspense fallback={<Spinner />}><FilesView /></React.Suspense>} />
          <Route path="asistente" element={<React.Suspense fallback={<Spinner />}><RagAssistant /></React.Suspense>} />
          <Route path="settings" element={<React.Suspense fallback={<Spinner />}><SettingsView /></React.Suspense>} />
          <Route path="admin" element={<AdminRoute><React.Suspense fallback={<Spinner />}><AdminLayout /></React.Suspense></AdminRoute>}>
            <Route index element={<React.Suspense fallback={<Spinner />}><Dashboard /></React.Suspense>} />
            <Route path="domains" element={<React.Suspense fallback={<Spinner />}><DomainsManager /></React.Suspense>} />
            <Route path="mailboxes" element={<React.Suspense fallback={<Spinner />}><MailboxManager /></React.Suspense>} />
            <Route path="aliases" element={<React.Suspense fallback={<Spinner />}><AliasManager /></React.Suspense>} />
            <Route path="groups" element={<React.Suspense fallback={<Spinner />}><GroupManager /></React.Suspense>} />
            <Route path="queue" element={<React.Suspense fallback={<Spinner />}><QueueViewer /></React.Suspense>} />
            <Route path="audit" element={<React.Suspense fallback={<Spinner />}><AuditLog /></React.Suspense>} />
            <Route path="disclaimer" element={<React.Suspense fallback={<Spinner />}><DisclaimerManager /></React.Suspense>} />
            <Route path="tracking" element={<React.Suspense fallback={<Spinner />}><MessageTracking /></React.Suspense>} />
            <Route path="spam" element={<React.Suspense fallback={<Spinner />}><SpamQuarantine /></React.Suspense>} />
            <Route path="compliance" element={<React.Suspense fallback={<Spinner />}><CompliancePanel /></React.Suspense>} />
            <Route path="firewall" element={<React.Suspense fallback={<Spinner />}><FirewallPanel /></React.Suspense>} />
            <Route path="bloqueos" element={<React.Suspense fallback={<Spinner />}><MailGuardPanel /></React.Suspense>} />
            <Route path="chat" element={<React.Suspense fallback={<Spinner />}><ChatSettingsPanel /></React.Suspense>} />
            <Route path="drive-externos" element={<React.Suspense fallback={<Spinner />}><DriveExternos /></React.Suspense>} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
