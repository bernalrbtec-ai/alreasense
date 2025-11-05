/**
 * Types para o módulo Flow Chat
 */

export interface Department {
  id: string;
  name: string;
  color?: string;
  ai_enabled: boolean;
  pending_count?: number;  // ✅ NOVO: Contador de conversas pendentes do backend
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: 'admin' | 'gerente' | 'agente';
}

export interface ContactTag {
  id: string;
  name: string;
  color: string;
}

export interface Conversation {
  id: string;
  tenant: string;
  department: string | { id: string; name: string } | null;  // Pode ser ID (string), objeto ou null
  department_name: string;
  contact_phone: string;
  contact_name: string;
  profile_pic_url?: string | null;
  instance_name?: string;
  instance_friendly_name?: string;
  assigned_to?: string;
  assigned_to_data?: User;
  status: 'pending' | 'open' | 'closed';
  conversation_type?: 'individual' | 'group' | 'broadcast';
  group_metadata?: {
    group_id?: string;
    group_name?: string;
    group_pic_url?: string;
    participants_count?: number;
    is_group?: boolean;
  };
  last_message_at?: string;
  metadata: Record<string, any>;
  participants: string[];
  participants_data?: User[];
  created_at: string;
  updated_at: string;
  last_message?: Message;
  unread_count: number;
  contact_tags?: ContactTag[];
}

export interface MessageReaction {
  id: string;
  message: string;
  user: string;
  user_data?: User;
  emoji: string;
  created_at: string;
}

export interface Message {
  id: string;
  conversation: string;
  sender?: string;
  sender_data?: User;
  sender_name?: string;  // Nome de quem enviou (para grupos)
  sender_phone?: string; // Telefone de quem enviou (para grupos)
  content: string;
  direction: 'incoming' | 'outgoing';
  message_id?: string;
  evolution_status?: string;
  error_message?: string;
  status: 'pending' | 'sent' | 'delivered' | 'seen' | 'failed';
  is_internal: boolean;
  attachments: MessageAttachment[];
  reactions?: MessageReaction[];
  reactions_summary?: Record<string, { count: number; users: Array<{ id: string; email: string; first_name?: string; last_name?: string }> }>;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface MessageAttachment {
  id: string;
  message: string;
  tenant: string;
  original_filename: string;
  mime_type: string;
  file_path: string;
  file_url: string;
  thumbnail_path?: string;
  storage_type: 'local' | 's3';
  size_bytes: number;
  expires_at: string;
  created_at: string;
  is_expired: boolean;
  is_image: boolean;
  is_video: boolean;
  is_audio: boolean;
  is_document: boolean;
  // ✨ Metadata (pode conter flags de processing)
  metadata?: Record<string, any> | null;
  // ✨ Campos IA
  transcription?: string | null;
  transcription_language?: string | null;
  ai_summary?: string | null;
  ai_tags?: string[] | null;
  ai_sentiment?: 'positive' | 'neutral' | 'negative' | null;
  ai_metadata?: any | null;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  processed_at?: string | null;
}

export interface WebSocketMessage {
  type: 'message_received' | 'message_status_update' | 'typing_status' | 'conversation_transferred' | 'user_joined' | 'message_reaction_update';
  message?: Message;
  message_id?: string;
  status?: string;
  user_id?: string;
  user_email?: string;
  is_typing?: boolean;
  conversation_id?: string;
  new_agent?: string;
  new_department?: string;
  transferred_by?: string;
  reaction?: {
    id?: string;
    emoji: string;
    removed?: boolean;
    user?: {
      id: string;
      email: string;
      first_name?: string;
      last_name?: string;
    };
    created_at?: string;
  };
}

export interface TransferPayload {
  new_department?: string;
  new_agent?: string;
  reason?: string;
}

export interface UploadResponse {
  url: string;
  filename: string;
  size: number;
  mime_type: string;
}

