import { useState, useEffect, useCallback } from "react";

export type Breakpoint = "mobile" | "tablet" | "desktop";

const MOBILE_MAX = 768;
const TABLET_MAX = 1024;

function getBreakpoint(w: number): Breakpoint {
  if (w < MOBILE_MAX) return "mobile";
  if (w < TABLET_MAX) return "tablet";
  return "desktop";
}

export function useResponsive() {
  const [bp, setBp] = useState<Breakpoint>(() => getBreakpoint(window.innerWidth));
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const onResize = () => {
      const next = getBreakpoint(window.innerWidth);
      setBp(prev => {
        if (prev !== next) {
          // Close drawer when switching to desktop
          if (next === "desktop") setDrawerOpen(false);
          return next;
        }
        return prev;
      });
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const toggleDrawer = useCallback(() => setDrawerOpen(prev => !prev), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  return {
    breakpoint: bp,
    isMobile: bp === "mobile",
    isTablet: bp === "tablet",
    isDesktop: bp === "desktop",
    drawerOpen,
    toggleDrawer,
    closeDrawer,
  };
}
