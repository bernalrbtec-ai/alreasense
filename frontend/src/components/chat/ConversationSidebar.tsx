/**
 * Sidebar de conversas (presentacional).
 * Lista virtualizada com avatar, preview, tempo, badge unread e sentimento.
 */

import React, { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { motion } from 'framer-motion';
import { Search, Plus } from 'lucide-react';
import type { ConversationSidebarConversation } from './adapters';
import { sentimentConfig } from '@/utils/sentiment';
import { formatTimeAgo } from '@/utils/formatTime';

const ROW_HEIGHT = 72;

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
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: conversations.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  const items = rowVirtualizer.getVirtualItems();

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
                className="w-full pl-8 sm:pl-10 pr-3 py-2 bg-[#f0f2f5] dark:bg-gray-800 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#00a884] focus:bg-white dark:focus:bg-gray-700 transition-colors text-gray-900 dark:text-white"
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
        ref={parentRef}
        className="flex-1 overflow-y-auto custom-scrollbar"
        aria-label="Lista de conversas"
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {items.map((virtualRow) => {
            const item = conversations[virtualRow.index];
            const isActive = activeId !== null && String(item.id) === String(activeId);
            const sentiment = sentimentConfig[item.sentimentScore];

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
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className={`
                  w-full flex items-center gap-2 sm:gap-3 px-3 sm:px-4
                  hover:bg-[#f0f2f5] dark:hover:bg-gray-700 active:scale-[0.99]
                  transition-colors border-b border-gray-100 dark:border-gray-700
                  cursor-pointer
                  ${isActive ? 'bg-[#f0f2f5] dark:bg-gray-700 ring-inset ring-2 ring-blue-500' : ''}
                `}
              >
                <div
                  className={`flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-full ${item.avatarColor} flex items-center justify-center text-white font-medium text-sm`}
                  aria-hidden
                >
                  {item.avatarInitials}
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
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sentiment.dot}`}
                      title={sentiment.label}
                      aria-hidden
                    />
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
