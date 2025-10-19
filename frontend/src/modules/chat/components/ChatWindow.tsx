/**
 * Janela de chat (header + messages + input)
 */
import React, { useState, useRef, useEffect } from 'react';
import { useChatStore } from '../store/chatStore';
import { useChatSocket } from '../hooks/useChatSocket';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TransferModal } from './TransferModal';
import { ArrowLeftRight, MoreVertical, User, Info, CheckCircle, XCircle, BellOff, ArrowLeft } from 'lucide-react';
import { usePermissions } from '@/hooks/usePermissions';
import { api } from '@/lib/api';
import { toast } from 'sonner';

export function ChatWindow() {
  const { activeConversation, updateConversation, setActiveConversation } = useChatStore();
  const { can_transfer_conversations } = usePermissions();
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // 🔌 Conectar WebSocket para receber atualizações em tempo real
  const { isConnected } = useChatSocket(activeConversation?.id);

  // Fecha menu ao clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    }
    
    if (showMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showMenu]);

  const handleCloseConversation = async () => {
    if (!activeConversation) return;
    
    try {
      await api.patch(`/chat/conversations/${activeConversation.id}/`, {
        status: 'closed'
      });
      
      const updated = { ...activeConversation, status: 'closed' as const };
      updateConversation(updated);
      setActiveConversation(null);
      toast.success('Conversa fechada com sucesso!');
      setShowMenu(false);
    } catch (error) {
      console.error('Erro ao fechar conversa:', error);
      toast.error('Erro ao fechar conversa');
    }
  };

  const handleMarkAsResolved = async () => {
    if (!activeConversation) return;
    
    try {
      await api.patch(`/chat/conversations/${activeConversation.id}/`, {
        status: 'closed'
      });
      
      const updated = { ...activeConversation, status: 'closed' as const };
      updateConversation(updated);
      toast.success('Conversa marcada como resolvida!');
      setShowMenu(false);
    } catch (error) {
      console.error('Erro ao marcar como resolvida:', error);
      toast.error('Erro ao marcar como resolvida');
    }
  };

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
      <div className="flex items-center justify-between px-4 md:px-6 py-4 bg-[#1f262e] border-b border-gray-800">
        <div className="flex items-center gap-3">
          {/* Botão Voltar (mobile) */}
          <button
            onClick={() => setActiveConversation(null)}
            className="md:hidden p-2 hover:bg-[#2b2f36] rounded-lg transition-colors text-gray-400 hover:text-white"
            title="Voltar"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
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
        <div className="flex items-center gap-2 relative">
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

          <div ref={menuRef} className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 hover:bg-[#2b2f36] rounded-lg transition-colors text-gray-400 hover:text-white"
            >
              <MoreVertical className="w-5 h-5" />
            </button>

            {/* Dropdown Menu */}
            {showMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-[#1f262e] border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
                <button
                  onClick={() => {
                    setShowInfoModal(true);
                    setShowMenu(false);
                  }}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#2b2f36] transition-colors text-gray-300 hover:text-white text-left"
                >
                  <Info className="w-4 h-4" />
                  <span className="text-sm">Informações</span>
                </button>

                {can_transfer_conversations && (
                  <button
                    onClick={() => {
                      setShowTransferModal(true);
                      setShowMenu(false);
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#2b2f36] transition-colors text-gray-300 hover:text-white text-left border-t border-gray-800"
                  >
                    <ArrowLeftRight className="w-4 h-4" />
                    <span className="text-sm">Transferir conversa</span>
                  </button>
                )}

                <button
                  onClick={handleMarkAsResolved}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#2b2f36] transition-colors text-gray-300 hover:text-white text-left border-t border-gray-800"
                >
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span className="text-sm">Marcar como resolvida</span>
                </button>

                <button
                  onClick={handleCloseConversation}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#2b2f36] transition-colors text-red-400 hover:text-red-300 text-left border-t border-gray-800"
                >
                  <XCircle className="w-4 h-4" />
                  <span className="text-sm">Fechar conversa</span>
                </button>
              </div>
            )}
          </div>
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
          onTransferSuccess={() => {
            // Recarregar conversas
            setShowTransferModal(false);
          }}
        />
      )}

      {/* Info Modal */}
      {showInfoModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1f262e] rounded-xl shadow-2xl w-full max-w-md border border-gray-800">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h2 className="text-lg font-semibold text-white">Informações da Conversa</h2>
              <button
                onClick={() => setShowInfoModal(false)}
                className="p-1 hover:bg-gray-700 rounded transition-colors"
              >
                <XCircle className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Nome</label>
                <p className="text-white">{activeConversation.contact_name || 'Não informado'}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Telefone</label>
                <p className="text-white font-mono">{activeConversation.contact_phone}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Departamento</label>
                <p className="text-white">{activeConversation.department_name}</p>
              </div>

              {activeConversation.assigned_to_data && (
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Atribuído a</label>
                  <p className="text-white">
                    {activeConversation.assigned_to_data.first_name || activeConversation.assigned_to_data.email}
                  </p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Status</label>
                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                  activeConversation.status === 'open'
                    ? 'bg-green-600/20 text-green-400'
                    : 'bg-gray-600/20 text-gray-400'
                }`}>
                  {activeConversation.status === 'open' ? 'Aberta' : 'Fechada'}
                </span>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Criada em</label>
                <p className="text-white text-sm">
                  {new Date(activeConversation.created_at).toLocaleString('pt-BR')}
                </p>
              </div>

              {activeConversation.last_message_at && (
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Última mensagem</label>
                  <p className="text-white text-sm">
                    {new Date(activeConversation.last_message_at).toLocaleString('pt-BR')}
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end px-6 py-4 border-t border-gray-800">
              <button
                onClick={() => setShowInfoModal(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-white"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

