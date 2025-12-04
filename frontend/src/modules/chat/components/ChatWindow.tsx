/**
 * Janela de chat principal - Estilo WhatsApp Web
 */
import React, { useState, useRef, useEffect } from 'react';
import { ArrowLeft, MoreVertical, Phone, Video, Search, X, ArrowRightLeft, CheckCircle, XCircle, Plus, User, Clock } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TransferModal } from './TransferModal';
import { usePermissions } from '@/hooks/usePermissions';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { useChatSocket } from '../hooks/useChatSocket';
import { usePollingFallback } from '../hooks/usePollingFallback';
import { getDisplayName } from '../utils/phoneFormatter';
import ContactModal from '@/components/contacts/ContactModal';
import ContactHistory from '@/components/contacts/ContactHistory';

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

export function ChatWindow() {
  const { activeConversation, setActiveConversation } = useChatStore();
  // ✅ CORREÇÃO: can_transfer_conversations pode não existir no tipo, usar verificação segura
  const permissions = usePermissions();
  const can_transfer_conversations = (permissions as any).can_transfer_conversations || false;
  
  // ✅ CORREÇÃO CRÍTICA: Inicializar todos os estados ANTES de qualquer hook que dependa de activeConversation
  const [showMenu, setShowMenu] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [existingContact, setExistingContact] = useState<any>(null);
  const [isCheckingContact, setIsCheckingContact] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showGroupInfo, setShowGroupInfo] = useState(false);
  const [groupInfo, setGroupInfo] = useState<any>(null);
  const [loadingGroupInfo, setLoadingGroupInfo] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  // ✅ NOVO: Ref para debounce do refresh-info (deve estar no nível superior)
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // ✅ CORREÇÃO: Capturar activeConversation.id de forma segura antes de usar em hooks
  const activeConversationId = activeConversation?.id;
  
  // 🔌 Conectar WebSocket para esta conversa (usa manager global) - DEPOIS de inicializar estados
  const { isConnected, sendMessage, sendTyping } = useChatSocket(activeConversationId);
  // ✅ NOVO: Fallback de polling quando WebSocket falha - DEPOIS de inicializar estados
  usePollingFallback(activeConversationId);
  
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
    if (!activeConversation || activeConversation.conversation_type === 'group') {
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
        const contact = contacts.find((c: any) => {
          const contactPhoneNormalized = normalizePhone(c.phone);
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

  // 📖 Marcar mensagens como lidas quando abre a conversa
  useEffect(() => {
    if (!activeConversation) return;
    
    let isCancelled = false;
    
    const markAsRead = async () => {
      // ✅ CORREÇÃO 1: Verificar se conversa ainda está ativa (usuário não saiu)
      if (isCancelled) {
        console.log('⏸️ [MARK READ] Marcação cancelada - conversa mudou antes do timeout');
        return;
      }
      
      // ✅ CORREÇÃO 2: Verificar novamente no momento da marcação
      const { activeConversation: current } = useChatStore.getState();
      if (current?.id !== activeConversation.id) {
        console.log('⏸️ [MARK READ] Marcação cancelada - conversa diferente da que foi aberta');
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
  }, [activeConversation?.id]);

  // 🔄 Atualizar informações da conversa quando abre (foto, nome, metadados)
  // ✅ MELHORIA ULTRA-REFINADA: Verificação inteligente com debounce e fallback
  useEffect(() => {
    if (!activeConversation?.id) return;
    
    // ✅ CORREÇÃO CRÍTICA: Cancelar refresh-info anterior quando muda de conversa
    let isCancelled = false;
    const currentConversationId = activeConversation.id;
    const currentConversationType = activeConversation.conversation_type;
    
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
            
            // ✅ Verificação padrão: foto e nome
            const hasPhoto: boolean = Boolean(current.profile_pic_url);
            const hasName: boolean = Boolean(
              current.contact_name && 
              current.contact_name !== 'Grupo WhatsApp' &&
              !current.contact_name.match(/^\d+$/)
            );
            
            // ✅ Decisão: só pular se tem foto + nome + participantes OK
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
      await api.patch(`/chat/conversations/${activeConversation.id}/`, {
        status: 'closed'
      });
      
      // ✅ FIX: Atualizar conversa na lista ao invés de remover
      // Se remover, quando nova mensagem chegar e reabrir, não aparece na lista
      const { updateConversation, setDepartments } = useChatStore.getState();
      updateConversation({
        ...activeConversation,
        status: 'closed'
      });
      
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

  const handleMarkAsResolved = async () => {
    if (!activeConversation) return;
    
    try {
      await api.patch(`/chat/conversations/${activeConversation.id}/`, {
        status: 'closed'
      });
      toast.success('Conversa marcada como resolvida!', {
        duration: 2000,
        position: 'bottom-right'
      });
      setShowMenu(false);
    } catch (error) {
      console.error('Erro ao marcar como resolvida:', error);
      toast.error('Erro ao marcar como resolvida', {
        duration: 4000,
        position: 'bottom-right'
      });
    }
  };

  if (!activeConversation) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#f0f2f5] p-8">
        <div className="max-w-md text-center">
          <div className="w-64 h-64 mx-auto mb-8 opacity-20">
            <svg viewBox="0 0 303 172" fill="currentColor" className="text-gray-400">
              <path d="M229.003 146.214c-18.832-35.882-34.954-69.436-38.857-96.056-4.154-28.35 4.915-49.117 35.368-59.544 30.453-10.426 60.904 4.154 71.33 34.607 10.427 30.453-4.154 60.904-34.607 71.33-15.615 5.346-32.123 4.58-47.234-.337zM3.917 63.734C14.344 33.281 44.795 18.7 75.248 29.127c30.453 10.426 45.034 40.877 34.607 71.33-10.426 30.453-40.877 45.034-71.33 34.607C7.972 124.638-6.61 94.187 3.917 63.734z"/>
            </svg>
          </div>
          <h2 className="text-2xl font-light text-gray-700 mb-2">Flow Chat Web</h2>
          <p className="text-gray-500 text-sm">
            Envie e receba mensagens sem manter seu celular conectado.<br/>
            Selecione uma conversa para começar.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full bg-[#efeae2] animate-fade-in overflow-hidden">
      {/* Main Chat Area */}
      <div className={`flex flex-col flex-1 min-w-0 transition-all duration-300 ${showHistory ? 'md:mr-[320px]' : ''}`}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-[#f0f2f5] border-b border-gray-300 shadow-sm flex-shrink-0">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Botão Voltar (mobile) */}
          <button
            onClick={() => setActiveConversation(null)}
            className="md:hidden p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md"
            title="Voltar"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>

          {/* Avatar */}
          <div className="w-10 h-10 rounded-full bg-gray-300 overflow-hidden flex-shrink-0 relative">
            {activeConversation.profile_pic_url ? (
              <>
                <img 
                  src={getMediaProxyUrl(activeConversation.profile_pic_url)}
                  alt={getDisplayName(activeConversation)}
                  className="w-full h-full object-cover"
                  onLoad={() => console.log('✅ [IMG] Foto carregada com sucesso!')}
                onError={(e) => {
                  console.error('❌ [IMG] Erro ao carregar foto:', e);
                  console.error('   URL:', e.currentTarget.src);
                  e.currentTarget.style.display = 'none';
                }}
              />
                {/* Badge de grupo */}
                {activeConversation.conversation_type === 'group' && (
                  <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center text-[8px]">
                    👥
                  </div>
                )}
              </>
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-lg">
                {activeConversation.conversation_type === 'group' ? '👥' : getDisplayName(activeConversation)[0].toUpperCase()}
              </div>
            )}
          </div>

          {/* Nome e Tags */}
          <div className="flex-1 min-w-0">
            {/* Nome com botão de contato */}
            <div className="flex items-center gap-2">
              <h2 className="text-base font-medium text-gray-900 truncate flex items-center gap-1.5">
                {activeConversation.conversation_type === 'group' && <span>👥</span>}
                {getDisplayName(activeConversation)}
              </h2>
              
              {/* ✅ Botão Adicionar/Ver Contato (apenas para contatos individuais) */}
              {activeConversation.conversation_type !== 'group' && (
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
                  className="flex-shrink-0 p-1.5 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md"
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
            
            {/* Tags: Instância + Tags do Contato */}
            <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
              {/* Tag da Instância (azul) - Exibe nome amigável, não UUID */}
              {(activeConversation.instance_friendly_name || activeConversation.instance_name) && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                  📱 {activeConversation.instance_friendly_name || activeConversation.instance_name}
                </span>
              )}
              
              {/* Tags do Contato (customizadas por cor) */}
              {activeConversation.contact_tags && activeConversation.contact_tags.length > 0 && (
                <>
                  {activeConversation.contact_tags.map((tag) => (
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
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Botão Histórico (apenas se contato existir) */}
          {existingContact && activeConversation?.conversation_type !== 'group' && (
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md ${
                showHistory ? 'bg-gray-200' : ''
              }`}
              title="Histórico do Contato"
            >
              <Clock className="w-5 h-5 text-gray-600" />
            </button>
          )}
          
          <button 
            className="p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md" 
            title="Buscar"
          >
            <Search className="w-5 h-5 text-gray-600" />
          </button>
          
          {/* Menu 3 pontos */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md"
              title="Menu"
            >
              <MoreVertical className="w-5 h-5 text-gray-600" />
            </button>

            {showMenu && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-lg shadow-xl border border-gray-200 py-1 z-50 animate-scale-in">
                {/* Informações do Grupo - apenas para grupos */}
                {activeConversation?.conversation_type === 'group' && (
                  <button
                    onClick={async () => {
                      if (!activeConversation?.id) return;
                      
                      setShowMenu(false);
                      setShowGroupInfo(true);
                      setLoadingGroupInfo(true);
                      setGroupInfo(null); // Limpar dados anteriores antes de carregar novos
                      
                      try {
                        const response = await api.get(`/chat/conversations/${activeConversation.id}/group-info/`);
                        
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
                      } catch (error: any) {
                        console.error('Erro ao buscar informações do grupo:', error);
                        toast.error(error?.response?.data?.error || 'Erro ao buscar informações do grupo');
                        setShowGroupInfo(false);
                        setGroupInfo(null);
                      } finally {
                        setLoadingGroupInfo(false);
                      }
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-3"
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
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-3"
                  >
                    <ArrowRightLeft className="w-4 h-4" />
                    Transferir conversa
                  </button>
                )}

                <button
                  onClick={handleMarkAsResolved}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-3"
                >
                  <CheckCircle className="w-4 h-4" />
                  Marcar como resolvida
                </button>

                <button
                  onClick={handleCloseConversation}
                  className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-3"
                >
                  <XCircle className="w-4 h-4" />
                  Fechar conversa
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-hidden">
        <MessageList />
      </div>

        {/* Input */}
        <MessageInput 
          sendMessage={sendMessage}
          sendTyping={sendTyping}
          isConnected={isConnected}
        />
      </div>

      {/* Sidebar de Histórico */}
      {showHistory && existingContact && activeConversation?.conversation_type !== 'group' && (
        <div className="hidden md:flex flex-col w-[320px] bg-white border-l border-gray-200 shadow-lg flex-shrink-0 h-full overflow-hidden">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
            <h3 className="font-semibold text-gray-900">Histórico</h3>
            <button
              onClick={() => setShowHistory(false)}
              className="p-1 hover:bg-gray-200 rounded transition-colors"
            >
              <X className="w-4 h-4 text-gray-600" />
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
      {showTransferModal && (
        <TransferModal
          conversation={activeConversation}
          onClose={() => setShowTransferModal(false)}
          onTransferSuccess={() => {
            setShowTransferModal(false);
          }}
        />
      )}

      {/* Modal de Informações do Grupo */}
      {showGroupInfo && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Informações do Grupo</h2>
              <button
                onClick={() => {
                  setShowGroupInfo(false);
                  setGroupInfo(null);
                }}
                className="p-1 hover:bg-gray-200 rounded transition-colors"
              >
                <X className="w-5 h-5 text-gray-600" />
              </button>
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
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Informações Básicas</h3>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600 w-24">Nome:</span>
                        <span className="text-sm font-medium text-gray-900">{groupInfo?.group_name || 'Sem nome'}</span>
                      </div>
                      {groupInfo?.description && (
                        <div className="flex items-start gap-2">
                          <span className="text-sm text-gray-600 w-24">Descrição:</span>
                          <span className="text-sm text-gray-900 flex-1">{groupInfo.description}</span>
                        </div>
                      )}
                      {groupInfo?.creation_date && (
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-gray-600 w-24">Criado em:</span>
                          <span className="text-sm text-gray-900">
                            {new Date(groupInfo.creation_date).toLocaleString('pt-BR', {
                              dateStyle: 'long',
                              timeStyle: 'short'
                            })}
                          </span>
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600 w-24">Participantes:</span>
                        <span className="text-sm font-medium text-gray-900">
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
                              <span className="text-sm font-medium text-gray-900">{admin?.name || admin?.phone || 'Admin'}</span>
                              {admin?.phone && admin?.name && (
                                <span className="text-xs text-gray-500">({admin.phone})</span>
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
                                <span className="text-xs text-gray-500">{participant.phone}</span>
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
                <div className="text-center py-8 text-gray-500">
                  Nenhuma informação disponível
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ✅ Modal de Contato */}
      {showContactModal && activeConversation && (
        <ContactModal
          isOpen={showContactModal}
          onClose={() => {
            setShowContactModal(false);
            setExistingContact(null);
          }}
          contact={existingContact}
          initialPhone={activeConversation.contact_phone || ''}
          initialName={getDisplayName(activeConversation)}
          onSuccess={async () => {
            // ✅ MELHORIA: Recarregar contato completo e atualizar activeConversation com tags
            if (activeConversation.contact_phone) {
              // Normalizar telefone para comparação
              const normalizePhone = (phone: string) => {
                if (!phone) return '';
                const hasPlus = phone.startsWith('+');
                const numbers = phone.replace(/\D/g, '');
                return hasPlus ? `+${numbers}` : numbers;
              };

              const normalizedPhone = normalizePhone(activeConversation.contact_phone);
              
              try {
                // Buscar contato completo com tags
                const response = await api.get('/contacts/contacts/', {
                  params: {
                    search: normalizedPhone
                  }
                });
                
                const contacts = response.data.results || response.data;
                const contact = contacts.find((c: any) => {
                  const contactPhoneNormalized = normalizePhone(c.phone);
                  return contactPhoneNormalized === normalizedPhone;
                });
                
                if (contact) {
                  // ✅ Atualizar existingContact com contato completo (incluindo tags)
                  setExistingContact(contact);
                  
                  // ✅ Atualizar activeConversation no store com tags atualizadas
                  const { updateConversation } = useChatStore.getState();
                  updateConversation({
                    ...activeConversation,
                    contact_tags: contact.tags || []
                  });
                  
                  console.log('✅ [CONTACT MODAL] Contato atualizado e conversa sincronizada com tags');
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
