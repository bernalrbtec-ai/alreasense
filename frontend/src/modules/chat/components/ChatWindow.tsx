/**
 * Janela de chat principal - Estilo WhatsApp Web
 */
import React, { useState, useRef, useEffect } from 'react';
import { ArrowLeft, MoreVertical, Phone, Video, Search, X, Info, ArrowRightLeft, CheckCircle, XCircle } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TransferModal } from './TransferModal';
import { usePermissions } from '@/hooks/usePermissions';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { useChatSocket } from '../hooks/useChatSocket';

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

export function ChatWindow() {
  const { activeConversation, setActiveConversation } = useChatStore();
  const { can_transfer_conversations } = usePermissions();
  const [showMenu, setShowMenu] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  
  // 🔍 Debug: Log quando profile_pic_url muda
  useEffect(() => {
    if (activeConversation) {
      console.log('🖼️ [ChatWindow] profile_pic_url atual:', activeConversation.profile_pic_url);
    }
  }, [activeConversation?.profile_pic_url]);

  // 🔌 Conectar WebSocket para esta conversa
  const { isConnected, sendMessage, sendTyping } = useChatSocket(activeConversation?.id);

  // 📖 Marcar mensagens como lidas quando abre a conversa
  useEffect(() => {
    if (activeConversation) {
      const markAsRead = async () => {
        try {
          await api.post(`/chat/conversations/${activeConversation.id}/mark_as_read/`);
          console.log('✅ Mensagens marcadas como lidas');
        } catch (error) {
          console.error('❌ Erro ao marcar como lidas:', error);
        }
      };
      
      // Marcar como lida após 1 segundo (simular visualização)
      const timeout = setTimeout(markAsRead, 1000);
      return () => clearTimeout(timeout);
    }
  }, [activeConversation?.id]);

  // Fechar menu ao clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleCloseConversation = async () => {
    if (!activeConversation) return;
    
    try {
      await api.patch(`/chat/conversations/${activeConversation.id}/`, {
        status: 'closed'
      });
      toast.success('Conversa fechada!');
      setShowMenu(false);
      setActiveConversation(null);
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
      toast.success('Conversa marcada como resolvida!');
      setShowMenu(false);
    } catch (error) {
      console.error('Erro ao marcar como resolvida:', error);
      toast.error('Erro ao marcar como resolvida');
    }
  };

  if (!activeConversation) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#f0f2f5] p-8">
        <div className="max-w-md text-center">
          <div className="w-64 h-64 mx-auto mb-8 opacity-20">
            <svg viewBox="0 0 303 172" fill="currentColor" className="text-gray-400">
              <path d="M229.003 146.214c-18.832-35.882-34.954-69.436-38.857-96.056-4.154-28.35 4.915-49.117 35.368-59.544 30.453-10.426 60.904 4.154 71.33 34.607 10.427 30.453-4.154 60.904-34.607 71.33-15.615 5.346-32.123 4.58-47.234-.337zM3.917 63.734C14.344 33.281 44.795 18.7 75.248 29.127c30.453 10.426 45.034 40.877 34.607 71.33-10.426 30.453-40.877 45.034-71.33 34.607C7.972 124.638-6.61 94.187 3.917 63.734z"/>
            </svg>
          </div>
          <h2 className="text-2xl font-light text-gray-700 mb-2">Flow Chat Web</h2>
          <p className="text-gray-500 text-sm">
            Envie e receba mensagens sem manter seu celular conectado.<br/>
            Selecione uma conversa para começar.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full bg-[#efeae2]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#f0f2f5] border-b border-gray-300">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Botão Voltar (mobile) */}
          <button
            onClick={() => setActiveConversation(null)}
            className="md:hidden p-2 hover:bg-gray-200 rounded-full transition-colors"
            title="Voltar"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>

          {/* Avatar */}
          <div className="w-10 h-10 rounded-full bg-gray-300 overflow-hidden flex-shrink-0">
            {activeConversation.profile_pic_url ? (
              <img 
                src={getMediaProxyUrl(activeConversation.profile_pic_url)}
                alt={activeConversation.contact_name || activeConversation.contact_phone}
                className="w-full h-full object-cover"
                onLoad={() => console.log('✅ [IMG] Foto carregada com sucesso!')}
                onError={(e) => {
                  console.error('❌ [IMG] Erro ao carregar foto:', e);
                  console.error('   URL:', e.currentTarget.src);
                  e.currentTarget.style.display = 'none';
                }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-lg">
                {(activeConversation.contact_name || activeConversation.contact_phone)[0].toUpperCase()}
              </div>
            )}
          </div>

          {/* Nome e Tags */}
          <div className="flex-1 min-w-0">
            {/* Nome */}
            <h2 className="text-base font-medium text-gray-900 truncate">
              {activeConversation.contact_name || activeConversation.contact_phone}
            </h2>
            
            {/* Tags: Instância + Tags do Contato */}
            <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
              {/* Tag da Instância (azul) - Exibe nome amigável, não UUID */}
              {(activeConversation.instance_friendly_name || activeConversation.instance_name) && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                  📱 {activeConversation.instance_friendly_name || activeConversation.instance_name}
                </span>
              )}
              
              {/* Tags do Contato (customizadas por cor) */}
              {activeConversation.contact_tags && activeConversation.contact_tags.length > 0 && (
                <>
                  {activeConversation.contact_tags.map((tag) => (
                    <span 
                      key={tag.id}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{
                        backgroundColor: `${tag.color}20`,
                        color: tag.color
                      }}
                    >
                      🏷️ {tag.name}
                    </span>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button className="p-2 hover:bg-gray-200 rounded-full transition-colors" title="Buscar">
            <Search className="w-5 h-5 text-gray-600" />
          </button>
          
          {/* Menu 3 pontos */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 hover:bg-gray-200 rounded-full transition-colors"
              title="Menu"
            >
              <MoreVertical className="w-5 h-5 text-gray-600" />
            </button>

            {showMenu && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                <button
                  onClick={() => {
                    setShowInfoModal(true);
                    setShowMenu(false);
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-3"
                >
                  <Info className="w-4 h-4" />
                  Informações do contato
                </button>

                {can_transfer_conversations && (
                  <button
                    onClick={() => {
                      setShowTransferModal(true);
                      setShowMenu(false);
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-3"
                  >
                    <ArrowRightLeft className="w-4 h-4" />
                    Transferir conversa
                  </button>
                )}

                <button
                  onClick={handleMarkAsResolved}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-3"
                >
                  <CheckCircle className="w-4 h-4" />
                  Marcar como resolvida
                </button>

                <button
                  onClick={handleCloseConversation}
                  className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-3"
                >
                  <XCircle className="w-4 h-4" />
                  Fechar conversa
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-hidden">
        <MessageList />
      </div>

      {/* Input */}
      <MessageInput 
        sendMessage={sendMessage}
        sendTyping={sendTyping}
        isConnected={isConnected}
      />

      {/* Modals */}
      {showInfoModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h2 className="text-lg font-semibold text-gray-900">Informações da Conversa</h2>
              <button
                onClick={() => setShowInfoModal(false)}
                className="p-1 hover:bg-gray-100 rounded transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              <div className="flex flex-col items-center pb-4 border-b">
                <div className="w-24 h-24 rounded-full bg-gray-300 mb-3 overflow-hidden">
                  {activeConversation.profile_pic_url ? (
                    <img 
                      src={`/api/chat/media-proxy/?url=${encodeURIComponent(activeConversation.profile_pic_url)}`}
                      alt={activeConversation.contact_name || activeConversation.contact_phone}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-600 font-medium text-3xl">
                      {(activeConversation.contact_name || activeConversation.contact_phone)[0].toUpperCase()}
                    </div>
                  )}
                </div>
                <h3 className="text-xl font-medium text-gray-900">
                  {activeConversation.contact_name || activeConversation.contact_phone}
                </h3>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-1">Telefone</p>
                <p className="text-base text-gray-900">{activeConversation.contact_phone}</p>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-1">Departamento</p>
                <p className="text-base text-gray-900">
                  {activeConversation.department_name || 'Inbox (Não atribuído)'}
                </p>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-1">Status</p>
                <p className="text-base text-gray-900 capitalize">{activeConversation.status}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {showTransferModal && (
        <TransferModal
          conversation={activeConversation}
          onClose={() => setShowTransferModal(false)}
          onTransferSuccess={() => {
            setShowTransferModal(false);
          }}
        />
      )}
    </div>
  );
}
