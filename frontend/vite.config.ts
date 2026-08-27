import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// Built dist is served by the OqlOS FastAPI app under /ui (StaticFiles mount).
// Hardware control still flows through /api/v3/hardware/* → OQL-over-MQTT → boardnet (.122).
export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  resolve: {
    alias: [
      // Vendored copy of the c2004 @semcod/hardware-client path constants (subpath first).
      {
        find: '@semcod/hardware-client/paths.js',
        replacement: fileURLToPath(new URL('./vendor/hardware-client/paths.js', import.meta.url)),
      },
      {
        find: '@semcod/hardware-client',
        replacement: fileURLToPath(new URL('./vendor/hardware-client/index.js', import.meta.url)),
      },
    ],
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
  server: {
    port: 3010,
    host: '0.0.0.0',
  },
});
