// ===========================================================================
// IMPORTANTE: base: '/webmail/' es CRÍTICO para el funcionamiento.
// NO CAMBIAR base sin actualizar nginx (sites-enabled/mail.example.org).
// Deploy: usar /opt/maquita-webmail/deploy-webmail.sh
// Los archivos compilados van en: /opt/maquita-webmail/www/webmail/
// NUNCA copiar dist/* directo a www/ — debe ser a www/webmail/
// ===========================================================================
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
// @ts-expect-error -- el paquete no publica tipos
import sri from 'vite-plugin-sri'
// Color de acento personalizable (Configuración → Apariencia): ver complementos/acento/tonos.ts
import { acentoEnCss, acentoEnLinea } from './complementos/acento/index.ts'
// Versión instalada para «Obtener diagnósticos» (git describe al compilar): ver complementos/version
import { versionInstalada } from './complementos/version/index.ts'

export default defineConfig({
  plugins: [acentoEnLinea(), react(), tailwindcss(), sri()],
  css: { postcss: { plugins: [acentoEnCss()] } },
  base: '/webmail/',
  define: { __VERSION_INSTALADA__: JSON.stringify(versionInstalada()) },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/')) {
            return 'vendor-react';
          }
          if (id.includes('node_modules/@tiptap')) {
            return 'vendor-tiptap';
          }
          if (id.includes('node_modules/date-fns') || id.includes('node_modules/zustand')) {
            return 'vendor-utils';
          }
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3')) {
            return 'vendor-charts';
          }
          if (id.includes('node_modules/lucide-react')) {
            return 'vendor-icons';
          }
        },
      },
    },
  },
})
