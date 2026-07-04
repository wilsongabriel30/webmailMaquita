import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../api/auth";
import { MyAccountModal } from "../components/MyAccountModal";

const navSections = [
  {
    title: "General",
    items: [
      { to: "/", label: "Dashboard", help: "Resumen general del servidor de correo: buzones, dominios, volumen de correo, almacenamiento y estado de los servicios.", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6", end: true },
    ],
  },
  {
    title: "Flujo de correo",
    items: [
      { to: "/tracking", label: "Rastreo de mensajes", help: "Busca y rastrea mensajes en los registros del servidor: quién envió, a quién, cuándo y si fue entregado, rebotado o rechazado.", icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" },
      { to: "/queue", label: "Colas de correo", help: "Correos pendientes de entrega en la cola del servidor; permite reintentar o eliminar mensajes atascados.", icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" },
      { to: "/quarantine", label: "Cuarentena", help: "Correos retenidos como spam por usuario: revisarlos, aprobarlos (entregar al buzón) o confirmarlos como spam.", icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" },
    ],
  },
  {
    title: "Destinatarios",
    items: [
      { to: "/mailboxes", label: "Buzones", help: "Crear y editar buzones (cuota, nombre), cambiar contraseñas, bloquear, eliminar, abrir el buzón como administrador y cambiar de titular.", icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
      { to: "/domains", label: "Dominios", help: "Dominios de correo del servidor: agregar o eliminar los dominios que reciben y envían correo.", icon: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" },
      { to: "/aliases", label: "Alias", help: "Direcciones alternativas que entregan en un buzón existente (p. ej. info@ entrega en el buzón de una persona).", icon: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" },
      { to: "/forwarding", label: "Reenvíos", help: "Reenvíos automáticos de un buzón hacia otras direcciones internas o externas.", icon: "M17 8l4 4m0 0l-4 4m4-4H3" },
      { to: "/groups", label: "Grupos de distribución", help: "Grupos de distribución: una dirección que reparte el correo a varios miembros a la vez.", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" },
      { to: "/signatures", label: "Firmas de correo", help: "Plantillas de firma corporativa que se aplican a los buzones de los usuarios.", icon: "M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" },
      { to: "/ai", label: "Configurar IA", help: "Configura el proveedor de IA (modelo y endpoint) usado por el asistente, resúmenes y respuestas inteligentes del webmail.", icon: "M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" },
      { to: "/office", label: "OnlyOffice / Nube", help: "Integración con Nextcloud y OnlyOffice: nube de archivos y edición de documentos desde el webmail.", icon: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z M13 3v5h5 M9 13h6 M9 17h6" },
      { to: "/voice", label: "Dictado por voz", help: "Dictado por voz: activa y configura la transcripción de audio a texto en el webmail.", icon: "M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z M19 10v2a7 7 0 01-14 0v-2 M12 19v4 M8 23h8" },
      { to: "/shared", label: "Buzones compartidos", help: "Buzones compartidos entre varios usuarios (p. ej. ventas@) con permisos por miembro.", icon: "M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" },
    ],
  },
  {
    title: "Herramientas",
    items: [
      { to: "/mailviewer", label: "Visor de buzones", help: "Ver el contenido de cualquier buzón (carpetas y mensajes) con fines de soporte; todo acceso queda auditado.", icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
      { to: "/autoresponder", label: "Respuestas automáticas", help: "Gestiona las respuestas automáticas (vacaciones / fuera de oficina) de cualquier usuario.", icon: "M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" },
      { to: "/dnscheck", label: "Verificación DNS", help: "Verifica los registros DNS del dominio: MX, SPF, DKIM, DMARC y PTR — esenciales para que el correo no caiga en spam.", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" },
      { to: "/ediscovery", label: "eDiscovery Forense", help: "Búsqueda forense en todos los buzones y exportación de evidencia.", icon: "M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z" },
    ],
  },
  {
    title: "Protección",
    items: [
      { to: "/risky-logins", label: "Inicios de sesión riesgosos", help: "Inicios de sesión sospechosos: IP inusual, países nuevos u horarios atípicos.", icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" },
      { to: "/threats", label: "Panel de amenazas", help: "Resumen de amenazas detectadas: spam, phishing, malware y adjuntos peligrosos.", icon: "M12 2l7 4v6c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6l7-4z M12 8v4 M12 16h.01" },
      { to: "/air", label: "AIR — investigación y respuesta", help: "Investigación y respuesta automatizada de incidentes de correo (AIR).", icon: "M9 12l2 2 4-4 M12 3a9 9 0 100 18 9 9 0 000-18z" },
      { to: "/sso", label: "SSO / Identidad", help: "Inicio de sesión único (SSO) con Keycloak/OIDC para el webmail.", icon: "M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" },
      { to: "/agents", label: "Agentes IA", help: "Agentes de IA que procesan y clasifican correo automáticamente.", icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
      { to: "/copiloto", label: "Copiloto Maquita", help: "Asistente conversacional del panel para consultas de administración.", icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4-.8L3 21l1.8-4A8 8 0 1121 12z" },
      { to: "/rag", label: "RAG — tu correo", help: "Búsqueda semántica (RAG) sobre el correo indexado de la organización.", icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" },
      { to: "/conditional-access", label: "Acceso Condicional", help: "Políticas de acceso condicional: restringe el acceso por red, dispositivo u horario.", icon: "M12 11c0-1.105.895-2 2-2s2 .895 2 2v3H8v-3c0-1.105.895-2 2-2 M12 15v2 M5 9V7a7 7 0 0114 0v2 M5 9h14v11a1 1 0 01-1 1H6a1 1 0 01-1-1V9z" },
      { to: "/recovery", label: "Recuperación", help: "Recupera correos eliminados de la papelera de cualquier usuario.", icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" },
      { to: "/services", label: "Servicios", help: "Estado y control de los servicios del servidor de correo (SMTP, IMAP, antispam…): ver estado y reiniciar.", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z" },
      { to: "/health", label: "Estado del sistema", help: "Métricas del servidor: CPU, memoria, disco, conexiones, fail2ban y salud general.", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
      { to: "/antispam", label: "Filtro Avanzado", help: "Filtro antispam avanzado: reglas, umbrales, listas blancas y negras, greylisting.", icon: "M12 2l7 4v6c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6l7-4z" },
      { to: "/dlp", label: "Protección de datos (DLP)", help: "Prevención de fuga de datos (DLP): detecta y bloquea el envío de información sensible.", icon: "M12 2l7 4v6c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6l7-4z M9 12l2 2 4-4" },
      { to: "/secure", label: "Correo cifrado", help: "Correo cifrado: mensajes protegidos que el destinatario abre mediante un enlace seguro con clave.", icon: "M12 11c0-1.1.9-2 2-2s2 .9 2 2 M5 11h14v10H5z M8 11V7a4 4 0 018 0v4" },
      { to: "/safelinks", label: "Protección de enlaces", help: "Protección de enlaces: analiza los enlaces de los correos entrantes al momento del clic.", icon: "M13.828 10.172a4 4 0 010 5.656l-3 3a4 4 0 01-5.656-5.656l1.5-1.5 M10.172 13.828a4 4 0 010-5.656l3-3a4 4 0 015.656 5.656l-1.5 1.5" },
      { to: "/zap", label: "Retiro de correos maliciosos (ZAP)", help: "Retiro automático de correos maliciosos ya entregados a los buzones (ZAP).", icon: "M3 7l9 6 9-6 M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z M9 11l3 3 3-3" },
      { to: "/safeattach", label: "Análisis de adjuntos", help: "Análisis de adjuntos sospechosos antes de entregarlos al buzón.", icon: "M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" },
      { to: "/anti-suplantacion", label: "Anti-suplantación y políticas", help: "Políticas anti-suplantación de dominios y de personas (spoofing e impersonación).", icon: "M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0M12 14a2 2 0 100-4 2 2 0 000 4zm0 0c1.3 0 2.4.8 2.8 2M9 16a3 3 0 012.8-2" },
      { to: "/phishsim", label: "Simulación de phishing", help: "Campañas simuladas de phishing para entrenar y medir a los usuarios.", icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
      { to: "__rspamd__", label: "Rspamd Antispam", help: "Abre la consola nativa del antispam Rspamd en una pestaña nueva.", icon: "M20.618 5.984A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z", external: "/rspamd/" },
    ],
  },
  {
    title: "Administración",
    items: [
      { to: "/audit", label: "Auditoría", help: "Registro de todas las acciones de los administradores del panel: quién hizo qué y cuándo.", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" },
      { to: "/admins", label: "Administradores", help: "Cuentas de administradores del panel: crear, editar rol y estado, cambiar contraseñas.", icon: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" },
      { to: "/branding", label: "Personalización", help: "Personaliza logo, colores y nombre de la organización en el webmail y el panel.", icon: "M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" },
    ],
  },
  {
    title: "Compliance",
    items: [
      { to: "/advanced-audit", label: "Auditoría avanzada", help: "Búsqueda avanzada en la auditoría con filtros, facetas y exportación.", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
      { to: "/ediscovery-premium", label: "Custodios y retención legal", help: "Casos legales con custodios y retención legal (legal hold) de buzones.", icon: "M3 6l9-4 9 4v6c0 5-3.8 8.6-9 10-5.2-1.4-9-5-9-10V6z M9 11l2 2 4-4" },
      { to: "/insider-risk", label: "Riesgo interno", help: "Detección de riesgo interno: usuarios con comportamiento anómalo (reenvíos masivos, borrados, etc.).", icon: "M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" },
      { to: "/comm-compliance", label: "Cumplimiento de comunicaciones", help: "Supervisión de comunicaciones: políticas que detectan contenido que incumple normas internas.", icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.7 9.7 0 01-4-.85L3 20l1.4-3.5A7.9 7.9 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" },
      { to: "/retention", label: "Retención", help: "Políticas de retención: cuánto tiempo se conservan los correos antes de archivarse o eliminarse.", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
      { to: "/compliance", label: "Centro de Compliance", help: "Centro de cumplimiento: vista integral de políticas, retención, auditoría y eDiscovery.", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" },
    ],
  },
];

export function AdminLayout() {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [showAccount, setShowAccount] = useState(false);

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar - Exchange style */}
      <header className="h-12 bg-ms-blue flex items-center px-4 shrink-0 z-20">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded hover:bg-white/15 text-white mr-3"
          title="Contraer o expandir el menú lateral"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span className="text-white font-semibold text-sm">Centro de Administración de Correo</span>
          <span className="text-white/60 text-xs ml-1">| Maquita Cushunchic</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-white/80 text-xs hidden md:block">{user?.display_name || user?.username}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/20 text-white">{user?.role}</span>
          <button
            onClick={() => setShowAccount(true)}
            className="p-1.5 rounded hover:bg-white/15 text-white/80 hover:text-white"
            title="Mi cuenta: cambiar mi contraseña y verificación en dos pasos (2FA)"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
          <button
            onClick={logout}
            className="p-1.5 rounded hover:bg-white/15 text-white/80 hover:text-white"
            title="Cerrar sesión"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <nav className={`${collapsed ? "w-12" : "w-56"} bg-ms-gray-150 text-white flex flex-col shrink-0 overflow-y-auto transition-all duration-200`}>
          {navSections.map((section) => (
            <div key={section.title}>
              {!collapsed && (
                <div className="px-4 pt-4 pb-1">
                  <span className="text-[11px] font-semibold text-white/40 uppercase tracking-wider">{section.title}</span>
                </div>
              )}
              {section.items.map((item) =>
                (item as any).external ? (
                  <a
                    key={item.to}
                    href={(item as any).external}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2.5 px-4 py-2 text-[13px] border-l-3 border-transparent text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                    title={(item as any).help || item.label}
                  >
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                    </svg>
                    {!collapsed && (
                      <span className="truncate flex items-center gap-1">
                        {item.label}
                        <svg className="w-3 h-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </span>
                    )}
                  </a>
                ) : (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={(item as any).end}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-4 py-2 text-[13px] border-l-3 transition-colors ${
                      isActive
                        ? "border-ms-blue bg-white/10 text-white font-medium"
                        : "border-transparent text-white/70 hover:text-white hover:bg-white/5"
                    }`
                  }
                  title={(item as any).help || item.label}
                >
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                  </svg>
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </NavLink>
                )
              )}
            </div>
          ))}
        </nav>

        {/* Main */}
        <main className="flex-1 overflow-auto bg-ms-gray-10">
          <Outlet />
        </main>
      </div>

      {showAccount && <MyAccountModal onClose={() => setShowAccount(false)} />}
    </div>
  );
}
