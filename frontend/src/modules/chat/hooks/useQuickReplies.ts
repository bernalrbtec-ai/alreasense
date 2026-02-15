import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';

export interface QuickReply {
  id: string;
  title: string;
  content: string;
  category?: string;
  use_count: number;
  created_at: string;
  updated_at: string;
}

const CACHE_KEY_PREFIX = 'quick_replies_cache';
const CACHE_TIMESTAMP_PREFIX = 'quick_replies_cache_timestamp';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutos

function getTenantId(): string | null {
  const user = useAuthStore.getState().user;
  const raw = user?.tenant_id ?? user?.tenant?.id;
  return raw ? String(raw) : null;
}

export function useQuickReplies(search: string = '', ordering: string = '-use_count,title') {
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tenantId = useAuthStore((s) => {
    const raw = s.user?.tenant_id ?? s.user?.tenant?.id;
    return raw ? String(raw) : null;
  });

  const getCachedData = useCallback((tid: string | null): QuickReply[] | null => {
    if (!tid) return null;
    try {
      const cacheKey = `${CACHE_KEY_PREFIX}:${tid}`;
      const timestampKey = `${CACHE_TIMESTAMP_PREFIX}:${tid}`;
      const cached = localStorage.getItem(cacheKey);
      const timestamp = localStorage.getItem(timestampKey);

      if (!cached || !timestamp) return null;

      const age = Date.now() - parseInt(timestamp, 10);
      if (age > CACHE_TTL_MS) {
        localStorage.removeItem(cacheKey);
        localStorage.removeItem(timestampKey);
        return null;
      }

      return JSON.parse(cached);
    } catch (e) {
      console.error('Erro ao ler cache quick_replies:', e);
      return null;
    }
  }, []);

  const setCachedData = useCallback((data: QuickReply[], tid: string | null) => {
    if (!tid) return;
    try {
      const cacheKey = `${CACHE_KEY_PREFIX}:${tid}`;
      const timestampKey = `${CACHE_TIMESTAMP_PREFIX}:${tid}`;
      localStorage.setItem(cacheKey, JSON.stringify(data));
      localStorage.setItem(timestampKey, Date.now().toString());
    } catch (e) {
      console.error('Erro ao salvar cache quick_replies:', e);
    }
  }, []);

  const invalidateCache = useCallback(() => {
    const tid = getTenantId();
    if (tid) {
      localStorage.removeItem(`${CACHE_KEY_PREFIX}:${tid}`);
      localStorage.removeItem(`${CACHE_TIMESTAMP_PREFIX}:${tid}`);
    }
  }, []);

  const fetchQuickReplies = useCallback(
    async (forceRefresh = false) => {
      const tid = tenantId;

      if (!tid) {
        setQuickReplies([]);
        setError(null);
        return;
      }

      if (!forceRefresh) {
        const cached = getCachedData(tid);
        if (cached) {
          setQuickReplies(cached);
          return;
        }
      }

      setLoading(true);
      setError(null);

      try {
        const { data } = await api.get('/chat/quick-replies/', {
          params: { search, ordering }
        });

        const replies = data.results ?? data ?? [];
        const currentTenantId = getTenantId();

        if (currentTenantId !== tid) {
          return;
        }

        setQuickReplies(replies);
        setCachedData(replies, tid);
      } catch (err: any) {
        const currentTenantId = getTenantId();
        if (currentTenantId !== tid) return;

        const errorMsg = err.response?.data?.error ?? 'Erro ao buscar respostas rápidas';
        setError(errorMsg);
        console.error('❌ [QUICK REPLIES] Erro:', errorMsg);
      } finally {
        setLoading(false);
      }
    },
    [search, ordering, tenantId, getCachedData, setCachedData]
  );

  useEffect(() => {
    fetchQuickReplies();
  }, [fetchQuickReplies]);

  return {
    quickReplies,
    loading,
    error,
    refetch: () => fetchQuickReplies(true),
    invalidateCache
  };
}

