/**
 * Wrapper da sidebar de conversas (V2).
 * Usa useConversationListData + store; filtro/ordenação e empty states alinhados ao ConversationList.
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Plus, Eye, Pin } from 'lucide-react';
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

export type QuickListFilter = 'all' | 'unread' | 'in_progress' | 'closed';

const QUICK_FILTER_LABELS: Record<QuickListFilter, string> = {
  all: 'Todos',
  unread: 'Não lidos',
  in_progress: 'Em atendimento',
  closed: 'Finalizados',
};

/** Ordem fixa na UI (não depender da ordem de chaves do objeto). */
const QUICK_FILTER_ORDER: QuickListFilter[] = ['all', 'unread', 'in_progress', 'closed'];

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
    difyActiveConversations,
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
      difyActiveConversations: s.difyActiveConversations,
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

  const authUser = useAuthStore((s) => s.user);
  const tenantKey = authUser?.tenant_id || authUser?.tenant?.id || 'no-tenant';
  const userKey = authUser?.id != null ? String(authUser.id) : 'anon';
  const storageFilterKey = `sense-chat:list-filter:${tenantKey}:${userKey}`;
  const storagePinKey = `sense-chat:pinned:${tenantKey}:${userKey}`;

  const [quickListFilter, setQuickListFilterState] = useState<QuickListFilter>('all');
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageFilterKey);
      if (raw && ['all', 'unread', 'in_progress', 'closed'].includes(raw)) {
        setQuickListFilterState(raw as QuickListFilter);
      }
    } catch {
      /* ignore */
    }
  }, [storageFilterKey]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storagePinKey);
      const arr = raw ? JSON.parse(raw) : [];
      if (Array.isArray(arr)) setPinnedIds(new Set(arr.map(String)));
    } catch {
      /* ignore */
    }
  }, [storagePinKey]);

  const setQuickListFilter = useCallback(
    (v: QuickListFilter) => {
      setQuickListFilterState(v);
      try {
        localStorage.setItem(storageFilterKey, v);
      } catch {
        /* ignore */
      }
    },
    [storageFilterKey]
  );

  const togglePin = useCallback(
    (id: string) => {
      setPinnedIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        try {
          localStorage.setItem(storagePinKey, JSON.stringify([...next]));
        } catch {
          /* ignore */
        }
        return next;
      });
    },
    [storagePinKey]
  );

  useEffect(() => {
    const valid = new Set(conversations.map((c) => String(c.id)));
    setPinnedIds((prev) => {
      const next = new Set([...prev].filter((i) => valid.has(i)));
      if (next.size === prev.size) return prev;
      try {
        localStorage.setItem(storagePinKey, JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, [conversations, storagePinKey]);

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
    const qf: QuickListFilter = waitingForResponseMode ? 'all' : quickListFilter;
    const { user } = useAuthStore.getState();

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
        if (departmentId) return false;
        if (qf === 'closed') return convStatus === 'closed';
        return convStatus === 'pending';
      }
      if (activeDepartment.id === 'my_conversations') {
        if (!user) return false;
        if (String(conversationItem.assigned_to ?? '') !== String(user.id ?? '')) return false;
        if (qf === 'closed') return convStatus === 'closed';
        return convStatus === 'open';
      }
      if (convDeptId !== activeDeptId) return false;
      if (qf === 'closed') return convStatus === 'closed';
      if (convStatus === 'closed') return false;

      if (qf === 'unread' && (conversationItem.unread_count ?? 0) <= 0) return false;
      if (qf === 'in_progress') {
        if (convStatus !== 'open') return false;
        const hasAssign =
          conversationItem.assigned_to != null &&
          String(conversationItem.assigned_to).trim() !== '';
        const difyName = difyActiveConversations[String(conversationItem.id)];
        if (!hasAssign && !difyName) return false;
      }

      return true;
    });

    let result = filtered;

    if (activeDepartment?.id === 'groups' && !waitingForResponseMode && result.length > 0) {
      const getGroupName = (c: Conversation) =>
        (c.group_metadata?.group_name || c.contact_name || c.contact_phone || '').toLowerCase().trim();
      const hasRealTime = (c: Conversation) => {
        const t = c.last_message_at;
        return t != null && t !== '' && !Number.isNaN(new Date(t).getTime());
      };
      result = [...result].sort((a, b) => {
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

    if (waitingForResponseMode) {
      const waitingList = result.filter((c) => c.last_message?.direction === 'incoming');
      const activeId = activeConversation?.id != null ? String(activeConversation.id) : null;
      const needsPin =
        activeId &&
        result.some((c) => String(c.id) === activeId) &&
        !waitingList.some((c) => String(c.id) === activeId);
      const sortedWaiting = [...waitingList].sort((a, b) => {
        const tA = new Date(a.last_message_at).getTime() || 0;
        const tB = new Date(b.last_message_at).getTime() || 0;
        return tA - tB || String(a.id).localeCompare(String(b.id));
      });
      return needsPin && activeConversation ? [activeConversation, ...sortedWaiting] : sortedWaiting;
    }

    if (pinnedIds.size > 0 && activeDepartment?.id !== 'groups') {
      result = [...result].sort((a, b) => {
        const ap = pinnedIds.has(String(a.id));
        const bp = pinnedIds.has(String(b.id));
        if (ap && !bp) return -1;
        if (!ap && bp) return 1;
        const tA = new Date(a.last_message_at || 0).getTime();
        const tB = new Date(b.last_message_at || 0).getTime();
        return tB - tA;
      });
    }

    return result;
  }, [
    conversations,
    debouncedSearchTerm,
    activeDepartment,
    waitingForResponseMode,
    activeConversation,
    quickListFilter,
    pinnedIds,
    difyActiveConversations,
  ]);

  const sidebarItems = useMemo(
    () =>
      filteredConversations.map((conv) =>
        conversationToSidebarItem(conv, {
          activeAgentName: difyActiveConversations[String(conv.id)] ?? null,
        })
      ),
    [filteredConversations, difyActiveConversations]
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
  const showQuickFilters = showSearchAndNew && !waitingForResponseMode;

  const listToolbar = showQuickFilters ? (
    <div role="toolbar" aria-label="Filtro rápido da lista" className="flex flex-wrap gap-1">
      {QUICK_FILTER_ORDER.map((key) => (
        <button
          key={key}
          type="button"
          role="radio"
          aria-checked={quickListFilter === key}
          onClick={() => setQuickListFilter(key)}
          className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-chat-ring ${
            quickListFilter === key
              ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm'
              : 'bg-gray-100 dark:bg-gray-700/80 text-gray-700 dark:text-gray-200 border-transparent hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
        >
          {QUICK_FILTER_LABELS[key]}
        </button>
      ))}
    </div>
  ) : undefined;

  const listEmptyState = useMemo(() => {
    if (sidebarItems.length > 0) return undefined;
    if (waitingForResponseMode) {
      return (
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
            Desativar filtro
          </button>
        </>
      );
    }
    if (activeDepartment?.id === 'groups') {
      return (
        <>
          <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">Nenhum grupo</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs mb-4">
            Grupos da sua instância WhatsApp aparecem aqui quando alguém envia ou recebe mensagem no grupo pela
            plataforma, ou quando você sincroniza a lista.
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
      );
    }
    if (debouncedSearchTerm.trim()) {
      return (
        <>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 max-w-xs">
            Nenhum resultado para &quot;{debouncedSearchTerm}&quot;.
          </p>
          <button
            type="button"
            onClick={() => setSearchTerm('')}
            className="px-4 py-2 bg-gray-200 dark:bg-gray-600 text-gray-900 dark:text-white text-sm font-medium rounded-lg"
          >
            Limpar busca
          </button>
        </>
      );
    }
    if (quickListFilter !== 'all') {
      return (
        <>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 max-w-xs">
            Nenhuma conversa neste filtro.
          </p>
          <button
            type="button"
            onClick={() => setQuickListFilter('all')}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg"
          >
            Mostrar todos
          </button>
        </>
      );
    }
    return (
      <>
        <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">Nenhuma conversa</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs">
          Inicie uma nova conversa para começar!
        </p>
      </>
    );
  }, [
    sidebarItems.length,
    waitingForResponseMode,
    activeDepartment?.id,
    debouncedSearchTerm,
    quickListFilter,
    syncingGroups,
    setWaitingForResponseMode,
    setQuickListFilter,
    setRetryTrigger,
  ]);

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

  return (
    <div className="flex flex-col h-full w-full">
      <ConversationSidebar
        conversations={sidebarItems}
        activeId={activeConversation?.id ?? null}
        onSelect={handleSelectConversation}
        listToolbar={listToolbar}
        emptyState={listEmptyState}
        renderTrailingAction={(item, isActive) => {
          const isPinned = pinnedIds.has(String(item.id));
          const isSpyActive = isActive && openInSpyMode;
          if (!showSearchAndNew && !canSpy) return null;
          return (
            <div className="flex items-center gap-0.5 flex-shrink-0">
              {showSearchAndNew ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    togglePin(String(item.id));
                  }}
                  className={`p-1.5 rounded-full transition-colors hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-chat-ring ${
                    isPinned ? 'text-amber-600 dark:text-amber-400' : 'text-gray-400 dark:text-gray-500'
                  }`}
                  title={isPinned ? 'Desfixar do topo' : 'Fixar no topo'}
                  aria-label={isPinned ? 'Desfixar conversa do topo' : 'Fixar conversa no topo'}
                  aria-pressed={isPinned}
                >
                  <Pin className={`w-4 h-4 ${isPinned ? 'fill-current' : ''}`} aria-hidden />
                </button>
              ) : null}
              {canSpy ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSpyToggle(item.id);
                  }}
                  className={`p-1.5 rounded-full transition-colors ${
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
              ) : null}
            </div>
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
