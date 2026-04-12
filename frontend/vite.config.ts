import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
// @ts-ignore
import sri from 'vite-plugin-sri'

export default defineConfig({
  plugins: [react(), tailwindcss(), sri()],
  base: '/webmail/',
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
