import { useState, useRef, useEffect } from "react";
import type { ViewMode } from "./types/calendar";
import { formatMonthYear } from "./utils/dateHelpers";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { addDays, addWeeks, addMonths, getWeekDates } from "./utils/dateHelpers";

interface Props {
  currentDate: Date;
  viewMode: ViewMode;
  onDateChange: (date: Date) => void;
  onViewChange: (mode: ViewMode) => void;
  onNewEvent: () => void;
  onToday: () => void;
}

/* ── dropdown hook ──────────────────────────────────────── */
function useDropdown() {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    // Calculate fixed position from the ref element
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPos({ top: rect.bottom + 2, left: rect.left });
    }
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        // Also check if click is inside a portal dropdown
        const target = e.target as HTMLElement;
        if (target.closest('[data-dropdown-portal]')) return;
        setOpen(false);
      }
    }
    // Close on scroll
    function onScroll() { setOpen(false); }
    document.addEventListener("mousedown", close);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", close);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open]);
  return { open, setOpen, ref, pos };
}

/* ── ICONS (Fluent UI / Outlook 1:1) ─────────────────────── */

/* Nuevo evento: calendar page + blue "+" circle (exactly like Outlook) */
const IconNewEvent = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <path d="M17.5 3H6.5C5.67 3 5 3.67 5 4.5V19.5C5 20.33 5.67 21 6.5 21H17.5C18.33 21 19 20.33 19 19.5V4.5C19 3.67 18.33 3 17.5 3Z" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M8 3V5M16 3V5" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M5 8H19" stroke="#605e5c" strokeWidth="1.2"/>
    <circle cx="17" cy="17" r="4.5" fill="white" stroke="#0078d4" strokeWidth="1.2"/>
    <path d="M17 14.5V19.5M14.5 17H19.5" stroke="#0078d4" strokeWidth="1.3" strokeLinecap="round"/>
  </svg>
);

/* Día: single calendar page (Outlook style) */
const IconDay = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="5" y="3" width="14" height="18" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M8 3V5.5M16 3V5.5" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M5 8H19" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M9 12H15M9 15H13" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
);

/* Semana laboral: 5 columns with selection box (Outlook style) */
const IconWorkWeek = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="4" width="18" height="16" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M3 8H21" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M6.6 8V20M10.2 8V20M13.8 8V20M17.4 8V20" stroke="#605e5c" strokeWidth="0.8" opacity="0.6"/>
    <rect x="6.6" y="8" width="3.6" height="12" fill="#0078d4" opacity="0.08" stroke="#0078d4" strokeWidth="0.8"/>
  </svg>
);

/* Semana: 3 vertical columns (Outlook style — thicker lines) */
const IconWeek = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="4" width="18" height="16" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M3 8H21" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M9 8V20M15 8V20" stroke="#605e5c" strokeWidth="1.0"/>
  </svg>
);

/* Mes: grid icon (4x4 cells in calendar) */
const IconMonth = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="4" width="18" height="16" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M3 8H21" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M3 12H21M3 16H21" stroke="#605e5c" strokeWidth="0.8"/>
    <path d="M7.5 8V20M12 8V20M16.5 8V20" stroke="#605e5c" strokeWidth="0.8"/>
  </svg>
);

/* Vista en dos paneles: split rectangle (Outlook style) */
const IconSplit = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="4" width="8" height="16" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <rect x="13" y="4" width="8" height="16" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
  </svg>
);

/* Filtrar: funnel — 3 horizontal lines narrowing (Outlook style) */
const IconFilter = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <path d="M4 6H20" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M7 11H17" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M10 16H14" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

/* Compartir calendario: share arrow from rectangle (Outlook blue) */
const IconShare = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <path d="M12 3L17 8M12 3L7 8M12 3V15" stroke="#0078d4" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M4 13V19C4 20.1 4.9 21 6 21H18C19.1 21 20 20.1 20 19V13" stroke="#0078d4" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
);

/* Imprimir: printer (Outlook style) */
const IconPrint = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <path d="M7 8V3H17V8" stroke="#605e5c" strokeWidth="1.2" strokeLinejoin="round"/>
    <rect x="3" y="8" width="18" height="9" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M7 14H17V21H7V14Z" stroke="#605e5c" strokeWidth="1.2" strokeLinejoin="round" fill="none"/>
    <circle cx="16" cy="11" r="0.8" fill="#605e5c"/>
  </svg>
);

