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
import { ChatWindow } from './ChatWindow';
import { useChatStore } from '../store/chatStore';
// ✅ REMOVIDO: useTenantSocket já está conectado globalmente no Layout.tsx
// Chamar aqui novamente cria conexão duplicada e recebe eventos duas vezes

export function ChatPage() {
  const { activeConversation, instanceStatusAlert } = useChatStore();
  const showBanner = instanceStatusAlert && instanceStatusAlert.connection_state !== 'open';

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-[#f0f2f5] dark:bg-gray-900">
      {/* Alerta quando a instância Evolution está conectando ou desconectada */}
      {showBanner && (
        <div className="flex-shrink-0 px-3 py-2 bg-amber-100 dark:bg-amber-900/40 border-b border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1">
            {instanceStatusAlert.connection_state === 'connecting'
              ? 'WhatsApp está conectando… Pode levar alguns segundos. Se demorar, verifique em Configurações.'
              : 'WhatsApp está desconectado. Mensagens podem não ser enviadas nem recebidas. Reconecte em Configurações.'}
          </span>
          <Link
            to="/connections"
            className="flex items-center gap-1 text-amber-800 dark:text-amber-300 font-medium hover:underline"
          >
            <Wifi className="h-4 w-4" />
            Conexões
          </Link>
        </div>
      )}

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
          flex-shrink-0 border-r border-gray-200 dark:border-gray-700 transition-all duration-300 ease-in-out
        `}>
          <ConversationList />
        </div>
        
        {/* Chat window - EXPANDE AO MÁXIMO quando conversa aberta */}
        <div className={`
          ${activeConversation ? 'flex flex-1 animate-slide-in-right' : 'hidden md:flex md:flex-1'}
          min-w-0 max-w-full
        `}>
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}
