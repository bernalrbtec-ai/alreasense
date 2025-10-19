/**
 * Página principal do Flow Chat
 */
import React from 'react';
import { DepartmentTabs } from './DepartmentTabs';
import { ConversationList } from './ConversationList';
import { ChatWindow } from './ChatWindow';
import { MessageSquare } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useTenantSocket } from '../hooks/useTenantSocket';

export function ChatPage() {
  const { activeConversation } = useChatStore();
  
  // 🔌 Conectar WebSocket global do tenant (novas conversas)
  useTenantSocket();
  
  return (
    <div className="flex flex-col h-screen bg-[#0e1115]">
      {/* Header com Logo + Departamentos */}
      <div className="flex-shrink-0">
        <div className="flex items-center gap-3 px-4 md:px-6 py-4 bg-[#1f262e] border-b border-gray-800">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 md:w-6 md:h-6 text-green-500" />
            <h1 className="text-lg md:text-xl font-bold text-white">Flow Chat</h1>
          </div>
        </div>
        
        <DepartmentTabs />
      </div>

      {/* Content: Conversations + Chat Window */}
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

