/**
 * Janela de chat principal - Estilo WhatsApp Web
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { ArrowLeft, MoreVertical, Search, X, ArrowRightLeft, XCircle, Plus, User, Clock, Eye, Zap, Bot, StopCircle } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TransferModal } from './TransferModal';
import { usePermissions } from '@/hooks/usePermissions';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { useChatSocket } from '../hooks/useChatSocket';
import { usePollingFallback } from '../hooks/usePollingFallback';
import ContactModal from '@/components/contacts/ContactModal';
import ContactHistory from '@/components/contacts/ContactHistory';
import { useAuthStore } from '@/stores/authStore';
import { Button } from '@/components/ui/Button';

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

// No-op estável para modo espião (evita re-renders do MessageInput quando sendTyping não é usado)
const noopTyping = () => {};

export function ChatWindow() {
  const { activeConversation, setActiveConversation, openInSpyMode, replyToMessage, clearReply } = useChatStore();
  const { user } = useAuthStore();
  // ✅ CORREÇÃO: can_transfer_conversations pode não existir no tipo, usar verificação segura
  const permissions = usePermissions();
  const can_transfer_conversations = (permissions as any).can_transfer_conversations || false;
  
  // ✅ CORREÇÃO CRÍTICA: Inicializar todos os estados ANTES de qualquer hook que dependa de activeConversation
  const [showMenu, setShowMenu] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showStartFlowModal, setShowStartFlowModal] = useState(false);
  const [flowsForStart, setFlowsForStart] = useState<Array<{ id: string; name: string; description?: string }>>([]);
  const [selectedFlowId, setSelectedFlowId] = useState<string | null>(null);
  const [loadingFlows, setLoadingFlows] = useState(false);
  const [startFlowLoading, setStartFlowLoading] = useState(false);
  // Dify agent modal state
  const [startFlowModalTab, setStartFlowModalTab] = useState<'flows' | 'dify'>('flows');
  const [difyAgents, setDifyAgents] = useState<Array<{ id: string; dify_app_id: string; display_name: string; description: string }>>([]);
  const [difyActiveState, setDifyActiveState] = useState<{ catalog_id: string; status: string; display_name?: string } | null>(null);
  const [selectedDifyAgentId, setSelectedDifyAgentId] = useState<string | null>(null);
  const [loadingDifyAgents, setLoadingDifyAgents] = useState(false);
  const [startDifyLoading, setStartDifyLoading] = useState(false);
  const [stopDifyLoading, setStopDifyLoading] = useState(false);
  // Badge permanente no header: busca o estado ativo ao carregar a conversa
  const [difyHeaderState, setDifyHeaderState] = useState<{ display_name: string } | null>(null);
  const [showDifySwapConfirm, setShowDifySwapConfirm] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [existingContact, setExistingContact] = useState<any>(null);
  const [isCheckingContact, setIsCheckingContact] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showGroupInfo, setShowGroupInfo] = useState(false);
  const [groupInfo, setGroupInfo] = useState<any>(null);
  const [loadingGroupInfo, setLoadingGroupInfo] = useState(false);
  // ✅ CORREÇÃO CRÍTICA: Adicionar estado para controlar se está pronto para renderizar
  const [isReady, setIsReady] = useState(false);
  const [loadingStart, setLoadingStart] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const chatPanelRef = useRef<HTMLDivElement>(null);
  // ✅ NOVO: Ref para debounce do refresh-info (deve estar no nível superior)
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // ✅ CORREÇÃO: Capturar activeConversation.id de forma segura antes de usar em hooks
  const activeConversationId = activeConversation?.id;
  
  // 🔌 Conectar WebSocket para esta conversa (usa manager global) - DEPOIS de inicializar estados
  const { isConnected, sendMessage, sendMessageAsTemplate, sendMessageWithButtons, sendMessageWithList, sendMessageWithContacts, sendTyping } = useChatSocket(activeConversationId);
  // ✅ NOVO: Fallback de polling quando WebSocket falha - DEPOIS de inicializar estados
  usePollingFallback(activeConversationId);

  // Callback para resposta por botão ou lista: envia apenas o texto da escolha, sem assinatura.
  const handleSendReplyButtonClick = useCallback(
    (buttonText: string, replyToMessageId: string) => {
      sendMessage(buttonText, false, false, replyToMessageId);
    },
    [sendMessage]
  );
  
  // Escape: se houver reply ativo, cancela o reply; senão deixa de exibir a conversa (volta à lista). NÃO fecha a conversa (sem API).
  useEffect(() => {
    if (!activeConversation) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      const target = e.target as Node | null;
      if (target instanceof HTMLElement && target.closest('[role="dialog"], [role="menu"]')) return;
      e.preventDefault();
      if (replyToMessage) {
        clearReply();
        return;
      }
      setActiveConversation(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activeConversation, setActiveConversation, replyToMessage, clearReply]);

  // ✅ DEBUG: Log quando activeConversation muda (especialmente contact_name) - DEPOIS de hooks
  useEffect(() => {
    if (activeConversation) {
      console.log('🔄 [ChatWindow] activeConversation atualizado:', {
        id: activeConversation.id,
        contact_name: activeConversation.contact_name,
        contact_phone: activeConversation.contact_phone
      });
    }
  }, [activeConversation?.id, activeConversation?.contact_name]);
  
  // 🔍 Debug: Log quando profile_pic_url muda - DEPOIS de hooks
  useEffect(() => {
    if (activeConversation) {
      console.log('🖼️ [ChatWindow] profile_pic_url atual:', activeConversation.profile_pic_url);
    }
  }, [activeConversation?.profile_pic_url]);

  // ✅ Verificar se contato existe quando conversa abre (apenas para contatos individuais)
  useEffect(() => {
    // ✅ CORREÇÃO: Verificar activeConversation e conversation_type de forma segura
    if (!activeConversation || !activeConversation.id) {
      setExistingContact(null);
      return;
    }
    
    // ✅ CORREÇÃO CRÍTICA: Capturar conversation_type de forma segura com optional chaining
    const conversationType = activeConversation?.conversation_type || 'individual';
    if (conversationType === 'group') {
      setExistingContact(null);
      return;
    }

    const checkContactExists = async () => {
      if (!activeConversation.contact_phone) {
        setExistingContact(null);
        return;
      }

      setIsCheckingContact(true);
      try {
        // Normalizar telefone para comparação (remover caracteres não numéricos exceto +)
        const normalizePhone = (phone: string) => {
          if (!phone) return '';
          // Manter + no início se existir, depois apenas números
          const hasPlus = phone.startsWith('+');
          const numbers = phone.replace(/\D/g, '');
          return hasPlus ? `+${numbers}` : numbers;
        };

        const normalizedPhone = normalizePhone(activeConversation.contact_phone);
        
        // Buscar contato por telefone usando search (busca em name, phone, email)
        const response = await api.get('/contacts/contacts/', {
          params: {
            search: normalizedPhone
          }
        });
        
        const contacts = response.data.results || response.data;
        // Verificar se encontrou contato com telefone exato (comparação normalizada)
        const contact = contacts.find((contactItem: any) => {
          const contactPhoneNormalized = normalizePhone(contactItem.phone);
          return contactPhoneNormalized === normalizedPhone;
        });
        
        setExistingContact(contact || null);
      } catch (error) {
        console.error('Erro ao verificar contato:', error);
        setExistingContact(null);
      } finally {
        setIsCheckingContact(false);
      }
    };

    checkContactExists();
  }, [activeConversation?.id, activeConversation?.contact_phone, activeConversation?.conversation_type]);

  // 📖 Marcar mensagens como lidas quando abre a conversa (não em modo espião)
  useEffect(() => {
    if (!activeConversation) return;
    if (openInSpyMode) {
      console.log('👁️ [MARK READ] Modo espião ativo - não agendando mark_as_read');
      return;
    }
    
    let isCancelled = false;
    
    const markAsRead = async () => {
      // ✅ CORREÇÃO 1: Verificar se conversa ainda está ativa (usuário não saiu)
      if (isCancelled) {
        console.log('⏸️ [MARK READ] Marcação cancelada - conversa mudou antes do timeout');
        return;
      }
      
      // ✅ CORREÇÃO 2: Verificar novamente no momento da marcação
      const { activeConversation: current, openInSpyMode: spy } = useChatStore.getState();
      if (current?.id !== activeConversation.id || spy) {
        console.log('⏸️ [MARK READ] Marcação cancelada - conversa diferente ou modo espião');
        return;
      }
      
      try {
        console.log('⏰ [MARK READ] Marcando conversa como lida após 2.5s de visualização');
        await api.post(`/chat/conversations/${activeConversation.id}/mark_as_read/`);
        console.log('✅ [MARK READ] Mensagens marcadas como lidas com sucesso');
        
        // ✅ FIX CRÍTICO: Refetch departamentos após marcar como lida para atualizar pending_count
        // Quando uma conversa é marcada como lida, o status pode mudar de 'pending' para 'open'
        // Isso deve atualizar o contador do departamento imediatamente
        const { setDepartments } = useChatStore.getState();
        console.log('🔄 [MARK READ] Refetching departamentos após marcar como lida...');
        api.get('/auth/departments/').then(response => {
          const depts = response.data.results || response.data;
          setDepartments(depts);
          console.log('✅ [MARK READ] Departamentos atualizados:', depts.map((d: any) => ({
            id: d.id,
            name: d.name,
            pending_count: d.pending_count
          })));
        }).catch(error => {
          console.error('❌ [MARK READ] Erro ao refetch departamentos:', error);
        });
      } catch (error) {
        console.error('❌ [MARK READ] Erro ao marcar como lidas:', error);
      }
    };
    
    // ✅ CORREÇÃO 3: Aumentar timeout de 1s → 2.5s (tempo razoável para usuário ver)
    console.log('⏰ [MARK READ] Iniciando timeout de 2.5s para marcar como lida');
    const timeout = setTimeout(markAsRead, 2500);
    
    return () => {
      isCancelled = true;
      clearTimeout(timeout);
      console.log('🔌 [MARK READ] Limpando timeout (usuário saiu da conversa)');
    };
  }, [activeConversation?.id, openInSpyMode]);

  // 🔄 Atualizar informações da conversa quando abre (foto, nome, metadados)
  // ✅ MELHORIA ULTRA-REFINADA: Verificação inteligente com debounce e fallback
  useEffect(() => {
    if (!activeConversation?.id) return;
    
    // ✅ CORREÇÃO CRÍTICA: Cancelar refresh-info anterior quando muda de conversa
    let isCancelled = false;
    // ✅ CORREÇÃO CRÍTICA: Usar optional chaining para evitar acesso antes da inicialização
    if (!activeConversation || !activeConversation.id) {
      return;
    }
    const currentConversationId = activeConversation.id;
    const currentConversationType = activeConversation.conversation_type || 'individual';
    
      const refreshInfo = async () => {
        try {
        // ✅ Verificar se ainda é a mesma conversa (pode ter mudado durante o request)
        if (isCancelled) {
          console.log(`⏸️ [REFRESH] Cancelado - conversa mudou durante request`);
          return;
        }
        
        const { activeConversation: current } = useChatStore.getState();
        if (!current || current.id !== currentConversationId) {
          console.log(`⏸️ [REFRESH] Cancelado - conversa diferente da que iniciou refresh`);
          return;
        }
        
        const type = currentConversationType === 'group' ? 'GRUPO' : 'CONTATO';
        
        // ✅ VERIFICAÇÃO ULTRA-REFINADA: Para grupos, verificar qualidade dos participantes
        if (currentConversationType === 'group') {
          // ✅ CORREÇÃO CRÍTICA: Garantir que group_metadata existe antes de acessar
          if (!current.group_metadata) {
            console.log(`🔄 [${type}] Sem group_metadata, forçando refresh-info`);
            // Continuar para fazer refresh-info
          } else {
            const groupMetadata = current.group_metadata;
            // ✅ CORREÇÃO: group_metadata pode ter propriedades extras não tipadas
            const metadataAny = groupMetadata as any;
            // ✅ CORREÇÃO: Inicializar variáveis ANTES de usar em expressões
            const participants: any[] = Array.isArray(metadataAny.participants) ? metadataAny.participants : [];
            const participantsCount: number = typeof groupMetadata.participants_count === 'number' ? groupMetadata.participants_count : 0;
            const participantsUpdatedAt: string | undefined = metadataAny.participants_updated_at;
            
            // ✅ Verificação 1: Inconsistência
            const hasInconsistency: boolean = participantsCount > 0 && participants.length === 0;
            
            // ✅ Verificação 2: Qualidade (pelo menos 50% válidos)
            const validParticipants = participants.filter((p: any) => p && p.phone && p.phone.length >= 10);
            const hasPoorQuality: boolean = participants.length > 0 && validParticipants.length < participants.length * 0.5;
            
            // ✅ Verificação 3: Timestamp (se disponível, verificar se > 1 hora)
            let isStale: boolean = false;
            if (participantsUpdatedAt && participants.length === 0) {
              const updatedTime = new Date(participantsUpdatedAt).getTime();
              const now = Date.now();
              const oneHourAgo = now - (60 * 60 * 1000);
              isStale = updatedTime < oneHourAgo;
            }
            
            const needsParticipants: boolean = hasInconsistency || hasPoorQuality || isStale;
            
            // Para grupos, nome real vem do refresh-info. Só confiar em group_name se tivermos participantes ou timestamp de refresh (senão pode ser nome do remetente salvo pelo webhook).
            const groupName = (groupMetadata as any).group_name;
            const hasParticipantsOrRefreshed = participants.length > 0 || Boolean(metadataAny.participants_updated_at);
            const hasRealGroupName: boolean = Boolean(
              typeof groupName === 'string' && groupName.trim() !== '' && groupName !== 'Grupo WhatsApp' && hasParticipantsOrRefreshed
            );
            const hasPhoto: boolean = Boolean(current.profile_pic_url);
            const hasName: boolean = hasRealGroupName;
            
            // ✅ Decisão: só pular se tem foto + nome real do grupo + participantes OK
            if (hasPhoto && hasName && !needsParticipants && participants.length > 0) {
              console.log(`✅ [${type}] Informações completas (foto + nome + participantes), pulando refresh-info`);
              return;
            }
            
            if (needsParticipants) {
              console.log(`🔄 [${type}] Forçando refresh-info para atualizar participantes`);
            }
          }
        } else {
          // ✅ Contatos individuais: verificação padrão (foto + nome)
          const hasPhoto = current.profile_pic_url;
          const hasName = current.contact_name && 
                         current.contact_name !== 'Grupo WhatsApp' &&
                         !current.contact_name.match(/^\d+$/);
          
          if (hasPhoto && hasName) {
            console.log(`✅ [${type}] Informações já disponíveis, pulando refresh-info`);
            return;
          }
          }
          
          console.log(`🔄 [${type}] Atualizando informações...`);
          
        const response = await api.post(`/chat/conversations/${currentConversationId}/refresh-info/`);
        
        // ✅ Verificar novamente se ainda é a mesma conversa após request
        if (isCancelled) {
          console.log(`⏸️ [REFRESH] Cancelado - conversa mudou após request`);
          return;
        }
        
        const { activeConversation: currentAfterRequest } = useChatStore.getState();
        if (currentAfterRequest?.id !== currentConversationId) {
          console.log(`⏸️ [REFRESH] Cancelado - conversa diferente após request`);
          return;
        }
        
        // ✅ NOVO: Verificar se refresh-info trouxe participantes (para grupos)
        if (response.data.conversation && currentConversationType === 'group') {
          const updatedConversation = response.data.conversation;
          const updatedGroupMetadata = updatedConversation.group_metadata || {};
          const updatedParticipants = updatedGroupMetadata.participants || [];
          
          // ✅ FALLBACK: Se refresh-info não trouxe participantes, tentar get_participants
          if (updatedParticipants.length === 0) {
            console.log(`🔄 [GRUPO] refresh-info não trouxe participantes, tentando get_participants...`);
            try {
              const participantsResponse = await api.get(
                `/chat/conversations/${currentConversationId}/participants/`
              );
              if (participantsResponse.data.participants?.length > 0) {
                console.log(`✅ [GRUPO] get_participants trouxe ${participantsResponse.data.participants.length} participantes`);
                // Atualizar conversation com participantes do get_participants
                const { updateConversation } = useChatStore.getState();
                updateConversation({
                  ...updatedConversation,
                  group_metadata: {
                    ...updatedGroupMetadata,
                    participants: participantsResponse.data.participants
                  }
                });
              }
            } catch (error) {
              console.warn('⚠️ Erro ao buscar participantes via get_participants:', error);
            }
          }
        }
        
        // ✅ CORREÇÃO CRÍTICA: Atualizar activeConversation diretamente se refresh-info trouxe dados novos
        // Isso garante que nome e foto sejam atualizados imediatamente quando muda de conversa
        if (response.data.conversation) {
          const updatedConversation = response.data.conversation;
          const { updateConversation } = useChatStore.getState();
          
          console.log(`🔄 [${type}] Atualizando activeConversation com dados do refresh-info:`, {
            oldName: current.contact_name,
            newName: updatedConversation.contact_name,
            oldPhoto: current.profile_pic_url,
            newPhoto: updatedConversation.profile_pic_url,
            conversationId: currentConversationId
          });
          
          // ✅ Atualizar tanto a lista quanto a activeConversation
          updateConversation(updatedConversation);
        }
          
          if (response.data.from_cache) {
            console.log(`✅ [${type}] Informações em cache (atualizadas recentemente)`);
          } else if (response.data.warning === 'group_not_found') {
            console.warn(`⚠️ [${type}] ${response.data.message}`);
            // Grupo não encontrado - pode ter sido deletado ou instância saiu
            // Não mostrar erro para não alarmar usuário
          } else {
            console.log(`✅ [${type}] Informações atualizadas:`, response.data.updated_fields);
            // Store será atualizado via WebSocket broadcast
          }
        } catch (error: any) {
        // ✅ Verificar se foi cancelado antes de logar erro
        if (isCancelled) {
          console.log(`⏸️ [REFRESH] Erro ignorado - conversa mudou durante request`);
          return;
        }
          // Silencioso: não mostrar toast se falhar (não crítico)
          console.warn('⚠️ Erro ao atualizar:', error.response?.data?.error || error.message);
        }
      };
      
    // ✅ NOVO: Debounce - aguardar 300ms antes de executar (evita múltiplas chamadas)
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
    }
    
    refreshTimeoutRef.current = setTimeout(() => {
      refreshInfo();
    }, 300);
    
    // ✅ Cleanup: cancelar se conversa mudar
    return () => {
      isCancelled = true;
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current);
      }
      console.log(`🔌 [REFRESH] Cleanup - cancelando refresh-info para conversa ${currentConversationId}`);
    };
    // ✅ CORREÇÃO: Usar apenas id e conversation_type nas dependências
    // group_metadata pode mudar de referência constantemente, causando re-execuções infinitas
    // Acessamos group_metadata diretamente dentro do useEffect quando necessário
  }, [activeConversation?.id, activeConversation?.conversation_type]);

  // Fechar menu ao clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleCloseConversation = async () => {
    if (!activeConversation) return;
    
    try {
      // Usar endpoint dedicado para garantir: mensagens não lidas → lidas, department/assigned_to limpos, fluxo interrompido
      const { data } = await api.post(`/chat/conversations/${activeConversation.id}/close/`);
      
      // ✅ FIX: Atualizar conversa na lista com a resposta do backend (department/assigned_to já limpos)
      const { updateConversation, setDepartments } = useChatStore.getState();
      updateConversation(data);
      
      // ✅ FIX: Refetch departamentos para atualizar contadores
      api.get('/auth/departments/').then(response => {
        const depts = response.data.results || response.data;
        setDepartments(depts);
      }).catch(error => {
        console.error('❌ [ChatWindow] Erro ao refetch departamentos:', error);
      });
      
      toast.success('Conversa fechada!', {
        duration: 2000,
        position: 'bottom-right'
      });
      setShowMenu(false);
      setActiveConversation(null);
    } catch (error) {
      console.error('Erro ao fechar conversa:', error);
      toast.error('Erro ao fechar conversa', {
        duration: 4000,
        position: 'bottom-right'
      });
    }
  };

  /**
   * Iniciar atendimento: atribui a conversa ao usuário atual mantendo o departamento.
   * Mesmo comportamento da transferência: conversa permanece na caixa do departamento
   * (com "X está atendendo") e também em "Minhas conversas".
   */
  const handleStartConversation = async () => {
    if (!activeConversation || !user?.id) return;
    
    try {
      setLoadingStart(true);
      // ✅ CORREÇÃO CRÍTICA: Usar endpoint /assign/ ao invés de /start/
      // /start/ é apenas para criar novas conversas, /assign/ é para atribuir conversas existentes
      const response = await api.post(`/chat/conversations/${activeConversation.id}/assign/`, {
        user_id: user.id
      });
      
      // Atualizar conversa no store usando o método do store
      const { updateConversation } = useChatStore.getState();
      updateConversation(response.data);
      
      // Atualizar conversa ativa
      setActiveConversation(response.data);
      
      // Mostrar notificação de sucesso
      toast.success('Atendimento iniciado com sucesso');
    } catch (error: any) {
      console.error('Erro ao iniciar atendimento:', error);
      toast.error(error.response?.data?.error || 'Erro ao iniciar atendimento');
    } finally {
      setLoadingStart(false);
    }
  };

  // ✅ CORREÇÃO CRÍTICA: Extrair TODAS as propriedades para estados separados para evitar problemas de inicialização
  // ✅ groupName é mantido como estado (pode ser útil no futuro), mas displayName é calculado diretamente no useEffect
  const [_groupName, setGroupName] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string>('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationType, setConversationType] = useState<string>('individual');
  const [contactName, setContactName] = useState<string>('');
  const [contactPhone, setContactPhone] = useState<string>('');
  const [profilePicUrl, setProfilePicUrl] = useState<string | null>(null);
  const [instanceFriendlyName, setInstanceFriendlyName] = useState<string | null>(null);
  const [instanceName, setInstanceName] = useState<string | null>(null);
  const [contactTags, setContactTags] = useState<any[]>([]);
  
  // ✅ CORREÇÃO CRÍTICA: Atualizar TODAS as propriedades em um único useEffect para evitar problemas de inicialização
  useEffect(() => {
    console.log('🔄 [ChatWindow] useEffect de propriedades executado', {
      hasActiveConversation: !!activeConversation,
      activeConversationId: activeConversation?.id,
      conversationType: activeConversation?.conversation_type,
      hasGroupMetadata: !!(activeConversation as any)?.group_metadata
    });
    
    if (!activeConversation || !activeConversation.id) {
      console.log('⚠️ [ChatWindow] Sem activeConversation, limpando estados');
      setConversationId(null);
      setConversationType('individual');
      setContactName('');
      setContactPhone('');
      setProfilePicUrl(null);
      setInstanceFriendlyName(null);
      setInstanceName(null);
      setContactTags([]);
      setGroupName(null);
      setDisplayName('');
      setIsReady(false);
      return;
    }
    
    try {
      console.log('✅ [ChatWindow] Iniciando atualização de propriedades para:', {
        id: activeConversation.id,
        type: activeConversation.conversation_type,
        isGroup: activeConversation.conversation_type === 'group'
      });
      
      const conv = activeConversation;
      const id = conv.id || null;
      const type = conv.conversation_type || 'individual';
      const name = conv.contact_name || '';
      const phone = conv.contact_phone || '';
      const pic = conv.profile_pic_url || null;
      const friendlyName = conv.instance_friendly_name || null;
      const instName = conv.instance_name || null;
      const tags = Array.isArray(conv.contact_tags) ? conv.contact_tags : [];
      
      console.log('📝 [ChatWindow] Propriedades extraídas:', {
        id,
        type,
        name: name.substring(0, 20),
        phone: phone.substring(0, 10),
        hasPic: !!pic,
        tagsCount: tags.length
      });
      
      setConversationId(id);
      setConversationType(type);
      setContactName(name);
      setContactPhone(phone);
      setProfilePicUrl(pic);
      setInstanceFriendlyName(friendlyName);
      setInstanceName(instName);
      setContactTags(tags);
      
      // ✅ Atualizar groupName (apenas para grupos)
      let newGroupName: string | null = null;
      if (type === 'group') {
        console.log('👥 [ChatWindow] Processando grupo, verificando group_metadata...');
        if ('group_metadata' in conv && conv.group_metadata) {
          const rawMetadata = conv.group_metadata;
          console.log('📦 [ChatWindow] group_metadata encontrado:', {
            hasMetadata: !!rawMetadata,
            metadataType: typeof rawMetadata,
            isObject: typeof rawMetadata === 'object' && rawMetadata !== null
          });
          
          if (rawMetadata && typeof rawMetadata === 'object' && rawMetadata !== null) {
            const metadataObj = rawMetadata as Record<string, any>;
            if ('group_name' in metadataObj) {
              const rawGroupName = metadataObj.group_name;
              console.log('📝 [ChatWindow] group_name encontrado:', {
                rawGroupName,
                type: typeof rawGroupName,
                isString: typeof rawGroupName === 'string'
              });
              
              if (rawGroupName && typeof rawGroupName === 'string') {
                const trimmed = rawGroupName.trim();
                if (trimmed.length > 0) {
                  newGroupName = trimmed;
                  console.log('✅ [ChatWindow] groupName definido:', newGroupName);
                }
              }
            } else {
              console.log('⚠️ [ChatWindow] group_name não encontrado em metadataObj');
            }
          }
        } else {
          console.log('⚠️ [ChatWindow] group_metadata não encontrado ou inválido');
        }
      }
      setGroupName(newGroupName); // Mantido para possível uso futuro
      
      // ✅ CORREÇÃO CRÍTICA: Calcular displayName DIRETAMENTE aqui para evitar problemas de inicialização
      // Isso evita dependência circular e garante que displayName seja calculado na mesma execução
      let newDisplayName = '';
      if (type === 'group') {
        // Para grupos: group_name → contact_name → fallback
        if (newGroupName && newGroupName.length > 0) {
          newDisplayName = newGroupName;
        } else if (name && name.length > 0) {
          newDisplayName = name;
        } else {
          newDisplayName = 'Grupo sem nome';
        }
      } else {
        // Para contatos individuais: contact_name → contact_phone → fallback
        if (name && name.length > 0) {
          newDisplayName = name;
        } else if (phone && phone.length > 0) {
          newDisplayName = phone;
        } else {
          newDisplayName = 'Contato sem nome';
        }
      }
      
      console.log('✅ [ChatWindow] displayName calculado:', {
        displayName: newDisplayName,
        type,
        usedGroupName: type === 'group' && newGroupName && newGroupName.length > 0
      });
      
      setDisplayName(newDisplayName);
      console.log('✅ [ChatWindow] Todos os estados atualizados com sucesso');
    } catch (e) {
      console.error('❌ [ChatWindow] ERRO ao atualizar propriedades:', e);
      console.error('❌ [ChatWindow] Stack trace:', (e as Error).stack);
      console.error('❌ [ChatWindow] activeConversation no momento do erro:', activeConversation);
      setConversationId(null);
      setConversationType('individual');
      setContactName('');
      setContactPhone('');
      setProfilePicUrl(null);
      setInstanceFriendlyName(null);
      setInstanceName(null);
      setContactTags([]);
      setGroupName(null);
      setDisplayName('');
      setIsReady(false);
      return;
    }
  }, [activeConversation]);
  
  // ✅ CORREÇÃO CRÍTICA: Marcar como pronto apenas quando conversationId e displayName estão definidos
  // Isso garante que todos os estados foram atualizados antes de renderizar
  useEffect(() => {
    console.log('🔍 [ChatWindow] Verificando isReady:', {
      conversationId,
      displayName,
      displayNameType: typeof displayName,
      displayNameLength: displayName?.length
    });
    
    if (conversationId && displayName !== undefined) {
      console.log('✅ [ChatWindow] Condições atendidas, aguardando tick para marcar como pronto...');
      // Aguardar um tick para garantir que todos os estados foram atualizados
      const timer = setTimeout(() => {
        console.log('✅ [ChatWindow] Marcando como pronto para renderizar');
        setIsReady(true);
      }, 0);
      return () => {
        console.log('🔌 [ChatWindow] Limpando timer de isReady');
        clearTimeout(timer);
      };
    } else {
      console.log('⚠️ [ChatWindow] Condições não atendidas, marcando como não pronto');
      setIsReady(false);
    }
  }, [conversationId, displayName]);

  // Badge permanente: buscar estado ativo Dify ao carregar/trocar de conversa
  useEffect(() => {
    if (!conversationId) { setDifyHeaderState(null); return; }
    let cancelled = false;
    api.get(`/chat/conversations/${conversationId}/dify-agents/`)
      .then((res) => {
        if (cancelled) return;
        const active = (res?.data as any)?.active_state;
        setDifyHeaderState(active?.status === 'active' ? { display_name: active.display_name || 'Dify' } : null);
      })
      .catch(() => { if (!cancelled) setDifyHeaderState(null); });
    return () => { cancelled = true; };
  }, [conversationId]);

  // Carregar fluxos e agentes Dify quando abrir o modal
  useEffect(() => {
    if (!showStartFlowModal || !conversationId) return;
    let cancelled = false;

    // Fluxos
    setLoadingFlows(true);
    setFlowsForStart([]);
    setSelectedFlowId(null);
    api.get(`/chat/conversations/${conversationId}/flows/`)
      .then((res) => {
        if (cancelled) return;
        const raw = res?.data;
        const list = Array.isArray(raw)
          ? raw
          : (Array.isArray((raw as any)?.results) ? (raw as any).results : []);
        const flows = list.map((f: any) => ({
          id: String(f?.id ?? ''),
          name: String(f?.name ?? ''),
          description: f?.description != null ? String(f.description) : '',
        })).filter((f: { id: string }) => f.id);
        setFlowsForStart(flows);
        if (flows.length === 1) setSelectedFlowId(flows[0].id);
      })
      .catch(() => {
        if (!cancelled) setFlowsForStart([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingFlows(false);
      });

    // Agentes Dify
    setLoadingDifyAgents(true);
    setDifyAgents([]);
    setDifyActiveState(null);
    setSelectedDifyAgentId(null);
    api.get(`/chat/conversations/${conversationId}/dify-agents/`)
      .then((res) => {
        if (cancelled) return;
        const data = res?.data as any;
        setDifyAgents(Array.isArray(data?.agents) ? data.agents : []);
        setDifyActiveState(data?.active_state ?? null);
        if (data?.active_state?.catalog_id) setSelectedDifyAgentId(data.active_state.catalog_id);
      })
      .catch(() => {
        if (!cancelled) { setDifyAgents([]); setDifyActiveState(null); }
      })
      .finally(() => {
        if (!cancelled) setLoadingDifyAgents(false);
      });

    return () => { cancelled = true; };
  }, [showStartFlowModal, conversationId]);

  const closeStartFlowModal = useCallback(() => {
    setShowStartFlowModal(false);
    setFlowsForStart([]);
    setSelectedFlowId(null);
    setStartFlowModalTab('flows');
    setDifyAgents([]);
    setDifyActiveState(null);
    setSelectedDifyAgentId(null);
    // A6: garantir que estados de loading sejam resetados ao fechar o modal
    setStartDifyLoading(false);
    setStopDifyLoading(false);
    setShowDifySwapConfirm(false);
  }, []);

  // Fechar modal com Escape
  useEffect(() => {
    if (!showStartFlowModal) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeStartFlowModal();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showStartFlowModal, closeStartFlowModal]);
  
  // ✅ REMOVIDO: useEffect separado para displayName - agora é calculado diretamente no useEffect acima
  // Isso evita problemas de inicialização e dependências circulares
  
  // ✅ CORREÇÃO CRÍTICA: Verificar se activeConversation, conversationId e isReady antes de renderizar
  // Isso evita problemas de inicialização quando um grupo é acessado
  // isReady garante que todos os estados foram atualizados antes de renderizar
  // Verificar também se displayName está definido (não vazio ou undefined)
  
  if (!activeConversation || !activeConversation.id || !conversationId || !isReady || displayName === undefined) {
    // ✅ CORREÇÃO: Se está carregando uma conversa mas ainda não está pronto, mostrar loading
    if (activeConversation && activeConversation.id && conversationId) {
      return (
        <div ref={chatPanelRef} className="flex-1 flex flex-col items-center justify-center bg-chat-bg dark:bg-gray-900 p-8 text-gray-500 dark:text-gray-400">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
            <p className="text-sm text-gray-500 dark:text-gray-400">Carregando conversa...</p>
          </div>
        </div>
      );
    }
    
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-chat-bg dark:bg-gray-900 p-8 text-gray-500 dark:text-gray-400">
        <div className="max-w-md text-center">
          <div className="w-64 h-64 mx-auto mb-8 opacity-20">
            <svg viewBox="0 0 303 172" fill="currentColor" className="text-gray-400 dark:text-gray-500">
              <path d="M229.003 146.214c-18.832-35.882-34.954-69.436-38.857-96.056-4.154-28.35 4.915-49.117 35.368-59.544 30.453-10.426 60.904 4.154 71.33 34.607 10.427 30.453-4.154 60.904-34.607 71.33-15.615 5.346-32.123 4.58-47.234-.337zM3.917 63.734C14.344 33.281 44.795 18.7 75.248 29.127c30.453 10.426 45.034 40.877 34.607 71.30-10.426 30.453-40.877 45.034-71.33 34.607C7.972 124.638-6.61 94.187 3.917 63.734z"/>
            </svg>
          </div>
          <h2 className="text-2xl font-light text-gray-700 dark:text-gray-300 mb-2">Alrea SENSE</h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Envie e receba mensagens sem manter seu celular conectado.<br/>
            Selecione uma conversa para começar.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div ref={chatPanelRef} className="flex h-full w-full bg-chat-panel dark:bg-gray-900 animate-fade-in overflow-hidden">
      {/* Main Chat Area */}
      {/* ✅ CORREÇÃO: Ocultar chat quando histórico estiver aberto */}
      {!showHistory && (
      <div className="flex flex-col flex-1 min-w-0 transition-all duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-chat-sidebar dark:bg-gray-800 border-b border-gray-300 dark:border-gray-700 shadow-sm flex-shrink-0">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Botão Voltar (mobile) */}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Voltar"
            onClick={() => setActiveConversation(null)}
            className="md:hidden rounded-full"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </Button>

          {/* Avatar */}
          <div className="w-10 h-10 rounded-full bg-gray-300 dark:bg-gray-600 overflow-hidden flex-shrink-0 relative">
            {profilePicUrl ? (
              <>
                <img 
                  src={getMediaProxyUrl(profilePicUrl)}
                  alt={displayName}
                  className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
                {/* Badge de grupo */}
                {/* ✅ CORREÇÃO: Usar activeConversation diretamente para evitar problema de inicialização */}
                {(activeConversation?.conversation_type || conversationType) === 'group' && (
                  <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center text-[8px]">
                    👥
                  </div>
                )}
              </>
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gray-300 dark:bg-gray-600 text-gray-600 dark:text-gray-300 font-medium text-lg">
                {/* ✅ CORREÇÃO: Usar activeConversation diretamente para evitar problema de inicialização */}
                {(activeConversation?.conversation_type || conversationType) === 'group' ? '👥' : (displayName[0] || '?').toUpperCase()}
              </div>
            )}
          </div>

          {/* Nome e Tags */}
          <div className="flex-1 min-w-0">
            {/* Nome com botão de contato */}
            <div className="flex items-center gap-2">
              <h2 className="text-base font-medium text-gray-900 dark:text-gray-100 truncate flex items-center gap-1.5">
                {/* ✅ CORREÇÃO: Usar activeConversation diretamente para evitar problema de inicialização */}
                {(activeConversation?.conversation_type || conversationType) === 'group' && <span>👥</span>}
                {displayName}
              </h2>
              
              {/* ✅ Botão Adicionar/Ver Contato (apenas para contatos individuais) */}
              {/* ✅ CORREÇÃO: Usar activeConversation diretamente para evitar problema de inicialização */}
              {(activeConversation?.conversation_type || conversationType) !== 'group' && (
                <button
                  onClick={() => {
                    if (existingContact) {
                      // Carregar contato completo antes de abrir modal
                      api.get(`/contacts/contacts/${existingContact.id}/`)
                        .then(response => {
                          setExistingContact(response.data);
                          setShowContactModal(true);
                        })
                        .catch(error => {
                          console.error('Erro ao carregar contato:', error);
                          toast.error('Erro ao carregar contato');
                        });
                    } else {
                      setShowContactModal(true);
                    }
                  }}
                  disabled={isCheckingContact}
                  className="flex-shrink-0 p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md"
                  title={existingContact ? 'Ver Contato' : 'Adicionar Contato'}
                >
                  {isCheckingContact ? (
                    <div className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
                  ) : existingContact ? (
                    <User className="w-4 h-4 text-blue-600" />
                  ) : (
                    <Plus className="w-4 h-4 text-green-600" />
                  )}
                </button>
              )}
            </div>
            
            {/* Tags: Instância + Tags do Contato + Atendente */}
            <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
              {/* Tag da Instância (azul) - Exibe nome amigável, não UUID */}
              {(instanceFriendlyName || instanceName) && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-200 rounded-full text-xs font-medium">
                  📱 {instanceFriendlyName || instanceName}
                </span>
              )}

              {/* Tags do Contato (customizadas por cor) */}
              {contactTags && contactTags.length > 0 && (
                <>
                  {contactTags.map((tag) => (
                    <span 
                      key={tag.id}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{
                        backgroundColor: `${tag.color}20`,
                        color: tag.color
                      }}
                    >
                      🏷️ {tag.name}
                    </span>
                  ))}
                </>
              )}

              {/* Badge de agente Dify ativo */}
              {difyHeaderState && (
                <span
                  title={`Agente Dify ativo: ${difyHeaderState.display_name}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 rounded-full text-xs font-medium cursor-default"
                >
                  <Bot className="w-3 h-3" />
                  {difyHeaderState.display_name}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* INICIAR ATENDIMENTO: atribui ao usuário; mantém no departamento; aparece nos dois lugares (departamento + Minhas conversas) com "X está atendendo" */}
        {/* Mostrar quando: conversa não atribuída E (pending OU open com department OU fallback: status !== 'closed' para payload incompleto ex. Meta) */}
        {activeConversation &&
         !activeConversation.assigned_to &&
         (activeConversation.status === 'pending' ||
          (activeConversation.status === 'open' && activeConversation.department) ||
          activeConversation.status !== 'closed') && (
          <div className="px-4 py-2 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800">
            <button
              onClick={handleStartConversation}
              disabled={loadingStart}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm"
            >
              {loadingStart ? 'Iniciando...' : 'INICIAR ATENDIMENTO'}
            </button>
            <p className="mt-1.5 text-xs text-center text-gray-600 dark:text-gray-400">
              Ou envie uma mensagem para ser atribuído automaticamente.
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Indicador Modo Espião (quando conversa aberta em spy) */}
          {openInSpyMode && (
            <span
              role="status"
              aria-live="polite"
              className="flex flex-shrink-0 items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200 text-xs font-medium"
              title="Visualização sem marcar como lida"
            >
              <Eye className="w-4 h-4 flex-shrink-0" aria-hidden />
              Modo espião
            </span>
          )}
          {/* Botão Histórico (apenas se contato existir) */}
          {/* ✅ CORREÇÃO: Usar activeConversation diretamente para evitar problema de inicialização */}
          {existingContact && (activeConversation?.conversation_type || conversationType) !== 'group' && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Histórico do Contato"
              onClick={() => setShowHistory(!showHistory)}
              className={`rounded-full ${showHistory ? 'bg-gray-200 dark:bg-gray-700' : ''}`}
            >
              <Clock className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </Button>
          )}
          
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Buscar"
            className="rounded-full"
          >
            <Search className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </Button>
          
          {/* Menu 3 pontos */}
          <div className="relative" ref={menuRef}>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Menu"
              onClick={() => setShowMenu(!showMenu)}
              className="rounded-full"
            >
              <MoreVertical className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </Button>

            {showMenu && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-1 z-50 animate-scale-in">
                {/* Informações do Grupo - apenas para grupos */}
                {/* ✅ CORREÇÃO: Usar activeConversation diretamente para evitar problema de inicialização */}
                {(activeConversation?.conversation_type || conversationType) === 'group' && (
                  <button
                    onClick={async () => {
                      if (!conversationId) return;
                      
                      setShowMenu(false);
                      setShowGroupInfo(true);
                      setLoadingGroupInfo(true);
                      setGroupInfo(null); // Limpar dados anteriores antes de carregar novos
                      
                      try {
                        const response = await api.get(`/chat/conversations/${conversationId}/group-info/`);
                        
                        // Garantir que response.data existe e inicializar valores padrão de forma segura
                        const groupData = response.data || {};
                        // ✅ CORREÇÃO: Inicializar objeto completo de uma vez para evitar TDZ
                        const safeGroupInfo = {
                          group_name: groupData.group_name || 'Sem nome',
                          description: groupData.description || null,
                          creation_date: groupData.creation_date || null,
                          participants_count: typeof groupData.participants_count === 'number' ? groupData.participants_count : 0,
                          participants: Array.isArray(groupData.participants) ? groupData.participants : [],
                          admins: Array.isArray(groupData.admins) ? groupData.admins : [],
                          warning: groupData.warning || null
                        };
                        setGroupInfo(safeGroupInfo);
                        // Atualizar nome/foto na lista e no header quando o backend retornar conversation
                        if (response.data?.conversation) {
                          useChatStore.getState().updateConversation(response.data.conversation);
                        }
                      } catch (error: any) {
                        console.error('Erro ao buscar informações do grupo:', error);
                        toast.error(error?.response?.data?.error || 'Erro ao buscar informações do grupo');
                        setShowGroupInfo(false);
                        setGroupInfo(null);
                      } finally {
                        setLoadingGroupInfo(false);
                      }
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
                  >
                    <User className="w-4 h-4" />
                    Informações do grupo
                  </button>
                )}

                {can_transfer_conversations && (
                  <button
                    onClick={() => {
                      setShowTransferModal(true);
                      setShowMenu(false);
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
                  >
                    <ArrowRightLeft className="w-4 h-4" />
                    Transferir conversa
                  </button>
                )}

                {activeConversation?.conversation_type !== 'group' && conversationId && (
                  <button
                    onClick={() => {
                      setShowMenu(false);
                      setShowStartFlowModal(true);
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
                  >
                    <Zap className="w-4 h-4" />
                    Automação
                  </button>
                )}

                {activeConversation?.conversation_type !== 'group' && (
                  <button
                    onClick={handleCloseConversation}
                    className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-3"
                  >
                    <XCircle className="w-4 h-4" />
                    Fechar conversa
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      {/* ✅ CORREÇÃO: Renderizar MessageList apenas se conversationId estiver inicializado */}
      {conversationId && (
      <div className="flex-1 overflow-hidden">
        <MessageList
          onSendReplyButtonClick={openInSpyMode ? undefined : handleSendReplyButtonClick}
        />
      </div>
      )}

        {/* Input */}
        {/* ✅ CORREÇÃO: Renderizar MessageInput apenas se conversationId estiver inicializado */}
        {conversationId && (
        <MessageInput 
          sendMessage={sendMessage}
          sendMessageAsTemplate={sendMessageAsTemplate}
          sendMessageWithButtons={sendMessageWithButtons}
          sendMessageWithList={sendMessageWithList}
          sendMessageWithContacts={sendMessageWithContacts}
          sendTyping={openInSpyMode ? noopTyping : sendTyping}
          isConnected={isConnected}
            conversationId={conversationId}
            conversationType={(activeConversation?.conversation_type || conversationType) as 'individual' | 'group' | 'broadcast'}
        />
        )}
      </div>
      )}

      {/* ✅ CORREÇÃO: Histórico ocupa toda a tela quando aberto */}
      {showHistory && existingContact && (activeConversation?.conversation_type || conversationType) !== 'group' && (
        <div className="flex flex-col flex-1 min-w-0 bg-white dark:bg-gray-900 h-full overflow-hidden">
          <div className="p-4 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between bg-gray-50 dark:bg-gray-800 flex-shrink-0">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Histórico</h3>
            <button
              onClick={() => setShowHistory(false)}
              className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
            >
              <X className="w-4 h-4 text-gray-600 dark:text-gray-400" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <ContactHistory
              contactId={existingContact.id}
              onClose={() => setShowHistory(false)}
            />
          </div>
        </div>
      )}

      {/* Modals */}
      {/* Modal Iniciar fluxo / Agentes Dify (abas) */}
      {showStartFlowModal && conversationId && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="start-flow-modal-title"
          onClick={closeStartFlowModal}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="px-5 pt-5 pb-0 flex items-center justify-between">
              <h2 id="start-flow-modal-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">Automação</h2>
              <Button type="button" variant="ghost" size="icon" aria-label="Fechar" onClick={closeStartFlowModal} className="rounded-full">
                <X className="w-5 h-5" />
              </Button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-200 dark:border-gray-700 mt-4 px-5">
              <button
                type="button"
                onClick={() => setStartFlowModalTab('flows')}
                className={`flex items-center gap-2 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                  startFlowModalTab === 'flows'
                    ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                <Zap className="w-4 h-4" />
                Fluxos
              </button>
              <button
                type="button"
                onClick={() => setStartFlowModalTab('dify')}
                className={`flex items-center gap-2 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                  startFlowModalTab === 'dify'
                    ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                <Bot className="w-4 h-4" />
                Agentes Dify
                {difyActiveState?.status === 'active' && (
                  <span className="w-2 h-2 rounded-full bg-green-500 inline-block" title="Agente ativo" />
                )}
              </button>
            </div>

            {/* Tab: Fluxos */}
            {startFlowModalTab === 'flows' && (
              <>
                <div className="p-5 overflow-y-auto flex-1">
                  {loadingFlows ? (
                    <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
                      <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" aria-hidden />
                      <span>Carregando fluxos...</span>
                    </div>
                  ) : flowsForStart.length === 0 ? (
                    <div className="text-sm text-gray-500 dark:text-gray-400 space-y-2">
                      <p>
                        Nenhum fluxo ativo para {(() => {
                          const conv = activeConversation;
                          const deptName = conv?.department_name || (typeof conv?.department === 'object' && conv?.department != null ? (conv.department as { name?: string }).name : null);
                          if (conv?.department != null && conv.department !== '' && deptName) return <>o departamento <strong>{deptName}</strong></>;
                          return <>o <strong>Inbox</strong></>;
                        })()} desta conversa.
                      </p>
                      <p className="text-xs">
                        Em <strong>Configurações &gt; Fluxos</strong>, crie ou edite um fluxo e vincule ao mesmo escopo (Inbox ou ao departamento desta conversa).
                      </p>
                    </div>
                  ) : (
                    <ul className="space-y-3">
                      {flowsForStart.map((f) => (
                        <li key={f.id}>
                          <label className="flex gap-3 cursor-pointer p-3 rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <input
                              type="radio"
                              name="flow"
                              value={f.id}
                              checked={selectedFlowId === f.id}
                              onChange={() => setSelectedFlowId(f.id)}
                              className="mt-1"
                            />
                            <div className="flex-1 min-w-0">
                              <span className="font-medium text-gray-900 dark:text-gray-100">{f.name}</span>
                              {f.description && (
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{f.description}</p>
                              )}
                            </div>
                          </label>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="px-5 py-4 border-t border-gray-200 dark:border-gray-600 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={closeStartFlowModal}
                    className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    disabled={loadingFlows || flowsForStart.length === 0 || (flowsForStart.length > 1 && !selectedFlowId) || startFlowLoading}
                    onClick={async () => {
                      const flowId = flowsForStart.length === 1 ? flowsForStart[0].id : selectedFlowId;
                      if (!flowId || !conversationId) return;
                      setStartFlowLoading(true);
                      try {
                        const res = await api.post(`/chat/conversations/${conversationId}/start-flow/`, {
                          flow_id: String(flowId),
                        });
                        if (res?.data?.success) {
                          const queued = res.data?.messages_queued;
                          if (typeof queued === 'number' && queued === 0) {
                            toast.warning('Fluxo iniciado, mas o Typebot não enviou nenhuma mensagem. Verifique se o primeiro bloco do fluxo é do tipo texto.');
                          } else {
                            toast.success('Fluxo iniciado. O cliente receberá o menu/etapas em instantes.');
                          }
                          closeStartFlowModal();
                        } else {
                          toast.error((res?.data?.message as string) || 'Nenhum fluxo ativo para esta conversa.');
                        }
                      } catch (e: any) {
                        const msg = e?.response?.data?.message ?? e?.response?.data?.detail;
                        toast.error(typeof msg === 'string' ? msg : 'Não foi possível iniciar o fluxo.');
                      } finally {
                        setStartFlowLoading(false);
                      }
                    }}
                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:pointer-events-none"
                  >
                    {startFlowLoading ? 'Iniciando...' : 'Confirmar ativação'}
                  </button>
                </div>
              </>
            )}

            {/* Tab: Agentes Dify */}
            {startFlowModalTab === 'dify' && (
              <>
                <div className="p-5 overflow-y-auto flex-1">
                  {/* Banner: agente ativo */}
                  {difyActiveState?.status === 'active' && (
                    <div className="mb-4 p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-sm text-green-800 dark:text-green-300">
                        <Bot className="w-4 h-4 shrink-0" />
                        <span>
                          Agente <strong>{difyAgents.find(a => a.id === difyActiveState.catalog_id)?.display_name || difyActiveState.display_name || 'Dify'}</strong> ativo nesta conversa.
                        </span>
                      </div>
                      <button
                        type="button"
                        disabled={stopDifyLoading}
                        onClick={async () => {
                          if (!conversationId) return;
                          setStopDifyLoading(true);
                          try {
                            const res = await api.post(`/chat/conversations/${conversationId}/stop-dify-agent/`);
                            if (res?.data?.success) {
                              toast.success('Agente parado.');
                              setDifyActiveState(null);
                              setSelectedDifyAgentId(null);
                              setDifyHeaderState(null);
                            } else {
                              toast.error(res?.data?.message || 'Erro ao parar agente.');
                            }
                          } catch (e: any) {
                            toast.error(e?.response?.data?.message || 'Erro ao parar agente.');
                          } finally {
                            setStopDifyLoading(false);
                          }
                        }}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                      >
                        <StopCircle className="w-3.5 h-3.5" />
                        {stopDifyLoading ? 'Parando...' : 'Parar agente'}
                      </button>
                    </div>
                  )}

                  {loadingDifyAgents ? (
                    <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
                      <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" aria-hidden />
                      <span>Carregando agentes...</span>
                    </div>
                  ) : difyAgents.length === 0 ? (
                    <div className="text-sm text-gray-500 dark:text-gray-400 space-y-2">
                      <p>Nenhum agente Dify cadastrado.</p>
                      <p className="text-xs">Em <strong>Configurações &gt; IA &gt; Dify</strong>, cadastre um agente para usar aqui.</p>
                    </div>
                  ) : (
                    <ul className="space-y-3">
                      {difyAgents.map((a) => (
                        <li key={a.id}>
                          <label className="flex gap-3 cursor-pointer p-3 rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <input
                              type="radio"
                              name="dify-agent"
                              value={a.id}
                              checked={selectedDifyAgentId === a.id}
                              onChange={() => setSelectedDifyAgentId(a.id)}
                              className="mt-1"
                            />
                            <div className="flex-1 min-w-0">
                              <span className="font-medium text-gray-900 dark:text-gray-100">{a.display_name}</span>
                              {a.description && (
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{a.description}</p>
                              )}
                              <p className="text-xs font-mono text-gray-400 dark:text-gray-500 mt-0.5">{a.dify_app_id}</p>
                            </div>
                          </label>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="px-5 py-4 border-t border-gray-200 dark:border-gray-600 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={closeStartFlowModal}
                    className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                  >
                    Cancelar
                  </button>
                  {/* Confirmação de troca de agente */}
                  {showDifySwapConfirm ? (
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-amber-700 dark:text-amber-300 text-xs">Encerra sessão atual. Confirmar?</span>
                      <button
                        type="button"
                        onClick={() => setShowDifySwapConfirm(false)}
                        className="px-3 py-1.5 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg text-xs"
                      >
                        Não
                      </button>
                      <button
                        type="button"
                        disabled={startDifyLoading}
                        onClick={async () => {
                          if (!selectedDifyAgentId || !conversationId) return;
                          setShowDifySwapConfirm(false);
                          setStartDifyLoading(true);
                          try {
                            const res = await api.post(`/chat/conversations/${conversationId}/start-dify-agent/`, {
                              catalog_id: selectedDifyAgentId,
                            });
                            if (res?.data?.success) {
                              const agentName = difyAgents.find(a => a.id === selectedDifyAgentId)?.display_name || res.data.display_name || 'Dify';
                              toast.success(res.data.message || 'Agente trocado.');
                              setDifyHeaderState({ display_name: agentName });
                              closeStartFlowModal();
                            } else {
                              toast.error(res?.data?.message || 'Erro ao trocar agente.');
                            }
                          } catch (e: any) {
                            toast.error(e?.response?.data?.message || 'Não foi possível trocar o agente.');
                          } finally {
                            setStartDifyLoading(false);
                          }
                        }}
                        className="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-xs hover:bg-amber-700 disabled:opacity-50"
                      >
                        {startDifyLoading ? '...' : 'Sim, trocar'}
                      </button>
                    </div>
                  ) : (
                  <button
                    type="button"
                    disabled={loadingDifyAgents || difyAgents.length === 0 || !selectedDifyAgentId || startDifyLoading}
                    onClick={async () => {
                      if (!selectedDifyAgentId || !conversationId) return;
                      // Se há agente diferente ativo, pedir confirmação antes de trocar
                      if (difyActiveState?.status === 'active' && selectedDifyAgentId !== difyActiveState.catalog_id) {
                        setShowDifySwapConfirm(true);
                        return;
                      }
                      setStartDifyLoading(true);
                      try {
                        const res = await api.post(`/chat/conversations/${conversationId}/start-dify-agent/`, {
                          catalog_id: selectedDifyAgentId,
                        });
                        if (res?.data?.success) {
                          const agentName = difyAgents.find(a => a.id === selectedDifyAgentId)?.display_name || res.data.display_name || 'Dify';
                          toast.success(res.data.message || 'Agente iniciado. As respostas serão enviadas automaticamente.');
                          setDifyHeaderState({ display_name: agentName });
                          closeStartFlowModal();
                        } else {
                          toast.error(res?.data?.message || 'Erro ao iniciar agente.');
                        }
                      } catch (e: any) {
                        toast.error(e?.response?.data?.message || 'Não foi possível iniciar o agente.');
                      } finally {
                        setStartDifyLoading(false);
                      }
                    }}
                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:pointer-events-none"
                  >
                    {startDifyLoading
                      ? 'Iniciando...'
                      : difyActiveState?.status === 'active' && selectedDifyAgentId !== difyActiveState.catalog_id
                        ? 'Trocar agente'
                        : 'Ativar agente'}
                  </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {showTransferModal && activeConversation && (
        <TransferModal
          conversation={{
            id: conversationId!,
            conversation_type: (activeConversation?.conversation_type || conversationType) as any,
            contact_name: contactName,
            contact_phone: contactPhone,
            tenant: activeConversation.tenant || '',
            department: activeConversation.department || null,
            department_name: activeConversation.department_name || '',
            status: activeConversation.status || 'open',
            metadata: activeConversation.metadata || {},
            participants: activeConversation.participants || [],
            created_at: activeConversation.created_at || '',
            updated_at: activeConversation.updated_at || '',
            unread_count: activeConversation.unread_count || 0,
            ...(activeConversation.group_metadata ? { group_metadata: activeConversation.group_metadata } : {}),
          } as any}
          onClose={() => setShowTransferModal(false)}
          onTransferSuccess={() => {
            setShowTransferModal(false);
          }}
        />
      )}

      {/* Modal de Informações do Grupo */}
      {showGroupInfo && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true" aria-labelledby="group-info-modal-title">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between">
              <h2 id="group-info-modal-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">Informações do Grupo</h2>
              <Button type="button" variant="ghost" size="icon" aria-label="Fechar" onClick={() => { setShowGroupInfo(false); setGroupInfo(null); }} className="rounded-full">
                <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </Button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4">
              {loadingGroupInfo ? (
                <div className="flex items-center justify-center py-8">
                  <div className="w-8 h-8 border-4 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                </div>
              ) : groupInfo ? (
                <div className="space-y-6">
                  {/* Informações Básicas */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Informações Básicas</h3>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600 dark:text-gray-400 w-24">Nome:</span>
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{groupInfo?.group_name || 'Sem nome'}</span>
                      </div>
                      {groupInfo?.description && (
                        <div className="flex items-start gap-2">
                          <span className="text-sm text-gray-600 dark:text-gray-400 w-24">Descrição:</span>
                          <span className="text-sm text-gray-900 dark:text-gray-100 flex-1">{groupInfo.description}</span>
                        </div>
                      )}
                      {groupInfo?.creation_date && (
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-gray-600 dark:text-gray-400 w-24">Criado em:</span>
                          <span className="text-sm text-gray-900 dark:text-gray-100">
                            {new Date(groupInfo.creation_date).toLocaleString('pt-BR', {
                              dateStyle: 'long',
                              timeStyle: 'short'
                            })}
                          </span>
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600 dark:text-gray-400 w-24">Participantes:</span>
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {(() => {
                            if (!groupInfo) return 0;
                            if (typeof groupInfo.participants_count === 'number') {
                              return groupInfo.participants_count;
                            }
                            if (Array.isArray(groupInfo.participants)) {
                              return groupInfo.participants.length;
                            }
                            return 0;
                          })()}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Administradores */}
                  {groupInfo?.admins && Array.isArray(groupInfo.admins) && groupInfo.admins.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-gray-700 mb-3">Administradores ({groupInfo.admins.length})</h3>
                      <div className="space-y-2">
                        {groupInfo.admins.map((admin: any, index: number) => (
                          admin && (
                            <div key={admin.id || admin.phone || index} className="flex items-center gap-2 p-2 bg-blue-50 rounded">
                              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{admin?.name || admin?.phone || 'Admin'}</span>
                              {admin?.phone && admin?.name && (
                                <span className="text-xs text-gray-500 dark:text-gray-400">({admin.phone})</span>
                              )}
                            </div>
                          )
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Participantes */}
                  {groupInfo?.participants && Array.isArray(groupInfo.participants) && groupInfo.participants.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-gray-700 mb-3">Participantes ({groupInfo.participants.length})</h3>
                      <div className="space-y-1 max-h-64 overflow-y-auto">
                        {groupInfo.participants.map((participant: any, index: number) => (
                          participant && (
                            <div 
                              key={participant.id || participant.phone || index} 
                              className={`flex items-center gap-2 p-2 rounded ${participant?.is_admin ? 'bg-blue-50' : 'bg-gray-50'}`}
                            >
                              <span className="text-sm text-gray-900 flex-1">
                                {participant?.name || participant?.phone || 'Participante'}
                              </span>
                              {participant?.phone && participant?.name && (
                                <span className="text-xs text-gray-500 dark:text-gray-400">{participant.phone}</span>
                              )}
                              {participant?.is_admin && (
                                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">Admin</span>
                              )}
                            </div>
                          )
                        ))}
                      </div>
                    </div>
                  )}

                  {groupInfo?.warning && (
                    <div className="p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
                      ⚠️ {groupInfo.warning}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  Nenhuma informação disponível
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ✅ Modal de Contato */}
      {showContactModal && (
        <ContactModal
          isOpen={showContactModal}
          onClose={() => {
            setShowContactModal(false);
            // ✅ CORREÇÃO: NÃO resetar existingContact ao fechar
            // O contato pode ter sido salvo/atualizado, então manter o estado
            // O existingContact será atualizado no onSuccess se necessário
          }}
          contact={existingContact}
          initialPhone={contactPhone || ''}
          initialName={displayName}
          onSuccess={async () => {
            // ✅ MELHORIA: Recarregar contato completo e atualizar activeConversation com tags
            if (contactPhone) {
              // Normalizar telefone para comparação
              const normalizePhone = (phone: string) => {
                if (!phone) return '';
                const hasPlus = phone.startsWith('+');
                const numbers = phone.replace(/\D/g, '');
                return hasPlus ? `+${numbers}` : numbers;
              };

              const normalizedPhone = normalizePhone(contactPhone);
              
              try {
                // Buscar contato completo com tags
                const response = await api.get('/contacts/contacts/', {
                  params: {
                    search: normalizedPhone
                  }
                });
                
                const contacts = response.data.results || response.data;
                const contact = contacts.find((contactItem: any) => {
                  const contactPhoneNormalized = normalizePhone(contactItem.phone);
                  return contactPhoneNormalized === normalizedPhone;
                });
                
                if (contact) {
                  // ✅ Atualizar existingContact com contato completo (incluindo tags)
                  setExistingContact(contact);
                  
                  // ✅ Atualizar activeConversation no store com tags atualizadas
                  // ✅ CORREÇÃO: Usar getState para garantir que temos a versão mais atualizada
                  const { updateConversation, activeConversation: currentActiveConversation } = useChatStore.getState();
                  if (currentActiveConversation && currentActiveConversation.id === conversationId) {
                  updateConversation({
                      ...currentActiveConversation,
                    contact_tags: contact.tags || []
                  });
                  
                  console.log('✅ [CONTACT MODAL] Contato atualizado e conversa sincronizada com tags');
                  }
                } else {
                  // Se não encontrou, limpar existingContact (contato foi deletado)
                  setExistingContact(null);
                }
              } catch (error) {
                console.error('❌ [CONTACT MODAL] Erro ao recarregar contato:', error);
              }
            }
          }}
        />
      )}
    </div>
  );
}
