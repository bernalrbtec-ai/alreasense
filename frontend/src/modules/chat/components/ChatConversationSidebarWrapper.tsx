/**
 * Wrapper da sidebar de conversas (V2).
 * Usa useConversationListData + store; filtro/ordenação e empty states alinhados ao ConversationList.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Plus, Eye } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { shallow } from 'zustand/shallow';
import { useConversationListData } from '../hooks/useConversationListData';
import { useAuthStore } from '@/stores/authStore';
import { api } from '@/lib/api';
import { ApiErrorHandler } from '@/lib/apiErrorHandler';
import { toast } from 'sonner';
import { conversationToSidebarItem } from '@/components/chat/adapters';
import { ConversationSidebar } from '@/components/chat/ConversationSidebar';
import { NewConversationModal } from './NewConversationModal';
import type { Conversation } from '../types';
import { usePermissions } from '@/hooks/usePermissions';

export function ChatConversationSidebarWrapper() {
  const {
    conversations,
    activeConversation,
    setActiveConversation,
    activeDepartment,
    waitingForResponseMode,
    setWaitingForResponseMode,
    setOpenInSpyMode,
    openInSpyMode,
  } = useChatStore(
    (s) => ({
      conversations: s.conversations,
      activeConversation: s.activeConversation,
      setActiveConversation: s.setActiveConversation,
      activeDepartment: s.activeDepartment,
      waitingForResponseMode: s.waitingForResponseMode,
      setWaitingForResponseMode: s.setWaitingForResponseMode,
      setOpenInSpyMode: s.setOpenInSpyMode,
      openInSpyMode: s.openInSpyMode,
    }),
    shallow
  );

  const permissions = usePermissions();
  const canSpy = permissions.isAdmin || permissions.isGerente;

  const {
    loading,
    loadError,
    tabLoadError,
    retryTrigger,
    setRetryTrigger,
    hasLoaded,
    setLoadError,
    setHasLoaded,
  } = useConversationListData();

  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [showNewConversation, setShowNewConversation] = useState(false);
  const [syncingGroups, setSyncingGroups] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearchTerm(searchTerm), 300);
    return () => clearTimeout(t);
  }, [searchTerm]);

  // Deep link: ?conversation_id=...
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const conversationId = params.get('conversation_id');
    if (!conversationId || activeConversation?.id === conversationId) return;
    const match = conversations.find((c) => String(c.id) === conversationId);
    if (match) {
      setActiveConversation(match);
      params.delete('conversation_id');
      const url = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}`;
      window.history.replaceState({}, '', url);
    }
  }, [conversations, activeConversation, setActiveConversation]);

  const filteredConversations = useMemo(() => {
    if (!Array.isArray(conversations) || !conversations.length) return [];
    const searchLower = (debouncedSearchTerm || '').toLowerCase().trim();

    const filtered = conversations.filter((conversationItem: Conversation) => {
      if (searchLower) {
        const matchesSearch =
          conversationItem.contact_name?.toLowerCase().includes(searchLower) ||
          conversationItem.contact_phone?.includes(debouncedSearchTerm) === true ||
          (conversationItem.group_metadata?.group_name || '').toLowerCase().includes(searchLower);
        if (!matchesSearch) return false;
      }

      if (activeDepartment?.id === 'groups') {
        const isGroup = conversationItem.conversation_type === 'group';
        const notClosed = (conversationItem.status ?? 'open') !== 'closed';
        const notRemoved = conversationItem.group_metadata?.instance_removed !== true;
        return isGroup && notClosed && notRemoved;
      }

      if (conversationItem.conversation_type === 'group') return false;
      if (!activeDepartment) return true;

      const departmentId =
        typeof conversationItem.department === 'string'
          ? conversationItem.department
          : conversationItem.department?.id || null;
      const convStatus = conversationItem.status || 'pending';
      const activeDeptId = String(activeDepartment.id);
      const convDeptId = departmentId ? String(departmentId) : null;

      if (activeDepartment.id === 'inbox') {
        return !departmentId && convStatus === 'pending';
      }
      if (activeDepartment.id === 'my_conversations') {
        const { user } = useAuthStore.getState();
        if (!user) return false;
        return (
          conversationItem.assigned_to === user.id &&
          (conversationItem.status ?? 'open') === 'open'
        );
      }
      if (conversationItem.status === 'closed') return false;
      return convDeptId === activeDeptId;
    });

    if (activeDepartment?.id === 'groups' && !waitingForResponseMode && filtered.length > 0) {
      const getGroupName = (c: Conversation) =>
        (c.group_metadata?.group_name || c.contact_name || c.contact_phone || '').toLowerCase().trim();
      const hasRealTime = (c: Conversation) => {
        const t = c.last_message_at;
        return t != null && t !== '' && !Number.isNaN(new Date(t).getTime());
      };
      return [...filtered].sort((a, b) => {
        const aHas = hasRealTime(a);
        const bHas = hasRealTime(b);
        if (aHas && !bHas) return -1;
        if (!aHas && bHas) return 1;
        if (aHas && bHas) {
          const tA = new Date(a.last_message_at!).getTime();
          const tB = new Date(b.last_message_at!).getTime();
          return tB - tA;
        }
        return getGroupName(a).localeCompare(getGroupName(b), 'pt-BR');
      });
    }

    if (!waitingForResponseMode) return filtered;

    const waitingList = filtered.filter((c) => c.last_message?.direction === 'incoming');
    const activeId = activeConversation?.id != null ? String(activeConversation.id) : null;
    const needsPin =
      activeId &&
      filtered.some((c) => String(c.id) === activeId) &&
      !waitingList.some((c) => String(c.id) === activeId);
    const sortedWaiting = [...waitingList].sort((a, b) => {
      const tA = new Date(a.last_message_at).getTime() || 0;
      const tB = new Date(b.last_message_at).getTime() || 0;
      return tA - tB || String(a.id).localeCompare(String(b.id));
    });
    return needsPin && activeConversation ? [activeConversation, ...sortedWaiting] : sortedWaiting;
  }, [
    conversations,
    debouncedSearchTerm,
    activeDepartment,
    waitingForResponseMode,
    activeConversation,
  ]);

  const sidebarItems = useMemo(
    () => filteredConversations.map(conversationToSidebarItem),
    [filteredConversations]
  );

  const handleSelectConversation = (id: string) => {
    const conv = filteredConversations.find((c) => String(c.id) === id);
    if (!conv) return;
    const isSame = activeConversation?.id === conv.id;
    if (isSame) return;
    setActiveConversation(conv);
    setOpenInSpyMode(false);
  };

  const handleSpyToggle = (id: string) => {
    if (!canSpy) return;
    const conv = filteredConversations.find((c) => String(c.id) === id);
    if (!conv) return;
    const isSame = activeConversation?.id === conv.id;
    const isSameAndSpy = isSame && openInSpyMode;
    if (isSameAndSpy) {
      setOpenInSpyMode(false);
      return;
    }
    if (!isSame) setActiveConversation(conv);
    setOpenInSpyMode(true);
  };

  const showSearchAndNew = activeDepartment?.id !== 'groups';

  if (loading && !hasLoaded) {
    return (
      <div className="flex flex-col h-full w-full bg-white dark:bg-gray-800 items-center justify-center py-12">
        <div className="flex gap-2 mb-3">
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400">Carregando conversas...</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex flex-col h-full w-full bg-white dark:bg-gray-800 items-center justify-center py-12 px-4">
        <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">
          Não foi possível carregar as conversas
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs mb-4">{loadError}</p>
        <button
          type="button"
          onClick={() => {
            setLoadError(null);
            setHasLoaded(false);
          }}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (
    tabLoadError &&
    (activeDepartment?.id === 'my_conversations' || activeDepartment?.id === 'groups')
  ) {
    return (
      <div className="flex flex-col h-full w-full bg-white dark:bg-gray-800 items-center justify-center py-12 px-4">
        <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">
          {activeDepartment?.id === 'groups'
            ? 'Não foi possível carregar os grupos'
            : 'Não foi possível carregar minhas conversas'}
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs mb-4">{tabLoadError}</p>
        <button
          type="button"
          onClick={() => setRetryTrigger((r) => r + 1)}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (filteredConversations.length === 0) {
    return (
      <div className="flex flex-col h-full w-full bg-white dark:bg-gray-800">
        {showSearchAndNew && (
          <div className="flex-shrink-0 flex items-center gap-2 p-2 sm:p-3 border-b border-gray-200 dark:border-gray-700">
            <div className="flex-1 relative min-w-0">
              <input
                type="search"
                aria-label="Buscar conversas"
                placeholder="Buscar ou iniciar conversa"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-2 bg-chat-sidebar dark:bg-gray-800 rounded-lg text-sm text-gray-900 dark:text-white"
              />
            </div>
            <button
              type="button"
              aria-label="Nova conversa"
              onClick={() => setShowNewConversation(true)}
              className="flex-shrink-0 p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full"
            >
              <Plus className="w-5 h-5 text-gray-600 dark:text-gray-400" aria-hidden />
            </button>
          </div>
        )}
        <div className="flex-1 flex flex-col items-center justify-center py-12 px-4">
          {waitingForResponseMode ? (
            <>
              <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">
                Nenhuma conversa aguardando resposta
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs mb-4">
                Desative o filtro para ver todas as conversas.
              </p>
              <button
                type="button"
                onClick={() => setWaitingForResponseMode(false)}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Desative o filtro
              </button>
            </>
          ) : activeDepartment?.id === 'groups' ? (
            <>
              <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">
                Nenhum grupo
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs mb-4">
                Grupos da sua instância WhatsApp aparecem aqui quando alguém envia ou recebe mensagem no grupo pela plataforma, ou quando você sincroniza a lista.
              </p>
              <button
                type="button"
                disabled={syncingGroups}
                aria-busy={syncingGroups}
                onClick={async () => {
                  setSyncingGroups(true);
                  try {
                    const { data } = await api.post('/chat/conversations/sync-groups/');
                    toast.success(data?.message || `${data?.created ?? 0} grupo(s) adicionado(s).`);
                    setRetryTrigger((r) => r + 1);
                  } catch (error) {
                    toast.error(ApiErrorHandler.extractMessage(error));
                  } finally {
                    setSyncingGroups(false);
                  }
                }}
                className="px-4 py-2 bg-[#8b5cf6] hover:bg-[#7c3aed] disabled:opacity-50 text-white text-sm font-medium rounded-lg"
              >
                {syncingGroups ? 'Sincronizando...' : 'Sincronizar grupos da instância'}
              </button>
            </>
          ) : (
            <>
              <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">
                Nenhuma conversa
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs">
                Inicie uma nova conversa para começar!
              </p>
            </>
          )}
        </div>
        <NewConversationModal isOpen={showNewConversation} onClose={() => setShowNewConversation(false)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full">
      <ConversationSidebar
        conversations={sidebarItems}
        activeId={activeConversation?.id ?? null}
        onSelect={handleSelectConversation}
        renderTrailingAction={(item, isActive) => {
          if (!canSpy) return null;
          const isSpyActive = isActive && openInSpyMode;
          return (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleSpyToggle(item.id);
              }}
              className={`ml-1 flex-shrink-0 p-1.5 rounded-full transition-colors ${
                isSpyActive
                  ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-800/40'
                  : 'hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
              title={isSpyActive ? 'Sair do modo espião (assumir conversa)' : 'Abrir em modo espião (não marca como lida)'}
              aria-label={isSpyActive ? 'Sair do modo espião' : 'Abrir em modo espião'}
              aria-pressed={isSpyActive}
            >
              <Eye className="w-4 h-4" aria-hidden />
            </button>
          );
        }}
        searchValue={showSearchAndNew ? searchTerm : undefined}
        onSearchChange={showSearchAndNew ? setSearchTerm : undefined}
        searchPlaceholder="Buscar ou iniciar conversa"
        onNewConversation={showSearchAndNew ? () => setShowNewConversation(true) : undefined}
      />
      <NewConversationModal isOpen={showNewConversation} onClose={() => setShowNewConversation(false)} />
    </div>
  );
}
