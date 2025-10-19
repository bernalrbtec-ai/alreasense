/**
 * Página principal do Flow Chat - Estilo WhatsApp Web
 * Usa a sidebar do Layout principal (com retrair/expandir)
 * WebSocket do tenant conecta no Layout (global)
 */
import React from 'react';
import { DepartmentTabs } from './DepartmentTabs';
import { ConversationList } from './ConversationList';
import { ChatWindow } from './ChatWindow';
import { useChatStore } from '../store/chatStore';

export function ChatPage() {
  const { activeConversation } = useChatStore();
  
  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-[#f0f2f5]">
      {/* Tabs de departamento */}
      <DepartmentTabs />

      {/* Content: Conversations + Chat Window - OCUPA TODO ESPAÇO */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* Lista de conversas - MINIMIZADA quando conversa está aberta */}
        <div className={`
          ${activeConversation 
            ? 'hidden md:flex md:w-[280px] lg:w-[300px]' 
            : 'flex w-full md:w-[340px] lg:w-[360px]'
          }
          flex-shrink-0 border-r border-gray-200 transition-all duration-300
        `}>
          <ConversationList />
        </div>
        
        {/* Chat window - EXPANDE AO MÁXIMO quando conversa aberta */}
        <div className={`
          ${activeConversation ? 'flex flex-1' : 'hidden md:flex md:flex-1'}
          min-w-0 max-w-full
        `}>
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
