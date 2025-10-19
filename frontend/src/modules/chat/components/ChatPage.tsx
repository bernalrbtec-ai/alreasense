/**
 * Página principal do Flow Chat - Estilo WhatsApp Web
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
    <div className="flex flex-col h-screen bg-[#f0f2f5]">
      {/* Header compacto */}
      <div className="flex-shrink-0 bg-[#00a884] px-4 py-2">
        <h1 className="text-white text-lg font-medium">Flow Chat</h1>
      </div>

      {/* Tabs de departamento */}
      <DepartmentTabs />

      {/* Content: Conversations + Chat Window - TELA CHEIA */}
      <div className="flex flex-1 overflow-hidden">
        {/* Lista de conversas: oculta no mobile quando há conversa ativa */}
        <div className={`${activeConversation ? 'hidden md:flex' : 'flex'}`}>
          <ConversationList />
        </div>
        
        {/* Chat window: oculta no mobile quando NÃO há conversa ativa */}
        <div className={`flex-1 ${activeConversation ? 'flex' : 'hidden md:flex'}`}>
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
