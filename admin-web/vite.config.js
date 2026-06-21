import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }
  },
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true }, // Windows/Docker 卷挂载下 HMR 生效
    proxy: {
      // 联调：/api 转发到 FastAPI 后端（Docker 内用 host.docker.internal）
      '/api': { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true }
    }
  }
})
