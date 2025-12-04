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
    // ✅ CORREÇÃO: Reativar minificação de forma conservadora
    // Mantém minifyIdentifiers: false para evitar renomeação de variáveis
    minify: 'esbuild',
    esbuild: {
      // ✅ CRÍTICO: Desabilitar minificação de identificadores para evitar conflitos
      // Isso previne que variáveis sejam renomeadas para letras únicas (c, u, m, etc.)
      minifyIdentifiers: false,
      // Manter minificação de sintaxe e espaços (reduz tamanho sem renomear variáveis)
      minifySyntax: true,
      minifyWhitespace: true,
      // Manter nomes de funções e classes para facilitar debug
      keepNames: true,
    },
    rollupOptions: {
      output: {
        // Manter nomes de funções e variáveis mais legíveis
        manualChunks: undefined,
      },
    },
  },
})
