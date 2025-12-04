import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
  },
  preview: {
    host: '0.0.0.0',
    port: 80,
    allowedHosts: 'all',
  },
  build: {
    // ✅ CORREÇÃO: Configurar minificação para evitar conflitos de nomes de variáveis
    minify: 'esbuild',
    esbuild: {
      // Manter nomes de variáveis mais descritivos durante minificação
      // Isso ajuda a evitar conflitos de inicialização
      keepNames: true,
      // ✅ CORREÇÃO CRÍTICA: Desabilitar minificação de nomes de variáveis locais
      // Isso previne que variáveis sejam renomeadas para letras únicas
      minifyIdentifiers: false,
      minifySyntax: true,
      minifyWhitespace: true,
    },
    rollupOptions: {
      output: {
        // Manter nomes de funções e variáveis mais legíveis
        manualChunks: undefined,
      },
    },
  },
})
