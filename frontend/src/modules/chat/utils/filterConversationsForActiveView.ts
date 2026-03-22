/**
 * Mesmos critérios de filtro que a lista de conversas (ConversationList),
 * para métricas do hub alinharem à fila visível.
 */
import type { Conversation, Department } from '../types';
import { useAuthStore } from '@/stores/authStore';

export function filterConversationsForActiveView(
  conversations: Conversation[],
  activeDepartment: Department | null,
  waitingForResponseMode: boolean,
  opts?: {
    searchLower?: string;
    debouncedSearchRaw?: string;
    activeConversation?: Conversation | null;
  }
): Conversation[] {
  if (!Array.isArray(conversations) || !conversations.length) return [];

  const searchLower = (opts?.searchLower ?? '').toLowerCase().trim();
  const debouncedSearchRaw = opts?.debouncedSearchRaw ?? '';
  const activeConversation = opts?.activeConversation ?? null;

  const filtered = conversations.filter((conversationItem) => {
    if (searchLower) {
      const matchesSearch =
        conversationItem.contact_name?.toLowerCase().includes(searchLower) ||
        conversationItem.contact_phone?.includes(debouncedSearchRaw) === true ||
        (conversationItem.group_metadata?.group_name || '').toLowerCase().includes(searchLower);
      if (!matchesSearch) return false;
    }

    if (activeDepartment?.id === 'groups') {
      const isGroup = conversationItem.conversation_type === 'group';
      const notClosed = (conversationItem.status ?? 'open') !== 'closed';
      const notRemoved = conversationItem.group_metadata?.instance_removed !== true;
      return isGroup && notClosed && notRemoved;
    }

    if (conversationItem.conversation_type === 'group') return false;

    if (!activeDepartment) return true;

    const departmentId =
      typeof conversationItem.department === 'string'
        ? conversationItem.department
        : conversationItem.department?.id || null;
    const convStatus = conversationItem.status || 'pending';
    const activeDeptId = String(activeDepartment.id);
    const convDeptId = departmentId ? String(departmentId) : null;

    if (activeDepartment.id === 'inbox') {
      return !departmentId && convStatus === 'pending';
    }

    if (activeDepartment.id === 'my_conversations') {
      const { user } = useAuthStore.getState();
      if (!user) return false;
      return (
        String(conversationItem.assigned_to ?? '') === String(user.id) &&
        (conversationItem.status ?? 'open') === 'open'
      );
    }

    if (conversationItem.status === 'closed') return false;
    return convDeptId === activeDeptId;
  });

  if (activeDepartment?.id === 'groups' && !waitingForResponseMode && filtered.length > 0) {
    const getGroupName = (c: (typeof filtered)[0]) =>
      (c.group_metadata?.group_name || c.contact_name || c.contact_phone || '').toLowerCase().trim();
    const hasRealTime = (c: (typeof filtered)[0]) => {
      const t = c.last_message_at;
      return t != null && t !== '' && !Number.isNaN(new Date(t).getTime());
    };
    return [...filtered].sort((a, b) => {
      const aHas = hasRealTime(a);
      const bHas = hasRealTime(b);
      if (aHas && !bHas) return -1;
      if (!aHas && bHas) return 1;
      if (aHas && bHas) {
        const tA = new Date(a.last_message_at!).getTime();
        const tB = new Date(b.last_message_at!).getTime();
        return tB - tA;
      }
      return getGroupName(a).localeCompare(getGroupName(b), 'pt-BR');
    });
  }

  if (!waitingForResponseMode) return filtered;

  const waitingList = filtered.filter((c) => c.last_message?.direction === 'incoming');
  const activeId = activeConversation?.id != null ? String(activeConversation.id) : null;
  const needsPin =
    activeId &&
    filtered.some((c) => String(c.id) === activeId) &&
    !waitingList.some((c) => String(c.id) === activeId);
  const sortedWaiting = [...waitingList].sort((a, b) => {
    const tA = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
    const tB = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
    return tA - tB || String(a.id).localeCompare(String(b.id));
  });
  return needsPin && activeConversation ? [activeConversation, ...sortedWaiting] : sortedWaiting;
}
