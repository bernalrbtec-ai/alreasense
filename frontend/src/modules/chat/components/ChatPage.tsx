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
        {/* Lista de conversas - REDUZIDA para dar mais espaço ao chat */}
        <div className={`
          ${activeConversation ? 'hidden lg:flex' : 'flex'}
          w-full lg:w-[320px] xl:w-[360px]
          flex-shrink-0 border-r border-gray-200
        `}>
          <ConversationList />
        </div>
        
        {/* Chat window - EXPANDE AO MÁXIMO (flex-1 = todo espaço restante) */}
        <div className={`
          ${activeConversation ? 'flex' : 'hidden lg:flex'}
          flex-1 min-w-0 max-w-full
        `}>
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
