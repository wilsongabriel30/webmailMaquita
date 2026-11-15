/**
 * Configuración → Apariencia (13/11/2026): cada persona elige cómo ve su correo.
 *
 * Esta pestaña solo reúne los controles; la lógica vive donde ya estaba:
 *   - color principal: lib/apariencia.ts
 *   - tema: store/themeStore.ts (el mismo que el botón de la barra superior)
 *   - tamaño: lib/escala.ts (el mismo que Vista → Zoom)
 *   - lista de correos y panel de lectura: store/mailStore.ts (los mismos que la cinta Vista)
 * Todo se aplica al momento y se guarda en la cuenta.
 */
import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { useThemeStore, type ModoTema } from '../../store/themeStore';
import { guardarVistaAhora } from '../../hooks/usePreferenciasVista';
import { preferenciasLocales, sincronizarAlEntrar } from '../../lib/preferenciasCuenta';
import { acentoElegido, elegirAcento } from '../../lib/apariencia';
import { ACENTO_INSTITUCIONAL, COLORES_ACENTO } from '../../lib/aparienciaColores';
import { aplicarEscala, escalaActual, type Escala } from '../../lib/escala';
import { showToast } from '../common/Toast';
import { GrupoOpciones, type Opcion } from './apariencia/GrupoOpciones';
import { VistaPreviaAspecto } from './apariencia/VistaPreviaAspecto';

type Panel = 'right' | 'bottom' | 'off';
type Densidad = 'linea' | 'compact' | 'medium' | 'full';

const COLORES: Opcion<string>[] = COLORES_ACENTO.map((c) => ({ valor: c.id, etiqueta: c.nombre, muestra: c.tonos.acento }));
const TEMAS: Opcion<ModoTema>[] = [
  { valor: 'claro', etiqueta: 'Claro' },
  { valor: 'oscuro', etiqueta: 'Oscuro' },
  { valor: 'equipo', etiqueta: 'Según el equipo' },
];
const TAMANOS: Opcion<Escala>[] = [
  { valor: 80, etiqueta: 'Muy pequeño (80 %)' },
  { valor: 90, etiqueta: 'Pequeño (90 %)' },
  { valor: 100, etiqueta: 'Normal (100 %)' },
  { valor: 110, etiqueta: 'Grande (110 %)' },
];
const DENSIDADES: Opcion<Densidad>[] = [
  { valor: 'linea', etiqueta: 'Una línea' },
  { valor: 'compact', etiqueta: 'Compacta' },
  { valor: 'medium', etiqueta: 'Media' },
  { valor: 'full', etiqueta: 'Completa' },
];
const PANELES: Opcion<Panel>[] = [
  { valor: 'right', etiqueta: 'A la derecha' },
  { valor: 'bottom', etiqueta: 'Abajo' },
  { valor: 'off', etiqueta: 'Apagado' },
];

interface Props {
  /** Avisa a Configuración de que cambió el panel de lectura (para que «General» no guarde el anterior). */
  alCambiarPanel?: (panel: Panel) => void;
}

