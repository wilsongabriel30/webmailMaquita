import { useState, useRef } from "react";
import type { CalendarEvent } from "./types/calendar";
import { formatTime } from "./utils/dateHelpers";

interface Props {
  event: CalendarEvent;
  onClick: (event: CalendarEvent) => void;
  compact?: boolean;
  style?: React.CSSProperties;
}

const RecurrenceIcon = ({ size = 10, color = "#605e5c" }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill={color} style={{ flexShrink: 0 }}>
    <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
    <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
  </svg>
);

export function EventCard({ event, onClick, compact, style }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const color = event.color || "#0078d4";
  const isRecurrent = !!event.rrule;

  const lightBg = (hex: string): string => {
    const num = parseInt(hex.replace("#", ""), 16);
    const r = (num >> 16) & 0xff;
    const g = (num >> 8) & 0xff;
    const b = num & 0xff;
    const lr = Math.round(r + (255 - r) * 0.9);
    const lg = Math.round(g + (255 - g) * 0.9);
    const lb = Math.round(b + (255 - b) * 0.9);
    return `rgb(${lr},${lg},${lb})`;
  };

  if (compact) {
    return (
      <div
        ref={ref}
        onClick={(e) => {
          e.stopPropagation();
          onClick(event);
        }}
        onMouseEnter={() => { setShowTooltip(true); setTimeout(() => setShowTooltip(false), 4000); }}
        onMouseLeave={() => setShowTooltip(false)}
        style={{
          borderLeft: `3px solid ${color}`,
          backgroundColor: lightBg(color),
          borderRadius: "4px",
          cursor: "pointer",
          padding: "1px 6px",
          height: "20px",
          display: "flex",
          alignItems: "center",
          overflow: "hidden",
          transition: "filter 150ms ease",
          fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
          position: "relative",
          ...style,
        }}
        className="outlook-pill-hover"
      >
        <span style={{ display: "flex", alignItems: "center", gap: "4px", overflow: "hidden", width: "100%" }}>
          {isRecurrent && <RecurrenceIcon size={10} color="#605e5c" />}
          {!event.all_day && (
            <span style={{ fontSize: "11px", fontWeight: 600, color: "#323130", whiteSpace: "nowrap", flexShrink: 0 }}>
              {formatTime(event.dtstart)}
            </span>
          )}
          <span style={{ fontSize: "11px", color: "#323130", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {event.summary}
          </span>
        </span>
        {showTooltip && <EventTooltip event={event} color={color} />}
      </div>
    );
  }

  // Week/Day view: SOLID filled block, white text
  return (
    <div
      ref={ref}
      onClick={(e) => {
        e.stopPropagation();
        onClick(event);
      }}
      onMouseEnter={() => { setShowTooltip(true); setTimeout(() => setShowTooltip(false), 4000); }}
      onMouseLeave={() => setShowTooltip(false)}
      style={{
        backgroundColor: color,
        borderRadius: "4px",
        cursor: "pointer",
        overflow: "hidden",
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: "20px",
        transition: "filter 150ms ease",
        fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
        ...style,
      }}
      className="outlook-block-hover"
    >
      <div style={{ padding: "4px 6px", display: "flex", flexDirection: "column", gap: "1px", height: "100%", overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          {isRecurrent && <RecurrenceIcon size={10} color="rgba(255,255,255,0.85)" />}
          {!event.all_day && (
            <span style={{ fontSize: "12px", color: "rgba(255,255,255,0.9)", fontWeight: 400, lineHeight: 1.3, whiteSpace: "nowrap" }}>
              {formatTime(event.dtstart)} - {formatTime(event.dtend)}
            </span>
          )}
        </div>
        <span style={{ fontSize: "12px", fontWeight: 600, color: "#fff", lineHeight: 1.3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {event.summary}
        </span>
      </div>
      {showTooltip && <EventTooltip event={event} color={color} />}
    </div>
  );
}

function EventTooltip({ event, color }: { event: CalendarEvent; color: string }) {
  return (
    <div
      style={{
        position: "absolute",
        zIndex: 50,
        left: 0,
        top: "100%",
        marginTop: "4px",
        background: "#fff",
        border: "1px solid #edebe9",
        borderRadius: "6px",
        boxShadow: "0 8px 24px rgba(0,0,0,0.14)",
        padding: "12px",
        minWidth: "220px",
        maxWidth: "300px",
        pointerEvents: "none",
        fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      <div style={{ borderLeft: `3px solid ${color}`, paddingLeft: "8px", marginBottom: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "4px", marginBottom: "2px" }}>
          {event.rrule && (
            <svg width="12" height="12" viewBox="0 0 16 16" fill="#605e5c">
              <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
              <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
            </svg>
          )}
          <p style={{ fontSize: "14px", fontWeight: 600, color: "#323130", margin: 0 }}>{event.summary}</p>
        </div>
        <p style={{ fontSize: "12px", color: "#605e5c", margin: 0 }}>
          {formatTime(event.dtstart)} - {formatTime(event.dtend)}
        </p>
      </div>
      {event.rrule && (
        <p style={{ fontSize: "11px", color: "#0078d4", margin: "0 0 6px 0", display: "flex", alignItems: "center", gap: "4px" }}>
          <svg width="11" height="11" viewBox="0 0 16 16" fill="#0078d4">
            <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
            <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
          </svg>
          Evento recurrente
        </p>
      )}
      {event.location && (
        <p style={{ fontSize: "12px", color: "#605e5c", margin: "0 0 6px 0", display: "flex", alignItems: "center", gap: "4px" }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          {event.location}
        </p>
      )}
      {event.calendar_name && (
        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "#a19f9d" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: color, flexShrink: 0 }} />
          <span>{event.calendar_name}</span>
        </div>
      )}
    </div>
  );
}
