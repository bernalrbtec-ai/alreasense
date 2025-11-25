/**
 * Componente para renderizar menções em mensagens
 * Também processa links (compatível com linkifyText)
 */
import React from 'react';

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

  // Se não tem menções, apenas retornar conteúdo (links serão processados pelo linkifyText)
  if (!mentions || mentions.length === 0) {
    return <span>{content}</span>;
  }

  // Criar mapa de telefone -> nome para busca rápida
  const phoneToName = new Map<string, string>();
  mentions.forEach(m => {
    phoneToName.set(m.phone, m.name);
  });

  // Regex para encontrar menções no formato @nome ou @número
  const mentionRegex = /@(\d+|\w[\w\s]*?)(?=\s|$|@|,|\.|!|\?)/g;
  
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = mentionRegex.exec(content)) !== null) {
    // Texto antes da menção
    const beforeMatch = content.substring(lastIndex, match.index);
    if (beforeMatch) {
      parts.push(<span key={`text-${lastIndex}`}>{beforeMatch}</span>);
    }

    const mentionText = match[1];
    // Tentar encontrar por nome primeiro, depois por número
    let mention: Mention | null = null;
    
    // Buscar por nome (case insensitive)
    for (const m of mentions) {
      if (m.name.toLowerCase() === mentionText.toLowerCase()) {
        mention = m;
        break;
      }
    }
    
    // Se não encontrou por nome, buscar por número
    if (!mention) {
      const cleanPhone = mentionText.replace(/\D/g, ''); // Remove não-dígitos
      for (const m of mentions) {
        const cleanMentionPhone = m.phone.replace(/\D/g, '');
        if (cleanMentionPhone === cleanPhone || cleanMentionPhone.endsWith(cleanPhone) || cleanPhone.endsWith(cleanMentionPhone)) {
          mention = m;
          break;
        }
      }
    }

    if (mention) {
      parts.push(
        <span
          key={`mention-${match.index}`}
          className="text-blue-600 font-medium bg-blue-50 px-1 rounded"
          title={`@${mention.name} (${mention.phone})`}
        >
          @{mention.name}
        </span>
      );
    } else {
      // Menção não encontrada, renderizar como texto normal
      parts.push(<span key={`text-${match.index}`}>@{mentionText}</span>);
    }

    lastIndex = match.index + match[0].length;
  }

  // Adicionar texto restante
  if (lastIndex < content.length) {
    parts.push(<span key={`text-${lastIndex}`}>{content.substring(lastIndex)}</span>);
  }

  return <>{parts}</>;
}
