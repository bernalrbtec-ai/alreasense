/**
 * Componente de input com suporte a menções (@)
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

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

  // Carregar participantes quando for grupo
  useEffect(() => {
    if (conversationType === 'group' && conversationId) {
      console.log('🔄 [MENTIONS] Carregando participantes para grupo:', conversationId);
      loadParticipants();
    } else {
      console.log('ℹ️ [MENTIONS] Não é grupo ou sem conversationId:', { conversationType, conversationId });
      setParticipants([]); // Limpar participantes se não for grupo
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, conversationType]);

  const loadParticipants = async (retryCount = 0) => {
    const maxRetries = 2;
    const retryDelay = 1000; // 1 segundo
    
    try {
      console.log('📡 [MENTIONS] Buscando participantes da API...');
      const response = await api.get(`/chat/conversations/${conversationId}/participants/`);
      const data = response.data;
      console.log('📥 [MENTIONS] Resposta da API:', data);
      
      // ✅ CORREÇÃO: Verificar se data é array direto ou objeto com participants
      let participantsList: Participant[] = [];
      if (Array.isArray(data)) {
        participantsList = data;
      } else {
        participantsList = data.participants || [];
      }
      
      console.log(`✅ [MENTIONS] ${participantsList.length} participantes carregados:`, participantsList);
      
      // ✅ DEBUG: Verificar estrutura dos participantes
      if (participantsList.length > 0) {
        console.log('🔍 [MENTIONS] Primeiro participante:', participantsList[0]);
        console.log('   - phone:', participantsList[0].phone);
        console.log('   - name:', participantsList[0].name);
        console.log('   - pushname:', participantsList[0].pushname);
      }
      
      setParticipants(participantsList);
    } catch (error: any) {
      // ✅ MELHORIA: Tratamento de erros mais robusto com retry
      const errorMessage = error.response?.data?.error || error.message;
      const statusCode = error.response?.status;
      
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
    }
  };

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
        
        // ✅ CORREÇÃO: Se query está vazia (apenas @), mostrar TODOS os participantes
        // Se tem query, filtrar baseado nela
        let filtered: Participant[] = [];
        if (query === '') {
          // Mostrar todos os participantes quando apenas @ é digitado
          filtered = participants;
          console.log('📋 [MENTIONS] Query vazia - mostrando todos os participantes:', filtered.length);
        } else {
          // ✅ NOVO: Filtrar participantes baseado na query (contact_name, pushname, name ou telefone)
          filtered = participants.filter(p => {
            // ✅ Prioridade: contact_name > pushname > name
            const displayName = (p.contact_name || p.pushname || p.name || '').toLowerCase();
            const nameMatch = displayName.includes(query.toLowerCase());
            const phoneMatch = p.phone.replace(/\D/g, '').includes(query.replace(/\D/g, ''));
            return nameMatch || phoneMatch;
          });
          console.log('🔍 [MENTIONS] Query filtrada:', query, 'Resultados:', filtered.length);
        }

        // ✅ CORREÇÃO: Mostrar sugestões se for grupo E tiver participantes (mesmo que filtrados)
        if (conversationType === 'group' && participants.length > 0) {
          setMentionStart(lastAtIndex);
          setSuggestions(filtered);
          setShowSuggestions(filtered.length > 0); // Mostrar apenas se houver resultados
          setSelectedIndex(0);
          console.log('✅ [MENTIONS] Sugestões ativadas:', filtered.length, 'participantes');
          return;
        } else {
          console.log('⚠️ [MENTIONS] Não mostrando sugestões:', {
            isGroup: conversationType === 'group',
            hasParticipants: participants.length > 0
          });
        }
      }
    }

    setShowSuggestions(false);
    setMentionStart(null);
  }, [onChange, participants, conversationType]);

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

    // ✅ MELHORIA: Extrair todas as menções do texto final e mapear para JIDs/telefones
    // ✅ IMPORTANTE: Usar JID quando disponível (mais confiável que phone, especialmente para @lid)
    // ✅ MELHORIA: Validar que apenas participantes válidos sejam mencionados
    const mentions: string[] = [];
    const mentionRegex = /@([^\s@,\.!?]+)/g;
    let match;
    
    // ✅ MELHORIA: Criar mapa de participantes válidos para validação rápida
    const validParticipantsMap = new Map<string, Participant>();
    participants.forEach(p => {
      const identifier = p.jid || p.phone;
      if (identifier) {
        validParticipantsMap.set(identifier, p);
        // ✅ NOVO: Mapear por contact_name (prioridade), pushname ou name para busca rápida
        const name = (p.contact_name || p.pushname || p.name || '').toLowerCase();
        if (name) {
          validParticipantsMap.set(name, p);
        }
      }
    });
    
    // Primeiro, adicionar o participante selecionado diretamente (sempre válido)
    // ✅ CORREÇÃO: Priorizar JID sobre phone (JID é o identificador único correto)
    const participantIdentifier = participant.jid || participant.phone;
    if (participantIdentifier && validParticipantsMap.has(participantIdentifier)) {
      mentions.push(participantIdentifier);
      console.log('✅ [MENTIONS] Participante selecionado:', {
        jid: participant.jid,
        phone: participant.phone,
        identifier: participantIdentifier
      });
    } else {
      console.warn('⚠️ [MENTIONS] Participante selecionado não está na lista válida:', participantIdentifier);
    }
    
    // Depois, processar outras menções que possam existir no texto
    while ((match = mentionRegex.exec(newValue)) !== null) {
      const mentionText = match[1];
      
      // ✅ MELHORIA: Buscar participante de forma mais eficiente usando o mapa
      let found: Participant | undefined;
      
      // Tentar buscar por nome primeiro (case-insensitive)
      const mentionLower = mentionText.toLowerCase();
      found = validParticipantsMap.get(mentionLower);
      
      // Se não encontrou por nome, tentar por número
      if (!found) {
        const mentionPhone = mentionText.replace(/\D/g, '');
        for (const [key, p] of validParticipantsMap.entries()) {
          const pPhone = p.phone?.replace(/\D/g, '') || '';
          if (pPhone && (pPhone === mentionPhone || pPhone.includes(mentionPhone) || mentionPhone.includes(pPhone))) {
            found = p;
            break;
          }
        }
      }
      
      // ✅ MELHORIA: Só adicionar se encontrou participante válido
      if (found) {
        // ✅ CORREÇÃO: Priorizar JID sobre phone
        const foundIdentifier = found.jid || found.phone;
        if (foundIdentifier && !mentions.includes(foundIdentifier)) {
          mentions.push(foundIdentifier);
          console.log('✅ [MENTIONS] Menção válida encontrada:', mentionText, '->', foundIdentifier);
        }
      } else {
        console.warn('⚠️ [MENTIONS] Menção inválida ignorada:', mentionText, '(não está na lista de participantes)');
      }
    }
    
    if (onMentionsChange) {
      onMentionsChange([...new Set(mentions)]); // Remover duplicatas
      console.log('✅ [MENTIONS] Menções atualizadas:', mentions);
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
                className={`px-3 py-2 cursor-pointer hover:bg-blue-50 ${
                  index === selectedIndex ? 'bg-blue-100' : ''
                }`}
                onMouseDown={(e) => {
                  e.preventDefault(); // Prevenir blur do textarea
                  console.log('🖱️ [MENTIONS] Participante selecionado:', participant);
                  insertMention(participant);
                }}
              >
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
            );
          })}
        </div>
      )}
    </div>
  );
}

