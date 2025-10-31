/**
 * AttachmentPreview - Visualiza diferentes tipos de anexos
 * 
 * Suporta:
 * - Imagens: Preview inline + lightbox
 * - Vídeos: Player HTML5
 * - Áudios: Player customizado estilo WhatsApp
 * - Documentos: Ícone + download
 * - IA: Transcrição + Resumo (se addon ativo)
 */
import React, { useState, useRef, useEffect } from 'react';
import { Download, FileText, Image, Video, Music, X, Play, Pause } from 'lucide-react';

interface Attachment {
  id: string;
  original_filename: string;
  mime_type: string;
  file_url: string;
  size_bytes: number;
  is_image: boolean;
  is_video: boolean;
  is_audio: boolean;
  is_document: boolean;
  metadata?: Record<string, any> | null;  // ✅ Adicionar metadata
  // ✨ Campos IA (podem ser null)
  transcription?: string | null;
  ai_summary?: string | null;
  ai_tags?: string[] | null;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
}

interface AttachmentPreviewProps {
  attachment: Attachment;
  showAI?: boolean;  // Se tenant tem addon Flow AI
}

export function AttachmentPreview({ attachment, showAI = false }: AttachmentPreviewProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  
  // 🎵 Estados do player de áudio
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);
  
  // Atualizar progresso do áudio
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    
    const updateTime = () => setCurrentTime(audio.currentTime);
    const updateDuration = () => setDuration(audio.duration);
    const handleEnded = () => setIsPlaying(false);
    
    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', updateDuration);
    audio.addEventListener('ended', handleEnded);
    
    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', updateDuration);
      audio.removeEventListener('ended', handleEnded);
    };
  }, []);
  
  // Formatar tempo (segundos → MM:SS)
  const formatTime = (seconds: number) => {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // Toggle play/pause
  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  };
  
  // Seek no áudio
  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    audio.currentTime = percentage * duration;
  };

  // 🖼️ IMAGEM
  if (attachment.is_image) {
    // ✅ Verificar se está processando ou se file_url é inválido
    const fileUrl = (attachment.file_url || '').trim();
    const isProcessing = attachment.metadata?.processing || !fileUrl || 
                         fileUrl.includes('whatsapp.net') || 
                         fileUrl.includes('evo.');
    
    if (isProcessing) {
      // Skeleton/Loading enquanto processa
      return (
        <div className="attachment-preview image">
          <div className="max-w-xs rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse flex items-center justify-center" style={{ height: '200px' }}>
            <div className="text-gray-400 text-sm">Processando imagem...</div>
          </div>
        </div>
      );
    }
    
    // Imagem pronta
    return (
      <div className="attachment-preview image">
        <img
          src={fileUrl}
          alt={attachment.original_filename}
          className="max-w-xs rounded-lg cursor-pointer hover:opacity-90 transition"
          onClick={() => setLightboxOpen(true)}
          onError={(e) => {
            console.error('❌ [AttachmentPreview] Erro ao carregar imagem:', fileUrl);
            // Fallback: mostrar skeleton se imagem falhar
            e.currentTarget.style.display = 'none';
          }}
        
        {/* Lightbox */}
        {lightboxOpen && (
          <div 
            className="fixed inset-0 bg-black bg-opacity-90 z-50 flex items-center justify-center p-4"
            onClick={() => setLightboxOpen(false)}
          >
            <button
              className="absolute top-4 right-4 text-white hover:text-gray-300"
              onClick={() => setLightboxOpen(false)}
            >
              <X size={32} />
            </button>
            <img
              src={attachment.file_url}
              alt={attachment.original_filename}
              className="max-w-full max-h-full object-contain"
            />
          </div>
        )}
      </div>
    );
  }

  // 🎥 VÍDEO
  if (attachment.is_video) {
    const fileUrl = (attachment.file_url || '').trim();
    const isProcessing = attachment.metadata?.processing || !fileUrl || 
                         fileUrl.includes('whatsapp.net') || 
                         fileUrl.includes('evo.');
    
    if (isProcessing) {
      return (
        <div className="attachment-preview video">
          <div className="max-w-md rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse flex items-center justify-center" style={{ height: '300px' }}>
            <div className="text-gray-400 text-sm">Processando vídeo...</div>
          </div>
        </div>
      );
    }
    
    return (
      <div className="attachment-preview video max-w-md">
        <video
          controls
          className="w-full rounded-lg"
          preload="metadata"
        >
          <source src={fileUrl} type={attachment.mime_type} />
          Seu navegador não suporta vídeo.
        </video>
        <p className="text-xs text-gray-500 mt-1">{attachment.original_filename}</p>
      </div>
    );
  }

  // 🎵 ÁUDIO (player customizado estilo WhatsApp - responsivo)
  if (attachment.is_audio) {
    const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
    
    // ✅ Detectar se áudio está disponível
    // URL válida = não vazia, não é URL temporária do WhatsApp/Evolution
    const isAudioReady = Boolean(
      attachment.file_url && 
      attachment.file_url.trim().length > 0 &&
      !attachment.file_url.includes('whatsapp.net') &&  // NÃO é URL temporária do WhatsApp
      !attachment.file_url.includes('evo.') &&          // NÃO é URL da Evolution API
      !attachment.metadata?.processing                   // NÃO está processando
    );
    
    return (
      <div className="attachment-preview audio w-full">
        {/* Player estilo WhatsApp - responsivo e com largura maior */}
        <div className="flex items-center gap-3 sm:gap-4 bg-white rounded-lg p-3 sm:p-4 shadow-sm w-full">
          {/* Botão Play/Pause - levemente maior */}
          <button
            onClick={togglePlay}
            disabled={!isAudioReady}
            className={`flex-shrink-0 w-10 h-10 sm:w-11 sm:h-11 rounded-full flex items-center justify-center transition-colors ${
              isAudioReady 
                ? 'bg-green-500 hover:bg-green-600 cursor-pointer' 
                : 'bg-gray-300 cursor-not-allowed'
            }`}
            title={isAudioReady ? (isPlaying ? 'Pausar' : 'Reproduzir') : 'Baixando áudio...'}
          >
            {!isAudioReady ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : isPlaying ? (
              <Pause className="text-white" size={20} fill="white" />
            ) : (
              <Play className="text-white ml-0.5" size={20} fill="white" />
            )}
          </button>
          
          {/* Progress Bar + Tempo */}
          <div className="flex-1 min-w-0">
            {/* Progress Bar - mais alta em mobile */}
            <div
              className="h-1.5 sm:h-1.5 bg-gray-200 rounded-full cursor-pointer mb-1.5 sm:mb-1"
              onClick={isAudioReady ? handleSeek : undefined}
            >
              <div
                className="h-full bg-green-500 rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            
            {/* Tempo atual / total - ajustado para mobile */}
            <div className="flex items-center justify-between text-[10px] sm:text-xs text-gray-500">
              <span>{isAudioReady ? formatTime(currentTime) : 'Baixando...'}</span>
              <span>{isAudioReady ? formatTime(duration) : '--:--'}</span>
            </div>
          </div>
        </div>
        
        {/* Áudio HTML5 (hidden - só para controle) */}
        {isAudioReady && (
          <audio
            ref={audioRef}
            src={attachment.file_url}
            preload="metadata"
            className="hidden"
          />
        )}

        {/* ✨ TRANSCRIÇÃO IA (se disponível e addon ativo) */}
        {showAI && attachment.transcription && (
          <div className="mt-3 p-3 bg-white rounded border border-gray-200">
            <p className="text-xs font-semibold text-gray-700 mb-1">📝 Transcrição:</p>
            <p className="text-sm text-gray-600">{attachment.transcription}</p>
          </div>
        )}

        {/* ✨ RESUMO IA */}
        {showAI && attachment.ai_summary && (
          <div className="mt-2 p-3 bg-indigo-50 rounded border border-indigo-200">
            <p className="text-xs font-semibold text-indigo-700 mb-1">🧠 Resumo IA:</p>
            <p className="text-sm text-indigo-900">{attachment.ai_summary}</p>
          </div>
        )}

        {/* ✨ TAGS IA */}
        {showAI && attachment.ai_tags && attachment.ai_tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {attachment.ai_tags.map((tag, i) => (
              <span
                key={i}
                className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 📄 DOCUMENTO
  return (
    <div className="attachment-preview document flex items-center gap-3 p-3 bg-gray-50 rounded-lg max-w-md">
      <FileText className="text-gray-600" size={24} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{attachment.original_filename}</p>
        <p className="text-xs text-gray-500">
          {(attachment.size_bytes / 1024).toFixed(0)} KB
        </p>
      </div>
      <a
        href={attachment.file_url}
        download={attachment.original_filename}
        className="p-2 bg-white border border-gray-300 rounded hover:bg-gray-100"
      >
        <Download size={18} />
      </a>
    </div>
  );
}


