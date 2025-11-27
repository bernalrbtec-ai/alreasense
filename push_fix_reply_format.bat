@echo off
echo ========================================
echo Fazendo commit e push da correção do formato Reply
echo ========================================
echo.

git add backend/apps/chat/tasks.py
git add ARQUIVOS_COM_CREDENCIAIS_REMOVER.md
git add push_fix_reply_format.bat

echo.
echo Status antes do commit:
git status --short

echo.
echo Fazendo commit...
git commit -m "fix: Corrige formato de Reply (Responder) para Evolution API

- Usa options.quoted com key.remoteJid e key.id (formato correto)
- Inclui textMessage wrapper para mensagens de texto
- Adiciona prefetch_related para attachments na mensagem original
- Melhora logs para debug do formato quoted"

echo.
echo Fazendo push...
git push origin main

echo.
echo ========================================
echo Concluído! Verifique no GitHub se o commit apareceu.
echo ========================================
pause

