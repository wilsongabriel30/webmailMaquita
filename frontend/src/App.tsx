import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { LoginPage } from './components/auth/LoginPage';
import { AppLayout } from './components/layout/AppLayout';
import { MailView } from './components/mail/MailView';
import { SettingsView } from './components/settings/SettingsView';
import { AdminLayout } from './components/admin/AdminLayout';
import { Dashboard } from './components/admin/Dashboard';
import { DomainsManager } from './components/admin/DomainsManager';
import { MailboxManager } from './components/admin/MailboxManager';
import { AliasManager } from './components/admin/AliasManager';
import { QueueViewer } from './components/admin/QueueViewer';
import { AuditLog } from './components/admin/AuditLog';
import { ContactsView } from './components/contacts/ContactsView';
import { TasksView } from "./components/tasks/TasksView";
import CalendarView from "./components/calendar/CalendarView";
import { ComposePopup } from "./components/mail/ComposePopup";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthStore();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
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
            <h2 className="text-lg font-semibold text-[#323130] mb-2">Algo salio mal</h2>
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
  const { setUser } = useAuthStore();

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

    fetch('/api/auth/me', { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => setUser(data.user || null))
      .catch(() => setUser(null));

    // Global error handler for unhandled promise rejections
    const handler = (e: PromiseRejectionEvent) => {
      console.error('[Maquita] Unhandled:', e.reason);
    };
    window.addEventListener('unhandledrejection', handler);
    return () => window.removeEventListener('unhandledrejection', handler);
  }, []);

  return (
    <ErrorBoundary>
    <BrowserRouter basename="/webmail">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/compose" element={<ProtectedRoute><ComposePopup /></ProtectedRoute>} />
        <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
          <Route index element={<MailView />} />
          <Route path="contacts" element={<ContactsView />} />
          <Route path="calendar" element={<CalendarView />} />
          <Route path="tasks" element={<TasksView />} />
          <Route path="settings" element={<SettingsView />} />
          <Route path="admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="domains" element={<DomainsManager />} />
            <Route path="mailboxes" element={<MailboxManager />} />
            <Route path="aliases" element={<AliasManager />} />
            <Route path="queue" element={<QueueViewer />} />
            <Route path="audit" element={<AuditLog />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
