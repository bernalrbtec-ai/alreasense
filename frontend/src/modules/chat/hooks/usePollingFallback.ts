/**
 * ✅ NOVO: Hook para fallback de polling quando WebSocket falha
 * 
 * Usa polling HTTP como fallback quando WebSocket não consegue conectar
 * após múltiplas tentativas.
 */

import { useEffect, useRef, useState } from 'react';
import { useChatStore } from '../store/chatStore';
import { chatWebSocketManager } from '../services/ChatWebSocketManager';
import { api } from '@/lib/api';

const POLLING_INTERVAL = 5000; // 5 segundos
const MAX_POLLING_ATTEMPTS = 10; // Parar após 10 tentativas (50s)

export function usePollingFallback(conversationId?: string) {
  const [isPolling, setIsPolling] = useState(false);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollingAttemptsRef = useRef(0);
  const lastMessageTimestampRef = useRef<string | null>(null);
  
  // ✅ CORREÇÃO: Usar getState() para evitar problemas de TDZ
  const getChatStore = () => useChatStore.getState();
  const { addMessage } = getChatStore();

  useEffect(() => {
    // Verificar se WebSocket falhou e deve usar polling
    if (chatWebSocketManager.shouldUsePollingFallback() && conversationId && !isPolling) {
      console.log('🔄 [POLLING] WebSocket falhou, ativando fallback de polling');
      setIsPolling(true);
      pollingAttemptsRef.current = 0;
      
      // Obter timestamp da última mensagem conhecida
      const { getMessagesArray, activeConversation: currentActiveConversation } = useChatStore.getState();
      const messages = currentActiveConversation ? getMessagesArray(currentActiveConversation.id) : [];
      if (messages.length > 0) {
        lastMessageTimestampRef.current = messages[messages.length - 1].created_at;
      }
    }

    // Se WebSocket reconectou, parar polling
    if (chatWebSocketManager.getIsConnected() && isPolling) {
      console.log('✅ [POLLING] WebSocket reconectado, parando polling');
      setIsPolling(false);
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      pollingAttemptsRef.current = 0;
    }

    // Iniciar polling se necessário
    if (isPolling && conversationId && pollingAttemptsRef.current < MAX_POLLING_ATTEMPTS) {
      const pollMessages = async () => {
        try {
          const params: any = {
            limit: 50,
            ordering: '-created_at'
          };
          
          if (lastMessageTimestampRef.current) {
            params.created_at__gt = lastMessageTimestampRef.current;
          }
          
          const response = await api.get(`/chat/conversations/${conversationId}/messages/`, { params });
          const newMessages = response.data.results || response.data;
          
          if (Array.isArray(newMessages) && newMessages.length > 0) {
            console.log(`📥 [POLLING] ${newMessages.length} nova(s) mensagem(ns) encontrada(s)`);
            
            // Adicionar mensagens (ordenadas do mais antigo para o mais recente)
            const sortedMessages = [...newMessages].sort((messageA, messageB) => 
              new Date(messageA.created_at).getTime() - new Date(messageB.created_at).getTime()
            );
            
            sortedMessages.forEach(message => {
              addMessage(message);
              // Atualizar timestamp da última mensagem
              if (!lastMessageTimestampRef.current || 
                  new Date(message.created_at).getTime() > new Date(lastMessageTimestampRef.current).getTime()) {
                lastMessageTimestampRef.current = message.created_at;
              }
            });
          }
          
          pollingAttemptsRef.current++;
          
          // Parar após max tentativas
          if (pollingAttemptsRef.current >= MAX_POLLING_ATTEMPTS) {
            console.warn('⚠️ [POLLING] Máximo de tentativas atingido, parando polling');
            setIsPolling(false);
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
          }
        } catch (error) {
          console.error('❌ [POLLING] Erro ao buscar mensagens:', error);
          pollingAttemptsRef.current++;
        }
      };
      
      // Poll imediatamente e depois a cada intervalo
      pollMessages();
      pollingIntervalRef.current = setInterval(pollMessages, POLLING_INTERVAL);
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isPolling, conversationId, addMessage]);

  // Listener para evento de falha de conexão
  useEffect(() => {
    const handleConnectionFailed = () => {
      if (conversationId && !isPolling) {
        console.log('🔄 [POLLING] Evento de falha recebido, ativando polling');
        setIsPolling(true);
      }
    };

    chatWebSocketManager.on('connection_failed', handleConnectionFailed);

    return () => {
      chatWebSocketManager.off('connection_failed', handleConnectionFailed);
    };
  }, [conversationId, isPolling]);

  return { isPolling };
}

