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
        replacement: fileURLToPath(new URL('./vendor/hardware-client/paths.ts', import.meta.url)),
      },
      {
        find: '@semcod/hardware-client',
        replacement: fileURLToPath(new URL('./vendor/hardware-client/index.ts', import.meta.url)),
      },
      // Monorepo SSOT (c2004/packages/*). Build OqlOS UI from the c2004 tree so
      // this resolves; BoardNet deploy ships built dist only.
      {
        find: '@semcod/frontend-services',
        replacement: fileURLToPath(
          new URL('../../../packages/frontend-services/src', import.meta.url),
        ),
      },
      {
        find: '@semcod/ts-utils/rbac.policy',
        replacement: fileURLToPath(
          new URL('../../../packages/ts-utils/src/rbac.policy.ts', import.meta.url),
        ),
      },
      {
        find: '@semcod/ts-utils',
        replacement: fileURLToPath(
          new URL('../../../packages/ts-utils/src', import.meta.url),
        ),
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