/* Calendar icon for nav bar */
const IconCalendar = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <rect x="2" y="3" width="14" height="13" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M5.5 1.5V4M12.5 1.5V4" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M2 7H16" stroke="#605e5c" strokeWidth="1.2"/>
  </svg>
);

/* Ayuda: question mark in circle */
const IconHelp = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="12" r="9" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M9.5 9.5C9.5 8.12 10.62 7 12 7C13.38 7 14.5 8.12 14.5 9.5C14.5 10.88 13.38 12 12 12V13.5" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
    <circle cx="12" cy="16.5" r="0.8" fill="#605e5c"/>
  </svg>
);

/* Recomendaciones: star (Outlook) — not used in calendar but keep */
const IconRecommend = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <path d="M12 3L14.5 8.5L20.5 9.3L16.25 13.3L17.3 19.3L12 16.5L6.7 19.3L7.75 13.3L3.5 9.3L9.5 8.5L12 3Z" stroke="#605e5c" strokeWidth="1.2" strokeLinejoin="round" fill="none"/>
  </svg>
);

/* Comentarios: speech bubbles (Outlook style) */
const IconFeedback = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <path d="M4 4H16C16.55 4 17 4.45 17 5V13C17 13.55 16.55 14 16 14H8L4 18V5C4 4.45 4.45 4 5 4Z" stroke="#605e5c" strokeWidth="1.2" strokeLinejoin="round" fill="none"/>
    <path d="M17 8H19C19.55 8 20 8.45 20 9V20L16 16H9" stroke="#605e5c" strokeWidth="1.0" opacity="0.5"/>
  </svg>
);

/* Obtener diagnósticos: chart/graph (Outlook style) */
const IconDiag = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="3" width="18" height="18" rx="2" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M7 15L10 11L13 13L17 8" stroke="#605e5c" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

/* Outlook Mobile: phone */
const IconMobile = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="6" y="2" width="12" height="20" rx="2" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M10 18H14" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M6 5H18" stroke="#605e5c" strokeWidth="0.8"/>
    <path d="M6 17H18" stroke="#605e5c" strokeWidth="0.8"/>
  </svg>
);

/* Configuración: gear (Outlook style) */
const IconGear = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="12" r="3" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M12 2V4.5M12 19.5V22M2 12H4.5M19.5 12H22M4.93 4.93L6.7 6.7M17.3 17.3L19.07 19.07M4.93 19.07L6.7 17.3M17.3 6.7L19.07 4.93" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
);

/* Vistas guardadas: layout with columns (Outlook style) */
const IconSavedViews = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="4" width="18" height="16" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none"/>
    <path d="M3 8H21" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M9 8V20" stroke="#605e5c" strokeWidth="1.0"/>
    <path d="M5 6H7" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
);

/* Escala de tiempo: clock (Outlook style) */
const IconTimescale = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="12" r="9" stroke="#605e5c" strokeWidth="1.2"/>
    <path d="M12 6V12L16 16" stroke="#605e5c" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

/* Correo icon for dropdown: envelope with pencil */
const IconCorreo = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <rect x="1" y="3" width="14" height="10" rx="1" stroke="#605e5c" strokeWidth="1" fill="none"/>
    <path d="M1 4L8 9L15 4" stroke="#605e5c" strokeWidth="1" strokeLinejoin="round"/>
  </svg>
);

/* Evento icon for dropdown: calendar page */
const IconEvento = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <rect x="2" y="2" width="12" height="12" rx="1" stroke="#605e5c" strokeWidth="1" fill="none"/>
    <path d="M5 2V4M11 2V4" stroke="#605e5c" strokeWidth="1" strokeLinecap="round"/>
    <path d="M2 6H14" stroke="#605e5c" strokeWidth="1"/>
  </svg>
);

const ChevronDown = ({ className = "w-3 h-3" }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);
const ChevronLeft = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
  </svg>
);
const ChevronRight = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);
const ChevronUp = () => (
  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
  </svg>
);
const ChevronDownSmall = () => (
  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);
const ChevronRightSmall = () => (
  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);
