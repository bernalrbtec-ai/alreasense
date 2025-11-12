/**
 * 🎯 Conversation Updater - Lógica unificada para atualizar conversas
 * 
 * Melhorias:
 * - Merge inteligente de dados (preserva campos importantes)
 * - Debounce para atualizações frequentes
 * - Ordenação otimizada (só reordena se necessário)
 * - Prevenção de duplicatas
 */

import { Conversation } from '../types';

// ✅ Cache de timestamps para debounce
const updateTimestamps = new Map<string, number>();
const DEBOUNCE_MS = 100; // 100ms de debounce

// ✅ Cache de última ordenação para evitar reordenação desnecessária
let lastSortedConversations: Conversation[] = [];
let lastSortTimestamp = 0;

/**
 * Faz merge inteligente de duas conversas, preservando campos importantes
 */
function mergeConversations(
  existing: Conversation,
  incoming: Conversation
): Conversation {
  return {
    ...existing,
    ...incoming, // Sobrescrever com dados novos
    
    // ✅ PRESERVAR campos importantes que podem ser perdidos:
    // - Metadados de grupo (fazer merge profundo)
    group_metadata: incoming.group_metadata || existing.group_metadata,
    
    // - Tags do contato (preservar se não vierem novas)
    contact_tags: incoming.contact_tags || existing.contact_tags,
    
    // - Última mensagem (preservar se não vier nova)
    last_message: incoming.last_message || existing.last_message,
    
    // ✅ GARANTIR campos obrigatórios:
    status: incoming.status || existing.status || 'pending',
    conversation_type: incoming.conversation_type || existing.conversation_type || 'individual',
  };
}

/**
 * Ordena conversas por last_message_at (mais recente primeiro)
 * ✅ Otimização: Só reordena se necessário
 */
function sortConversations(conversations: Conversation[]): Conversation[] {
  // ✅ Verificar se precisa reordenar (cache de última ordenação)
  const now = Date.now();
  const needsResort = 
    conversations.length !== lastSortedConversations.length ||
    conversations.some((conv, idx) => {
      const lastConv = lastSortedConversations[idx];
      return !lastConv || conv.id !== lastConv.id || 
             conv.last_message_at !== lastConv.last_message_at;
    });
  
  if (!needsResort && now - lastSortTimestamp < 1000) {
    // ✅ Cache ainda válido (última ordenação foi há menos de 1s)
    return lastSortedConversations;
  }
  
  // ✅ Reordenar
  const sorted = [...conversations].sort((a, b) => {
    const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
    const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
    return bTime - aTime; // Mais recente primeiro
  });
  
  // ✅ Atualizar cache
  lastSortedConversations = sorted;
  lastSortTimestamp = now;
  
  return sorted;
}

/**
 * Atualiza ou adiciona conversa com debounce e merge inteligente
 */
export function upsertConversation(
  conversations: Conversation[],
  incoming: Conversation
): Conversation[] {
  // ✅ Validação
  if (!incoming || !incoming.id) {
    console.error('❌ [UPDATER] Conversa inválida:', incoming);
    return conversations;
  }
  
  // ✅ Debounce: Ignorar atualizações muito frequentes da mesma conversa
  const now = Date.now();
  const lastUpdate = updateTimestamps.get(incoming.id) || 0;
  
  if (now - lastUpdate < DEBOUNCE_MS) {
    // ✅ Atualização muito recente, aguardar um pouco
    // Mas ainda processar se for uma atualização importante (nova mensagem, mudança de status)
    const isImportantUpdate = 
      incoming.unread_count !== undefined ||
      incoming.status !== undefined ||
      incoming.last_message_at !== undefined;
    
    if (!isImportantUpdate) {
      console.log(`⏸️ [UPDATER] Debounce: ignorando update muito frequente de ${incoming.id}`);
      return conversations;
    }
  }
  
  // ✅ Atualizar timestamp
  updateTimestamps.set(incoming.id, now);
  
  // ✅ Verificar se conversa já existe
  const existingIndex = conversations.findIndex(c => c.id === incoming.id);
  
  if (existingIndex === -1) {
    // ✅ NOVA CONVERSA: Adicionar e ordenar
    console.log('✅ [UPDATER] Nova conversa adicionada:', incoming.contact_name || incoming.contact_phone);
    
    const newConversations = [
      ...conversations,
      {
        ...incoming,
        status: incoming.status || 'pending',
        conversation_type: incoming.conversation_type || 'individual',
      }
    ];
    
    // ✅ Sempre ordenar após adicionar (garante ordem correta)
    return sortConversations(newConversations);
  }
  
  // ✅ CONVERSA EXISTENTE: Fazer merge inteligente
  const existing = conversations[existingIndex];
  const merged = mergeConversations(existing, incoming);
  
  console.log('🔄 [UPDATER] Conversa atualizada:', {
    id: incoming.id,
    contact: incoming.contact_name || incoming.contact_phone,
    changes: {
      unread_count: existing.unread_count !== incoming.unread_count 
        ? `${existing.unread_count} → ${incoming.unread_count}` 
        : undefined,
      status: existing.status !== incoming.status 
        ? `${existing.status} → ${incoming.status}` 
        : undefined,
      last_message_at: existing.last_message_at !== incoming.last_message_at 
        ? 'atualizado' 
        : undefined,
    }
  });
  
  // ✅ Substituir conversa existente
  const updatedConversations = [
    ...conversations.slice(0, existingIndex),
    merged,
    ...conversations.slice(existingIndex + 1)
  ];
  
  // ✅ MELHORIA UX: Sempre reordenar após atualizar conversa (garante ordem correta)
  // Isso garante que conversas com mensagens novas (enviadas ou recebidas) vão para o topo
  return sortConversations(updatedConversations);
}

/**
 * Limpa cache de debounce (útil para testes ou reset)
 */
export function clearUpdateCache(): void {
  updateTimestamps.clear();
  lastSortedConversations = [];
  lastSortTimestamp = 0;
}

