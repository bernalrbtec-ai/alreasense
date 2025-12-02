/**
 * Componente para renderizar menções em mensagens
 * Também processa formatação WhatsApp (negrito, itálico, riscado, monoespaçado) e links
 */
import React from 'react';
import { formatWhatsAppTextWithLinks } from '../utils/whatsappFormatter';

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

interface Mention {
  phone: string;
  name: string;
}

interface MentionRendererProps {
  content: string;
  mentions?: Mention[];
}

export function MentionRenderer({ content, mentions = [] }: MentionRendererProps) {
  if (!content) return null;

  // Se não tem menções, apenas retornar conteúdo formatado (WhatsApp + links)
  if (!mentions || mentions.length === 0) {
    return <span dangerouslySetInnerHTML={{ __html: formatWhatsAppTextWithLinks(content) }} />;
  }

  // ✅ MELHORIA: Criar mapas otimizados para busca rápida
  const phoneToMention = new Map<string, Mention>();
  const nameToMention = new Map<string, Mention>(); // Nome lowercase -> Mention
  
  mentions.forEach(m => {
    phoneToMention.set(m.phone, m);
    // Mapear por nome (case-insensitive)
    if (m.name) {
      nameToMention.set(m.name.toLowerCase(), m);
      // Também mapear por nome parcial (primeiras palavras)
      const nameWords = m.name.toLowerCase().split(/\s+/);
      nameWords.forEach(word => {
        if (word.length > 2) { // Ignorar palavras muito curtas
          nameToMention.set(word, m);
        }
      });
    }
  });

  // Regex para encontrar menções no formato @nome ou @número
  const mentionRegex = /@(\d+|\w[\w\s]*?)(?=\s|$|@|,|\.|!|\?)/g;
  
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = mentionRegex.exec(content)) !== null) {
    // Texto antes da menção (com formatação WhatsApp)
    const beforeMatch = content.substring(lastIndex, match.index);
    if (beforeMatch) {
      parts.push(
        <span 
          key={`text-${lastIndex}`}
          dangerouslySetInnerHTML={{ __html: formatWhatsAppTextWithLinks(beforeMatch) }}
        />
      );
    }

    const mentionText = match[1];
    let mention: Mention | null = null;
    
    // ✅ MELHORIA: Busca otimizada usando mapas
    // 1. Tentar buscar por nome exato (case-insensitive)
    mention = nameToMention.get(mentionText.toLowerCase()) || null;
    
    // 2. Se não encontrou, tentar busca parcial por nome
    if (!mention) {
      const mentionLower = mentionText.toLowerCase();
      for (const [key, m] of nameToMention.entries()) {
        if (key.includes(mentionLower) || mentionLower.includes(key)) {
          mention = m;
          break;
        }
      }
    }
    
    // 3. Se não encontrou por nome, buscar por número
    if (!mention) {
      const cleanPhone = mentionText.replace(/\D/g, ''); // Remove não-dígitos
      for (const [phone, m] of phoneToMention.entries()) {
        const cleanMentionPhone = phone.replace(/\D/g, '');
        if (cleanMentionPhone === cleanPhone || 
            cleanMentionPhone.endsWith(cleanPhone) || 
            cleanPhone.endsWith(cleanMentionPhone)) {
          mention = m;
          break;
        }
      }
    }

    if (mention) {
      // ✅ MELHORIA: Mostrar telefone formatado quando nome não existe ou está vazio
      const displayName = mention.name && mention.name.trim() 
        ? mention.name 
        : formatPhoneForDisplay(mention.phone);
      
      parts.push(
        <span
          key={`mention-${match.index}`}
          className="text-blue-600 font-medium bg-blue-50 px-1 rounded"
          title={`@${displayName} (${mention.phone})`}
        >
          @{displayName}
        </span>
      );
    } else {
      // Menção não encontrada, renderizar como texto normal
      parts.push(<span key={`text-${match.index}`}>@{mentionText}</span>);
    }

    lastIndex = match.index + match[0].length;
  }

  // Adicionar texto restante (com formatação WhatsApp)
  if (lastIndex < content.length) {
    const remainingText = content.substring(lastIndex);
    parts.push(
      <span 
        key={`text-${lastIndex}`}
        dangerouslySetInnerHTML={{ __html: formatWhatsAppTextWithLinks(remainingText) }}
      />
    );
  }

  return <>{parts}</>;
}
