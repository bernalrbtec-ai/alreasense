#!/bin/bash

echo "Limpando todos os caches do projeto..."

echo ""
echo "[1/5] Limpando node_modules/.vite..."
if [ -d "node_modules/.vite" ]; then
    rm -rf "node_modules/.vite"
    echo "✅ Cache do Vite limpo"
else
    echo "⚠️ Pasta node_modules/.vite não encontrada"
fi

echo ""
echo "[2/5] Limpando dist..."
if [ -d "dist" ]; then
    rm -rf "dist"
    echo "✅ Pasta dist limpa"
else
    echo "⚠️ Pasta dist não encontrada"
fi

echo ""
echo "[3/5] Limpando .vite no diretório raiz..."
if [ -d ".vite" ]; then
    rm -rf ".vite"
    echo "✅ Cache .vite limpo"
else
    echo "⚠️ Pasta .vite não encontrada"
fi

echo ""
echo "[4/5] Limpando cache do npm..."
npm cache clean --force
echo "✅ Cache do npm limpo"

echo ""
echo "[5/5] Reinstalando dependências..."
npm install
echo "✅ Dependências reinstaladas"

echo ""
echo "========================================"
echo "✅ LIMPEZA COMPLETA!"
echo "========================================"
echo ""
echo "Agora execute: npm run dev"
echo ""

