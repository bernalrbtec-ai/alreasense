/**
 * Componente de input com suporte a menções (@)
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

interface Participant {
  phone: string;
  name: string;
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
      loadParticipants();
    }
  }, [conversationId, conversationType]);

  const loadParticipants = async () => {
    try {
      const response = await api.get(`/chat/conversations/${conversationId}/participants/`);
      const data = response.data;
      // ✅ CORREÇÃO: Verificar se data é array direto ou objeto com participants
      if (Array.isArray(data)) {
        setParticipants(data);
      } else {
        setParticipants(data.participants || []);
      }
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

    if (lastAtIndex !== -1) {
      // Verificar se @ não está dentro de uma palavra (deve ter espaço antes ou estar no início)
      const charBeforeAt = lastAtIndex > 0 ? textBeforeCursor[lastAtIndex - 1] : ' ';
      if (charBeforeAt === ' ' || charBeforeAt === '\n' || lastAtIndex === 0) {
        const query = textBeforeCursor.substring(lastAtIndex + 1).trim();
        
        // Filtrar participantes baseado na query
        const filtered = participants.filter(p => {
          const nameMatch = p.name.toLowerCase().includes(query.toLowerCase());
          const phoneMatch = p.phone.includes(query);
          return nameMatch || phoneMatch;
        });

        if (filtered.length > 0 && conversationType === 'group') {
          setMentionStart(lastAtIndex);
          setSuggestions(filtered);
          setShowSuggestions(true);
          setSelectedIndex(0);
          return;
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
              <div className="font-medium text-gray-900">{participant.name}</div>
              <div className="text-xs text-gray-500">{participant.phone}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

