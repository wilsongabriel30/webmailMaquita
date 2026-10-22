import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { consulta, type Flujo, type Rango } from "./api";
import { COLOR, Estado, Kpi, Seccion, etiqueta, useDatos } from "./comunes";

/* Tablero «Flujo de correo»: entregados, enviados, rechazados, spam y cola, por hora o por día. */
export function FlujoCorreo({ rango }: { rango: Rango }) {
  const { datos, error, cargando } = useDatos<Flujo>(`/seguridad/flujo?${consulta(rango)}`);
  const serie = (datos?.serie || []).map((p) => ({
    ...p,
    x: etiqueta(p.t, datos!.paso),
    rechazados_total: p.rechazados + p.rechazados_filtro,
    spam: p.spam_rechazado + p.spam_marcado,
  }));
  const t = datos?.totales || {};
  const n = (k: keyof typeof t) => t[k] || 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <Kpi titulo="Entregados a buzones" valor={n("recibidos")} ayuda="Mensajes guardados en buzones de este servidor (llegados de fuera o enviados entre buzones propios)." />
        <Kpi titulo="Enviados fuera" valor={n("enviados")} ayuda="Mensajes entregados a otros servidores de correo." />
        <Kpi titulo="Rechazados" valor={n("rechazados") + n("rechazados_filtro")} tono="text-ms-red" ayuda="Rechazados en la conexión (destinatario inexistente, listas negras, políticas) y por el filtro antispam." />
        <Kpi titulo="Spam" valor={n("spam_rechazado") + n("spam_marcado")} tono="text-ms-orange" ayuda="Rspamd: rechazados como spam más los marcados como spam (cabecera o asunto)." />
        <Kpi titulo="Rebotados" valor={n("rebotados")} ayuda="Envíos que no se pudieron entregar y volvieron al remitente." />
        <Kpi titulo="Diferidos" valor={n("diferidos")} ayuda="Intentos de entrega aplazados (un mismo mensaje puede sumar varios intentos)." />
        <Kpi titulo="En cola ahora" valor={datos?.cola_actual ?? null} ayuda="Mensajes en la cola de Postfix en la última pasada del recolector." />
      </div>
      <Estado cargando={cargando} error={error} vacio={!cargando && !error && serie.length === 0} />
      {serie.length > 0 && (
        <>
          <Seccion titulo={`Correo ${datos!.paso === "hour" ? "por hora" : "por día"}`}>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={serie}>
                <CartesianGrid strokeDasharray="3 3" stroke="#edebe9" />
                <XAxis dataKey="x" tick={{ fontSize: 11 }} minTickGap={12} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="recibidos" name="Entregados a buzones" stackId="a" fill={COLOR.azul} />
                <Bar dataKey="enviados" name="Enviados fuera" stackId="a" fill={COLOR.ok} />
                <Bar dataKey="rechazados_total" name="Rechazados" stackId="b" fill={COLOR.fallo} />
                <Bar dataKey="rebotados" name="Rebotados" stackId="b" fill={COLOR.naranja} />
              </BarChart>
            </ResponsiveContainer>
          </Seccion>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Seccion titulo="Antispam (Rspamd)">
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={serie}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#edebe9" />
                  <XAxis dataKey="x" tick={{ fontSize: 11 }} minTickGap={12} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area dataKey="analizados" name="Analizados" stroke={COLOR.gris} fill="#f3f2f1" />
                  <Area dataKey="spam_marcado" name="Marcados como spam" stroke={COLOR.amarillo} fill="#fff4ce" />
                  <Area dataKey="spam_rechazado" name="Rechazados como spam" stroke={COLOR.fallo} fill="#fde7e9" />
                  <Area dataKey="spam_aplazado" name="Aplazados (greylist)" stroke={COLOR.morado} fill="#efe6f6" />
                </AreaChart>
              </ResponsiveContainer>
            </Seccion>
            <Seccion titulo="Cola de correo">
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={serie}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#edebe9" />
                  <XAxis dataKey="x" tick={{ fontSize: 11 }} minTickGap={12} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Area dataKey="en_cola" name="Mensajes en cola" stroke={COLOR.azul} fill="#deecf9" />
                  <Area dataKey="diferidos" name="Intentos diferidos" stroke={COLOR.naranja} fill="#fbe5d6" />
                </AreaChart>
              </ResponsiveContainer>
            </Seccion>
          </div>
        </>
      )}
    </div>
  );
}
