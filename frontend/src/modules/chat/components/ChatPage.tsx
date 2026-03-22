/**
 * Página principal do Flow Chat - Estilo WhatsApp Web
 * Usa a sidebar do Layout principal (com retrair/expandir)
 * WebSocket do tenant conecta no Layout (global) - NÃO precisa chamar aqui novamente
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, Wifi } from 'lucide-react';
import { DepartmentTabs } from './DepartmentTabs';
import { ConversationList } from './ConversationList';
import { ChatConversationSidebarWrapper } from './ChatConversationSidebarWrapper';
import { ChatWindow } from './ChatWindow';
import { useChatStore } from '../store/chatStore';
// ✅ REMOVIDO: useTenantSocket já está conectado globalmente no Layout.tsx
// Chamar aqui novamente cria conexão duplicada e recebe eventos duas vezes

export function ChatPage() {
  const { activeConversation, instanceStatusAlert } = useChatStore();
  const connectionState = instanceStatusAlert?.connection_state ?? '';
  const showBanner = instanceStatusAlert && connectionState !== 'open' && connectionState !== '';

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-chat-bg dark:bg-gray-900">
      {/* Aviso bem visível quando WhatsApp está conectando ou desconectado */}
      {showBanner && instanceStatusAlert && (
        <div
          className={`flex-shrink-0 w-full px-4 py-4 border-b-4 flex items-center gap-4 ${
            connectionState === 'connecting'
              ? 'bg-amber-50 dark:bg-amber-950/50 border-amber-500 text-amber-900 dark:text-amber-100'
              : 'bg-red-50 dark:bg-red-950/50 border-red-500 text-red-900 dark:text-red-100'
          }`}
        >
          <AlertCircle className="h-10 w-10 flex-shrink-0 opacity-90" />
          <div className="flex-1 min-w-0">
            <p className="text-lg font-semibold leading-tight">
              {connectionState === 'connecting'
                ? 'WhatsApp está conectando'
                : 'WhatsApp está desconectado'}
            </p>
            <p className="mt-1 text-base">
              {connectionState === 'connecting'
                ? 'Pode levar alguns segundos. Se demorar, use Verificar Status em Conexões.'
                : 'Mensagens podem não ser enviadas nem recebidas. Reconecte em Conexões ou use Verificar Status.'}
            </p>
          </div>
          <Link
            to="/connections"
            className="flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-lg font-semibold bg-white/80 dark:bg-black/30 hover:bg-white dark:hover:bg-black/50 border-2 border-current shadow-sm transition-colors"
          >
            <Wifi className="h-5 w-5" />
            Ir para Conexões
          </Link>
        </div>
      )}

      {/* Tabs de departamento */}
      <DepartmentTabs />

      {/* Content: Conversations + Chat Window - OCUPA TODO ESPAÇO */}
      {/* Sem overflow-hidden aqui: o menu ⋮ do header abre para a esquerda e não pode ser cortado pela lista */}
      <div className="flex flex-1 min-h-0">
        {/* Lista de conversas - MINIMIZADA quando conversa está aberta */}
        <div
          data-chat-conversation-list
          className={`
          ${activeConversation 
            ? 'hidden md:flex md:w-[280px] lg:w-[300px]' 
            : 'flex w-full md:w-[340px] lg:w-[360px]'
          }
          flex-shrink-0 border-r border-gray-200 dark:border-gray-700 transition-all duration-300 ease-in-out
          relative z-0
        `}>
          {import.meta.env.VITE_CHAT_UI_V2 !== 'false' ? (
            <ChatConversationSidebarWrapper />
          ) : (
            <ConversationList />
          )}
        </div>
        
        {/* Chat window - EXPANDE AO MÁXIMO quando conversa aberta; z-10 para dropdown do header sobrepor a lista */}
        <div className={`
          ${activeConversation ? 'flex flex-1 animate-slide-in-right' : 'hidden md:flex md:flex-1'}
          min-w-0 max-w-full relative z-10
        `}>
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
