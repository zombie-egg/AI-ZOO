import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/kiosk/',
  server: {
    port: 4175,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        headers: { 'X-Kiosk-Token': 'local-kiosk-test-token' },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
