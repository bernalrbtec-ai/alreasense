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

  const loadParticipants = async () => {
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
      setParticipants(participantsList);
    } catch (error: any) {
      // ✅ CORREÇÃO: Não mostrar erro se grupo não foi encontrado (pode ser grupo antigo)
      const errorMessage = error.response?.data?.error || error.message;
      if (errorMessage?.includes('não encontrado') || errorMessage?.includes('not found')) {
        console.warn('⚠️ [MENTIONS] Grupo não encontrado ou sem acesso - participantes não disponíveis');
      } else {
        console.error('❌ [MENTIONS] Erro ao carregar participantes:', errorMessage);
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
          // Filtrar participantes baseado na query
          filtered = participants.filter(p => {
            const nameMatch = p.name.toLowerCase().includes(query.toLowerCase());
            const phoneMatch = p.phone.includes(query);
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

    const textBefore = value.substring(0, mentionStart);
    const textAfter = value.substring(inputRef.current.selectionStart);
    const newValue = `${textBefore}@${participant.name} ${textAfter}`;
    
    onChange(newValue);
    setShowSuggestions(false);
    setMentionStart(null);

    // Extrair todas as menções do texto final
    const mentions: string[] = [];
    const mentionRegex = /@(\d+|\w[\w\s]*?)(?=\s|$|@|,|\.|!|\?)/g;
    let match;
    while ((match = mentionRegex.exec(newValue)) !== null) {
      const mentionText = match[1];
      // Buscar participante por nome ou número
      const found = participants.find(p => 
        p.name.toLowerCase() === mentionText.toLowerCase() || 
        p.phone.includes(mentionText.replace(/\D/g, ''))
      );
      if (found) {
        mentions.push(found.phone);
      }
    }
    
    if (onMentionsChange) {
      onMentionsChange([...new Set(mentions)]); // Remover duplicatas
    }

    // Focar no input novamente
    setTimeout(() => {
      inputRef.current?.focus();
      const newCursorPos = textBefore.length + participant.name.length + 2; // +2 para @ e espaço
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
    }
    // ✅ IMPORTANTE: Não prevenir Enter se não houver sugestões (deixa passar para o MessageInput processar)
  }, [showSuggestions, suggestions, selectedIndex, insertMention]);

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
        onKeyPress={onKeyPress}
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
          {suggestions.map((participant, index) => (
            <div
              key={participant.phone}
              className={`px-3 py-2 cursor-pointer hover:bg-blue-50 ${
                index === selectedIndex ? 'bg-blue-100' : ''
              }`}
              onMouseDown={(e) => {
                e.preventDefault(); // Prevenir blur do textarea
                insertMention(participant);
              }}
            >
              <div className="font-medium text-gray-900">
                {participant.pushname || participant.name}
              </div>
              <div className="text-xs text-gray-500">
                {formatPhoneForDisplay(participant.phone)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

