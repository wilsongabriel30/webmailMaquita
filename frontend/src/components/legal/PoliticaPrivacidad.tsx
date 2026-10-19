/**
 * Política de privacidad y cookies del correo web (pública, sin sesión): /webmail/privacidad.
 * Base: Ley Orgánica de Protección de Datos Personales del Ecuador (LOPDP, R.O. 459 de 26/05/2021)
 * y su reglamento. El nombre de la organización sale de la marca configurada, no del código.
 */
import { useEffect, useState } from 'react';

interface Marca { org_name?: string; app_name?: string; primary_color?: string }

const COOKIES = [
  { nombre: 'access_token', uso: 'Identifica tu sesión mientras usas el correo.', dura: 'Minutos; se renueva sola mientras trabajas.' },
  { nombre: 'refresh_token', uso: 'Renueva la sesión sin volver a pedir la contraseña.', dura: 'Hasta cerrar sesión o vencer.' },
  { nombre: 'dispositivo_confianza', uso: 'Recuerda que ya verificaste este equipo con el segundo factor (solo desde la aplicación).', dura: 'Según la política de seguridad de la organización.' },
  { nombre: 'mail_app', uso: 'Dentro del cliente de escritorio, oculta la cabecera porque el cliente trae la suya. No se usa en navegadores normales.', dura: 'Un año; se borra con ?app=0.' },
];

export function PoliticaPrivacidad() {
  const [marca, setMarca] = useState<Marca>({});
  useEffect(() => {
    fetch('/api/branding').then(r => r.ok ? r.json() : {}).then((b: Marca) => setMarca(b)).catch(() => {});
  }, []);
  const org = marca.org_name || 'la organización';
  const app = marca.app_name || 'el correo web';
  const color = marca.primary_color || '#0078d4';
  useEffect(() => { document.title = `Política de privacidad y cookies — ${app}`; }, [app]);

  return (
    <main className="min-h-screen bg-[#f3f2f1] text-[#323130]">
      <div className="max-w-[760px] mx-auto px-4 py-8 bg-white my-0 sm:my-6 sm:rounded sm:shadow-sm">
        <h1 className="text-[22px] font-semibold" style={{ color }}>Política de privacidad y cookies</h1>
        <p className="text-[13px] text-[#605e5c] mt-1">{app} · {org}</p>

        <h2 className="text-[16px] font-semibold mt-6">1. Responsable del tratamiento</h2>
        <p className="text-[14px] mt-1">{org} es la responsable de los datos personales que se tratan en este servicio de correo institucional, conforme a la Ley Orgánica de Protección de Datos Personales del Ecuador (LOPDP) y su reglamento.</p>

        <h2 className="text-[16px] font-semibold mt-5">2. Qué datos se tratan y para qué</h2>
        <ul className="list-disc pl-5 text-[14px] mt-1 space-y-1">
          <li><strong>Cuenta y sesión:</strong> tu dirección de correo institucional, el equipo y la dirección IP desde la que entras. Sirven para darte acceso, proteger tu cuenta y auditar accesos.</li>
          <li><strong>Correo, contactos, calendario y archivos:</strong> el contenido que tú y tus interlocutores generan. Se usa solo para prestarte el servicio.</li>
          <li><strong>Seguridad:</strong> registros de inicio de sesión, segundo factor y filtrado de correo no deseado y de suplantaciones.</li>
        </ul>
        <p className="text-[14px] mt-2">Base legal: ejecución de la relación laboral o institucional con {org} y su interés legítimo en la seguridad de sus sistemas (art. 7 LOPDP). No se venden ni ceden datos a terceros con fines comerciales.</p>

        <h2 className="text-[16px] font-semibold mt-5">3. Cookies</h2>
        <p className="text-[14px] mt-1">Este sitio usa únicamente cookies <strong>estrictamente necesarias</strong> para prestar el servicio que pediste; por eso no se solicita consentimiento, pero sí se informa de ellas. No hay cookies de publicidad, analítica ni de terceros.</p>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-[13px] border-collapse">
            <thead>
              <tr className="text-left bg-[#f3f2f1]">
                <th className="p-2 border border-[#e1dfdd]">Cookie</th>
                <th className="p-2 border border-[#e1dfdd]">Para qué sirve</th>
                <th className="p-2 border border-[#e1dfdd]">Duración</th>
              </tr>
            </thead>
            <tbody>
              {COOKIES.map(c => (
                <tr key={c.nombre}>
                  <td className="p-2 border border-[#e1dfdd] font-mono text-[12px]">{c.nombre}</td>
                  <td className="p-2 border border-[#e1dfdd]">{c.uso}</td>
                  <td className="p-2 border border-[#e1dfdd]">{c.dura}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[14px] mt-2">Además, el navegador guarda localmente (no en cookies) preferencias de uso como el tema, el ámbito de búsqueda y una copia de tu correo para trabajar sin conexión. Puedes borrarlas desde la configuración del navegador; al hacerlo se cierra tu sesión.</p>

        <h2 className="text-[16px] font-semibold mt-5">4. Conservación</h2>
        <p className="text-[14px] mt-1">Los datos de la cuenta se conservan mientras la relación con {org} esté vigente y, después, el tiempo que exijan las obligaciones legales y de auditoría. Los registros de seguridad se conservan según la política de retención de la organización.</p>

        <h2 className="text-[16px] font-semibold mt-5">5. Tus derechos</h2>
        <p className="text-[14px] mt-1">Puedes ejercer los derechos de acceso, rectificación, actualización, eliminación, oposición, portabilidad y a no ser objeto de decisiones automatizadas que reconoce la LOPDP. Escribe al área de Tecnología o al delegado de protección de datos de {org} por los canales institucionales; te responderemos en los plazos que fija la ley. Si no quedas conforme, puedes acudir a la Superintendencia de Protección de Datos Personales.</p>

        <h2 className="text-[16px] font-semibold mt-5">6. Seguridad</h2>
        <p className="text-[14px] mt-1">El acceso se protege con cifrado en tránsito, verificación en dos pasos, control de dispositivos y registros de auditoría. El correo se aloja en servidores administrados por {org}.</p>

        <p className="text-[12px] text-[#605e5c] mt-6">Última actualización: 19 de octubre de 2026.</p>
        <p className="mt-4"><a href="/webmail/" className="text-[14px] underline" style={{ color }}>← Volver al correo</a></p>
      </div>
    </main>
  );
}
