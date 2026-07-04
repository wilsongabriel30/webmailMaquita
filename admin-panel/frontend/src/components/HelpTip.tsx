import { useEffect } from "react";

/*
 * Motor global de ayudas contextuales (mismo patrón que las tarjetas de ayuda
 * de FARO): cualquier elemento con atributo title= (o data-help=) muestra una
 * tarjeta flotante estilizada al pasar el mouse o al recibir foco con teclado.
 * El title nativo se convierte a data-help en el primer hover para suprimir
 * el tooltip del navegador. Se monta UNA sola vez en App.tsx.
 */

const STYLE = `
#helpTip { position: fixed; z-index: 9999; width: max-content; max-width: min(340px, 86vw);
  background: #fff; border: 1px solid #bee3f8; border-left: 4px solid #0078d4; border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,97,161,0.22); padding: 0.55rem 0.75rem; pointer-events: none;
  opacity: 0; transform: translateY(-3px); transition: opacity 0.15s ease, transform 0.15s ease; }
#helpTip.visible { opacity: 1; transform: translateY(0); }
#helpTip .help-tip-text { font-size: 0.78rem; color: #4a5568; line-height: 1.45; white-space: pre-line; }
@media (prefers-color-scheme: dark) {
  #helpTip { background: #fff; }
}`;

export function HelpTip() {
  useEffect(() => {
    if (document.getElementById("helpTip")) return;

    const style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);

    const tip = document.createElement("div");
    tip.id = "helpTip";
    tip.setAttribute("role", "tooltip");
    tip.innerHTML = '<div class="help-tip-text"></div>';
    document.body.appendChild(tip);

    let current: HTMLElement | null = null;

    const show = (el: HTMLElement, text: string) => {
      current = el;
      (tip.querySelector(".help-tip-text") as HTMLElement).textContent = text;
      const r = el.getBoundingClientRect();
      tip.classList.remove("visible");
      tip.style.left = "0px";
      tip.style.top = "0px";
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      const x = Math.min(Math.max(8, r.left), window.innerWidth - tw - 8);
      let y = r.bottom + 8;
      if (y + th > window.innerHeight - 8) y = r.top - th - 8; // arriba si no cabe abajo
      if (y < 8) y = 8;
      tip.style.left = x + "px";
      tip.style.top = y + "px";
      tip.classList.add("visible");
    };

    const hide = () => {
      current = null;
      tip.classList.remove("visible");
    };

    const onOver = (e: Event) => {
      let el = e.target as HTMLElement | null;
      // Subir por el DOM buscando title= o data-help= (los iconos internos de
      // un botón disparan el evento, pero la ayuda vive en el botón).
      while (el && el !== document.body && el.getAttribute) {
        const title = el.getAttribute("title");
        if (title) {
          el.dataset.help = title;
          el.removeAttribute("title"); // suprime el tooltip nativo del navegador
        }
        if (el.dataset && el.dataset.help) {
          if (current !== el) show(el, el.dataset.help);
          return;
        }
        el = el.parentElement;
      }
      if (current) hide();
    };

    const onHide = () => { if (current) hide(); };

    document.addEventListener("mouseover", onOver, true);
    document.addEventListener("focusin", onOver, true);
    document.addEventListener("scroll", onHide, true);
    document.addEventListener("click", onHide, true);

    return () => {
      document.removeEventListener("mouseover", onOver, true);
      document.removeEventListener("focusin", onOver, true);
      document.removeEventListener("scroll", onHide, true);
      document.removeEventListener("click", onHide, true);
      tip.remove();
      style.remove();
    };
  }, []);

  return null;
}
