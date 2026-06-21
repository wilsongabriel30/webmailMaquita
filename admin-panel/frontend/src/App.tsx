import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthContext, AdminUser } from "./api/auth";
import { api } from "./api/client";
import { Login } from "./pages/Login";
import { AdminLayout } from "./layouts/AdminLayout";
import { Dashboard } from "./pages/Dashboard";
import { Domains } from "./pages/Domains";
import { Mailboxes } from "./pages/Mailboxes";
import { Aliases } from "./pages/Aliases";
import { Forwarding } from "./pages/Forwarding";
import { Tracking } from "./pages/Tracking";
import { Queue } from "./pages/Queue";
import { Quarantine } from "./pages/Quarantine";
import { Recovery } from "./pages/Recovery";
import { Health } from "./pages/Health";
import { Audit } from "./pages/Audit";
import { Admins } from "./pages/Admins";
import { Services } from "./pages/Services";
import { Groups } from "./pages/Groups";
import { MailViewer } from "./pages/MailViewer";
import { Signatures } from "./pages/Signatures";
import { AutoResponder } from "./pages/AutoResponder";
import { DnsCheck } from "./pages/DnsCheck";
import { AiConfig } from "./pages/AiConfig";
import { OfficeConfig } from "./pages/OfficeConfig";
import { VoiceConfig } from "./pages/VoiceConfig";
import { DlpConfig } from "./pages/DlpConfig";
import { SecureConfig } from "./pages/SecureConfig";
import { SafeLinksConfig } from "./pages/SafeLinksConfig";
import { Zap } from "./pages/Zap";
import { SafeAttachments } from "./pages/SafeAttachments";
import { PhishSim } from "./pages/PhishSim";
import { ThreatDashboard } from "./pages/ThreatDashboard";
import { Air } from "./pages/Air";
import { Sso } from "./pages/Sso";
import { Agents } from "./pages/Agents";
import { Copiloto } from "./pages/Copiloto";
import { CommCompliance } from "./pages/CommCompliance";
import { InsiderRisk } from "./pages/InsiderRisk";
import { EDiscoveryPremium } from "./pages/EDiscoveryPremium";
import { AdvancedAudit } from "./pages/AdvancedAudit";
import { RiskyLogins } from "./pages/RiskyLogins";
import { AntispamAvanzado } from "./pages/AntispamAvanzado";
import { SharedMailboxes } from "./pages/SharedMailboxes";
import { EDiscovery } from "./pages/EDiscovery";
import { Branding } from "./pages/Branding";
import { Compliance } from "./pages/Compliance";

function App() {
  const [user, setUser] = useState<AdminUser | null>(() => {
    const saved = localStorage.getItem("admin_user");
    return saved ? JSON.parse(saved) : null;
  });

  const login = async (username: string, password: string) => {
    const res = await api.post<{ token: string; user: AdminUser }>("/auth/login", { username, password });
    localStorage.setItem("admin_token", res.token);
    localStorage.setItem("admin_user", JSON.stringify(res.user));
    setUser(res.user);
  };

  const logout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    setUser(null);
  };


  // Load branding (favicon, title)
  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (!token) return;
    fetch("/api/branding", { headers: { Authorization: "Bearer " + token } })
      .then(r => r.ok ? r.json() : ({} as any))
      .then((b: any) => {
        if (b.favicon_url) {
          const link = document.querySelector("link[rel=\"icon\"]") as HTMLLinkElement;
          if (link) { link.href = b.favicon_url; link.type = ""; }
        }
        if (b.org_name) {
          document.title = b.org_name + " - Admin";
        }
      })
      .catch(() => {});
  }, [user]);

  useEffect(() => {
    if (user) {
      api.get("/auth/me").catch(() => { logout(); });
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
          <Route element={user ? <AdminLayout /> : <Navigate to="/login" />}>
            <Route index element={<Dashboard />} />
            <Route path="domains" element={<Domains />} />
            <Route path="mailboxes" element={<Mailboxes />} />
            <Route path="aliases" element={<Aliases />} />
            <Route path="forwarding" element={<Forwarding />} />
            <Route path="groups" element={<Groups />} />
            <Route path="shared" element={<SharedMailboxes />} />
            <Route path="tracking" element={<Tracking />} />
            <Route path="queue" element={<Queue />} />
            <Route path="quarantine" element={<Quarantine />} />
            <Route path="mailviewer" element={<MailViewer />} />
            <Route path="signatures" element={<Signatures />} />
            <Route path="autoresponder" element={<AutoResponder />} />
            <Route path="dnscheck" element={<DnsCheck />} />
            <Route path="recovery" element={<Recovery />} />
            <Route path="services" element={<Services />} />
            <Route path="health" element={<Health />} />
            <Route path="audit" element={<Audit />} />
            <Route path="admins" element={<Admins />} />
            <Route path="ediscovery" element={<EDiscovery />} />
            <Route path="branding" element={<Branding />} />
            <Route path="ai" element={<AiConfig />} />
            <Route path="office" element={<OfficeConfig />} />
            <Route path="voice" element={<VoiceConfig />} />
            <Route path="antispam" element={<AntispamAvanzado />} />
            <Route path="compliance" element={<Compliance />} />
            <Route path="dlp" element={<DlpConfig />} />
            <Route path="secure" element={<SecureConfig />} />
            <Route path="safelinks" element={<SafeLinksConfig />} />
            <Route path="zap" element={<Zap />} />
            <Route path="safeattach" element={<SafeAttachments />} />
            <Route path="phishsim" element={<PhishSim />} />
            <Route path="threats" element={<ThreatDashboard />} />
            <Route path="air" element={<Air />} />
            <Route path="sso" element={<Sso />} />
            <Route path="agents" element={<Agents />} />
            <Route path="copiloto" element={<Copiloto />} />
            <Route path="comm-compliance" element={<CommCompliance />} />
            <Route path="insider-risk" element={<InsiderRisk />} />
            <Route path="ediscovery-premium" element={<EDiscoveryPremium />} />
            <Route path="advanced-audit" element={<AdvancedAudit />} />
            <Route path="risky-logins" element={<RiskyLogins />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}

export default App;
