@echo off
echo ========================================
echo Fazendo commit e push da funcionalidade de Responder mensagens
echo ========================================
echo.

git add frontend/src/modules/chat/components/MessageInput.tsx
git add frontend/src/modules/chat/components/MessageList.tsx
git add backend/apps/chat/tasks.py
git add backend/apps/chat/webhooks.py

echo.
echo Status antes do commit:
git status --short

echo.
echo Fazendo commit...
git commit -m "feat: Implementa funcionalidade completa de Responder mensagens (Reply)

- Frontend: Preview visual no MessageInput quando respondendo
- Frontend: Melhorias no preview no MessageList (scroll, truncamento, tipos de anexo)
- Backend: Suporte a reply_to ao enviar para Evolution API (quotedMessageId)
- Backend: Processa contextInfo.quotedMessage ao receber do WhatsApp
- Backend: Busca e salva referência da mensagem original no metadata.reply_to
- Funciona tanto para envio quanto recebimento de mensagens"

echo.
echo Fazendo push...
git push origin main

echo.
echo ========================================
echo Concluído! Verifique no GitHub se o commit apareceu.
echo ========================================
pause


