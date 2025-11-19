/**
 * Modal com informações detalhadas da mensagem
 */
import React from 'react';
import { X, Clock, CheckCircle2, Eye, User, FileText, Image, Video, Music, File } from 'lucide-react';
import type { Message } from '../types';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface MessageInfoModalProps {
  message: Message;
  onClose: () => void;
}

export function MessageInfoModal({ message, onClose }: MessageInfoModalProps) {
  const formatDateTime = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return format(date, "dd 'de' MMMM 'de' yyyy 'às' HH:mm", { locale: ptBR });
    } catch {
      return dateString;
    }
  };

  const getMessageType = () => {
    if (message.attachments && message.attachments.length > 0) {
      const firstAttachment = message.attachments[0];
      const mimeType = firstAttachment.mime_type || '';
      
      if (mimeType.startsWith('image/')) return { icon: Image, label: 'Imagem' };
      if (mimeType.startsWith('video/')) return { icon: Video, label: 'Vídeo' };
      if (mimeType.startsWith('audio/')) return { icon: Music, label: 'Áudio' };
      return { icon: File, label: 'Arquivo' };
    }
    return { icon: FileText, label: 'Texto' };
  };

  const getStatusInfo = () => {
    switch (message.status) {
      case 'sent':
        return { icon: CheckCircle2, label: 'Enviada', color: 'text-blue-600' };
      case 'delivered':
        return { icon: CheckCircle2, label: 'Entregue', color: 'text-green-600' };
      case 'seen':
        return { icon: Eye, label: 'Vista', color: 'text-green-700' };
      case 'failed':
        return { icon: X, label: 'Falhou', color: 'text-red-600' };
      default:
        return { icon: Clock, label: 'Pendente', color: 'text-gray-600' };
    }
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const messageType = getMessageType();
  const statusInfo = getStatusInfo();
  const StatusIcon = statusInfo.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl border border-gray-200 w-full max-w-md mx-4 max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Informações da Mensagem</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto flex-1">
          <div className="space-y-4">
            {/* Tipo da Mensagem */}
            <div className="flex items-start gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                {React.createElement(messageType.icon, { className: "w-5 h-5 text-gray-600" })}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700">Tipo</p>
                <p className="text-sm text-gray-600">{messageType.label}</p>
              </div>
            </div>

            {/* Status */}
            <div className="flex items-start gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <StatusIcon className={`w-5 h-5 ${statusInfo.color}`} />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700">Status</p>
                <p className={`text-sm ${statusInfo.color}`}>{statusInfo.label}</p>
              </div>
            </div>

            {/* Data/Hora de Envio */}
            <div className="flex items-start gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <Clock className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700">Enviada em</p>
                <p className="text-sm text-gray-600">{formatDateTime(message.created_at)}</p>
              </div>
            </div>

            {/* Remetente */}
            {message.sender_name && (
              <div className="flex items-start gap-3">
                <div className="p-2 bg-gray-100 rounded-lg">
                  <User className="w-5 h-5 text-gray-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-700">Remetente</p>
                  <p className="text-sm text-gray-600">{message.sender_name}</p>
                  {message.sender_phone && (
                    <p className="text-xs text-gray-500">{message.sender_phone}</p>
                  )}
                </div>
              </div>
            )}

            {/* Direção */}
            <div className="flex items-start gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                {message.direction === 'outgoing' ? (
                  <FileText className="w-5 h-5 text-blue-600" />
                ) : (
                  <FileText className="w-5 h-5 text-green-600" />
                )}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700">Direção</p>
                <p className="text-sm text-gray-600">
                  {message.direction === 'outgoing' ? 'Enviada' : 'Recebida'}
                </p>
              </div>
            </div>

            {/* Anexos */}
            {message.attachments && message.attachments.length > 0 && (
              <div className="flex items-start gap-3">
                <div className="p-2 bg-gray-100 rounded-lg">
                  <File className="w-5 h-5 text-gray-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-700">Anexos</p>
                  <div className="mt-1 space-y-1">
                    {message.attachments.map((attachment) => (
                      <div key={attachment.id} className="text-sm text-gray-600">
                        <p className="font-medium">{attachment.original_filename || 'Arquivo'}</p>
                        {attachment.file_size && (
                          <p className="text-xs text-gray-500">
                            {formatFileSize(attachment.file_size)}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Conteúdo (se for texto) */}
            {message.content && (
              <div className="flex items-start gap-3">
                <div className="p-2 bg-gray-100 rounded-lg">
                  <FileText className="w-5 h-5 text-gray-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-700">Conteúdo</p>
                  <p className="text-sm text-gray-600 break-words">{message.content}</p>
                </div>
              </div>
            )}

            {/* ID da Mensagem */}
            <div className="flex items-start gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <FileText className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700">ID</p>
                <p className="text-xs text-gray-500 font-mono break-all">{message.id}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

