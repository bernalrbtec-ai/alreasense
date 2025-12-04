@echo off
echo Limpando todos os caches do projeto...

echo.
echo [1/5] Limpando node_modules/.vite...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo ✅ Cache do Vite limpo
) else (
    echo ⚠️ Pasta node_modules/.vite não encontrada
)

echo.
echo [2/5] Limpando dist...
if exist "dist" (
    rmdir /s /q "dist"
    echo ✅ Pasta dist limpa
) else (
    echo ⚠️ Pasta dist não encontrada
)

echo.
echo [3/5] Limpando .vite no diretório raiz...
if exist ".vite" (
    rmdir /s /q ".vite"
    echo ✅ Cache .vite limpo
) else (
    echo ⚠️ Pasta .vite não encontrada
)

echo.
echo [4/5] Limpando cache do npm...
call npm cache clean --force
echo ✅ Cache do npm limpo

echo.
echo [5/5] Reinstalando dependências...
call npm install
echo ✅ Dependências reinstaladas

echo.
echo ========================================
echo ✅ LIMPEZA COMPLETA!
echo ========================================
echo.
echo Agora execute: npm run dev
echo.
pause

