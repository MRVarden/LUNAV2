import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { readFileSync, writeFileSync } from 'fs'

const LICENSE_BANNER = `/*! Luna Dashboard v7.0 — CC-BY-NC-4.0 — (c) Varden | https://creativecommons.org/licenses/by-nc/4.0/ */\n`

function licenseBannerPlugin() {
  return {
    name: 'license-banner',
    writeBundle(_options: any, bundle: Record<string, any>) {
      for (const [fileName, chunk] of Object.entries(bundle)) {
        if (chunk.type === 'chunk' && fileName.endsWith('.js')) {
          const filePath = path.resolve(__dirname, 'dist', fileName)
          const content = readFileSync(filePath, 'utf-8')
          writeFileSync(filePath, LICENSE_BANNER + content, 'utf-8')
        }
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), licenseBannerPlugin()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          recharts: ['recharts'],
          'framer-motion': ['framer-motion'],
        },
      },
    },
  },
  server: {
    port: 3618,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8618',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
