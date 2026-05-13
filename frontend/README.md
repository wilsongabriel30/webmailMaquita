# Maquita Webmail — Frontend

Interfaz web tipo Outlook construida con React 19, TypeScript y Vite 6.

## Stack

- **React 19** con TypeScript
- **Vite 6** (build + HMR)
- **TailwindCSS 4** para estilos
- **TipTap** como editor de correo (tablas, imagenes, firmas HTML)
- **Zustand** para estado global
- **React Router 7** para navegacion
- **DOMPurify** para sanitizar HTML de correos

## Desarrollo

```bash
npm ci
npm run dev
```

Abre http://localhost:5173 — el proxy a la API backend esta configurado en `vite.config.ts`.

## Build

```bash
npm run build
```

Produce la carpeta `dist/` lista para servir con Nginx.

## Lint

```bash
npx eslint .
```

## Estructura

```
src/
├── components/    # Componentes reutilizables
├── pages/         # Vistas principales (Inbox, Compose, Calendar, etc.)
├── stores/        # Estado global (Zustand)
├── services/      # Llamadas API
├── hooks/         # Hooks personalizados
├── types/         # Tipos TypeScript
└── utils/         # Utilidades
```

## Notas

- El frontend se comunica con el backend FastAPI en `/api/`
- Los correos HTML se renderizan con sanitizacion DOMPurify
- PWA habilitada via Service Worker
- Atajos de teclado y paleta de comandos (Ctrl+K)
