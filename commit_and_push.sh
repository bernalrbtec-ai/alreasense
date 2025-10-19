#!/bin/bash

echo "🚀 Fazendo commit e push..."

git add -A

git commit -m "feat(chat): redesenhar completamente estilo WhatsApp Web com modo claro e fotos de perfil

- Backend: adicionar campo profile_pic_url no modelo Conversation
- Backend: webhook salva foto de perfil automaticamente
- Frontend: modo claro estilo WhatsApp Web (#f0f2f5, #d9fdd3, etc)
- Frontend: ChatPage redesenhado com tela cheia
- Frontend: DepartmentTabs com Inbox em destaque
- Frontend: ConversationList com fotos de perfil dos contatos
- Frontend: ChatWindow com header estilo WhatsApp
- Frontend: MessageList com bolhas verdes/brancas
- Frontend: MessageInput com botões de emoji e anexo
- Frontend: Status de mensagens com ícones (✓, ✓✓, ✓✓ azul)
- Frontend: Avatar com fallback se foto não carregar
- Frontend: Tela cheia aproveitando todo espaço
- SQL: script para adicionar campo profile_pic_url"

git push

echo "✅ Push concluído!"

