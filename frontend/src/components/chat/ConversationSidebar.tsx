/**
 * Sidebar de conversas (presentacional).
 * Lista simples (sem virtualização) com avatar (foto ou iniciais), preview, tempo, badge unread.
 * Mantemos a lista sem virtualização por estabilidade em todos os browsers/tenants.
 */

import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Search, Plus } from 'lucide-react';
import type { ConversationSidebarConversation } from './adapters';
import { formatTimeAgo } from '@/utils/formatTime';

function getMediaProxyUrl(externalUrl: string): string {
  const API_BASE_URL = (import.meta as unknown as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
}

export interface ConversationSidebarProps {
  conversations: ConversationSidebarConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  /** Opcional: controle de busca pelo wrapper */
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  /** Opcional: exibe botão Nova conversa ao lado da busca */
  onNewConversation?: () => void;
}

export function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'Buscar ou iniciar conversa',
  onNewConversation,
}: ConversationSidebarProps) {
  const [failedImageIds, setFailedImageIds] = useState<Set<string>>(() => new Set());

  const handleAvatarError = useCallback((id: string) => {
    setFailedImageIds((prev) => new Set(prev).add(id));
  }, []);

  return (
    <div className="flex flex-col h-full w-full bg-white dark:bg-gray-800">
      {(onSearchChange || onNewConversation) && (
        <div className="flex-shrink-0 flex items-center gap-2 p-2 sm:p-3 border-b border-gray-200 dark:border-gray-700">
          {onSearchChange && (
            <div className="flex-1 relative min-w-0">
              <Search className="absolute left-2 sm:left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" aria-hidden />
              <input
                type="search"
                aria-label="Buscar conversas ou contatos"
                placeholder={searchPlaceholder}
                value={searchValue}
                onChange={(e) => onSearchChange(e.target.value)}
                className="w-full pl-8 sm:pl-10 pr-3 py-2 bg-chat-sidebar dark:bg-gray-800 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-chat-ring focus:bg-white dark:focus:bg-gray-700 transition-colors text-gray-900 dark:text-white"
              />
            </div>
          )}
          {onNewConversation && (
            <button
              type="button"
              aria-label="Nova conversa"
              onClick={onNewConversation}
              className="flex-shrink-0 p-2 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md"
              title="Nova conversa"
            >
              <Plus className="w-5 h-5 text-gray-600 dark:text-gray-400" aria-hidden />
            </button>
          )}
        </div>
      )}

      <div
        className="flex-1 overflow-y-auto custom-scrollbar min-h-0"
        aria-label="Lista de conversas"
      >
        <div className="flex flex-col">
          {conversations.map((item) => {
            const isActive = activeId !== null && String(item.id) === String(activeId);

            return (
              <motion.div
                key={item.id}
                role="button"
                tabIndex={0}
                onClick={() => onSelect(item.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect(item.id);
                  }
                }}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15 }}
                className={`
                  w-full flex items-center gap-2 sm:gap-3 px-3 sm:px-4 flex-shrink-0
                  hover:bg-chat-sidebar dark:hover:bg-gray-700 active:scale-[0.99]
                  transition-colors duration-150 ease-out transition-transform
                  border-b border-gray-100 dark:border-gray-700
                  cursor-pointer
                  min-h-[72px]
                  ${isActive ? 'bg-chat-sidebar dark:bg-gray-700 ring-inset ring-2 ring-chat-ring' : ''}
                `}
              >
                <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-white font-medium text-sm">
                  {item.profilePicUrl && !failedImageIds.has(item.id) ? (
                    <img
                      src={getMediaProxyUrl(item.profilePicUrl)}
                      alt=""
                      className="w-full h-full object-cover"
                      onError={() => handleAvatarError(item.id)}
                    />
                  ) : (
                    <span className={`w-full h-full flex items-center justify-center ${item.avatarColor}`} aria-hidden>
                      {item.avatarInitials}
                    </span>
                  )}
                </div>

                <div className="flex-1 min-w-0 text-left">
                  <div className="flex items-baseline justify-between gap-2 mb-0.5">
                    <span className="font-medium text-gray-900 dark:text-gray-100 truncate text-sm block">
                      {item.contactName}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
                      {formatTimeAgo(item.lastMessageAt)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1 min-w-0">
                      {item.lastMessage || 'Sem mensagens'}
                    </span>
                    {item.unreadCount > 0 && (
                      <span className="flex-shrink-0 min-w-[18px] h-[18px] rounded-full bg-green-500 text-white text-[10px] font-bold flex items-center justify-center">
                        {item.unreadCount > 99 ? '99+' : item.unreadCount}
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
