/**
 * 🌐 GLOBAL CHAT WEBSOCKET MANAGER
 * 
 * Gerencia UMA ÚNICA conexão WebSocket para TODAS as conversas do chat.
 * Ao trocar de conversa, apenas envia comandos subscribe/unsubscribe.
 * 
 * Benefícios:
 * - 1 conexão persistente (vs N conexões)
 * - Zero latência ao trocar conversas
 * - Sem memory leaks
 * - Escalável para 10-20+ conversas simultâneas
 */

import { useAuthStore } from '@/stores/authStore';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'wss://alreasense-backend-production.up.railway.app';

export interface WebSocketMessage {
  type: string;
  message?: any;
  message_id?: string;
  status?: string;
  user_id?: string;
  user_email?: string;
  conversation?: any;
  error?: string;
  [key: string]: any;
}

type EventCallback = (data: any) => void;

class ChatWebSocketManager {
  private static instance: ChatWebSocketManager;
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private messageQueue: Array<{ type: string; data: any }> = [];
  private eventListeners: Map<string, Set<EventCallback>> = new Map();
  private currentConversationId: string | null = null;
  private isConnecting = false;
  private isConnected = false;
  private tenantId: string | null = null;
  private token: string | null = null;
  // ✅ NOVO: Page Visibility API
  private isPaused = false; // Pausado quando aba está em background
  private lastConnectedAt: number | null = null; // Timestamp da última conexão bem-sucedida
  private visibilityChangeHandler: (() => void) | null = null;

  private constructor() {
    console.log('🏗️ [MANAGER] ChatWebSocketManager criado (Singleton)');
    // ✅ NOVO: Registrar Page Visibility API
    this.setupPageVisibilityListener();
  }
  
  /**
   * ✅ NOVO: Configura listener para Page Visibility API
   * Pausa reconexão quando aba está em background
   */
  private setupPageVisibilityListener(): void {
    if (typeof document === 'undefined') return; // SSR
    
    this.visibilityChangeHandler = () => {
      if (document.hidden) {
        // Aba está em background - pausar reconexão
        console.log('⏸️ [MANAGER] Aba em background - pausando reconexão');
        this.isPaused = true;
        // Cancelar reconexão pendente
        if (this.reconnectTimeout) {
          clearTimeout(this.reconnectTimeout);
          this.reconnectTimeout = null;
        }
      } else {
        // Aba voltou ao foreground - retomar
        console.log('▶️ [MANAGER] Aba em foreground - retomando conexão');
        this.isPaused = false;
        // Se estava desconectado, tentar reconectar
        if (!this.isConnected && !this.isConnecting && this.tenantId && this.token) {
          console.log('🔄 [MANAGER] Tentando reconectar após voltar ao foreground...');
          this.reconnectAttempts = 0; // Resetar tentativas
          this.connect(this.tenantId, this.token);
        }
      }
    };
    
    document.addEventListener('visibilitychange', this.visibilityChangeHandler);
  }

  public static getInstance(): ChatWebSocketManager {
    if (!ChatWebSocketManager.instance) {
      ChatWebSocketManager.instance = new ChatWebSocketManager();
    }
    return ChatWebSocketManager.instance;
  }

