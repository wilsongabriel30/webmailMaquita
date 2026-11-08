/**
 * Barra inferior del mensaje (Responder, Responder a todos, Reenviar, No deseado, IA…).
 *
 * Compacta a propósito (una fila de ~34 px): antes medía ~72 px porque las etiquetas se partían
 * en dos líneas, y restaba espacio para leer el correo. Si el panel es estrecho, las acciones
 * secundarias quedan solo con su icono y, más estrecho aún, también las principales; el nombre
 * sigue en la descripción emergente (estilos en index.css, `.barra-acciones-correo`).
 */
import React from 'react';
import { AccionesCorreoNoDeseado } from './AccionesCorreoNoDeseado';
import { BotonAsignarCorreo } from '../tareas/BotonAsignarCorreo';
import { BotonEtiquetasCorreo } from '../labels/BotonEtiquetasCorreo';

const estiloBotonBarra: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#0078d4',
  fontWeight: 600,
  padding: '7px 10px',
  fontSize: 14,
  minHeight: 34,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  borderRadius: 4,
  whiteSpace: 'nowrap',
  flexShrink: 0,
};

// Botones principales con borde, como Outlook (07/11/2026): icono azul y texto oscuro.
const estiloPrincipal: React.CSSProperties = {
  ...estiloBotonBarra, border: '1px solid #d2d0ce', color: '#323130', fontWeight: 400,
  padding: '5px 14px', background: '#fff', gap: 6,
};

const Etiqueta = ({ texto, secundaria }: { texto: string; secundaria?: boolean }) => (
  <span className={secundaria ? 'barra-etiqueta barra-etiqueta-sec' : 'barra-etiqueta'}>{texto}</span>
);

export function BarraAccionesCorreo({
  esBorrador, onEditarBorrador, onResponder, onResponderTodos, onReenviar,
  folder, uid, from, asunto, conAsignar,
  onRespuestaIA, generandoRespuestas, onResumir, resumiendo, children,
}: {
  esBorrador: boolean;
  onEditarBorrador: () => void;
  onResponder: () => void;
  onResponderTodos: () => void;
  onReenviar: () => void;
  /** «Reenviar como adjunto»: el correo sale como .eml dentro de uno nuevo. */
  onReenviarAdjunto?: () => void;
  folder: string;
  uid: number;
  from: string;
  asunto: string;
  conAsignar?: boolean;
  onRespuestaIA: () => void;
  generandoRespuestas: boolean;
  onResumir: () => void;
  resumiendo: boolean;
  /** Extra a la derecha (p. ej. «Recuperar mensaje» en Enviados). */
  children?: React.ReactNode;
}) {
  return (
    <div className="barra-acciones-correo" style={{
      padding: '8px 88px 10px 24px', borderTop: '1px solid #f3f2f1', flexShrink: 0,
      display: 'flex', alignItems: 'center', gap: 6, background: '#fff', flexWrap: 'wrap', rowGap: 4,
    }}>
      {esBorrador ? (
        <button style={{ ...estiloBotonBarra, background: '#0078d4', color: '#fff', padding: '5px 16px' }} onClick={onEditarBorrador}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          Editar borrador
        </button>
      ) : (<>
        <button className="hover:!bg-[#f3f2f1]" style={estiloPrincipal} onClick={onResponder} title="Responder">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="#0078d4"><path d="M6.5 3L1 8l5.5 5V10c4.5 0 7 1.5 8.5 5-1-4.5-3.5-8-8.5-8.5V3z"/></svg>
          <Etiqueta texto="Responder" />
        </button>
        <button className="hover:!bg-[#f3f2f1]" style={estiloPrincipal} onClick={onResponderTodos} title="Responder a todos">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="#0078d4"><path d="M9.5 3L4 8l5.5 5V10c4.5 0 6 1.5 7.5 5-1-4.5-3-8-7.5-8.5V3zM3 8L0 5.5v5L3 8z"/></svg>
          <Etiqueta texto="Responder a todos" />
        </button>
        <button className="hover:!bg-[#f3f2f1]" style={estiloPrincipal} onClick={onReenviar} title="Reenviar">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="#0078d4"><path d="M9.5 3L15 8l-5.5 5V10C5 10 2.5 11.5 1 15c1-4.5 3.5-8 8.5-8.5V3z"/></svg>
          <Etiqueta texto="Reenviar" />
        </button>
        {/* «Como adjunto», «No deseado» y «Bloquear» están en «⋯» arriba a la derecha (07/11/2026).
            En Correo no deseado se quedan aquí «No es spam» y «Confiar». */}
        {(folder === 'Junk' || folder === 'Spam') && <AccionesCorreoNoDeseado folder={folder} uid={uid} from={from} estilo={estiloBotonBarra} />}
        {conAsignar && <BotonAsignarCorreo estilo={estiloBotonBarra} correo={{ folder, uid, subject: asunto, from }} />}
        <BotonEtiquetasCorreo folder={folder} uid={uid} estilo={estiloBotonBarra} />
        {/* «Respuesta IA» y «Resumir» conservan siempre su texto (revisión 04/11/2026, H11): solo con
            icono no se reconocen, y en pantalla táctil no hay descripción emergente. Si falta sitio, la
            barra pasa a una segunda fila. */}
        <button style={{ ...estiloBotonBarra, color: '#8764b8' }} onClick={onRespuestaIA} disabled={generandoRespuestas} title="Respuestas sugeridas por IA">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
          <Etiqueta texto={generandoRespuestas ? 'Generando...' : 'Respuesta IA'} />
        </button>
        <button style={{ ...estiloBotonBarra, color: '#498205' }} onClick={onResumir} disabled={resumiendo} title="Resumir con IA">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" /></svg>
          <Etiqueta texto={resumiendo ? 'Resumiendo...' : 'Resumir'} />
        </button>
      </>)}
      {children}
    </div>
  );
}
