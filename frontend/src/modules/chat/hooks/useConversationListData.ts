/**
 * Hook que centraliza o fetch de conversas (inicial, Minhas conversas, Grupos, refresh).
 * Usado pelo ChatConversationSidebarWrapper; ConversationList mantém lógica inline.
 */

import { useState, useEffect } from 'react';
import { useChatStore } from '../store/chatStore';
import { api } from '@/lib/api';
import { ApiErrorHandler } from '@/lib/apiErrorHandler';
import { clearUpdateCache, upsertConversation } from '../store/conversationUpdater';
import { toast } from 'sonner';

const REFRESH_INTERVAL_MS = 30_000;

export function useConversationListData() {
  const setConversations = useChatStore((s) => s.setConversations);
  const activeDepartment = useChatStore((s) => s.activeDepartment);

  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tabLoadError, setTabLoadError] = useState<string | null>(null);
  const [retryTrigger, setRetryTrigger] = useState(0);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(0);

  // Limpar tabLoadError ao sair das abas que usam fetch específico
  useEffect(() => {
    if (activeDepartment?.id !== 'my_conversations' && activeDepartment?.id !== 'groups') {
      setTabLoadError(null);
    }
  }, [activeDepartment?.id]);

  // Fetch inicial (uma vez)
  useEffect(() => {
    if (hasLoaded) return;

    const fetchConversations = async () => {
      try {
        setLoadError(null);
        setLoading(true);
        const response = await api.get('/chat/conversations/', {
          params: { ordering: '-last_message_at' },
        });
        const convs = response.data.results || response.data;

        clearUpdateCache();
        const { conversations: currentConvs } = useChatStore.getState();
        let updatedConvs = currentConvs;
        for (const c of convs) {
          updatedConvs = upsertConversation(updatedConvs, c);
        }
        setConversations(updatedConvs);
        setHasLoaded(true);
        setLastRefresh(Date.now());
      } catch (error) {
        const msg = ApiErrorHandler.extractMessage(error);
        toast.error(msg);
        setLoadError(msg);
        setHasLoaded(true);
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
  }, [hasLoaded, setConversations]);

  // Aba Minhas conversas
  useEffect(() => {
    if (activeDepartment?.id !== 'my_conversations' || !hasLoaded) return;
    setTabLoadError(null);
    const fetchMy = async () => {
      try {
        setLoading(true);
        const response = await api.get('/chat/conversations/', {
          params: { ordering: '-last_message_at', assigned_to_me: 'true' },
        });
        const convs = response.data.results || response.data;
        clearUpdateCache();
        const { conversations: currentConvs } = useChatStore.getState();
        let updated = currentConvs;
        for (const c of convs) updated = upsertConversation(updated, c);
        setConversations(updated);
      } catch (error) {
        const msg = ApiErrorHandler.extractMessage(error);
        toast.error(msg);
        setTabLoadError(msg);
      } finally {
        setLoading(false);
      }
    };
    fetchMy();
  }, [activeDepartment?.id, hasLoaded, setConversations, retryTrigger]);

  // Aba Grupos
  useEffect(() => {
    if (activeDepartment?.id !== 'groups' || !hasLoaded) return;
    setTabLoadError(null);
    const fetchGroups = async () => {
      try {
        setLoading(true);
        const response = await api.get('/chat/conversations/', {
          params: {
            ordering: '-last_message_at',
            conversation_type: 'group',
            page_size: '100',
          },
        });
        const convs = response.data.results || response.data;
        clearUpdateCache();
        const { conversations: currentConvs } = useChatStore.getState();
        let updated = currentConvs;
        for (const c of convs) updated = upsertConversation(updated, c);
        setConversations(updated);
      } catch (error) {
        const msg = ApiErrorHandler.extractMessage(error);
        toast.error(msg);
        setTabLoadError(msg);
      } finally {
        setLoading(false);
      }
    };
    fetchGroups();
  }, [activeDepartment?.id, hasLoaded, setConversations, retryTrigger]);

  // Refresh periódico (30s)
  useEffect(() => {
    if (!hasLoaded) return;
    const timeSince = Date.now() - lastRefresh;
    if (timeSince < REFRESH_INTERVAL_MS) return;

    const refresh = async () => {
      try {
        const { activeDepartment: dept, conversations: current } = useChatStore.getState();
        const params: Record<string, string> = { ordering: '-last_message_at' };
        if (dept?.id === 'groups') {
          params.conversation_type = 'group';
          params.page_size = '100';
        }
        const response = await api.get('/chat/conversations/', { params });
        const convs = response.data.results || response.data;
        let updated = current;
        for (const c of convs) updated = upsertConversation(updated, c);
        setConversations(updated);
        setLastRefresh(Date.now());
      } catch {
        // silencioso
      }
    };

    const interval = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [hasLoaded, lastRefresh, setConversations]);

  return {
    loading,
    loadError,
    tabLoadError,
    retryTrigger,
    setRetryTrigger,
    hasLoaded,
    setLoadError,
    setHasLoaded,
  };
}
