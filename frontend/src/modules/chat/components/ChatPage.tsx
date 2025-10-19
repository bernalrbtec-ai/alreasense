/**
 * Página principal do Flow Chat - Estilo WhatsApp Web
 * Usa a sidebar do Layout principal (com retrair/expandir)
 */
import React from 'react';
import { DepartmentTabs } from './DepartmentTabs';
import { ConversationList } from './ConversationList';
import { ChatWindow } from './ChatWindow';
import { useChatStore } from '../store/chatStore';
import { useTenantSocket } from '../hooks/useTenantSocket';

export function ChatPage() {
  const { activeConversation } = useChatStore();
  
  // 🔌 Conectar WebSocket global do tenant (novas conversas)
  useTenantSocket();
  
  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-[#f0f2f5]">
      {/* Tabs de departamento */}
      <DepartmentTabs />

      {/* Content: Conversations + Chat Window - OCUPA TODO ESPAÇO */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* Lista de conversas */}
        <div className={`
          ${activeConversation ? 'hidden lg:flex' : 'flex'}
          w-full lg:w-[380px] xl:w-[420px]
          flex-shrink-0 border-r border-gray-200
        `}>
          <ConversationList />
        </div>
        
        {/* Chat window - EXPANDE PARA OCUPAR TODO ESPAÇO DISPONÍVEL */}
        <div className={`
          ${activeConversation ? 'flex' : 'hidden lg:flex'}
          flex-1 min-w-0
        `}>
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
