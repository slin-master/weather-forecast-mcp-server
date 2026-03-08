import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    emptyOutDir: true,
    outDir: '../src/weather_forecast_mcp_server/ui',
    rollupOptions: {
      input: resolve(__dirname, 'index.html'),
      output: {
        entryFileNames: 'weather_dashboard.js',
        assetFileNames: 'weather_dashboard.[ext]'
      }
    }
  }
});