export function Apariencia({ alCambiarPanel }: Props) {
  const modo = useThemeStore((s) => s.modo);
  const oscuro = useThemeStore((s) => s.dark);
  const densidad = useMailStore((s) => s.density);
  const panel = useMailStore((s) => s.readingPane);
  const [color, setColor] = useState(acentoElegido);
  const [escala, setEscala] = useState<Escala>(escalaActual);

  // Lo guardado en la cuenta manda al entrar, y desde ese momento cada cambio se guarda en ella.
  // (Si se llega aquí sin pasar por la bandeja, esta comprobación aún no se había hecho.)
  useEffect(() => {
    api.get<{ vista?: { local?: unknown } | null }>('/settings')
      .then((s) => sincronizarAlEntrar(s?.vista?.local, () => useMailStore.getState().composeWindows.length > 0))
      .catch(() => { /* sin conexión: los cambios quedan en este navegador */ });
  }, []);

  // Se guarda en la cuenta en el momento (no a los 2 s habituales): si la persona vuelve enseguida a la
  // bandeja, lo que hay en la cuenta ya es lo que acaba de elegir.
  const guardarYa = () => { api.put('/settings', { vista: { local: preferenciasLocales() } }).catch(() => { /* queda en este navegador */ }); };

  const cambiarColor = (id: string) => { elegirAcento(id, oscuro); setColor(id); guardarYa(); };
  const cambiarTema = (m: ModoTema) => { useThemeStore.getState().setModo(m); guardarYa(); };
  const cambiarEscala = (v: Escala) => { aplicarEscala(v); setEscala(v); guardarYa(); };
  const cambiarDensidad = (d: Densidad) => { useMailStore.getState().setDensity(d); void guardarVistaAhora(); };
  const cambiarPanel = (p: Panel) => {
    useMailStore.getState().setReadingPane(p);
    alCambiarPanel?.(p);
    api.put('/settings', { reading_pane: p }).catch(() => { /* queda para esta visita */ });
  };

  const restablecer = () => {
    elegirAcento(ACENTO_INSTITUCIONAL, false); setColor(ACENTO_INSTITUCIONAL);
    useThemeStore.getState().setModo('claro');
    aplicarEscala(100); setEscala(100);
    guardarYa();
    cambiarDensidad('medium');
    cambiarPanel('right');
    showToast('Su correo volvió al aspecto institucional');
  };

  const panelElegido = panel === 'right' || panel === 'bottom' || panel === 'off' ? panel : null;

  return (
    <div className="space-y-6">
      <p className="text-sm text-[#605e5c]">
        Elija cómo quiere ver su correo. Cada cambio se aplica al momento y se guarda en su cuenta:
        lo encontrará igual cuando entre desde otro equipo.
      </p>

      <GrupoOpciones titulo="Color principal" ayuda="Es el color de los botones, los enlaces y lo que está seleccionado."
        opciones={COLORES} valor={color} alElegir={cambiarColor} />

      <VistaPreviaAspecto />

      <GrupoOpciones titulo="Tema" ayuda="«Según el equipo» sigue el modo claro u oscuro que tenga su computadora o su teléfono."
        opciones={TEMAS} valor={modo} alElegir={cambiarTema} />

      <GrupoOpciones titulo="Tamaño de la letra" ayuda="Agranda o reduce todo el correo: letras, botones e iconos."
        opciones={TAMANOS} valor={escala} alElegir={cambiarEscala} />

      <GrupoOpciones titulo="Lista de correos" ayuda="Cuánto espacio ocupa cada correo en la lista. Con «Una línea» caben más correos en la pantalla."
        opciones={DENSIDADES} valor={densidad} alElegir={cambiarDensidad} />

      <GrupoOpciones titulo="Panel de lectura" ayuda="Dónde se muestra el correo que usted selecciona en la lista."
        opciones={PANELES} valor={panelElegido} alElegir={cambiarPanel} />
      {!panelElegido && (
        <p className="text-xs text-[#605e5c]" role="note">
          Ahora tiene elegida otra disposición desde la cinta Vista (pantalla completa o ventana aparte). Si elige una de estas tres, la reemplaza.
        </p>
      )}

      <div className="pt-4 border-t border-[#edebe9]">
        <button type="button" onClick={restablecer}
          className="aspecto-opcion px-4 py-1.5 border border-[#8a8886] text-sm text-[#323130] rounded hover:bg-[#f3f2f1]">
          Restablecer el aspecto institucional
        </button>
        <p className="mt-1.5 text-xs text-[#605e5c]">
          Vuelve al color azul, al tema claro, al tamaño normal y a la disposición habitual de la lista y del panel de lectura.
        </p>
      </div>
    </div>
  );
}
