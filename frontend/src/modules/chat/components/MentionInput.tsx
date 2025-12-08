/**
 * Componente de input com suporte a menções (@)
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  if (!externalUrl) return null;
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

// Função para formatar telefone para exibição
function formatPhoneForDisplay(phone: string): string {
  if (!phone) return phone;
  
  // Remover tudo exceto números
  const clean = phone.replace(/\D/g, '');
  
  // Remover código do país (55) se presente
  let digits = clean;
  if (clean.startsWith('55') && clean.length >= 12) {
    digits = clean.substring(2);
  }
  
  // Formatar baseado no tamanho
  if (digits.length === 11) {
    // (11) 99999-9999
    return `(${digits.substring(0, 2)}) ${digits.substring(2, 7)}-${digits.substring(7)}`;
  } else if (digits.length === 10) {
    // (11) 9999-9999
    return `(${digits.substring(0, 2)}) ${digits.substring(2, 6)}-${digits.substring(6)}`;
  } else if (digits.length === 9) {
    // 99999-9999
    return `${digits.substring(0, 5)}-${digits.substring(5)}`;
  } else if (digits.length === 8) {
    // 9999-9999
    return `${digits.substring(0, 4)}-${digits.substring(4)}`;
  }
  
  return phone; // Retornar original se não conseguir formatar
}

interface Participant {
  phone: string;
  name: string;
  pushname?: string;
  jid?: string;
  // ✅ NOVO: Informações de contato cadastrado
  is_contact?: boolean;
  contact_name?: string | null;
  profile_pic_url?: string | null;  // ✅ NOVO: Foto de perfil do contato
}

interface MentionInputProps {
  value: string;
  onChange: (value: string) => void;
  onMentionsChange?: (mentions: string[]) => void;
  conversationId?: string;
  conversationType?: 'individual' | 'group' | 'broadcast';
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  onKeyPress?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onPaste?: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void;
}

export function MentionInput({
  value,
  onChange,
  onMentionsChange,
  conversationId,
  conversationType = 'individual',
  placeholder = 'Digite uma mensagem...',
  className = '',
  disabled = false,
  onKeyPress,
  onKeyDown,
  onPaste,
}: MentionInputProps) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<Participant[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  
  // ✅ NOVO: Ref para evitar múltiplas chamadas simultâneas
  const loadingRef = useRef(false);
  // ✅ NOVO: Ref para rastrear se já tentou carregar para esta conversa
  const loadedConversationRef = useRef<string | null>(null);
  // ✅ NOVO: Ref para rastrear @ pendente (aguardando carregamento)
  const pendingMentionRef = useRef<{ position: number; query: string } | null>(null);

  // ✅ CORREÇÃO CRÍTICA: Mover loadParticipants para ANTES do useEffect que o usa
  // Isso previne erro "Cannot access 'loadParticipants' before initialization"
  const loadParticipants = useCallback(async (retryCount = 0) => {
    const maxRetries = 2;
    const retryDelay = 1000; // 1 segundo
    
    // ✅ NOVO: Validação antes de fazer a requisição
    if (!conversationId) {
      console.error('❌ [MENTIONS] conversationId não definido, não é possível carregar participantes');
      setParticipants([]);
      loadingRef.current = false;
      return;
    }
    
    if (conversationType !== 'group') {
      console.warn('⚠️ [MENTIONS] Não é grupo, não é necessário carregar participantes');
      setParticipants([]);
      loadingRef.current = false;
      return;
    }
    
    // ✅ NOVO: Marcar como carregando
    if (retryCount === 0) {
      loadingRef.current = true;
    }
    
    try {
      console.log('📡 [MENTIONS] Buscando participantes da API...', {
        conversationId,
        conversationType,
        url: `/chat/conversations/${conversationId}/participants/`
      });
      
      const response = await api.get(`/chat/conversations/${conversationId}/participants/`);
      const data = response.data;
      
      console.log('📥 [MENTIONS] Resposta completa da API:', {
        status: response.status,
        dataType: typeof data,
        isArray: Array.isArray(data),
        hasParticipants: !!(data?.participants),
        participantsCount: Array.isArray(data) ? data.length : (data?.participants?.length || 0),
        fullData: data
      });
      
      // ✅ CORREÇÃO: Verificar se data é array direto ou objeto com participants
      let participantsList: Participant[] = [];
      if (Array.isArray(data)) {
        participantsList = data;
        console.log('✅ [MENTIONS] Data é array direto, usando como participantes');
      } else if (data && typeof data === 'object') {
        participantsList = data.participants || [];
        console.log('✅ [MENTIONS] Data é objeto, extraindo participants:', participantsList.length);
      } else {
        console.warn('⚠️ [MENTIONS] Formato de resposta inesperado:', typeof data);
      }
      
      console.log(`✅ [MENTIONS] ${participantsList.length} participantes carregados`);
      
      // ✅ DEBUG: Verificar estrutura dos participantes
      if (participantsList.length > 0) {
        console.log('🔍 [MENTIONS] Primeiro participante:', participantsList[0]);
        console.log('   - phone:', participantsList[0].phone);
        console.log('   - name:', participantsList[0].name);
        console.log('   - pushname:', participantsList[0].pushname);
        console.log('   - contact_name:', participantsList[0].contact_name);
        console.log('   - is_contact:', participantsList[0].is_contact);
      } else {
        console.warn('⚠️ [MENTIONS] Lista de participantes está vazia após processamento');
      }
      
      setParticipants(participantsList);
      loadingRef.current = false; // ✅ Marcar como concluído
      // ✅ NOVO: Marcar que esta conversa foi carregada
      if (conversationId) {
        loadedConversationRef.current = conversationId;
      }
      
      // ✅ NOVO: Se havia @ pendente, processar sugestões agora
      if (pendingMentionRef.current && participantsList.length > 0) {
        const pending = pendingMentionRef.current;
        pendingMentionRef.current = null; // Limpar pendência
        
        // Processar sugestões com participantes recém-carregados
        let filtered: Participant[] = [];
        if (pending.query === '') {
          filtered = participantsList;
        } else {
          filtered = participantsList.filter(p => {
            const displayName = (p.contact_name || p.pushname || p.name || '').toLowerCase();
            const nameMatch = displayName.includes(pending.query.toLowerCase());
            const phoneMatch = p.phone.replace(/\D/g, '').includes(pending.query.replace(/\D/g, ''));
            return nameMatch || phoneMatch;
          });
        }
        
        setMentionStart(pending.position);
        setSuggestions(filtered);
        setShowSuggestions(filtered.length > 0);
        setSelectedIndex(0);
        console.log('✅ [MENTIONS] Sugestões processadas após carregamento:', filtered.length, 'participantes');
      }
    } catch (error: any) {
      // ✅ MELHORIA: Tratamento de erros mais robusto com retry
      const errorMessage = error.response?.data?.error || error.message;
      const statusCode = error.response?.status;
      
      console.error('❌ [MENTIONS] Erro ao carregar participantes:', {
        errorMessage,
        statusCode,
        retryCount,
        conversationId,
        conversationType,
        error: error
      });
      
      // Retry automático para erros temporários (500, 502, 503, 504)
      if (retryCount < maxRetries && statusCode >= 500 && statusCode < 600) {
        console.warn(`⚠️ [MENTIONS] Erro temporário (${statusCode}), tentando novamente em ${retryDelay}ms... (tentativa ${retryCount + 1}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, retryDelay * (retryCount + 1))); // Backoff exponencial
        return loadParticipants(retryCount + 1);
      }
      
      // Não mostrar erro se grupo não foi encontrado (pode ser grupo antigo)
      if (errorMessage?.includes('não encontrado') || errorMessage?.includes('not found') || statusCode === 404) {
        console.warn('⚠️ [MENTIONS] Grupo não encontrado ou sem acesso - participantes não disponíveis');
      } else if (statusCode === 403) {
        console.warn('⚠️ [MENTIONS] Sem permissão para acessar participantes deste grupo');
      } else if (statusCode === 400) {
        console.warn('⚠️ [MENTIONS] Requisição inválida - verifique se é um grupo');
      } else {
        console.error('❌ [MENTIONS] Erro ao carregar participantes:', errorMessage, `(Status: ${statusCode || 'N/A'})`);
      }
      
      setParticipants([]);
      loadingRef.current = false; // ✅ Marcar como concluído mesmo em caso de erro
    }
  }, [conversationId, conversationType]);

  // ✅ NOVO: Carregar participantes automaticamente quando conversa é aberta (grupos)
  useEffect(() => {
    // Só carregar se:
    // 1. É um grupo
    // 2. Tem conversationId
    // 3. Ainda não carregou para esta conversa
    // 4. Não está carregando no momento
    if (
      conversationType === 'group' &&
      conversationId &&
      loadedConversationRef.current !== conversationId &&
      !loadingRef.current &&
      participants.length === 0
    ) {
      console.log('🔄 [MENTIONS] Carregando participantes automaticamente ao abrir grupo...');
      loadParticipants();
    }
  }, [conversationId, conversationType, loadParticipants, participants.length]);

  // ✅ NOVO: Resetar participantes quando conversa muda
  useEffect(() => {
    // Se conversationId mudou, resetar participantes e flag de carregamento
    if (loadedConversationRef.current && loadedConversationRef.current !== conversationId) {
      console.log('🔄 [MENTIONS] Conversa mudou, resetando participantes...');
      setParticipants([]);
      loadedConversationRef.current = null;
      loadingRef.current = false;
      pendingMentionRef.current = null; // Limpar @ pendente
    }
  }, [conversationId]);

  // Detectar menções enquanto digita
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    onChange(newValue);

    // Detectar @ seguido de texto
    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = newValue.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    console.log('🔍 [MENTIONS] handleInputChange:', {
      newValue,
      cursorPos,
      textBeforeCursor,
      lastAtIndex,
      participantsCount: participants.length,
      conversationType
    });

    if (lastAtIndex !== -1) {
      // Verificar se @ não está dentro de uma palavra (deve ter espaço antes ou estar no início)
      const charBeforeAt = lastAtIndex > 0 ? textBeforeCursor[lastAtIndex - 1] : ' ';
      if (charBeforeAt === ' ' || charBeforeAt === '\n' || lastAtIndex === 0) {
        const query = textBeforeCursor.substring(lastAtIndex + 1).trim();
        console.log('✅ [MENTIONS] @ detectado! Query:', query, 'Participantes disponíveis:', participants.length);
        
        // ✅ OTIMIZAÇÃO: Se for grupo e não tem participantes, tentar recarregar E aguardar
        if (conversationType === 'group' && participants.length === 0 && conversationId && !loadingRef.current) {
          console.log('🔄 [MENTIONS] @ digitado mas sem participantes, carregando agora...');
          // ✅ MELHORIA: Marcar posição do @ e query para processar após carregamento
          setMentionStart(lastAtIndex);
          pendingMentionRef.current = { position: lastAtIndex, query };
          
          // Carregar participantes (o processamento será feito no callback do loadParticipants)
          loadParticipants();
          return; // Não processar sugestões ainda, aguardar carregamento
        }
        
        // ✅ CORREÇÃO: Se query está vazia (apenas @), mostrar TODOS os participantes
        // Se tem query, filtrar baseado nela
        let filtered: Participant[] = [];
        if (query === '') {
          filtered = participants;
          console.log('📋 [MENTIONS] Query vazia - mostrando todos os participantes:', filtered.length);
        } else {
          filtered = participants.filter(p => {
            const displayName = (p.contact_name || p.pushname || p.name || '').toLowerCase();
            const nameMatch = displayName.includes(query.toLowerCase());
            const phoneMatch = p.phone.replace(/\D/g, '').includes(query.replace(/\D/g, ''));
            return nameMatch || phoneMatch;
          });
          console.log('🔍 [MENTIONS] Query filtrada:', query, 'Resultados:', filtered.length);
        }

        // ✅ CORREÇÃO: Mostrar sugestões se for grupo E tiver participantes
        if (conversationType === 'group') {
          if (participants.length > 0) {
            setMentionStart(lastAtIndex);
            setSuggestions(filtered);
            setShowSuggestions(filtered.length > 0);
            setSelectedIndex(0);
            console.log('✅ [MENTIONS] Sugestões ativadas:', filtered.length, 'participantes');
            return;
          } else if (loadingRef.current) {
            console.log('⏳ [MENTIONS] Aguardando carregamento de participantes...');
            setMentionStart(lastAtIndex);
            return;
          }
        }
      }
    }

    setShowSuggestions(false);
    setMentionStart(null);
  }, [onChange, participants, conversationType, conversationId, loadParticipants]);

  // Processar seleção de menção
  const insertMention = useCallback((participant: Participant) => {
    if (mentionStart === null || !inputRef.current) return;

    // ✅ NOVO: Prioridade: contact_name (contato cadastrado) > pushname > name > telefone formatado
    const displayName = participant.contact_name || 
                       participant.pushname || 
                       participant.name || 
                       (participant.phone ? formatPhoneForDisplay(participant.phone) : 'Contato');
    
    const textBefore = value.substring(0, mentionStart);
    const textAfter = value.substring(inputRef.current.selectionStart);
    const newValue = `${textBefore}@${displayName} ${textAfter}`;
    
    onChange(newValue);
    setShowSuggestions(false);
    setMentionStart(null);

    // ✅ CORREÇÃO CRÍTICA: Extrair todas as menções do texto final e mapear para JIDs/telefones
    // ✅ IMPORTANTE: Usar JID quando disponível (mais confiável que phone, especialmente para @lid)
    // ✅ CORREÇÃO: Garantir que cada participante seja mencionado apenas UMA vez
    const mentions: string[] = [];
    const mentionRegex = /@([^\s@,\.!?]+)/g;
    let match;
    
    // ✅ CORREÇÃO: Criar mapa de participantes válidos para validação rápida
    // Usar Map com chave única por participante (JID ou phone)
    const validParticipantsMap = new Map<string, Participant>();
    
    participants.forEach(p => {
      // ✅ CORREÇÃO: Sempre usar JID como identificador único quando disponível
      const primaryIdentifier = p.jid || p.phone;
      if (primaryIdentifier) {
        validParticipantsMap.set(primaryIdentifier, p);
        
        // ✅ NOVO: Mapear por contact_name (prioridade), pushname ou name para busca rápida
        const name = (p.contact_name || p.pushname || p.name || '').toLowerCase();
        if (name) {
          validParticipantsMap.set(name, p);
        }
      }
    });
    
    // ✅ CORREÇÃO CRÍTICA: Set para rastrear participantes já adicionados (usando identificador único)
    const addedParticipants = new Set<string>();
    
    // ✅ CORREÇÃO: Função auxiliar para adicionar participante sem duplicatas
    const addParticipantSafely = (p: Participant, source: string) => {
      // Sempre usar JID como identificador único quando disponível
      const uniqueId = p.jid || p.phone;
      if (!uniqueId) {
        console.warn(`⚠️ [MENTIONS] Participante sem identificador válido:`, p);
        return false;
      }
      
      // ✅ CORREÇÃO CRÍTICA: Verificar se já foi adicionado usando identificador único
      if (addedParticipants.has(uniqueId)) {
        console.log(`🔄 [MENTIONS] Participante já adicionado (${source}):`, uniqueId);
        return false;
      }
      
      // Verificar se o participante está na lista válida
      if (!validParticipantsMap.has(uniqueId)) {
        console.warn(`⚠️ [MENTIONS] Participante não está na lista válida (${source}):`, uniqueId);
        return false;
      }
      
      // Adicionar ao array e marcar como adicionado
      mentions.push(uniqueId);
      addedParticipants.add(uniqueId);
      console.log(`✅ [MENTIONS] Participante adicionado (${source}):`, {
        jid: p.jid,
        phone: p.phone,
        identifier: uniqueId,
        name: p.contact_name || p.pushname || p.name
      });
      return true;
    };
    
    // ✅ CORREÇÃO: Primeiro, adicionar o participante selecionado diretamente (sempre válido)
    addParticipantSafely(participant, 'seleção direta');
    
    // ✅ CORREÇÃO: Depois, processar outras menções que possam existir no texto
    // Resetar regex para processar do início
    mentionRegex.lastIndex = 0;
    while ((match = mentionRegex.exec(newValue)) !== null) {
      const mentionText = match[1];
      
      // ✅ CORREÇÃO: Buscar participante de forma mais eficiente usando o mapa
      let found: Participant | undefined;
      
      // Tentar buscar por nome primeiro (case-insensitive)
      const mentionLower = mentionText.toLowerCase();
      found = validParticipantsMap.get(mentionLower);
      
      // Se não encontrou por nome, tentar por número
      if (!found) {
        const mentionPhone = mentionText.replace(/\D/g, '');
        for (const [key, p] of validParticipantsMap.entries()) {
          // ✅ CORREÇÃO: Verificar se a chave é um identificador (não nome)
          if (key === p.jid || key === p.phone) {
            const pPhone = p.phone?.replace(/\D/g, '') || '';
            if (pPhone && (pPhone === mentionPhone || pPhone.includes(mentionPhone) || mentionPhone.includes(pPhone))) {
              found = p;
              break;
            }
          }
        }
      }
      
      // ✅ CORREÇÃO: Só adicionar se encontrou participante válido E ainda não foi adicionado
      if (found) {
        addParticipantSafely(found, `regex: "${mentionText}"`);
      } else {
        console.warn('⚠️ [MENTIONS] Menção inválida ignorada:', mentionText, '(não está na lista de participantes)');
      }
    }
    
    if (onMentionsChange) {
      // ✅ CORREÇÃO: Já removemos duplicatas acima, mas garantir com Set para segurança extra
      const uniqueMentions = [...new Set(mentions)];
      onMentionsChange(uniqueMentions);
      console.log('✅ [MENTIONS] Menções atualizadas (sem duplicatas):', uniqueMentions);
    }

    // Focar no input novamente
    setTimeout(() => {
      inputRef.current?.focus();
      const newCursorPos = textBefore.length + displayName.length + 2; // +2 para @ e espaço
      inputRef.current?.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  }, [value, mentionStart, onChange, participants, onMentionsChange]);

  // Navegação com teclado
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : 0));
      } else if (e.key === 'Enter' && !e.shiftKey) {
        // ✅ CORREÇÃO: Só processar Enter se não tiver Shift (Shift+Enter = nova linha)
        e.preventDefault();
        insertMention(suggestions[selectedIndex]);
      } else if (e.key === 'Tab') {
        e.preventDefault();
        insertMention(suggestions[selectedIndex]);
      } else if (e.key === 'Escape') {
        setShowSuggestions(false);
        setMentionStart(null);
      }
    } else {
      // ✅ NOVO: Se não há sugestões, passar o evento para o onKeyDown do MessageInput
      // Isso permite que Enter envie a mensagem e Shift+Enter pule linha
      if (onKeyDown) {
        onKeyDown(e);
      }
    }
  }, [showSuggestions, suggestions, selectedIndex, insertMention, onKeyDown]);

  // Scroll para sugestão selecionada
  useEffect(() => {
    if (showSuggestions && suggestionsRef.current) {
      const selectedElement = suggestionsRef.current.children[selectedIndex] as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex, showSuggestions]);

  return (
    <div className="relative w-full" data-mention-input>
      <textarea
        ref={inputRef}
        value={value}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onPaste={onPaste}
        placeholder={placeholder}
        disabled={disabled}
        className={className}
        rows={1}
        style={{ minHeight: '44px', maxHeight: '120px', resize: 'none' }}
        onBlur={(e) => {
          // Delay para permitir clique na sugestão
          setTimeout(() => {
            if (!suggestionsRef.current?.contains(document.activeElement)) {
              setShowSuggestions(false);
            }
          }, 200);
        }}
      />
      
      {showSuggestions && suggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute bottom-full left-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto z-50 min-w-[200px]"
        >
          {suggestions.map((participant, index) => {
            // ✅ NOVO: Prioridade: contact_name (contato cadastrado) > pushname > name > telefone formatado
            const displayName = participant.contact_name || 
                               participant.pushname || 
                               participant.name || 
                               (participant.phone ? formatPhoneForDisplay(participant.phone) : 'Sem nome');
            
            // ✅ Se tem contact_name, mostrar como contato cadastrado (destaque)
            // ✅ Se não tem contact_name mas tem pushname/name, mostrar nome + telefone
            // ✅ Se não tem nenhum nome, mostrar apenas telefone formatado
            const hasContactName = !!participant.contact_name;
            const hasAnyName = !!(participant.pushname || participant.name);
            
            return (
              <div
                key={participant.phone}
                className={`px-3 py-2 cursor-pointer hover:bg-blue-50 flex items-center gap-3 ${
                  index === selectedIndex ? 'bg-blue-100' : ''
                }`}
                onMouseDown={(e) => {
                  e.preventDefault(); // Prevenir blur do textarea
                  console.log('🖱️ [MENTIONS] Participante selecionado:', participant);
                  insertMention(participant);
                }}
              >
                {/* ✅ NOVO: Avatar com foto de perfil */}
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-200 overflow-hidden">
                  {participant.profile_pic_url ? (
                    <img
                      src={getMediaProxyUrl(participant.profile_pic_url) || ''}
                      alt={displayName}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        // Fallback se imagem não carregar
                        const target = e.currentTarget as HTMLImageElement;
                        target.style.display = 'none';
                        const parent = target.parentElement;
                        if (parent) {
                          parent.innerHTML = `
                            <div class="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-sm">
                              ${displayName.charAt(0).toUpperCase()}
                            </div>
                          `;
                        }
                      }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-sm">
                      {displayName.charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>
                
                {/* Informações do participante */}
                <div className="flex-1 min-w-0">
                  <div className={`font-medium ${hasContactName ? 'text-blue-700' : 'text-gray-900'}`}>
                    {displayName}
                    {hasContactName && (
                      <span className="ml-2 text-xs text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded">
                        Contato
                      </span>
                    )}
                  </div>
                  {/* ✅ Mostrar telefone apenas se não for contato cadastrado OU se tiver nome adicional */}
                  {(hasAnyName && !hasContactName) || hasContactName ? (
                    <div className="text-xs text-gray-500">
                      {participant.phone ? formatPhoneForDisplay(participant.phone) : 'Sem telefone'}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