  /**
   * Conecta ao WebSocket global (1 vez por sessão)
   */
  public connect(tenantId: string, token: string): void {
    if (this.isConnected || this.isConnecting) {
      console.log('⏸️ [MANAGER] Já conectado/conectando');
      return;
    }

    this.tenantId = tenantId;
    this.token = token;
    this.isConnecting = true;

    const wsUrl = `${WS_BASE_URL}/ws/chat/tenant/${tenantId}/?token=${token}`;
    console.log('🔌 [MANAGER] Conectando ao WebSocket global:', wsUrl);

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('✅ [MANAGER] WebSocket global conectado!');
        this.isConnected = true;
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.lastConnectedAt = Date.now(); // ✅ NOVO: Registrar timestamp de conexão bem-sucedida

        // Processar fila de mensagens pendentes
        this.processMessageQueue();

        // Se tinha uma conversa ativa, resubscrever
        if (this.currentConversationId) {
          console.log(`🔄 [MANAGER] Resubscrevendo à conversa: ${this.currentConversationId}`);
          this.subscribe(this.currentConversationId);
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          console.log('📨 [MANAGER] Mensagem recebida:', data);
          this.handleMessage(data);
        } catch (error) {
          console.error('❌ [MANAGER] Erro ao parsear mensagem:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('❌ [MANAGER] Erro no WebSocket:', error);
        this.isConnected = false;
        this.isConnecting = false;
      };

      this.ws.onclose = (event) => {
        console.warn('🔌 [MANAGER] WebSocket fechado:', event.code, event.reason);
        this.isConnected = false;
        this.isConnecting = false;
        this.ws = null;

        // ✅ NOVO: Não reconectar se está pausado (aba em background)
        if (this.isPaused) {
          console.log('⏸️ [MANAGER] Reconexão pausada (aba em background)');
          return;
        }

        // ✅ MELHORIA: Resetar tentativas após 5 minutos conectado
        if (this.lastConnectedAt && Date.now() - this.lastConnectedAt > 5 * 60 * 1000) {
          console.log('🔄 [MANAGER] Resetando tentativas após conexão prolongada');
          this.reconnectAttempts = 0;
        }

        // Reconectar automaticamente com exponential backoff + jitter
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          const baseDelay = 1000 * Math.pow(2, this.reconnectAttempts);
          const jitter = Math.random() * 1000; // ✅ NOVO: Jitter aleatório (0-1s)
          const delay = Math.min(baseDelay + jitter, 30000);
          console.log(`🔄 [MANAGER] Reconectando em ${Math.round(delay)}ms (tentativa ${this.reconnectAttempts + 1})...`);

          this.reconnectTimeout = setTimeout(() => {
            // ✅ Verificar novamente se não está pausado antes de reconectar
            if (this.isPaused) {
              console.log('⏸️ [MANAGER] Reconexão cancelada (aba ainda em background)');
              return;
            }
            
            this.reconnectAttempts++;
            if (this.tenantId && this.token) {
              this.connect(this.tenantId, this.token);
            }
          }, delay);
        } else {
          console.error('❌ [MANAGER] Máximo de tentativas de reconexão atingido');
          // ✅ NOVO: Emitir evento para ativar fallback de polling
          this.emit('connection_failed', { reason: 'max_attempts_reached' });
        }
      };
    } catch (error) {
      console.error('❌ [MANAGER] Erro ao criar WebSocket:', error);
      this.isConnecting = false;
    }
  }

  /**
   * Desconecta o WebSocket global (logout)
   */
  public disconnect(): void {
    console.log('🔌 [MANAGER] Desconectando WebSocket global...');

    // ✅ NOVO: Remover listener de Page Visibility
    if (this.visibilityChangeHandler && typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.visibilityChangeHandler);
      this.visibilityChangeHandler = null;
    }

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.isConnected = false;
    this.isConnecting = false;
    this.currentConversationId = null;
    this.messageQueue = [];
    this.reconnectAttempts = 0;
    this.isPaused = false;
    this.lastConnectedAt = null;
  }
  
  /**
   * ✅ NOVO: Pausar reconexão (chamado quando aba está em background)
   */
  public pause(): void {
    console.log('⏸️ [MANAGER] Pausando WebSocket');
    this.isPaused = true;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }
  
  /**
   * ✅ NOVO: Retomar reconexão (chamado quando aba volta ao foreground)
   */
  public resume(): void {
    console.log('▶️ [MANAGER] Retomando WebSocket');
    this.isPaused = false;
    // Se estava desconectado, tentar reconectar
    if (!this.isConnected && !this.isConnecting && this.tenantId && this.token) {
      this.reconnectAttempts = 0; // Resetar tentativas
      this.connect(this.tenantId, this.token);
    }
  }

  /**
   * Subscribe to a specific conversation
   */
  public subscribe(conversationId: string): void {
    console.log(`📥 [MANAGER] Subscrevendo à conversa: ${conversationId}`);
    
    // Unsubscribe da conversa anterior (se houver)
    if (this.currentConversationId && this.currentConversationId !== conversationId) {
      this.unsubscribe(this.currentConversationId);
    }

    this.currentConversationId = conversationId;
    this.sendMessage({
      type: 'subscribe',
      conversation_id: conversationId,
    });
  }

  /**
   * Unsubscribe from a conversation
   */
  public unsubscribe(conversationId: string): void {
    console.log(`📤 [MANAGER] Desinscrevendo da conversa: ${conversationId}`);
    
    this.sendMessage({
      type: 'unsubscribe',
      conversation_id: conversationId,
    });

    if (this.currentConversationId === conversationId) {
      this.currentConversationId = null;
    }
  }

  /**
   * Envia uma mensagem de chat
   */
  public sendChatMessage(content: string, includeSignature = true, isInternal = false, mentions?: string[]): boolean {
    if (!this.currentConversationId) {
      console.error('❌ [MANAGER] Nenhuma conversa ativa');
      return false;
    }

    const payload: any = {
      type: 'send_message',
      content,
      include_signature: includeSignature,
      is_internal: isInternal,
    };
    
    // ✅ NOVO: Adicionar mentions se fornecido
    if (mentions && mentions.length > 0) {
      payload.mentions = mentions;
    }

    return this.sendMessage(payload);
  }

  /**
   * Envia evento de digitação
   */
  public sendTyping(isTyping: boolean): void {
    if (!this.currentConversationId) return;

    this.sendMessage({
      type: 'typing',
      is_typing: isTyping,
    });
  }

  /**
   * Marca mensagem como vista
   */
  public markAsSeen(messageId: string): void {
    if (!this.currentConversationId) return;

    this.sendMessage({
      type: 'mark_as_seen',
      message_id: messageId,
    });
  }

  /**
   * Envia mensagem ao WebSocket (ou enfileira se desconectado)
   */
  private sendMessage(data: any): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // Se não está conectado, enfileirar
      if (data.type === 'send_message') {
        console.log('📦 [MANAGER] Enfileirando mensagem (WebSocket desconectado)');
        this.messageQueue.push({ type: data.type, data });
      }
      return false;
    }

    try {
      // ✅ DEBUG: Log detalhado do payload sendo enviado
      if (data.type === 'send_message') {
        console.log('📤 [MANAGER] Enviando send_message:', {
          type: data.type,
          conversation_id: data.conversation_id,
          content: data.content?.substring(0, 50),
          reply_to: data.reply_to,
          include_signature: data.include_signature,
          is_internal: data.is_internal,
          mentions: data.mentions
        });
        console.log('📤 [MANAGER] Payload completo (JSON):', JSON.stringify(data, null, 2));
        console.log('📤 [MANAGER] Reply_to existe?', !!data.reply_to, '| Valor:', data.reply_to);
      }
      const jsonPayload = JSON.stringify(data);
      console.log('📤 [MANAGER] Enviando JSON string:', jsonPayload.substring(0, 200));
      this.ws.send(jsonPayload);
      console.log('✅ [MANAGER] Mensagem enviada com sucesso:', data.type);
      return true;
    } catch (error) {
      console.error('❌ [MANAGER] Erro ao enviar mensagem:', error);
      return false;
    }
  }

  /**
   * Processa fila de mensagens pendentes
   */
  private processMessageQueue(): void {
    if (this.messageQueue.length === 0) return;

    console.log(`📦 [MANAGER] Processando ${this.messageQueue.length} mensagens pendentes...`);

    while (this.messageQueue.length > 0) {
      const { data } = this.messageQueue.shift()!;
      this.sendMessage(data);
    }
  }

  /**
   * Trata mensagens recebidas do WebSocket
   */
  private handleMessage(data: WebSocketMessage): void {
    // Emitir evento específico
    this.emit(data.type, data);

    // Emitir evento genérico 'message'
    this.emit('message', data);
  }

  /**
   * Registra listener para eventos
   */
  public on(event: string, callback: EventCallback): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event)!.add(callback);
  }

  /**
   * Remove listener de eventos
   */
  public off(event: string, callback: EventCallback): void {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event)!.delete(callback);
    }
  }

  /**
   * Emite evento para listeners
   */
  private emit(event: string, data: any): void {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event)!.forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`❌ [MANAGER] Erro ao executar callback de '${event}':`, error);
        }
      });
    }
  }

  /**
   * Getters
   */
  public getIsConnected(): boolean {
    return this.isConnected;
  }

  public getCurrentConversationId(): string | null {
    return this.currentConversationId;
  }
}

// Export singleton instance
export const chatWebSocketManager = ChatWebSocketManager.getInstance();

