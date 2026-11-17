import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Matches a node_modules path of any of the given packages on both / and \ separators.
const pkg = (names: string) => new RegExp(`node_modules[/\\\\](${names})`);

// Dev server on 127.0.0.1:5173 (spec 5.4) with strictPort, so a port already used by another local
// app fails loudly instead of silently splitting "localhost" between IPv4 and IPv6 (PLAN.md A-49).
// Use another port with: npm run dev -- --port 5174. /api is proxied to the FastAPI backend.
// Vendor chunks: the UI kit and the framework/data libs are cached separately from app code,
// which keeps every chunk under the size warning without raising the limit.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'vendor-fluent-a', test: pkg('@fluentui[/\\\\]react-[a-d]'), priority: 30 },
            { name: 'vendor-fluent-m', test: pkg('@fluentui[/\\\\]react-[e-m]'), priority: 30 },
            { name: 'vendor-fluent-b', test: pkg('@fluentui[/\\\\]react-[n-z]'), priority: 30 },
            {
              name: 'vendor-fluent-base',
              test: pkg('@fluentui|@griffel|@floating-ui'),
              priority: 20,
            },
            {
              name: 'vendor-react',
              test: pkg(
                'react[/\\\\]|react-dom[/\\\\]|react-router[/\\\\]|scheduler[/\\\\]|@tanstack',
              ),
              priority: 10,
            },
          ],
        },
      },
    },
  },
});
