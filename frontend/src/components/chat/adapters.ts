/**
 * Adapters: converte tipos do domínio (Conversation, Message) para o formato da UI (sidebar e painel).
 */

import type { Conversation, Message } from '@/modules/chat/types';
import { getDisplayName } from '@/modules/chat/utils/phoneFormatter';
import { getMessagePreviewText } from '@/modules/chat/utils/messageUtils';
import type { SentimentScore } from '@/utils/sentiment';

/** Item de conversa para a sidebar (spec). */
export interface ConversationSidebarConversation {
  id: string;
  contactName: string;
  contactPhone: string;
  avatarInitials: string;
  avatarColor: string;
  /** URL da foto de perfil (ex.: WhatsApp); null = usar apenas iniciais */
  profilePicUrl: string | null;
  /** Atendente atual (quando conversa está atribuída) */
  assignedToId?: number | null;
  assignedToName?: string | null;
  lastMessage: string;
  lastMessageAt: string;
  unreadCount: number;
  isOnline: boolean;
  sentimentScore: SentimentScore;
}

/** Contato para o header do painel (spec). */
export interface ChatPanelContact {
  name: string;
  phone: string;
  avatarInitials: string;
  avatarColor: string;
  isOnline: boolean;
}

/** Mensagem para o painel (spec). */
export interface ChatPanelMessage {
  id: string;
  content: string;
  direction: 'inbound' | 'outbound';
  sentAt: string;
  status: 'sent' | 'delivered' | 'read';
  senderInitials?: string;
}

const AVATAR_COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-violet-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-cyan-500',
  'bg-indigo-500',
  'bg-teal-500',
];

function getAvatarColor(id: string): string {
  let hash = 0;
  const str = String(id).toLowerCase();
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % AVATAR_COLORS.length;
  return AVATAR_COLORS[index];
}

function getSentimentFromMessage(lastMessage: Conversation['last_message']): SentimentScore {
  if (!lastMessage) return 'neutral';
  const att = lastMessage.attachments?.[0];
  const sentiment = att?.ai_sentiment ?? (lastMessage as { ai_sentiment?: string })?.ai_sentiment;
  if (sentiment === 'positive') return 'positive';
  if (sentiment === 'negative') return 'negative';
  return 'neutral';
}

export function conversationToSidebarItem(conv: Conversation): ConversationSidebarConversation {
  const name = getDisplayName(conv);
  const lastMsg = conv.last_message;
  const rawPreview = lastMsg
    ? getMessagePreviewText(lastMsg.content ?? '', lastMsg.metadata as Record<string, unknown> | undefined) || ''
    : '';
  const lastMessageText =
    conv.conversation_type === 'group' && lastMsg?.sender_name
      ? `${lastMsg.sender_name}: ${rawPreview || '📎 Anexo'}`
      : rawPreview || '';
  const lastMessageAt =
    conv.last_message_at ?? conv.updated_at ?? conv.created_at ?? '';

  let avatarInitials = '?';
  if (conv.conversation_type === 'group') {
    const groupName = conv.group_metadata?.group_name || name;
    avatarInitials = groupName ? groupName.trim().slice(0, 2).toUpperCase() : '👥';
  } else {
    avatarInitials = name ? name.trim().slice(0, 2).toUpperCase() : '?';
  }

  return {
    id: String(conv.id),
    contactName: name,
    contactPhone: conv.contact_phone ?? '',
    avatarInitials,
    avatarColor: getAvatarColor(conv.id),
    profilePicUrl: conv.profile_pic_url ?? null,
    assignedToId:
      typeof (conv as any).assigned_to === 'number'
        ? (conv as any).assigned_to
        : (typeof (conv as any).assigned_to === 'string' && (conv as any).assigned_to.trim() !== '')
        ? Number((conv as any).assigned_to)
        : null,
    assignedToName:
      ((conv as any).assigned_to_data?.first_name || (conv as any).assigned_to_data?.email || '')
        ?.toString()
        .trim() || null,
    lastMessage: lastMessageText,
    lastMessageAt,
    unreadCount: conv.unread_count ?? 0,
    isOnline: false,
    sentimentScore: getSentimentFromMessage(lastMsg),
  };
}

export function messageToPanelMessage(msg: Message): ChatPanelMessage {
  const direction = msg.direction === 'incoming' ? 'inbound' : 'outbound';
  let status: 'sent' | 'delivered' | 'read' = 'sent';
  if (msg.status === 'seen') status = 'read';
  else if (msg.status === 'delivered') status = 'delivered';
  else if (msg.status === 'sent') status = 'sent';

  let content = (msg.content ?? '').trim();
  if (!content && msg.attachments?.length) content = '📎 Anexo';

  return {
    id: String(msg.id),
    content,
    direction,
    sentAt: msg.created_at ?? '',
    status,
    senderInitials: msg.sender_data
      ? `${msg.sender_data.first_name?.[0] ?? ''}${msg.sender_data.last_name?.[0] ?? ''}`.toUpperCase() || undefined
      : msg.sender_name?.trim().slice(0, 2).toUpperCase(),
  };
}