const IconHamburger = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#323130" strokeWidth="1.4">
    <path d="M2 4h12M2 8h12M2 12h12" strokeLinecap="round" />
  </svg>
);
const IconCheck = () => (
  <svg className="w-3 h-3 inline mr-1" viewBox="0 0 12 12" fill="none" stroke="#0078d4" strokeWidth="2">
    <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IconX = () => (
  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 2l8 8M10 2l-8 8" strokeLinecap="round" />
  </svg>
);

/* ── Filter state types ─────────────────────────────────── */
interface FilterState {
  citas: boolean;
  reuniones: boolean;
  sondeos: boolean;
  categorias: boolean;
  mostrarComo: boolean;
  periodicidad: boolean;
  enPersona: boolean;
}

const defaultFilters: FilterState = {
  citas: true,
  reuniones: true,
  sondeos: true,
  categorias: true,
  mostrarComo: true,
  periodicidad: true,
  enPersona: true,
};

/* ── Ribbon button component ────────────────────────────── */
function RibbonBtn({
  icon,
  label,
  active = false,
  onClick,
  dropdown,
  onDropdownClick,
  accent = false,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
  dropdown?: boolean;
  onDropdownClick?: (e: React.MouseEvent) => void;
  accent?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        flex flex-col items-center justify-end gap-[2px] px-[12px] pt-[8px] pb-[4px]
        text-[11px] leading-[14px] whitespace-nowrap
        hover:bg-[#f3f2f1] rounded-sm transition-colors relative
        ${accent ? "text-[#0078d4]" : "text-[#605e5c]"}
        ${active ? "text-[#0078d4]" : ""}
      `}
    >
      <span className="flex items-center justify-center h-[30px]">{icon}</span>
      <span className="flex items-center gap-[2px]">
        {label}
        {dropdown && (
          <span
            className="cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              onDropdownClick?.(e);
            }}
          >
            <ChevronDown className="w-[10px] h-[10px]" />
          </span>
        )}
      </span>
      {active && (
        <span className="absolute bottom-0 left-[6px] right-[6px] h-[2px] bg-[#0078d4] rounded-t" />
      )}
    </button>
  );
}

/* ── Tab type ───────────────────────────────────────────── */
type TabId = "inicio" | "ver" | "ayuda";

/* ── MAIN COMPONENT ────────────────────────────────────── */
export function CalendarHeader({
  currentDate,
  viewMode,
  onDateChange,
  onViewChange,
  onNewEvent,
  onToday,
}: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("inicio");
  const newDrop = useDropdown();
  const dayDrop = useDropdown();
  const filterDrop = useDropdown();
  const timeScaleDrop = useDropdown();
  const savedViewsDrop = useDropdown();
  const [filterState, setFilterState] = useState<FilterState>(defaultFilters);
  const [expandedFilter, setExpandedFilter] = useState<string | null>(null);
  const [selectedTimeScale, setSelectedTimeScale] = useState("30");
  const [splitView, setSplitView] = useState(false);
  
  const calToast = (msg: string) => {
    const el = document.createElement('div');
    el.textContent = msg;
    el.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#323130;color:white;padding:10px 20px;border-radius:4px;font-size:13px;z-index:99999;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  };

  /* navigation */
  function navigate(dir: -1 | 1) {
    switch (viewMode) {
      case "month":
        onDateChange(addMonths(currentDate, dir));
        break;
      case "week":
      case "workweek":
        onDateChange(addWeeks(currentDate, dir));
        break;
      case "day":
        onDateChange(addDays(currentDate, dir));
        break;
      case "agenda":
        onDateChange(addMonths(currentDate, dir));
        break;
    }
  }

  function smallStep(dir: -1 | 1) {
    onDateChange(addDays(currentDate, dir));
  }

  function getLabel(): string {
    switch (viewMode) {
      case "month":
        return formatMonthYear(currentDate);
      case "week": {
        const days = getWeekDates(currentDate);
        const s = format(days[0], "d", { locale: es });
        const e = format(days[6], "d 'de' MMMM 'de' yyyy", { locale: es });
        return `${s}\u2013${e}`;
      }
      case "workweek": {
        const days = getWeekDates(currentDate);
        const s = format(days[0], "d", { locale: es });
        const e = format(days[4], "d 'de' MMMM 'de' yyyy", { locale: es });
        return `${s}\u2013${e}`;
      }
      case "day":
        return format(currentDate, "EEEE, d 'de' MMMM 'de' yyyy", { locale: es });
      case "agenda":
        return formatMonthYear(currentDate);
    }
  }

  const toggleFilter = (key: keyof FilterState) => {
    setFilterState((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const clearFilters = () => {
    setFilterState(defaultFilters);
    filterDrop.setOpen(false);
  };

  /* ── Render ribbon content per tab ──────────────────── */
  function renderTabInicio() {
    return (
      <div className="flex items-end h-full">
        {/* Group: Nuevo */}
        <div className="flex flex-col items-center" ref={newDrop.ref}>
          <div className="flex items-end relative">
            <RibbonBtn
              icon={<IconNewEvent />}
              label="Nuevo evento"
              accent
              dropdown
              onClick={onNewEvent}
              onDropdownClick={() => newDrop.setOpen(!newDrop.open)}
            />
            {newDrop.open && (
              <div data-dropdown-portal style={{ top: newDrop.pos.top, left: newDrop.pos.left }} className="fixed bg-white border border-[#e0e0e0] rounded shadow-lg z-[9999] py-1 min-w-[180px]">
                <button
                  className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2"
                  onClick={() => {
                    newDrop.setOpen(false);
                    window.open(
                      "/webmail/compose",
                      "CorreoNuevo",
                      "width=950,height=750,menubar=no,toolbar=no,location=no,status=no,scrollbars=yes,resizable=yes"
                    );
                  }}
                >
                  <IconCorreo />
                  Correo
                </button>
                <button
                  className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2"
                  onClick={() => { newDrop.setOpen(false); onNewEvent(); }}
                >
                  <IconEvento />
                  Evento
                </button>
              </div>
            )}
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Nuevo</span>
        </div>

        <div className="w-px bg-[#e0e0e0] self-stretch my-[6px] mx-[4px]" />

        {/* Group: Organizar */}
        <div className="flex flex-col items-center">
          <div className="flex items-end">
            <div className="relative" ref={dayDrop.ref}>
              <RibbonBtn
                icon={<IconDay />}
                label="Día"
                active={viewMode === "day"}
                dropdown
                onClick={() => onViewChange("day")}
                onDropdownClick={() => dayDrop.setOpen(!dayDrop.open)}
              />
              {dayDrop.open && (
                <div data-dropdown-portal style={{ top: dayDrop.pos.top, left: dayDrop.pos.left }} className="fixed bg-white border border-[#e0e0e0] rounded shadow-lg z-[9999] py-1 min-w-[120px]">
                  {[1, 2, 3, 4, 5, 6, 7].map((n) => (
                    <button
                      key={n}
                      className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1]"
                      onClick={() => { dayDrop.setOpen(false); onViewChange("day"); }}
                    >
                      {n} {n === 1 ? "día" : "días"}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <RibbonBtn
              icon={<IconWorkWeek />}
              label="Semana laboral"
              active={viewMode === "workweek"}
              onClick={() => onViewChange("workweek")}
            />
            <RibbonBtn
              icon={<IconWeek />}
              label="Semana"
              active={viewMode === "week"}
              onClick={() => onViewChange("week")}
            />
            <RibbonBtn
              icon={<IconMonth />}
              label="Mes"
              active={viewMode === "month"}
              onClick={() => onViewChange("month")}
            />
            <RibbonBtn
              icon={<IconSplit />}
              label="Vista en dos paneles"
              active={splitView}
              onClick={() => { setSplitView(!splitView); calToast(splitView ? 'Vista simple activada' : 'Vista en dos paneles activada'); }}
            />
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Organizar</span>
        </div>

        <div className="w-px bg-[#e0e0e0] self-stretch my-[6px] mx-[4px]" />

        {/* Group: Filtrar */}
        <div className="flex flex-col items-center" ref={filterDrop.ref}>
          <div className="relative">
            <RibbonBtn
              icon={<IconFilter />}
              label="Filtrar"
              dropdown
              onClick={() => filterDrop.setOpen(!filterDrop.open)}
              onDropdownClick={() => filterDrop.setOpen(!filterDrop.open)}
            />
            {renderFilterDropdown()}
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Filtrar</span>
        </div>

        <div className="w-px bg-[#e0e0e0] self-stretch my-[6px] mx-[4px]" />

        {/* Group: Compartir */}
        <div className="flex flex-col items-center">
          <div className="flex items-end">
            <RibbonBtn
              icon={<IconShare />}
              label="Compartir calendario"
              onClick={() => {
                const url = `${window.location.origin}/radicale/user/default.ics`;
                navigator.clipboard.writeText(url).then(
                  () => calToast('URL CalDAV copiada al portapapeles: ' + url),
                  () => calToast('URL CalDAV: ' + url)
                );
              }}
            />
            <RibbonBtn
              icon={<IconPrint />}
              label="Imprimir"
              onClick={() => window.print()}
            />
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Compartir</span>
        </div>
      </div>
    );
  }

  function renderTabVer() {
    return (
      <div className="flex items-end h-full">
        {/* Group: Organizar (views) */}
        <div className="flex flex-col items-center">
          <div className="flex items-end">
            <div className="relative" ref={dayDrop.ref}>
              <RibbonBtn
                icon={<IconDay />}
                label="Día"
                active={viewMode === "day"}
                dropdown
                onClick={() => onViewChange("day")}
                onDropdownClick={() => dayDrop.setOpen(!dayDrop.open)}
              />
              {dayDrop.open && (
                <div data-dropdown-portal style={{ top: dayDrop.pos.top, left: dayDrop.pos.left }} className="fixed bg-white border border-[#e0e0e0] rounded shadow-lg z-[9999] py-1 min-w-[120px]">
                  {[1, 2, 3, 4, 5, 6, 7].map((n) => (
                    <button
                      key={n}
                      className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1]"
                      onClick={() => { dayDrop.setOpen(false); onViewChange("day"); }}
                    >
                      {n} {n === 1 ? "día" : "días"}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <RibbonBtn
              icon={<IconWorkWeek />}
              label="Semana laboral"
              active={viewMode === "workweek"}
              onClick={() => onViewChange("workweek")}
            />
            <RibbonBtn
              icon={<IconWeek />}
              label="Semana"
              active={viewMode === "week"}
              onClick={() => onViewChange("week")}
            />
            <RibbonBtn
              icon={<IconMonth />}
              label="Mes"
              active={viewMode === "month"}
              onClick={() => onViewChange("month")}
            />
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Organizar</span>
        </div>

        <div className="w-px bg-[#e0e0e0] self-stretch my-[6px] mx-[4px]" />

        {/* Group: Organizar 2 */}
        <div className="flex flex-col items-center">
          <div className="flex items-end">
            <div className="relative" ref={savedViewsDrop.ref}>
              <RibbonBtn
                icon={<IconSavedViews />}
                label="Vistas guardadas"
                dropdown
                onClick={() => savedViewsDrop.setOpen(!savedViewsDrop.open)}
                onDropdownClick={() => savedViewsDrop.setOpen(!savedViewsDrop.open)}
              />
              {savedViewsDrop.open && (
                <div data-dropdown-portal style={{ top: savedViewsDrop.pos.top, left: savedViewsDrop.pos.left }} className="fixed bg-white border border-[#e0e0e0] rounded shadow-lg z-[9999] py-1 min-w-[200px]">
                  <button
                    className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1]"
                    onClick={() => { savedViewsDrop.setOpen(false); calToast('Vista guardada: ' + viewMode + ' - ' + getLabel()); }}
                  >
                    Guardar vista actual
                  </button>
                </div>
              )}
            </div>
            <RibbonBtn
              icon={<IconSplit />}
              label="Vista en dos paneles"
              active={splitView}
              onClick={() => { setSplitView(!splitView); calToast(splitView ? 'Vista simple activada' : 'Vista en dos paneles activada'); }}
            />
            <div className="relative" ref={timeScaleDrop.ref}>
              <RibbonBtn
                icon={<IconTimescale />}
                label="Escala de tiempo"
                dropdown
                onClick={() => timeScaleDrop.setOpen(!timeScaleDrop.open)}
                onDropdownClick={() => timeScaleDrop.setOpen(!timeScaleDrop.open)}
              />
              {timeScaleDrop.open && (
                <div data-dropdown-portal style={{ top: timeScaleDrop.pos.top, left: timeScaleDrop.pos.left }} className="fixed bg-white border border-[#e0e0e0] rounded shadow-lg z-[9999] py-1 min-w-[160px]">
                  {[
                    { value: "60", label: "60 minutos" },
                    { value: "30", label: "30 minutos" },
                    { value: "15", label: "15 minutos" },
                    { value: "10", label: "10 minutos" },
                    { value: "6", label: "6 minutos" },
                    { value: "5", label: "5 minutos" },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] flex items-center"
                      onClick={() => { setSelectedTimeScale(opt.value); timeScaleDrop.setOpen(false); }}
                    >
                      <span className="w-[18px] inline-block">
                        {selectedTimeScale === opt.value && <IconCheck />}
                      </span>
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Organizar</span>
        </div>

        <div className="w-px bg-[#e0e0e0] self-stretch my-[6px] mx-[4px]" />

        {/* Group: Filtrar */}
        <div className="flex flex-col items-center" ref={filterDrop.ref}>
          <div className="relative">
            <RibbonBtn
              icon={<IconFilter />}
              label="Filtrar"
              dropdown
              onClick={() => filterDrop.setOpen(!filterDrop.open)}
              onDropdownClick={() => filterDrop.setOpen(!filterDrop.open)}
            />
            {renderFilterDropdown()}
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Filtrar</span>
        </div>

        <div className="w-px bg-[#e0e0e0] self-stretch my-[6px] mx-[4px]" />

        {/* Group: Configuración */}
        <div className="flex flex-col items-center">
          <div className="flex items-end">
            <RibbonBtn
              icon={<IconGear />}
              label="Configuración del calendario"
              onClick={() => { window.location.href = '/webmail/settings'; }}
            />
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Configuración</span>
        </div>
      </div>
    );
  }

  function renderTabAyuda() {
    return (
      <div className="flex items-end h-full">
        <div className="flex flex-col items-center">
          <div className="flex items-end">
            <RibbonBtn icon={<IconHelp />} label="Ayuda" onClick={() => {
              calToast('Atajos: Ctrl+N nuevo evento · Ctrl+1 día · Ctrl+2 semana · Ctrl+3 mes · T ir a hoy');
            }} />
            <RibbonBtn icon={<IconRecommend />} label="Recomendaciones" onClick={() => {
              calToast('Tip: Haz clic en cualquier hora del calendario para crear un evento rápido');
            }} />
            <RibbonBtn icon={<IconFeedback />} label="Comentarios" onClick={() => {
              window.open('/webmail/?compose=new&to=gestiontecnologia@maquita.org&subject=Comentario sobre Calendario', '_blank');
            }} />
            <RibbonBtn icon={<IconDiag />} label="Obtener diagnósticos" onClick={() => {
              const info = [
                'Diagnósticos del Calendario',
                '─────────────────────',
                'Navegador: ' + navigator.userAgent.split(' ').pop(),
                'Resolución: ' + window.innerWidth + 'x' + window.innerHeight,
                'Zona horaria: ' + Intl.DateTimeFormat().resolvedOptions().timeZone,
                'Hora local: ' + new Date().toLocaleString('es-EC'),
                'CalDAV: Radicale v3 (127.0.0.1:5232)',
                'Estado: Conectado',
              ].join('\n');
              calToast(info);
            }} />
            <RibbonBtn icon={<IconMobile />} label="Maquita Móvil" onClick={() => {
              calToast('Maquita Móvil: próximamente');
            }} />
          </div>
          <span className="text-[9px] text-[#a19f9d] pb-[3px] mt-[1px]">Ayuda</span>
        </div>
      </div>
    );
  }

  /* ── Filter dropdown (complex, with sub-menus) ──────── */
  function renderFilterDropdown() {
    if (!filterDrop.open) return null;

    const filterCategories = [
      {
        key: "citas" as keyof FilterState,
        label: "Citas",
        hasSub: false,
      },
      {
        key: "reuniones" as keyof FilterState,
        label: "Reuniones",
        hasSub: true,
        subItems: [
          { type: "action", label: "Deseleccionar todo" },
          { type: "header", label: "Soy el organizador:" },
          { type: "item", label: "Enviado" },
          { type: "item", label: "Borrador" },
          { type: "header", label: "Soy un asistente:" },
          { type: "item", label: "Aceptado" },
          { type: "item", label: "Rechazado" },
          { type: "item", label: "Provisional" },
          { type: "item", label: "Cancelado" },
          { type: "item", label: "Sin respuesta" },
        ],
      },
      {
        key: "sondeos" as keyof FilterState,
        label: "Sondeos en espera",
        hasSub: true,
        subItems: [
          { type: "action", label: "Ver todo" },
          { type: "item", label: "Retenciones del organizador" },
          { type: "header", label: "Retenciones de asistentes:" },
          { type: "item", label: "Votó: sí" },
          { type: "item", label: "Votó: no" },
          { type: "item", label: "No votó" },
        ],
      },
      {
        key: "categorias" as keyof FilterState,
        label: "Categorías",
        hasSub: true,
        subItems: [
          { type: "action", label: "Deseleccionar todo" },
          { type: "item", label: "Sin categoría" },
          { type: "item", label: "Categoría roja", color: "#e74c3c" },
          { type: "item", label: "Categoría naranja", color: "#e67e22" },
          { type: "item", label: "Categoría amarilla", color: "#f1c40f" },
          { type: "item", label: "Categoría verde", color: "#2ecc71" },
          { type: "item", label: "Categoría azul", color: "#3498db" },
          { type: "item", label: "Categoría púrpura", color: "#9b59b6" },
        ],
      },
      {
        key: "mostrarComo" as keyof FilterState,
        label: "Mostrar como",
        hasSub: true,
        subItems: [
          { type: "action", label: "Deseleccionar todo" },
          { type: "item", label: "Disponible" },
          { type: "item", label: "Trabajando en otro sitio" },
          { type: "item", label: "Provisional" },
          { type: "item", label: "Ocupado" },
          { type: "item", label: "Fuera de la oficina" },
        ],
      },
      {
        key: "periodicidad" as keyof FilterState,
        label: "Periodicidad",
        hasSub: true,
        subItems: [
          { type: "item", label: "Simples" },
          { type: "item", label: "Serie" },
        ],
      },
      {
        key: "enPersona" as keyof FilterState,
        label: "En persona",
        hasSub: true,
        subItems: [
          { type: "item", label: "Solicitado" },
          { type: "item", label: "No solicitado" },
        ],
      },
    ];

    return (
      <div data-dropdown-portal style={{ top: filterDrop.pos.top, left: filterDrop.pos.left }} className="fixed bg-white border border-[#e0e0e0] rounded shadow-lg z-[9999] py-1 min-w-[220px]">
        {/* Clear filters */}
        <button
          className="w-full text-left px-3 py-[6px] text-[12px] text-[#a4262c] hover:bg-[#f3f2f1] flex items-center gap-[6px]"
          onClick={clearFilters}
        >
          <IconX />
          <span>Borrar filtros</span>
        </button>
        <div className="h-px bg-[#e0e0e0] my-1" />

        {filterCategories.map((cat) => (
          <div
            key={cat.key}
            className="relative"
            onMouseEnter={() => cat.hasSub && setExpandedFilter(cat.key)}
            onMouseLeave={() => setExpandedFilter(null)}
          >
            <button
              className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] flex items-center justify-between"
              onClick={() => !cat.hasSub && toggleFilter(cat.key)}
            >
              <span className="flex items-center gap-[6px]">
                <span
                  className={`w-[14px] h-[14px] border rounded-[2px] flex items-center justify-center text-[10px] ${
                    filterState[cat.key]
                      ? "bg-[#0078d4] border-[#0078d4] text-white"
                      : "border-[#8a8886]"
                  }`}
                >
                  {filterState[cat.key] && "✓"}
                </span>
                {cat.label}
              </span>
              {cat.hasSub && <ChevronRightSmall />}
            </button>

            {/* Sub-menu */}
            {cat.hasSub && expandedFilter === cat.key && (
              <div className="absolute left-full top-0 bg-white border border-[#e0e0e0] rounded shadow-lg z-50 py-1 min-w-[200px]">
                {cat.subItems?.map((sub, idx) => {
                  if (sub.type === "header") {
                    return (
                      <div key={idx} className="px-3 py-[4px] text-[11px] text-[#605e5c] font-semibold">
                        {sub.label}
                      </div>
                    );
                  }
                  if (sub.type === "action") {
                    return (
                      <button
                        key={idx}
                        className="w-full text-left px-3 py-[6px] text-[12px] text-[#0078d4] hover:bg-[#f3f2f1]"
                        onClick={() => calToast(sub.label + ': aplicado')}
                      >
                        {sub.label}
                      </button>
                    );
                  }
                  return (
                    <button
                      key={idx}
                      className="w-full text-left px-3 py-[6px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-[6px]"
                      onClick={() => calToast('Filtro "' + sub.label + '" aplicado')}
                    >
                      <span className="w-[14px] h-[14px] border border-[#0078d4] bg-[#0078d4] rounded-[2px] flex items-center justify-center text-[10px] text-white">
                        ✓
                      </span>
                      {(sub as any).color && (
                        <span
                          className="w-[10px] h-[10px] rounded-full inline-block"
                          style={{ backgroundColor: (sub as any).color }}
                        />
                      )}
                      {sub.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: "inicio", label: "Inicio" },
    { id: "ver", label: "Ver" },
    { id: "ayuda", label: "Ayuda" },
  ];

  return (
    <div className="shrink-0 bg-white select-none relative z-40">
      {/* ── TAB BAR ───────────────────────────────── */}
      <div className="flex items-center h-[32px] border-b border-[#edebe9] px-1">
        {/* Hamburger */}
        <button
          className="flex items-center justify-center w-[32px] h-[32px] hover:bg-[#f3f2f1] rounded-sm"
          onClick={() => window.dispatchEvent(new CustomEvent('toggle-sidebar'))}
        >
          <IconHamburger />
        </button>

        {/* Tabs */}
        <div className="flex items-stretch h-full ml-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-[12px] text-[12px] leading-[32px] relative
                hover:bg-[#f3f2f1] transition-colors
                ${activeTab === tab.id ? "text-[#323130] font-medium" : "text-[#605e5c]"}
              `}
            >
              {tab.label}
              {activeTab === tab.id && (
                <span className="absolute bottom-0 left-[8px] right-[8px] h-[2px] bg-[#0078d4] rounded-t" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── RIBBON CONTENT ────────────────────────── */}
      <div className="border-b border-[#edebe9] overflow-x-auto overflow-y-visible">
        <div className="flex items-stretch min-h-[76px] px-[6px]">
          {activeTab === "inicio" && renderTabInicio()}
          {activeTab === "ver" && renderTabVer()}
          {activeTab === "ayuda" && renderTabAyuda()}
        </div>
      </div>

      {/* ── NAVIGATION BAR ────────────────────────── */}
      <div className="flex items-center gap-[6px] px-[10px] h-[36px] border-b border-[#edebe9]">
        {/* Calendar icon */}
        <span className="text-[#605e5c] flex items-center">
          <IconCalendar />
        </span>

        {/* Hoy button */}
        <button
          onClick={onToday}
          className="px-[10px] h-[26px] text-[13px] font-normal border border-[#8a8886] rounded-[3px] hover:bg-[#f3f2f1] text-[#323130] transition-colors leading-[24px]"
        >
          Hoy
        </button>

        {/* Up/Down stacked arrows */}
        <div className="flex flex-col items-center justify-center -space-y-[2px]">
          <button
            onClick={() => smallStep(-1)}
            className="p-0 text-[#605e5c] hover:text-[#323130] transition-colors h-[14px] flex items-center"
            aria-label="Día anterior"
          >
            <ChevronUp />
          </button>
          <button
            onClick={() => smallStep(1)}
            className="p-0 text-[#605e5c] hover:text-[#323130] transition-colors h-[14px] flex items-center"
            aria-label="Día siguiente"
          >
            <ChevronDownSmall />
          </button>
        </div>

        {/* Left/Right nav */}
        <button
          onClick={() => navigate(-1)}
          className="p-[2px] rounded-sm hover:bg-[#f3f2f1] text-[#605e5c]"
          aria-label="Anterior"
        >
          <ChevronLeft />
        </button>
        <button
          onClick={() => navigate(1)}
          className="p-[2px] rounded-sm hover:bg-[#f3f2f1] text-[#605e5c]"
          aria-label="Siguiente"
        >
          <ChevronRight />
        </button>

        {/* Date label */}
        <h2 className="text-[15px] font-semibold text-[#323130] capitalize flex items-center gap-[4px] cursor-default ml-[2px]">
          {getLabel()}
          <ChevronDown className="w-[12px] h-[12px] text-[#605e5c]" />
        </h2>
      </div>
    </div>
  );
}
