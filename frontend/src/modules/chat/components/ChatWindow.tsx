/**
 * Janela de chat (header + messages + input)
 */
import React, { useState } from 'react';
import { useChatStore } from '../store/chatStore';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TransferModal } from './TransferModal';
import { ArrowLeftRight, MoreVertical, User } from 'lucide-react';
import { usePermissions } from '@/hooks/usePermissions';

export function ChatWindow() {
  const { activeConversation } = useChatStore();
  const { can_transfer_conversations } = usePermissions();
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  if (!activeConversation) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#0e1115] text-gray-500">
        <User className="w-16 h-16 mb-4 text-gray-700" />
        <p className="text-lg">Selecione uma conversa</p>
        <p className="text-sm">Escolha uma conversa da lista para começar</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0e1115]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-[#1f262e] border-b border-gray-800">
        <div className="flex items-center gap-3">
          {/* Avatar */}
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-green-600 to-green-700 flex items-center justify-center text-white font-semibold">
            {(activeConversation.contact_name || activeConversation.contact_phone)[0].toUpperCase()}
          </div>

          {/* Info */}
          <div>
            <h2 className="font-semibold text-white">
              {activeConversation.contact_name || activeConversation.contact_phone}
            </h2>
            <p className="text-xs text-gray-400">
              {activeConversation.contact_phone}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {can_transfer_conversations && (
            <button
              onClick={() => setShowTransferModal(true)}
              className="flex items-center gap-2 px-3 py-2 hover:bg-[#2b2f36] rounded-lg transition-colors text-gray-300 hover:text-white"
              title="Transferir conversa"
            >
              <ArrowLeftRight className="w-4 h-4" />
              <span className="text-sm">Transferir</span>
            </button>
          )}

          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-2 hover:bg-[#2b2f36] rounded-lg transition-colors text-gray-400 hover:text-white"
          >
            <MoreVertical className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Agente atribuído badge */}
      {activeConversation.assigned_to_data && (
        <div className="px-6 py-2 bg-[#1f262e] border-b border-gray-800">
          <p className="text-xs text-gray-400">
            📍 Atendido por:{' '}
            <span className="text-green-500 font-medium">
              {activeConversation.assigned_to_data.first_name || activeConversation.assigned_to_data.email}
            </span>
          </p>
        </div>
      )}

      {/* Messages */}
      <MessageList />

      {/* Input */}
      <MessageInput />

      {/* Transfer Modal */}
      {showTransferModal && (
        <TransferModal
          conversation={activeConversation}
          onClose={() => setShowTransferModal(false)}
        />
      )}
    </div>
  );
}

