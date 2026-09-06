import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const devApiTarget = process.env.VITE_DEV_API_PROXY_TARGET || 'http://127.0.0.1:8080'

export default defineConfig({
  plugins: [vue()],
  base: '/kiosk/',
  server: {
    port: 4175,
    strictPort: true,
    proxy: {
      '/api': {
        target: devApiTarget,
        changeOrigin: true,
        headers: { 'X-Kiosk-Token': 'local-kiosk-test-token' },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
