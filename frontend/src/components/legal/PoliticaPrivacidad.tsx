/**
 * Política de privacidad y cookies del correo web (pública, sin sesión): /webmail/privacidad.
 * Texto oficial aprobado por Gestión de Tecnología el 19/10/2026 (Documentación →
 * 14-PROTECCION-DATOS-PERSONALES/06-PLANTILLAS/politica-privacidad-correo-OFICIAL.docx).
 * Base: Ley Orgánica de Protección de Datos Personales del Ecuador (LOPDP) y su Reglamento.
 * El nombre del producto y de la organización salen de la marca configurada (/api/branding);
 * los datos del responsable y del delegado, de la configuración del servidor cuando exista
 * (`/api/branding` → `privacidad`), con los valores de abajo como reserva.
 */
import { useEffect, useState } from 'react';

/** Claves públicas de /api/branding (tabla branding_settings) que usa esta página. */
interface Marca {
  org_name?: string; app_name?: string; primary_color?: string; org_email?: string;
  org_ruc?: string; org_address?: string; privacy_contact_area?: string; privacy_contact_email?: string;
  dpo_name?: string; dpo_email?: string; dpo_phone?: string; privacy_updated?: string; privacy_version?: string;
}

const COOKIES_SEGURIDAD = [
  ['access_token', 'Identifica la sesión activa mientras se usa el correo. Dura pocos minutos y se renueva automáticamente durante el uso.'],
  ['refresh_token', 'Permite renovar la sesión de forma segura sin volver a pedir la contraseña. Se mantiene hasta que se cierra la sesión o vence.'],
  ['dispositivo_confianza', 'Recuerda que el equipo ya fue verificado con el segundo factor de autenticación. Solo se usa en la aplicación de escritorio y su duración depende de la política de seguridad institucional.'],
];

