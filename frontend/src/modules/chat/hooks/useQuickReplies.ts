import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

export interface QuickReply {
  id: string;
  title: string;
  content: string;
  category?: string;
  use_count: number;
  created_at: string;
  updated_at: string;
}

const CACHE_KEY = 'quick_replies_cache';
const CACHE_TIMESTAMP_KEY = 'quick_replies_cache_timestamp';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutos

export function useQuickReplies(search: string = '', ordering: string = '-use_count,title') {
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getCachedData = (): QuickReply[] | null => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      const timestamp = localStorage.getItem(CACHE_TIMESTAMP_KEY);
      
      if (!cached || !timestamp) return null;
      
      const age = Date.now() - parseInt(timestamp, 10);
      if (age > CACHE_TTL_MS) {
        // Cache expirado
        localStorage.removeItem(CACHE_KEY);
        localStorage.removeItem(CACHE_TIMESTAMP_KEY);
        return null;
      }
      
      return JSON.parse(cached);
    } catch (e) {
      console.error('Erro ao ler cache:', e);
      return null;
    }
  };

  const setCachedData = (data: QuickReply[]) => {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(data));
      localStorage.setItem(CACHE_TIMESTAMP_KEY, Date.now().toString());
    } catch (e) {
      console.error('Erro ao salvar cache:', e);
    }
  };

  const invalidateCache = useCallback(() => {
    localStorage.removeItem(CACHE_KEY);
    localStorage.removeItem(CACHE_TIMESTAMP_KEY);
  }, []);

  const fetchQuickReplies = useCallback(async (forceRefresh = false) => {
    // ✅ Tentar cache primeiro (se não for refresh forçado)
    if (!forceRefresh) {
      const cached = getCachedData();
      if (cached) {
        console.log('✅ [QUICK REPLIES] Cache HIT (localStorage)');
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
      
      const replies = data.results || data;
      setQuickReplies(replies);
      
      // ✅ Salvar no cache
      setCachedData(replies);
      console.log('💾 [QUICK REPLIES] Cache salvo (localStorage)');
    } catch (err: any) {
      const errorMsg = err.response?.data?.error || 'Erro ao buscar respostas rápidas';
      setError(errorMsg);
      console.error('❌ [QUICK REPLIES] Erro:', errorMsg);
    } finally {
      setLoading(false);
    }
  }, [search, ordering]);

  // ✅ FIX: Usar search e ordering diretamente no useEffect para evitar loops
  useEffect(() => {
    fetchQuickReplies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, ordering]); // Não incluir fetchQuickReplies nas dependências

  return {
    quickReplies,
    loading,
    error,
    refetch: () => fetchQuickReplies(true),
    invalidateCache
  };
}

