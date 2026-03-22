/**
 * Sidebar de conversas (presentacional).
 * Lista simples (sem virtualização) com avatar (foto ou iniciais), preview, tempo, badge unread.
 * Mantemos a lista sem virtualização por estabilidade em todos os browsers/tenants.
 */

import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Search, Plus, Flame } from 'lucide-react';
import type { ConversationSidebarConversation } from './adapters';
import { formatTimeAgo } from '@/utils/formatTime';
import { STATUS_CHIP_VARIANT_CLASSES } from '@/modules/chat/utils/conversationStatusPresentation';

function getMediaProxyUrl(externalUrl: string): string {
  const API_BASE_URL = (import.meta as unknown as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
}

export interface ConversationSidebarProps {
  conversations: ConversationSidebarConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  /** Opcional: renderiza ação à direita de cada item (ex.: modo espião) */
  renderTrailingAction?: (item: ConversationSidebarConversation, isActive: boolean) => React.ReactNode;
  /** Opcional: controle de busca pelo wrapper */
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  /** Opcional: exibe botão Nova conversa ao lado da busca */
  onNewConversation?: () => void;
  /** Barra acima da lista (ex.: filtros rápidos) */
  listToolbar?: React.ReactNode;
  /** Lista vazia (ex.: filtro sem resultados) */
  emptyState?: React.ReactNode;
}

export function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  renderTrailingAction,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'Buscar ou iniciar conversa',
  onNewConversation,
  listToolbar,
  emptyState,
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

      {listToolbar ? (
        <div className="flex-shrink-0 px-2 sm:px-3 pt-1 pb-2 border-b border-gray-100 dark:border-gray-700">
          {listToolbar}
        </div>
      ) : null}

      <div
        className="flex-1 overflow-y-auto custom-scrollbar min-h-0"
        aria-label="Lista de conversas"
      >
        {conversations.length === 0 && emptyState ? (
          <div className="flex flex-col items-center justify-center py-10 px-4 text-center min-h-[200px]">{emptyState}</div>
        ) : null}

        <div className="flex flex-col">
          {conversations.map((item) => {
            const isActive = activeId !== null && String(item.id) === String(activeId);

            return (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15 }}
                className={`
                  w-full flex items-center gap-2 sm:gap-3 px-3 sm:px-4 flex-shrink-0
                  hover:bg-chat-sidebar dark:hover:bg-gray-700
                  transition-colors duration-150 ease-out
                  border-b border-gray-100 dark:border-gray-700
                  min-h-[72px]
                  ${isActive ? 'bg-chat-sidebar dark:bg-gray-700 ring-inset ring-2 ring-chat-ring' : ''}
                `}
              >
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect(item.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelect(item.id);
                    }
                  }}
                  className="flex-1 min-w-0 flex items-center gap-2 sm:gap-3 cursor-pointer active:scale-[0.99] transition-transform"
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
                      <span className="font-semibold text-gray-900 dark:text-gray-50 truncate text-base leading-tight block">
                        {item.contactName}
                      </span>
                      <span className="text-[10px] tabular-nums text-gray-400 dark:text-gray-500 flex-shrink-0">
                        {formatTimeAgo(item.lastMessageAt)}
                      </span>
                    </div>

                    <div className="flex items-center gap-1 mb-0.5 min-w-0">
                      <span
                        className={`inline-flex items-center gap-0.5 max-w-full truncate px-1.5 py-0.5 rounded-md text-[10px] font-medium ${STATUS_CHIP_VARIANT_CLASSES[item.statusVariant]}`}
                        title={item.statusLabel}
                      >
                        {item.showUrgentIndicator ? (
                          <Flame className="w-3 h-3 flex-shrink-0 text-orange-600 dark:text-orange-400" aria-hidden />
                        ) : null}
                        <span className="truncate">{item.statusLabel}</span>
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <span className="text-sm text-gray-800 dark:text-gray-200 truncate flex-1 min-w-0">
                        {item.lastMessage || 'Sem mensagens'}
                      </span>
                      {item.unreadCount > 0 && (
                        <span className="flex-shrink-0 min-w-[18px] h-[18px] rounded-full bg-green-500 text-white text-[10px] font-bold flex items-center justify-center">
                          {item.unreadCount > 99 ? '99+' : item.unreadCount}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {renderTrailingAction ? (
                  <div className="flex-shrink-0 flex items-center">
                    {renderTrailingAction(item, isActive)}
                  </div>
                ) : null}
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