export function PoliticaPrivacidad() {
  const [marca, setMarca] = useState<Marca>({});
  useEffect(() => {
    fetch('/api/branding').then(r => r.ok ? r.json() : {}).then((b: Marca) => setMarca(b)).catch(() => {});
  }, []);
  const org = marca.org_name || 'la organización';
  const app = marca.app_name || 'el correo web';
  const color = marca.primary_color || '#0078d4';
  const p = {
    razon_social: marca.org_name,
    ruc: marca.org_ruc || '',
    direccion: marca.org_address || '',
    contacto_area: marca.privacy_contact_area || 'Área de Tecnología',
    contacto_correo: marca.privacy_contact_email || marca.org_email || '',
    delegado_nombre: marca.dpo_name, delegado_correo: marca.dpo_email, delegado_telefono: marca.dpo_phone,
    actualizado: marca.privacy_updated || '19 de octubre de 2026',
    version: marca.privacy_version || '1.1',
  };
  const contactoDerechos = p.delegado_correo || p.contacto_correo;
  useEffect(() => { document.title = `Política de privacidad y cookies — ${app}`; }, [app]);

  const h2 = 'text-[16px] font-semibold mt-6';
  const h3 = 'text-[14px] font-semibold mt-4';
  const txt = 'text-[14px] mt-1 leading-relaxed';
  const ul = 'list-disc pl-5 text-[14px] mt-1 space-y-1';

  return (
    <main className="min-h-screen bg-[#f3f2f1] text-[#323130]">
      <div className="max-w-[760px] mx-auto px-4 py-8 bg-white my-0 sm:my-6 sm:rounded sm:shadow-sm">
        <h1 className="text-[22px] font-semibold" style={{ color }}>Política de privacidad y cookies</h1>
        <p className="text-[13px] text-[#605e5c] mt-1">{app} · {p.razon_social || org}</p>

        <p className={txt}>
          En esta página se describe cómo {p.razon_social || org} trata los datos personales en su servicio de correo institucional {app},
          con qué fines y qué cookies y tecnologías similares utiliza. Se emite conforme a la Ley Orgánica de Protección de Datos
          Personales (LOPDP) del Ecuador y su Reglamento.
        </p>
        <p className={txt}>
          <strong>Responsable del tratamiento:</strong> {p.razon_social || org}{p.ruc ? `, RUC ${p.ruc}` : ''}{p.direccion ? `, ${p.direccion}` : ''}.<br />
          <strong>Contacto:</strong> {p.contacto_area}{p.contacto_correo ? <>, <a href={`mailto:${p.contacto_correo}`} className="underline" style={{ color }}>{p.contacto_correo}</a></> : null}.
          {p.delegado_nombre ? (
            <><br /><strong>Delegado/a de Protección de Datos Personales:</strong> {p.delegado_nombre}
              {p.delegado_correo ? <>, <a href={`mailto:${p.delegado_correo}`} className="underline" style={{ color }}>{p.delegado_correo}</a></> : null}
              {p.delegado_telefono ? <>, {p.delegado_telefono}</> : null}.</>
          ) : (
            <><br /><strong>Delegado/a de Protección de Datos Personales:</strong> en proceso de designación y registro ante la Superintendencia; mientras tanto, el contacto es el indicado arriba.</>
          )}
        </p>

        <h2 className={h2}>Datos que se tratan y para qué</h2>
        <h3 className={h3}>Cuenta y sesión</h3>
        <p className={txt}>Se tratan la dirección de correo institucional, el equipo y la dirección IP desde la que se accede. Sirven para habilitar el acceso, proteger la cuenta y auditar los ingresos al servicio.</p>
        <h3 className={h3}>Contenido del servicio</h3>
        <p className={txt}>Mensajes, contactos, eventos de calendario y archivos que la persona usuaria y sus interlocutores generan. Se tratan únicamente para prestar el servicio.</p>
        <h3 className={h3}>Seguridad</h3>
        <p className={txt}>Registros de inicio de sesión, eventos del segundo factor de autenticación y resultados del filtrado de correo no deseado y de suplantaciones. Sirven para detectar y prevenir accesos no autorizados, fraudes y abusos.</p>

        <h2 className={h2}>Base legal</h2>
        <p className={txt}>El tratamiento se sustenta en el artículo 7 de la LOPDP, por dos motivos:</p>
        <ul className={ul}>
          <li>La ejecución de la relación laboral o institucional con {org}.</li>
          <li>El interés legítimo de {org} en garantizar la seguridad de sus sistemas.</li>
        </ul>
        <p className={txt}>Los datos no se venden, no se ceden a terceros con fines comerciales y no se usan para elaborar perfiles.</p>

        <h2 className={h2}>Cómo usa {app} las cookies</h2>
        <p className={txt}>Las cookies son pequeños archivos de texto que un sitio web envía al navegador para recordar información sobre la visita. Para fines similares también se usan otras tecnologías, como el almacenamiento local del navegador.</p>
        <p className={txt}>{app} utiliza únicamente cookies propias y <strong>estrictamente necesarias</strong> para prestar el servicio. Por su naturaleza no requieren consentimiento, pero se informan en cumplimiento del principio de transparencia.</p>
        <h3 className={h3}>Seguridad</h3>
        <p className={txt}>Estas cookies autentican a la persona usuaria y garantizan que solo el titular de una cuenta pueda acceder a ella.</p>
        <ul className={ul}>
          {COOKIES_SEGURIDAD.map(([n, d]) => <li key={n}><span className="font-mono text-[12px]">{n}</span>: {d}</li>)}
        </ul>
        <h3 className={h3}>Funcionalidad</h3>
        <p className={txt}>Estas cookies y tecnologías similares permiten el funcionamiento correcto de la interfaz y conservan preferencias de uso.</p>
        <ul className={ul}>
          <li><span className="font-mono text-[12px]">mail_app</span>: adapta la interfaz cuando el correo se abre desde el cliente de escritorio, ocultando la cabecera web porque el cliente tiene la suya. No se usa en navegadores convencionales. Dura un año y se elimina accediendo con el parámetro <span className="font-mono text-[12px]">?app=0</span>.</li>
          <li><strong>Almacenamiento local:</strong> el navegador guarda en el propio equipo preferencias como el tema visual y el ámbito de búsqueda, además de una copia temporal del correo para trabajar sin conexión. Esta información no se envía a terceros. Se recomienda no usar el modo sin conexión en equipos compartidos.</li>
        </ul>
        <h3 className={h3}>Estadísticas, publicidad y personalización</h3>
        <p className={txt}>{app} no utiliza cookies ni tecnologías similares con fines estadísticos, publicitarios, de seguimiento o de personalización, ni cookies de terceros. Si en el futuro se incorporan con alguno de estos fines, se pedirá antes el consentimiento de la persona usuaria, quien podrá rechazarlas o revocarlo en cualquier momento.</p>
        <h3 className={h3}>Aplicación de escritorio</h3>
        <p className={txt}>Al cerrar sesión desde la aplicación de escritorio se eliminan sus cookies y datos locales, incluido el registro de dispositivo de confianza.</p>

        <h2 className={h2}>Conservación</h2>
        <p className={txt}>Los datos de la cuenta se conservan mientras esté vigente la relación con {org}. Después se conservan solo el tiempo que exijan las obligaciones legales y de auditoría, y luego se eliminan o anonimizan. Los registros de seguridad se conservan según la política de retención institucional.</p>

        <h2 className={h2}>Seguridad</h2>
        <p className={txt}>El acceso se protege con:</p>
        <ul className={ul}>
          <li>Cifrado de las comunicaciones en tránsito.</li>
          <li>Verificación en dos pasos.</li>
          <li>Control de dispositivos de confianza.</li>
          <li>Registros de auditoría.</li>
        </ul>
        <p className={txt}>El correo se aloja en servidores propios administrados por {org}, ubicados en el Ecuador.</p>

        <h2 className={h2}>Derechos</h2>
        <p className={txt}>La persona usuaria puede ejercer los derechos que reconoce la LOPDP:</p>
        <ul className={ul}>
          <li>Acceso</li>
          <li>Rectificación y actualización</li>
          <li>Eliminación</li>
          <li>Oposición</li>
          <li>Portabilidad</li>
          <li>Suspensión del tratamiento</li>
          <li>A no ser objeto de decisiones automatizadas</li>
        </ul>
        <p className={txt}>
          Para hacerlo debe escribir a <a href={`mailto:${contactoDerechos}`} className="underline" style={{ color }}>{contactoDerechos}</a>, indicando su nombre y la cuenta de correo.
          {' '}{org} responderá en un plazo máximo de <strong>quince (15) días</strong>. Si no queda conforme, puede presentar un reclamo ante la
          Superintendencia de Protección de Datos Personales (SPDP), <a href="https://spdp.gob.ec" target="_blank" rel="noopener" className="underline" style={{ color }}>spdp.gob.ec</a>.
        </p>

        <p className="text-[12px] text-[#605e5c] mt-6">Versión {p.version} · Última actualización: {p.actualizado}.</p>
        <p className="mt-4"><a href="/webmail/" className="text-[14px] underline" style={{ color }}>← Volver al correo</a></p>
      </div>
    </main>
  );
}
