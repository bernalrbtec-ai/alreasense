/**
 * Página principal do Flow Chat - Estilo WhatsApp Web
 * Layout tela cheia responsivo (100vh x 100vw)
 */
import React from 'react';
import { DepartmentTabs } from './DepartmentTabs';
import { ConversationList } from './ConversationList';
import { ChatWindow } from './ChatWindow';
import { useChatStore } from '../store/chatStore';
import { useTenantSocket } from '../hooks/useTenantSocket';
import { MessageSquare, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export function ChatPage() {
  const { activeConversation } = useChatStore();
  const navigate = useNavigate();
  
  // 🔌 Conectar WebSocket global do tenant (novas conversas)
  useTenantSocket();
  
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#f0f2f5]">
      {/* Header compacto e responsivo */}
      <div className="flex-shrink-0 bg-[#00a884] px-3 sm:px-4 py-2.5 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-2">
          {/* Botão voltar (mobile) */}
          <button
            onClick={() => navigate('/dashboard')}
            className="md:hidden p-1.5 hover:bg-white/10 rounded-full transition-colors"
            title="Voltar"
          >
            <ArrowLeft className="w-5 h-5 text-white" />
          </button>
          
          <MessageSquare className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
          <h1 className="text-white text-base sm:text-lg font-medium">Flow Chat</h1>
        </div>
        
        {/* Link Dashboard (desktop) */}
        <button
          onClick={() => navigate('/dashboard')}
          className="hidden md:block text-white/90 hover:text-white text-sm px-3 py-1 rounded-lg hover:bg-white/10 transition-colors"
        >
          Dashboard
        </button>
      </div>

      {/* Tabs de departamento - responsivo */}
      <DepartmentTabs />

      {/* Content: Conversations + Chat Window - TELA CHEIA RESPONSIVO */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* Lista de conversas: 
            Mobile: 100% quando não há conversa ativa, oculto quando há
            Desktop: largura fixa responsiva (md:350px lg:380px xl:420px) */}
        <div className={`
          ${activeConversation ? 'hidden md:flex' : 'flex'}
          w-full md:w-[350px] lg:w-[380px] xl:w-[420px]
          flex-shrink-0 border-r border-gray-200
        `}>
          <ConversationList />
        </div>
        
        {/* Chat window: 
            Mobile: 100% quando há conversa, oculto quando não há
            Desktop: flex-1 (ocupa espaço restante) */}
        <div className={`
          ${activeConversation ? 'flex' : 'hidden md:flex'}
          flex-1 min-w-0
        `}>
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
